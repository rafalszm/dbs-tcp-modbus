"""DBS TCP Modbus integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one DBS TCP Modbus station."""
    from .const import DOMAIN, PLATFORMS
    from .coordinator import DBSModbusCoordinator
    from .models import StationConfig, parse_optional_register_csv

    station = StationConfig.from_data(dict(entry.data))
    registers = parse_optional_register_csv(station.map_csv)
    coordinator = DBSModbusCoordinator(hass, station, registers)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "station": station,
        "registers": registers,
    }

    await _async_remove_stale_entities(hass, entry, station, registers)
    await coordinator.async_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate older config entries to the current data shape."""
    from .const import CONF_STATION_ID
    from .models import legacy_station_id

    if CONF_STATION_ID not in entry.data:
        data = dict(entry.data)
        data[CONF_STATION_ID] = legacy_station_id(data)
        hass.config_entries.async_update_entry(entry, data=data, minor_version=2, version=1)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload one station."""
    from .const import DOMAIN, PLATFORMS

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    runtime = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if runtime is not None:
        await runtime["coordinator"].async_close()
    return unloaded


def expected_unique_ids(station, registers) -> set[str]:
    """Return entity unique IDs expected for the current station map."""
    from .const import DOMAIN

    return {
        f"{DOMAIN}_{station.station_id}_connection",
        *(f"{DOMAIN}_{station.station_id}_{definition.key}" for definition in registers),
    }


async def _async_remove_stale_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    station,
    registers,
) -> None:
    """Remove entity registry entries left behind after a CSV map edit."""
    from homeassistant.helpers import entity_registry as er

    from .const import DOMAIN

    registry = er.async_get(hass)
    keep_unique_ids = expected_unique_ids(station, registers)
    unique_id_prefix = f"{DOMAIN}_{station.station_id}_"

    for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        unique_id = registry_entry.unique_id
        if (
            unique_id
            and unique_id.startswith(unique_id_prefix)
            and unique_id not in keep_unique_ids
        ):
            registry.async_remove(registry_entry.entity_id)
