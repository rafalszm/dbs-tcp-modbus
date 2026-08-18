"""Constants for DBS TCP Modbus."""

from __future__ import annotations

DOMAIN = "dbs_tcp_modbus"
NAME = "DBS TCP Modbus"
VERSION = "1.0.1"

PLATFORMS = ["sensor", "binary_sensor"]

CONF_MAP_CSV = "map_csv"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_STATION_ID = "station_id"
CONF_STATION_NAME = "station_name"
CONF_TIMEOUT = "timeout"
CONF_UNIT_ID = "unit_id"

DEFAULT_PORT = 502
DEFAULT_SCAN_INTERVAL = 10
DEFAULT_TIMEOUT = 3.0
DEFAULT_UNIT_ID = 1
