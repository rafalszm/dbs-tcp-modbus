"""Async Modbus TCP client wrapper for DBS TCP Modbus."""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from typing import Any

from pymodbus.client import AsyncModbusTcpClient

from .models import ModbusValue, RegisterDefinition, StationConfig, decode_register_value


class ModbusReadError(RuntimeError):
    """Raised when a station cannot be read."""


class DbsModbusClient:
    """Small compatibility wrapper around pymodbus."""

    def __init__(self, station: StationConfig) -> None:
        self.station = station
        self._client: AsyncModbusTcpClient | None = None
        self._device_kw = _device_id_keyword()

    async def connect(self) -> None:
        """Open a TCP connection if needed."""
        if self._client is not None and getattr(self._client, "connected", False):
            return
        self._client = AsyncModbusTcpClient(
            host=self.station.host,
            port=self.station.port,
            timeout=self.station.timeout,
        )
        connected = self._client.connect()
        if inspect.isawaitable(connected):
            connected = await connected
        if connected is False or not getattr(self._client, "connected", True):
            raise ModbusReadError(f"Cannot connect to {self.station.host}:{self.station.port}")

    async def close(self) -> None:
        """Close the TCP connection."""
        if self._client is None:
            return
        result = self._client.close()
        if inspect.isawaitable(result):
            await result
        self._client = None

    async def read_values(self, registers: list[RegisterDefinition]) -> tuple[dict[str, ModbusValue], list[str]]:
        """Read all registers, returning values plus non-fatal batch errors."""
        await self.connect()
        values: dict[str, ModbusValue] = {}
        errors: list[str] = []
        for batch in _build_batches(registers):
            try:
                payload = await self._read_batch(batch.function, batch.address, batch.count)
            except Exception as exc:
                errors.append(f"function={batch.function} address={batch.address} count={batch.count}: {exc}")
                continue

            now = datetime.now(timezone.utc)
            for definition in batch.registers:
                offset = definition.address - batch.address
                end = offset + definition.effective_count
                raw_payload = payload[offset:end]
                try:
                    raw = decode_register_value(definition, raw_payload)
                    values[definition.key] = ModbusValue(
                        raw=raw,
                        value=definition.apply_scale(raw),
                        updated_at=now,
                    )
                except Exception as exc:
                    errors.append(f"{definition.key}: {exc}")

        if errors and not values:
            raise ModbusReadError("; ".join(errors))
        return values, errors

    async def read_probe(self, definition: RegisterDefinition) -> None:
        """Read one definition to validate a station during setup."""
        await self.connect()
        await self._read_batch(definition.function, definition.address, definition.effective_count)

    async def _read_batch(self, function: int, address: int, count: int) -> list[int] | list[bool]:
        if self._client is None:
            raise ModbusReadError("Client is not connected")
        kwargs = {"address": address, "count": count, self._device_kw: self.station.unit_id}
        if function == 1:
            result = await self._client.read_coils(**kwargs)
            _raise_if_error(result)
            return list(result.bits[:count])
        if function == 2:
            result = await self._client.read_discrete_inputs(**kwargs)
            _raise_if_error(result)
            return list(result.bits[:count])
        if function == 3:
            result = await self._client.read_holding_registers(**kwargs)
            _raise_if_error(result)
            return list(result.registers[:count])
        if function == 4:
            result = await self._client.read_input_registers(**kwargs)
            _raise_if_error(result)
            return list(result.registers[:count])
        raise ModbusReadError(f"Unsupported function {function}")


class _Batch:
    def __init__(self, function: int, address: int, registers: list[RegisterDefinition]) -> None:
        self.function = function
        self.address = address
        self.registers = registers

    @property
    def count(self) -> int:
        return max(reg.address + reg.effective_count for reg in self.registers) - self.address


def _build_batches(registers: list[RegisterDefinition]) -> list[_Batch]:
    batches: list[_Batch] = []
    for function in sorted({item.function for item in registers}):
        max_count = 1900 if function in (1, 2) else 120
        current: list[RegisterDefinition] = []
        current_start = 0
        for definition in sorted((item for item in registers if item.function == function), key=lambda item: item.address):
            if not current:
                current = [definition]
                current_start = definition.address
                continue
            next_end = definition.address + definition.effective_count
            span = next_end - current_start
            if span <= max_count:
                current.append(definition)
                continue
            batches.append(_Batch(function, current_start, current))
            current = [definition]
            current_start = definition.address
        if current:
            batches.append(_Batch(function, current_start, current))
    return batches


def _raise_if_error(result: Any) -> None:
    if result is None:
        raise ModbusReadError("Empty Modbus response")
    is_error = getattr(result, "isError", None)
    if callable(is_error) and is_error():
        raise ModbusReadError(str(result))


def _device_id_keyword() -> str:
    try:
        import pymodbus

        parts = [int(part) for part in pymodbus.__version__.split(".")[:2]]
        if tuple(parts) >= (3, 10):
            return "device_id"
    except Exception:
        pass
    return "slave"


async def test_modbus_connection(station: StationConfig, registers: list[RegisterDefinition]) -> None:
    """Validate that the station answers at least one read."""
    client = DbsModbusClient(station)
    try:
        await client.read_probe(registers[0])
    finally:
        await client.close()

