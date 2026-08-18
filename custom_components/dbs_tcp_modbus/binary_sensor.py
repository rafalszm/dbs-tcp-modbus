"""Binary sensor platform for DBS TCP Modbus."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME, VERSION
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
    entities = [DBSModbusConnectionSensor(coordinator, station)]
    entities.extend(
        DBSModbusBinarySensor(coordinator, station, definition)
        for definition in registers
        if definition.is_binary
    )
    async_add_entities(entities)


class DBSModbusConnectionSensor(CoordinatorEntity[DBSModbusCoordinator], BinarySensorEntity):
    """Diagnostic connection status for one Modbus TCP station."""

    _attr_has_entity_name = True
    _attr_name = "Connection"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: DBSModbusCoordinator, station: StationConfig) -> None:
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.station = station
        self._attr_unique_id = f"{DOMAIN}_{station.station_id}_connection"

    @property
    def available(self) -> bool:
        """Connection sensor stays available to report the latest poll status."""
        return True

    @property
    def is_on(self) -> bool:
        """Return true when the latest coordinator refresh succeeded."""
        return self.coordinator.last_update_success

    @property
    def device_info(self) -> DeviceInfo:
        """Return Home Assistant device info for the station."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.station.station_id)},
            name=self.station.name,
            manufacturer="Digital Best Solutions",
            model=NAME,
            sw_version=VERSION,
            configuration_url=f"http://{self.station.host}",
        )

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return connection metadata."""
        return {
            "host": self.station.host,
            "port": self.station.port,
            "modbus_unit_id": self.station.unit_id,
            "mapped_entities": len(self.coordinator.registers),
        }


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
