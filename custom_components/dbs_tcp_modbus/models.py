"""CSV parsing and Modbus value decoding for DBS TCP Modbus."""

from __future__ import annotations

import csv
import io
import re
import struct
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any

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
)

SUPPORTED_FUNCTIONS = {1, 2, 3, 4}
SUPPORTED_TYPES = {"coil", "discrete", "uint16", "int16", "uint32", "int32", "float32"}
REQUIRED_COLUMNS = {"key", "name", "function", "address", "type"}
VALID_WORD_ORDERS = {"high_low", "low_high"}
VALID_BYTE_ORDERS = {"big", "little"}


class CsvMapError(ValueError):
    """Raised when the pasted CSV map is not usable."""


@dataclass(frozen=True)
class StationConfig:
    """Connection settings for one Modbus TCP station."""

    name: str
    host: str
    station_id: str
    port: int = DEFAULT_PORT
    unit_id: int = DEFAULT_UNIT_ID
    scan_interval: int = DEFAULT_SCAN_INTERVAL
    timeout: float = DEFAULT_TIMEOUT
    map_csv: str = ""

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "StationConfig":
        """Build settings from a Home Assistant config entry payload."""
        return cls(
            name=str(data[CONF_STATION_NAME]).strip(),
            host=str(data["host"]).strip(),
            station_id=str(data.get(CONF_STATION_ID) or legacy_station_id(data)).strip(),
            port=int(data.get("port", DEFAULT_PORT)),
            unit_id=int(data.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)),
            scan_interval=int(data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
            timeout=float(data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
            map_csv=str(data.get(CONF_MAP_CSV, "")),
        )


@dataclass(frozen=True)
class RegisterDefinition:
    """One entity/register definition from the CSV map."""

    key: str
    name: str
    function: int
    address: int
    value_type: str
    unit: str = ""
    scale: float = 1.0
    offset: float = 0.0
    precision: int | None = None
    device_class: str | None = None
    state_class: str | None = None
    icon: str | None = None
    section: str | None = None
    enabled_by_default: bool = True
    count: int | None = None
    word_order: str = "high_low"
    byte_order: str = "big"

    @property
    def is_binary(self) -> bool:
        """Return true for binary Home Assistant entities."""
        return self.function in (1, 2) or self.value_type in {"coil", "discrete"}

    @property
    def effective_count(self) -> int:
        """Return how many bits/registers must be read for this value."""
        if self.count is not None:
            return self.count
        return 2 if self.value_type in {"uint32", "int32", "float32"} else 1

    def apply_scale(self, raw: bool | int | float) -> bool | int | float:
        """Scale and round a raw decoded value."""
        if isinstance(raw, bool):
            return raw
        value = raw * self.scale + self.offset
        if self.precision is not None and isinstance(value, float):
            return round(value, self.precision)
        return value


@dataclass(frozen=True)
class ModbusValue:
    """Latest decoded value for one register."""

    raw: bool | int | float
    value: bool | int | float
    updated_at: datetime


def slugify(value: str) -> str:
    """Return a stable slug usable in unique IDs."""
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", normalized).strip("_").lower()
    slug = re.sub(r"_+", "_", slug)
    return slug or "value"


def legacy_station_id(data: dict[str, Any]) -> str:
    """Build a stable fallback ID for entries created before station_id existed."""
    name = str(data.get(CONF_STATION_NAME, "station"))
    host = str(data.get("host", "host"))
    port = str(data.get("port", DEFAULT_PORT))
    unit_id = str(data.get(CONF_UNIT_ID, DEFAULT_UNIT_ID))
    return slugify(f"{name}_{host}_{port}_{unit_id}")


def parse_register_csv(text: str) -> list[RegisterDefinition]:
    """Parse a pasted CSV register map."""
    if not text or not text.strip():
        raise CsvMapError("CSV map is empty")

    handle = io.StringIO(text.strip().lstrip("\ufeff"))
    reader = csv.DictReader(handle)
    fieldnames = set(reader.fieldnames or [])
    missing = sorted(REQUIRED_COLUMNS - fieldnames)
    if missing:
        raise CsvMapError(f"CSV map is missing required columns: {', '.join(missing)}")

    registers: list[RegisterDefinition] = []
    seen: set[str] = set()
    for line_number, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values()):
            continue

        key = slugify(_required(row, "key", line_number))
        if key in seen:
            raise CsvMapError(f"Duplicate key '{key}' at line {line_number}")
        seen.add(key)

        function = _parse_int(row, "function", line_number)
        if function not in SUPPORTED_FUNCTIONS:
            raise CsvMapError(f"Unsupported function '{function}' at line {line_number}")

        value_type = _required(row, "type", line_number).lower()
        if value_type not in SUPPORTED_TYPES:
            raise CsvMapError(f"Unsupported type '{value_type}' at line {line_number}")
        if function in (1, 2) and value_type not in {"coil", "discrete"}:
            raise CsvMapError(f"Function {function} must use coil or discrete type at line {line_number}")
        if function in (3, 4) and value_type in {"coil", "discrete"}:
            raise CsvMapError(f"Function {function} must use a register type at line {line_number}")

        count = _parse_optional_int(row, "count", line_number)
        minimum_count = 2 if value_type in {"uint32", "int32", "float32"} else 1
        if count is not None and count < minimum_count:
            raise CsvMapError(f"Count for {value_type} must be at least {minimum_count} at line {line_number}")

        word_order = _optional(row, "word_order") or "high_low"
        if word_order not in VALID_WORD_ORDERS:
            raise CsvMapError(f"Invalid word_order '{word_order}' at line {line_number}")
        byte_order = _optional(row, "byte_order") or "big"
        if byte_order not in VALID_BYTE_ORDERS:
            raise CsvMapError(f"Invalid byte_order '{byte_order}' at line {line_number}")

        registers.append(
            RegisterDefinition(
                key=key,
                name=_required(row, "name", line_number),
                function=function,
                address=_parse_int(row, "address", line_number, minimum=0),
                value_type=value_type,
                unit=_optional(row, "unit") or "",
                scale=_parse_optional_float(row, "scale", line_number, default=1.0),
                offset=_parse_optional_float(row, "offset", line_number, default=0.0),
                precision=_parse_optional_int(row, "precision", line_number, minimum=0),
                device_class=_optional(row, "device_class"),
                state_class=_optional(row, "state_class"),
                icon=_optional(row, "icon"),
                section=_optional(row, "section"),
                enabled_by_default=_parse_optional_bool(row, "enabled_by_default", default=True),
                count=count,
                word_order=word_order,
                byte_order=byte_order,
            )
        )

    if not registers:
        raise CsvMapError("CSV map does not contain any registers")
    return registers


def parse_optional_register_csv(text: str) -> list[RegisterDefinition]:
    """Parse a pasted CSV map, returning no registers when the map is blank."""
    if not text or not text.strip():
        return []
    return parse_register_csv(text)


def decode_register_value(definition: RegisterDefinition, payload: list[int] | list[bool]) -> bool | int | float:
    """Decode one Modbus response slice according to a register definition."""
    if definition.is_binary:
        if not payload:
            raise ValueError(f"No bits returned for {definition.key}")
        return bool(payload[0])

    words = [int(word) for word in payload[: definition.effective_count]]
    if len(words) < definition.effective_count:
        raise ValueError(f"Not enough registers returned for {definition.key}")

    if definition.effective_count > 1 and definition.word_order == "low_high":
        words = list(reversed(words))

    raw_bytes = b"".join(_word_bytes(word, definition.byte_order) for word in words)
    value_type = definition.value_type
    if value_type == "uint16":
        return int.from_bytes(raw_bytes[:2], "big", signed=False)
    if value_type == "int16":
        return int.from_bytes(raw_bytes[:2], "big", signed=True)
    if value_type == "uint32":
        return int.from_bytes(raw_bytes[:4], "big", signed=False)
    if value_type == "int32":
        return int.from_bytes(raw_bytes[:4], "big", signed=True)
    if value_type == "float32":
        return struct.unpack(">f", raw_bytes[:4])[0]
    raise ValueError(f"Unsupported type {value_type}")


def _word_bytes(word: int, byte_order: str) -> bytes:
    if not 0 <= word <= 0xFFFF:
        raise ValueError(f"Register word out of range: {word}")
    data = word.to_bytes(2, "big")
    return data if byte_order == "big" else data[::-1]


def _required(row: dict[str, Any], field: str, line_number: int) -> str:
    value = (row.get(field) or "").strip()
    if not value:
        raise CsvMapError(f"Missing '{field}' at line {line_number}")
    return value


def _optional(row: dict[str, Any], field: str) -> str | None:
    value = (row.get(field) or "").strip()
    return value or None


def _parse_int(row: dict[str, Any], field: str, line_number: int, minimum: int | None = None) -> int:
    value_text = _required(row, field, line_number)
    try:
        value = int(value_text)
    except ValueError as exc:
        raise CsvMapError(f"Invalid integer '{value_text}' for '{field}' at line {line_number}") from exc
    if minimum is not None and value < minimum:
        raise CsvMapError(f"'{field}' must be at least {minimum} at line {line_number}")
    return value


def _parse_optional_int(
    row: dict[str, Any], field: str, line_number: int, minimum: int | None = None
) -> int | None:
    value_text = _optional(row, field)
    if value_text is None:
        return None
    try:
        value = int(value_text)
    except ValueError as exc:
        raise CsvMapError(f"Invalid integer '{value_text}' for '{field}' at line {line_number}") from exc
    if minimum is not None and value < minimum:
        raise CsvMapError(f"'{field}' must be at least {minimum} at line {line_number}")
    return value


def _parse_optional_float(row: dict[str, Any], field: str, line_number: int, default: float) -> float:
    value_text = _optional(row, field)
    if value_text is None:
        return default
    try:
        return float(value_text.replace(",", "."))
    except ValueError as exc:
        raise CsvMapError(f"Invalid number '{value_text}' for '{field}' at line {line_number}") from exc


def _parse_optional_bool(row: dict[str, Any], field: str, default: bool) -> bool:
    value_text = _optional(row, field)
    if value_text is None:
        return default
    return value_text.lower() not in {"0", "false", "no", "off", "nie"}
