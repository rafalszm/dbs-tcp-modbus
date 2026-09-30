from __future__ import annotations

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components"))

from dbs_tcp_modbus import expected_unique_ids
from dbs_tcp_modbus.const import (
    CONF_MAP_CSV,
    CONF_SCAN_INTERVAL,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_TIMEOUT,
    CONF_UNIT_ID,
)
from dbs_tcp_modbus.models import (
    CsvMapError,
    RegisterDefinition,
    StationConfig,
    decode_register_value,
    parse_register_csv,
    parse_optional_register_csv,
)


class TestModels(unittest.TestCase):
    def test_parse_valid_csv(self) -> None:
        csv_text = """key,name,function,address,type,unit,scale,offset,precision,device_class,state_class,enabled_by_default
pressure,Pressure,4,10,uint16,bar,0.1,1,1,pressure,measurement,false
running,Running,1,2,coil,,,,,,,
"""

        registers = parse_register_csv(csv_text)

        self.assertEqual(len(registers), 2)
        self.assertEqual(registers[0].key, "pressure")
        self.assertEqual(registers[0].scale, 0.1)
        self.assertEqual(registers[0].offset, 1)
        self.assertEqual(registers[0].precision, 1)
        self.assertFalse(registers[0].enabled_by_default)
        self.assertTrue(registers[1].is_binary)

    def test_parse_missing_required_column(self) -> None:
        with self.assertRaisesRegex(CsvMapError, "missing required columns"):
            parse_register_csv("key,name,function,address\nx,X,4,1\n")

    def test_parse_optional_accepts_blank_map(self) -> None:
        self.assertEqual(parse_optional_register_csv(""), [])
        self.assertEqual(parse_optional_register_csv("  \n"), [])

    def test_parse_rejects_bad_function_and_type_combinations(self) -> None:
        with self.assertRaisesRegex(CsvMapError, "Function 1"):
            parse_register_csv("key,name,function,address,type\nx,X,1,1,uint16\n")
        with self.assertRaisesRegex(CsvMapError, "Function 4"):
            parse_register_csv("key,name,function,address,type\nx,X,4,1,coil\n")

    def test_parse_and_decode_register_bit(self) -> None:
        registers = parse_register_csv("key,name,function,address,type,bit\nrun,Run,3,10,bit,3\n")

        self.assertTrue(registers[0].is_binary)
        self.assertEqual(registers[0].bit, 3)
        self.assertTrue(decode_register_value(registers[0], [0b1000]))
        self.assertFalse(decode_register_value(registers[0], [0b0100]))

    def test_parse_rejects_bad_bit_config(self) -> None:
        with self.assertRaisesRegex(CsvMapError, "Missing 'bit'"):
            parse_register_csv("key,name,function,address,type\nx,X,3,1,bit\n")
        with self.assertRaisesRegex(CsvMapError, "between 0 and 15"):
            parse_register_csv("key,name,function,address,type,bit\nx,X,3,1,bit,16\n")
        with self.assertRaisesRegex(CsvMapError, "only supported"):
            parse_register_csv("key,name,function,address,type,bit\nx,X,3,1,uint16,1\n")

    def test_parse_rejects_duplicate_slug_keys(self) -> None:
        with self.assertRaisesRegex(CsvMapError, "Duplicate key"):
            parse_register_csv("key,name,function,address,type\nA B,One,4,1,uint16\na_b,Two,4,2,uint16\n")

    def test_decode_uint16_and_int16(self) -> None:
        self.assertEqual(decode_register_value(_reg("uint16"), [0x00FF]), 255)
        self.assertEqual(decode_register_value(_reg("int16"), [0xFFFF]), -1)

    def test_decode_uint32_and_int32(self) -> None:
        self.assertEqual(decode_register_value(_reg("uint32"), [0x0001, 0x0002]), 65538)
        self.assertEqual(decode_register_value(_reg("int32"), [0xFFFF, 0xFFFF]), -1)

    def test_decode_float32_and_word_order(self) -> None:
        self.assertAlmostEqual(decode_register_value(_reg("float32"), [0x3F80, 0x0000]), 1.0)
        low_high = _reg("uint32", word_order="low_high")
        self.assertEqual(decode_register_value(low_high, [0x0002, 0x0001]), 65538)

    def test_decode_coil_and_scaling(self) -> None:
        coil = RegisterDefinition("run", "Run", 1, 0, "coil")
        scaled = RegisterDefinition("pressure", "Pressure", 4, 0, "uint16", scale=0.1, offset=1, precision=1)
        self.assertTrue(decode_register_value(coil, [True]))
        self.assertEqual(scaled.apply_scale(decode_register_value(scaled, [123])), 13.3)

    def test_station_config_uses_stable_station_id(self) -> None:
        data = {
            CONF_STATION_ID: "abc123",
            CONF_STATION_NAME: "Station",
            "host": "192.168.1.10",
            "port": 502,
            CONF_UNIT_ID: 1,
            CONF_SCAN_INTERVAL: 10,
            CONF_TIMEOUT: 3,
            CONF_MAP_CSV: "key,name,function,address,type\nx,X,4,1,uint16\n",
        }

        station = StationConfig.from_data(data)

        self.assertEqual(station.station_id, "abc123")

    def test_station_config_falls_back_for_legacy_entries(self) -> None:
        data = {
            CONF_STATION_NAME: "Station",
            "host": "192.168.1.10",
            "port": 502,
            CONF_UNIT_ID: 1,
            CONF_SCAN_INTERVAL: 10,
            CONF_TIMEOUT: 3,
            CONF_MAP_CSV: "key,name,function,address,type\nx,X,4,1,uint16\n",
        }

        station = StationConfig.from_data(data)

        self.assertEqual(station.station_id, "station_192_168_1_10_502_1")

    def test_expected_unique_ids_include_connection_and_map_keys(self) -> None:
        station = StationConfig(
            station_id="station_a",
            name="Station A",
            host="192.168.1.10",
            port=502,
            unit_id=1,
            scan_interval=10,
            timeout=3,
            map_csv="",
        )
        registers = [
            RegisterDefinition("pressure", "Pressure", 4, 10, "uint16"),
            RegisterDefinition("running", "Running", 1, 2, "coil"),
        ]

        self.assertEqual(
            expected_unique_ids(station, registers),
            {
                "dbs_tcp_modbus_station_a_connection",
                "dbs_tcp_modbus_station_a_pressure",
                "dbs_tcp_modbus_station_a_running",
            },
        )

    def test_example_maps_are_valid(self) -> None:
        examples_dir = Path(__file__).resolve().parents[1] / "examples"
        for filename in ("czarnow.csv", "gawartowa_wola.csv", "feliksow.csv"):
            with self.subTest(filename=filename):
                registers = parse_register_csv((examples_dir / filename).read_text(encoding="utf-8"))
                self.assertGreater(len(registers), 0)


def _reg(value_type: str, **kwargs: object) -> RegisterDefinition:
    return RegisterDefinition("x", "X", 4, 0, value_type, **kwargs)


if __name__ == "__main__":
    unittest.main()
