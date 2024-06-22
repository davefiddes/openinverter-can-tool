"""openinverter remote database unit tests"""
import csv
import tempfile
import unittest
from pathlib import Path
from typing import List, Tuple

import canopen

from openinverter_can_tool.paramdb import import_database
from openinverter_can_tool.remote_db import RemoteDatabaseNode

TX = 1
RX = 2

CAPTURE_DATA_DIR = Path(__file__).parent / "test_data" / "captures"

# Reduce test verbosity
# pylint: disable=missing-function-docstring


class TestRemoteDatabaseNode(unittest.TestCase):
    """
    Test the openinverter specific database access SDO indices
    """

    def _send_message(self, can_id, data, remote=False):
        """Will be used instead of the usual Network.send_message method.

        Checks that the message data is according to expected and answers
        with the provided data.
        """
        next_data = self.data.pop(0)
        self.assertEqual(next_data[0], TX, "No transmission was expected")
        self.assertSequenceEqual(data, next_data[1])
        self.assertEqual(can_id, 0x602)
        while self.data and self.data[0][0] == RX:
            self.network.notify(0x582, bytearray(self.data.pop(0)[1]), 0.0)

        # pretend to use remote
        _ = remote

    def setUp(self):
        network = canopen.Network()
        network.send_message = self._send_message
        node = RemoteDatabaseNode(network, 2)
        node.sdo_client.RESPONSE_TIMEOUT = 0.01
        self.node = node
        self.network = network
        self.data: List[Tuple[int, bytes]] = []

    def tearDown(self) -> None:
        # At the end of every test all of the data data should have been
        # consumed by _send_message()
        assert len(self.data) == 0

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

    def test_query_zombieverter_paramdb(self):
        self.load_capture(
            "zombieverter-node3-query-paramdb.csv",
            0x603,
            0x583)
        self.node.node_id = 3

        checksum = self.node.param_db_checksum()

        with tempfile.NamedTemporaryFile() as db_file:
            db_file.write(self.node.param_db())
            db_file.flush()

            db = import_database(Path(db_file.name))

        assert checksum == 181129
        assert len(db.names) == 194


if __name__ == "__main__":
    unittest.main()
