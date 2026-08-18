"""Sensor platform for DBS TCP Modbus."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import DBSModbusCoordinator
from .entity import DBSModbusEntity
from .models import RegisterDefinition, StationConfig


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for one station."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinator: DBSModbusCoordinator = runtime["coordinator"]
    station: StationConfig = runtime["station"]
    registers: list[RegisterDefinition] = runtime["registers"]
    async_add_entities(
        DBSModbusSensor(coordinator, station, definition)
        for definition in registers
        if not definition.is_binary
    )


class DBSModbusSensor(DBSModbusEntity, SensorEntity):
    """Read-only Modbus register sensor."""

    def __init__(
        self,
        coordinator: DBSModbusCoordinator,
        station: StationConfig,
        definition: RegisterDefinition,
    ) -> None:
        super().__init__(coordinator, station, definition)
        self._attr_native_unit_of_measurement = definition.unit or None
        self._attr_device_class = definition.device_class
        self._attr_state_class = definition.state_class
        self._attr_suggested_display_precision = definition.precision

    @property
    def native_value(self) -> int | float | bool | None:
        """Return the latest scaled value."""
        item = (self.coordinator.data or {}).get(self.definition.key)
        return None if item is None else item.value

