"""openinverter remote database unit tests"""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

from openinverter_can_tool.paramdb import import_database
from openinverter_can_tool.remote_db import RemoteDatabaseNode

from .network_test_case import NetworkTestCase

TX = 1
RX = 2

CAPTURE_DATA_DIR = Path(__file__).parent / "test_data" / "captures"

# Reduce test verbosity
# pylint: disable=missing-function-docstring


class TestRemoteDatabaseNode(NetworkTestCase):
    """
    Test the openinverter specific database access SDO indices
    """

    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        self._node_type = RemoteDatabaseNode

    def test_paramdb_checksum(self):
        self.data = [
            (TX, b'\x40\x00\x50\x03\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x50\x03\x12\x70\x01\x00')
        ]
        checksum = self.node.param_db_checksum()
        assert checksum == 94226

    def load_capture(self, capture: str, tx_id: int, rx_id: int) -> None:
        """Load a CAN capture from SavvyCAN in CSV format into the data"""
        with open(CAPTURE_DATA_DIR / capture,
                  newline="", encoding="utf-8") as capture_file:
            reader = csv.DictReader(capture_file)

            for row in reader:
                frame_id = int(row["ID"], 16)

                if frame_id == tx_id:
                    direction = TX
                elif frame_id == rx_id:
                    direction = RX
                else:
                    continue

                assert int(row["LEN"]) == 8

                frame = row["D1"] + row["D2"] + row["D3"] + row["D4"] + \
                    row["D5"] + row["D6"] + row["D7"] + row["D8"]
                self.data.append((direction, bytes.fromhex(frame)))

    @pytest.mark.skipif(sys.version_info < (3, 12),
                        reason="NamedTemporaryFile() missing delete_on_close "
                        "before python 3.12")
    def test_query_zombieverter_paramdb(self):
        self.load_capture(
            "zombieverter-node3-query-paramdb.csv",
            0x603,
            0x583)
        self.node.node_id = 3

        checksum = self.node.param_db_checksum()

        with tempfile.NamedTemporaryFile(delete_on_close=False) as db_file:
            db_file.write(self.node.param_db())
            db_file.close()

            db = import_database(Path(db_file.name))

        assert checksum == 181129
        assert len(db.names) == 194


if __name__ == "__main__":
    unittest.main()
