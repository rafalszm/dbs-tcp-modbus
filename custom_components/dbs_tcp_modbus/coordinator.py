"""DataUpdateCoordinator for DBS TCP Modbus."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import DbsModbusClient, ModbusReadError
from .const import DOMAIN
from .models import ModbusValue, RegisterDefinition, StationConfig

LOGGER = logging.getLogger(__name__)


class DBSModbusCoordinator(DataUpdateCoordinator[dict[str, ModbusValue]]):
    """Coordinate polling for one Modbus TCP station."""

    def __init__(
        self,
        hass: HomeAssistant,
        station: StationConfig,
        registers: list[RegisterDefinition],
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_{station.host}_{station.unit_id}",
            update_interval=timedelta(seconds=station.scan_interval),
        )
        self.station = station
        self.registers = registers
        self.client = DbsModbusClient(station)
        self.last_errors: list[str] = []

    async def _async_update_data(self) -> dict[str, ModbusValue]:
        try:
            values, errors = await self.client.read_values(self.registers)
        except ModbusReadError as exc:
            self.last_errors = [str(exc)]
            await self.client.close()
            raise UpdateFailed(str(exc)) from exc
        except Exception as exc:
            self.last_errors = [str(exc)]
            await self.client.close()
            raise UpdateFailed(str(exc)) from exc
        self.last_errors = errors
        if errors:
            LOGGER.debug("Partial Modbus read errors for %s: %s", self.station.name, "; ".join(errors))
        return values

    async def async_close(self) -> None:
        """Close the TCP client."""
        await self.client.close()

