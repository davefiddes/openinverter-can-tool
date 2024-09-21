"""
Test CAN message map to dbc persistence
"""
import unittest
from pathlib import Path

import canopen.objectdictionary
import pytest
from approvaltests import verify

from openinverter_can_tool.map_persistence import (export_dbc_map,
                                                   export_json_map,
                                                   transform_map_to_canopen_db)
from openinverter_can_tool.oi_node import CanMessage, MapEntry
from openinverter_can_tool.paramdb import import_database

DB_DIR = Path(__file__).parent / "test_data" / "paramdb"

# Reduce test verbosity
# pylint: disable=missing-function-docstring


class TestDBCMaps:
    """Test CAN message map persistence to DBC message definition files"""

    def test_transform_empty_map(self):
        canopen_db = transform_map_to_canopen_db(
            None,
            [],
            [],
            canopen.ObjectDictionary())

        verify(canopen_db)

    def test_transform_single_tx_message_single_param(self):

        tx_map = [
            CanMessage(0x123, [MapEntry(1, 24, 8, -1.0, 0)])
        ]

        db = import_database(DB_DIR / "single-param.json")

        canopen_db = transform_map_to_canopen_db(None, tx_map, [], db)

        verify(canopen_db)

    def test_transform_simple_tx_and_rx_message_map(self):

        tx_map = [
            CanMessage(0x123, [MapEntry(1, 24, 8, -1.0, 0)]),
        ]
        rx_map = [
            CanMessage(0x321, [MapEntry(1, 23, -16, 2.5, -42)])
        ]

        db = import_database(DB_DIR / "single-param.json")

        canopen_db = transform_map_to_canopen_db(None, tx_map, rx_map, db)

        verify(canopen_db)

    def test_transform_multiple_tx_messages_with_multiple_params(
            self):

        tx_map = [
            CanMessage(0x101, [
                MapEntry(17, 24, 8, -1.0, 0),
                MapEntry(18, 0, 8, 1.0, 0),
                MapEntry(17, 8, 8, -1.0, 0),
                MapEntry(18, 16, 8, 1.0, 0)
            ]),
            CanMessage(0x333, [
                MapEntry(2035, 0, 8, 1.0, 0),
                MapEntry(107, 8, 8, -1.0, 0),
                MapEntry(2035, 16, 8,  1.0, 0),
                MapEntry(107, 24, 8, -1.0, 0)
            ])
        ]

        db = import_database(DB_DIR / "complex.json")

        canopen_db = transform_map_to_canopen_db(None, tx_map, [], db)

        verify(canopen_db)

    def test_transform_map_with_invalid_param_id(self):

        rx_map = [
            CanMessage(0x123, [MapEntry(2, 24, 8, -1.0, 0)])
        ]

        db = import_database(DB_DIR / "single-param.json")

        with pytest.raises(KeyError):
            transform_map_to_canopen_db(None, [], rx_map, db)

    def test_export_multiple_tx_messages_with_multiple_params(
            self, tmp_path: Path):

        tx_map = [
            CanMessage(0x101, [
                MapEntry(17, 24, 8, -1.0, 0),
                MapEntry(18, 0, 8, 1.0, 0),
                MapEntry(17, 8, 8, -1.0, 0),
                MapEntry(18, 16, 8, 1.0, 0)
            ]),
            CanMessage(0x333, [
                MapEntry(2035, 0, 8, 1.0, 0),
                MapEntry(107, 8, 8, -1.0, 0),
                MapEntry(2035, 16, 8,  1.0, 0),
                MapEntry(107, 24, 8, -1.0, 0)
            ])
        ]

        db = import_database(DB_DIR / "complex.json")

        dbc_path = tmp_path / "multiple_tx_messages_with_multiple_params.dbc"
        export_dbc_map(None, tx_map, [], db, dbc_path)

        with open(dbc_path, "rt", encoding="utf-8") as dbc_file:
            verify(dbc_file.read())

    def test_export_complex_tx_and_rx_map(
            self, tmp_path: Path):

        tx_map = [
            # Simple 8-bit mapping of common temperature values
            CanMessage(0x101, [
                MapEntry(2019, 0, 8, 1.0, 0),
                MapEntry(2020, 8, 8, 1.0, 0)
            ]),

            # 8-bit mapping with an offset
            CanMessage(0x102, [
                MapEntry(2019, 0, 8, 1.0, 10),
                MapEntry(2020, 8, 8, 1.0, 10)
            ]),

            # Little-endian full 32-bit mapping with generous scale
            CanMessage(0x103, [
                MapEntry(2019, 0, 32, 100.0, 0),
                MapEntry(2020, 32, 32, 100.0, 0)
            ]),

            # Big-endian 16-bit mapping of an inverter parameter
            CanMessage(0x104, [
                MapEntry(22, 23, -16, 1.0, 0)
            ]),

            # Big-endian full 32-bit mapping with generous scale
            CanMessage(0x105, [
                MapEntry(2019, 31, -32, 100.0, 0),
                MapEntry(2020, 63, -32, 100.0, 0)
            ])
        ]

        rx_map = [
            # Receive an inverter parameter with a big-endian mapping
            CanMessage(0x201, [
                MapEntry(22, 23, -16, 1.0, 0)
            ])
        ]

        db = import_database(DB_DIR / "mapable-params.json")

        dbc_path = tmp_path / "complex_tx_and_rx_map.dbc"
        export_dbc_map(None, tx_map, rx_map, db, dbc_path)

        with open(dbc_path, "rt", encoding="utf-8") as dbc_file:
            verify(dbc_file.read())

        # export a JSON map to allow the resulting DBC to be manually tested
        # with SavvyCAN on real hardware
        map_file_path = tmp_path / "complex_tx_and_rx_map.json"
        with open(map_file_path, "wt", encoding="utf-8") as map_file:
            export_json_map(tx_map, rx_map, db, map_file)

    def test_export_tx_map_with_enum_param(self, tmp_path: Path):

        tx_map = [
            # Map an enum param to the first 8 bits of a frame
            CanMessage(1, [
                MapEntry(95, 0, 8, 1.0, 0),
            ]),
        ]

        db = import_database(DB_DIR / "mapable-params.json")

        dbc_path = tmp_path / "tx_map_with_enum_param.dbc"
        export_dbc_map(None, tx_map, [], db, dbc_path)

        with open(dbc_path, "rt", encoding="utf-8") as dbc_file:
            verify(dbc_file.read())

    def test_export_tx_map_with_bitfield_spot_value(self, tmp_path: Path):

        tx_map = [
            # Map a bitfield spot value param to the first 8 bits of a frame
            CanMessage(1, [
                MapEntry(2044, 0, 8, 1.0, 0),
            ]),
        ]

        db = import_database(DB_DIR / "mapable-params.json")

        dbc_path = tmp_path / "tx_map_with_bitfield_spot_value.dbc"
        export_dbc_map(None, tx_map, [], db, dbc_path)

        with open(dbc_path, "rt", encoding="utf-8") as dbc_file:
            verify(dbc_file.read())

    def test_export_tx_and_rx_map_with_node_name(self, tmp_path: Path):

        tx_map = [
            CanMessage(1, [MapEntry(2019, 0, 8, 1.0, 0)])
        ]

        rx_map = [
            CanMessage(2, [MapEntry(22, 32, 16, 1.0, 0)])
        ]

        db = import_database(DB_DIR / "mapable-params.json")

        dbc_path = tmp_path / "tx_and_rx_map_with_node_name.dbc"
        export_dbc_map("custom_node_name", tx_map, rx_map, db, dbc_path)

        with open(dbc_path, "rt", encoding="utf-8") as dbc_file:
            verify(dbc_file.read())

    def test_export_tx_message_with_extended_frame_ids(self, tmp_path: Path):

        tx_map = [
            CanMessage(0x00000123, [MapEntry(1, 24, 8, -1.0, 0)], True),
            CanMessage(0x12345678, [MapEntry(1, 24, 8, -1.0, 0)], True)
        ]

        db = import_database(DB_DIR / "single-param.json")

        dbc_path = tmp_path / "tx_message_with_extended_frame_ids.dbc"
        export_dbc_map(None, tx_map, [], db, dbc_path)

        with open(dbc_path, "rt", encoding="utf-8") as dbc_file:
            verify(dbc_file.read())

        # export a JSON map to allow the resulting DBC to be manually tested
        # with SavvyCAN on real hardware
        map_file_path = tmp_path / "tx_message_with_extended_frame_ids.json"
        with open(map_file_path, "wt", encoding="utf-8") as map_file:
            export_json_map(tx_map, [], db, map_file)

    def test_export_tx_map_with_enum_param_with_offset_and_gain(
            self, tmp_path: Path):

        tx_map = [
            # Map an enum param to the first 8 bits of a frame
            # Add an offset and gain to muddle the actual transmitted values
            CanMessage(1, [
                MapEntry(95, 0, 8, 5.0, 13),
            ]),
        ]

        db = import_database(DB_DIR / "mapable-params.json")

        dbc_path = tmp_path / "tx_map_with_enum_param_and_offset.dbc"
        export_dbc_map(None, tx_map, [], db, dbc_path)

        with open(dbc_path, "rt", encoding="utf-8") as dbc_file:
            verify(dbc_file.read())

    def test_export_tx_map_with_bitfield_spot_value_and_offset_and_gain(
            self, tmp_path: Path):

        tx_map = [
            # Map a bitfield spot value param to the first 8 bits of a frame
            # add an offset and gain to muddle the actual transmitted values
            CanMessage(1, [
                MapEntry(2044, 0, 16, 4.0, 1),
            ]),
        ]

        db = import_database(DB_DIR / "mapable-params.json")

        dbc_path = tmp_path / "tx_map_with_bitfield_spot_value_and_offset.dbc"
        export_dbc_map(None, tx_map, [], db, dbc_path)

        with open(dbc_path, "rt", encoding="utf-8") as dbc_file:
            verify(dbc_file.read())


if __name__ == '__main__':
    unittest.main()
