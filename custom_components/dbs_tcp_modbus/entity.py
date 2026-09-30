"""Shared entity helpers for DBS TCP Modbus."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME, VERSION
from .coordinator import DBSModbusCoordinator
from .models import RegisterDefinition, StationConfig


class DBSModbusEntity(CoordinatorEntity[DBSModbusCoordinator]):
    """Base entity for values from one station."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DBSModbusCoordinator,
        station: StationConfig,
        definition: RegisterDefinition,
    ) -> None:
        super().__init__(coordinator)
        self.station = station
        self.definition = definition
        self._attr_unique_id = f"{DOMAIN}_{station.station_id}_{definition.key}"
        self._attr_name = definition.name
        self._attr_icon = definition.icon
        self._attr_entity_registry_enabled_default = definition.enabled_by_default

    @property
    def available(self) -> bool:
        """Return if entity has a value from the latest successful update."""
        return super().available and self.definition.key in (self.coordinator.data or {})

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
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return static register metadata."""
        attrs: dict[str, Any] = {
            "modbus_function": self.definition.function,
            "modbus_address": self.definition.address,
            "modbus_unit_id": self.station.unit_id,
            "value_type": self.definition.value_type,
        }
        if self.definition.section:
            attrs["section"] = self.definition.section
        if self.definition.bit is not None:
            attrs["modbus_bit"] = self.definition.bit
        return attrs
