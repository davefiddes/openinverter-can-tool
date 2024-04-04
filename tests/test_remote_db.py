"""openinverter remote database unit tests"""
import unittest
from typing import List, Tuple

import canopen

from openinverter_can_tool.remote_db import RemoteDatabaseNode

TX = 1
RX = 2

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


if __name__ == "__main__":
    unittest.main()
