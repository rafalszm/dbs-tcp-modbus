"""Binary sensor platform for DBS TCP Modbus."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    """Set up binary sensors for one station."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinator: DBSModbusCoordinator = runtime["coordinator"]
    station: StationConfig = runtime["station"]
    registers: list[RegisterDefinition] = runtime["registers"]
    async_add_entities(
        DBSModbusBinarySensor(coordinator, station, definition)
        for definition in registers
        if definition.is_binary
    )


class DBSModbusBinarySensor(DBSModbusEntity, BinarySensorEntity):
    """Read-only Modbus coil/discrete input binary sensor."""

    def __init__(
        self,
        coordinator: DBSModbusCoordinator,
        station: StationConfig,
        definition: RegisterDefinition,
    ) -> None:
        super().__init__(coordinator, station, definition)
        self._attr_device_class = definition.device_class

    @property
    def is_on(self) -> bool | None:
        """Return the latest binary value."""
        item = (self.coordinator.data or {}).get(self.definition.key)
        return None if item is None else bool(item.value)

