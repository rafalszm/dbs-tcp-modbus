"""Config flow for DBS TCP Modbus."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .client import ModbusReadError, test_modbus_connection
from .const import (
    CONF_MAP_CSV,
    CONF_SCAN_INTERVAL,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_TIMEOUT,
    CONF_UNIT_ID,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_UNIT_ID,
    DOMAIN,
)
from .models import CsvMapError, StationConfig, parse_optional_register_csv, slugify


class DBSTCPModbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle DBS TCP Modbus setup."""

    VERSION = 1
    MINOR_VERSION = 3

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle manual setup from the UI."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _normalize_input(user_input)
            errors = await self._validate_for_setup(data)
            if not errors:
                if self._is_duplicate_connection(data):
                    errors["base"] = "already_configured"
                else:
                    await self.async_set_unique_id(_unique_id(data))
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=data[CONF_STATION_NAME], data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle reconfiguration of an existing station."""
        entry = self._get_reconfigure_entry()
        defaults = dict(entry.data)
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _normalize_input(user_input, defaults)
            errors = self._validate_for_reconfigure(data)
            if not errors:
                if self._is_duplicate_connection(data, entry.entry_id):
                    errors["base"] = "already_configured"
                else:
                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates=data,
                    )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(user_input or defaults),
            errors=errors,
        )

    async def _validate_for_setup(self, data: dict[str, Any]) -> dict[str, str]:
        try:
            registers = parse_optional_register_csv(data[CONF_MAP_CSV])
            await test_modbus_connection(StationConfig.from_data(data), registers)
        except CsvMapError:
            return {"base": "invalid_csv"}
        except ModbusReadError:
            return {"base": "cannot_connect"}
        except Exception:
            return {"base": "unknown"}
        return {}

    def _validate_for_reconfigure(self, data: dict[str, Any]) -> dict[str, str]:
        try:
            parse_optional_register_csv(data[CONF_MAP_CSV])
        except CsvMapError:
            return {"base": "invalid_csv"}
        except Exception:
            return {"base": "unknown"}
        return {}

    def _is_duplicate_connection(self, data: dict[str, Any], current_entry_id: str | None = None) -> bool:
        return _is_duplicate_connection(self.hass, data, current_entry_id)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> DBSTCPModbusOptionsFlow:
        """Create the options flow for editing an existing station."""
        return DBSTCPModbusOptionsFlow()


class DBSTCPModbusOptionsFlow(config_entries.OptionsFlow):
    """Handle station edits from the integration options button."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Edit connection settings and the CSV map."""
        defaults = {**dict(self.config_entry.data), **dict(self.config_entry.options)}
        errors: dict[str, str] = {}

        if user_input is not None:
            data = _normalize_input(user_input, defaults)
            errors = _validate_map(data)
            if not errors:
                if _is_duplicate_connection(self.hass, data, self.config_entry.entry_id):
                    errors["base"] = "already_configured"
                else:
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        title=data[CONF_STATION_NAME],
                        data=data,
                    )
                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(self.config_entry.entry_id)
                    )
                    return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(user_input or defaults),
            errors=errors,
        )


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_STATION_NAME, default=defaults.get(CONF_STATION_NAME, "")): str,
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Optional(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
            vol.Optional(CONF_UNIT_ID, default=defaults.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=247)
            ),
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=2, max=3600)),
            vol.Optional(CONF_TIMEOUT, default=defaults.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)): vol.All(
                vol.Coerce(float), vol.Range(min=0.5, max=60)
            ),
            vol.Required(CONF_MAP_CSV, default=defaults.get(CONF_MAP_CSV, "")): selector.TextSelector(
                selector.TextSelectorConfig(multiline=True)
            ),
        }
    )


def _validate_map(data: dict[str, Any]) -> dict[str, str]:
    try:
        parse_optional_register_csv(data[CONF_MAP_CSV])
    except CsvMapError:
        return {"base": "invalid_csv"}
    except Exception:
        return {"base": "unknown"}
    return {}


def _normalize_input(data: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = existing or {}
    return {
        CONF_STATION_ID: str(existing.get(CONF_STATION_ID) or uuid4().hex),
        CONF_STATION_NAME: str(data[CONF_STATION_NAME]).strip(),
        CONF_HOST: str(data[CONF_HOST]).strip(),
        CONF_PORT: int(data.get(CONF_PORT, DEFAULT_PORT)),
        CONF_UNIT_ID: int(data.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)),
        CONF_SCAN_INTERVAL: int(data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
        CONF_TIMEOUT: float(data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
        CONF_MAP_CSV: str(data[CONF_MAP_CSV]).strip(),
    }


def _unique_id(data: dict[str, Any]) -> str:
    return str(data[CONF_STATION_ID])


def _connection_key(data: dict[str, Any]) -> str:
    return (
        f"{data[CONF_HOST].lower()}:{data[CONF_PORT]}:"
        f"{data[CONF_UNIT_ID]}:{slugify(data[CONF_STATION_NAME])}"
    )


def _is_duplicate_connection(hass: Any, data: dict[str, Any], current_entry_id: str | None = None) -> bool:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id == current_entry_id:
            continue
        entry_data = {**dict(entry.data), **dict(entry.options)}
        if _connection_key(entry_data) == _connection_key(data):
            return True
    return False
