"""
Test CAN message map persistence
"""
import filecmp
import unittest
from pathlib import Path

import canopen.objectdictionary
import pytest

from openinverter_can_tool.map_persistence import (export_json_map,
                                                   import_json_map)
from openinverter_can_tool.oi_node import CanMessage, MapEntry
from openinverter_can_tool.paramdb import import_database

MAP_DIR = Path(__file__).parent / "test_data" / "maps"
DB_DIR = Path(__file__).parent / "test_data" / "paramdb"

# Reduce test verbosity
# pylint: disable=missing-function-docstring


class TestJSONMaps:
    """Test CAN message map persistence to and from JSON"""

    def test_export_empty_map(self, tmp_path: Path):
        map_file_path = tmp_path / "empty.json"

        with open(map_file_path, "wt", encoding="utf-8") as map_file:
            export_json_map([], [], canopen.ObjectDictionary(), map_file)

        assert filecmp.cmp(map_file_path, MAP_DIR / "empty.json",
                           shallow=False)

    def test_export_single_tx_message_single_param(self, tmp_path: Path):

        tx_map = [
            CanMessage(0x123, [MapEntry(1, 24, 8, -1.0, 0)])
        ]

        db = import_database(DB_DIR / "single-param.json")

        map_file_path = tmp_path / "single-tx-message-single-param.json"
        with open(map_file_path, "wt", encoding="utf-8") as map_file:
            export_json_map(tx_map, [], db, map_file)

        assert filecmp.cmp(
            map_file_path,
            MAP_DIR / "single-tx-message-single-param.json",
            shallow=False)

    def test_export_simple_tx_and_rx_message_map(self, tmp_path: Path):

        tx_map = [
            CanMessage(0x123, [MapEntry(1, 24, 8, -1.0, 0)]),
        ]
        rx_map = [
            CanMessage(0x321, [MapEntry(1, 23, -16, 2.5, -42)])
        ]

        db = import_database(DB_DIR / "single-param.json")

        map_file_path = tmp_path / "simple-tx-rx-message-map.json"
        with open(map_file_path, "wt", encoding="utf-8") as map_file:
            export_json_map(tx_map, rx_map, db, map_file)

        assert filecmp.cmp(
            map_file_path,
            MAP_DIR / "simple-tx-rx-message-map.json",
            shallow=False)

    def test_export_multiple_tx_messages_with_multiple_params(
            self,
            tmp_path: Path):

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

        map_file_path = tmp_path / "multiple-tx-messages.json"
        with open(map_file_path, "wt", encoding="utf-8") as map_file:
            export_json_map(tx_map, [], db, map_file)

        assert filecmp.cmp(
            map_file_path,
            MAP_DIR / "multiple-tx-messages.json",
            shallow=False)

    def test_export_map_with_invalid_param_id(self, tmp_path: Path):

        rx_map = [
            CanMessage(0x123, [MapEntry(2, 24, 8, -1.0, 0)])
        ]

        db = import_database(DB_DIR / "single-param.json")

        map_file_path = tmp_path / "empty-file.json"
        with pytest.raises(KeyError):
            with open(map_file_path, "wt", encoding="utf-8") as map_file:
                export_json_map([], rx_map, db, map_file)

        assert map_file_path.stat().st_size == 0

    def test_import_empty_maps(self):
        db = import_database(DB_DIR / "single-param.json")

        with open(MAP_DIR / "empty.json", "rt", encoding="utf-8") as map_file:
            (tx_map, rx_map) = import_json_map(map_file, db)
            assert not tx_map
            assert not rx_map

    def test_import_single_tx_message_single_param(self):
        db = import_database(DB_DIR / "single-param.json")

        expected_tx_map = [
            CanMessage(0x123, [MapEntry(1, 24, 8, -1.0, 0)])
        ]

        with open(MAP_DIR / "single-tx-message-single-param.json",
                  "rt",
                  encoding="utf-8") as map_file:
            (tx_map, rx_map) = import_json_map(map_file, db)
            assert tx_map == expected_tx_map
            assert not rx_map

    def test_import_simple_tx_and_rx_message_map(self):
        db = import_database(DB_DIR / "single-param.json")

        expected_tx_map = [
            CanMessage(0x123, [MapEntry(1, 24, 8, -1.0, 0)])
        ]
        expected_rx_map = [
            CanMessage(0x321, [MapEntry(1, 23, -16, 2.5, -42)])
        ]

        with open(MAP_DIR / "simple-tx-rx-message-map.json",
                  "rt",
                  encoding="utf-8") as map_file:
            (tx_map, rx_map) = import_json_map(map_file, db)
            assert tx_map == expected_tx_map
            assert rx_map == expected_rx_map

    def test_import_multiple_tx_messages_with_multiple_params(self):
        db = import_database(DB_DIR / "complex.json")

        expected_tx_map = [
            CanMessage(0x101, [
                MapEntry(17, 24, 8, -1.0, 0),
                MapEntry(18, 0, 8, 1.0, 0),
                MapEntry(17, 8, 8, -1.0, 0),
                MapEntry(18, 16, 8, 1.0, 0)
            ]),
            CanMessage(0x333, [
                MapEntry(2035, 0, 8, 1.0, 0),
                MapEntry(107, 8, 8, -1.0, 0),
                MapEntry(2035, 16, 8, 1.0, 0),
                MapEntry(107, 24, 8, -1.0, 0)
            ])
        ]

        with open(MAP_DIR / "multiple-tx-messages.json",
                  "rt",
                  encoding="utf-8") as map_file:
            (tx_map, rx_map) = import_json_map(map_file, db)
            assert repr(tx_map) == repr(expected_tx_map)
            assert not rx_map

    def test_import_unsupported_future_version(self):
        with pytest.raises(RuntimeError, match="Unsupported version: 999"):
            with open(MAP_DIR / "unsupported-version.json",
                      "rt",
                      encoding="utf-8") as map_file:
                import_json_map(
                    map_file, canopen.ObjectDictionary())

    def test_import_invalid_file_format(self):
        with pytest.raises(RuntimeError, match="Invalid file format"):
            with open(DB_DIR / "empty-but-valid.json",
                      "rt",
                      encoding="utf-8") as map_file:
                import_json_map(map_file, canopen.ObjectDictionary())

    def test_import_corrupt_missing_can_id(self):
        db = import_database(DB_DIR / "single-param.json")
        with pytest.raises(KeyError):
            with open(MAP_DIR / "corrupt-missing-can-id.json",
                      "rt",
                      encoding="utf-8") as map_file:
                import_json_map(map_file, db)

    def test_import_corrupt_invalid_param_name(self):
        db = import_database(DB_DIR / "single-param.json")
        with pytest.raises(KeyError):
            with open(MAP_DIR / "corrupt-invalid-param-name.json",
                      "rt",
                      encoding="utf-8") as map_file:
                import_json_map(map_file, db)

    def test_round_trip_complex_tx_and_rx_map(self, tmp_path: Path):

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

        map_file_path = tmp_path / "complex_tx_and_rx_map.json"
        with open(map_file_path, "wt", encoding="utf-8") as map_file:
            export_json_map(tx_map, rx_map, db, map_file)

        with open(map_file_path, "rt", encoding="utf-8") as read_map_file:
            (in_tx_map, in_rx_map) = import_json_map(read_map_file, db)
            assert in_tx_map == tx_map
            assert in_rx_map == rx_map

    def test_import_simple_tx_and_rx_message_map_without_extended_support(
            self):
        """The original file format from 0.0.9"""
        db = import_database(DB_DIR / "single-param.json")

        expected_tx_map = [
            CanMessage(0x123, [MapEntry(1, 24, 8, -1.0, 0)])
        ]
        expected_rx_map = [
            CanMessage(0x321, [MapEntry(1, 23, -16, 2.5, -42)])
        ]

        with open(MAP_DIR /
                  "simple-tx-rx-message-map-without-extended-support.json",
                  "rt",
                  encoding="utf-8") as map_file:
            (tx_map, rx_map) = import_json_map(map_file, db)
            assert tx_map == expected_tx_map
            assert rx_map == expected_rx_map

    def test_import_multiple_tx_messages_with_extended_can_ids(self):
        db = import_database(DB_DIR / "complex.json")

        expected_tx_map = [
            CanMessage(0x101, [
                MapEntry(17, 24, 8, -1.0, 0),
                MapEntry(18, 0, 8, 1.0, 0),
                MapEntry(17, 8, 8, -1.0, 0),
                MapEntry(18, 16, 8, 1.0, 0)
            ], is_extended_frame=True),
            CanMessage(0x12345678, [
                MapEntry(2035, 0, 8, 1.0, 0),
                MapEntry(107, 8, 8, -1.0, 0),
                MapEntry(2035, 16, 8, 1.0, 0),
                MapEntry(107, 24, 8, -1.0, 0)
            ], is_extended_frame=True)
        ]

        with open(MAP_DIR / "multiple-tx-extended-id-messages.json",
                  "rt",
                  encoding="utf-8") as map_file:
            (tx_map, rx_map) = import_json_map(map_file, db)
            assert repr(tx_map) == repr(expected_tx_map)
            assert not rx_map

    def test_import_corrupt_out_of_range_extended_can_id(self):
        db = import_database(DB_DIR / "single-param.json")
        with pytest.raises(ValueError):
            with open(MAP_DIR / "corrupt-out-of-range-extended-can-id.json",
                      "rt",
                      encoding="utf-8") as map_file:
                import_json_map(map_file, db)


if __name__ == '__main__':
    unittest.main()
