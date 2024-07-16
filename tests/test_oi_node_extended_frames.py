"""
openinverter custom SDO protocol unit tests
Extended frame specific tests
"""

import unittest
from typing import List, Tuple

import canopen

from openinverter_can_tool.oi_node import (CanMessage, Direction,
                                           MapEntry, OpenInverterNode)
from openinverter_can_tool.paramdb import OIVariable

TX = 1
RX = 2

# Reduce test verbosity
# pylint: disable=missing-function-docstring


class TestOpenInverterNodeExtendedFrames(unittest.TestCase):
    """
    Test the custom openinverter node protocol by example
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
        node = OpenInverterNode(network, 2)
        node.sdo.RESPONSE_TIMEOUT = 0.01
        self.node = node
        self.network = network
        self.data: List[Tuple[int, bytes]] = []

    def tearDown(self) -> None:
        # At the end of every test all of the data data should have been
        # consumed by _send_message()
        assert len(self.data) == 0

    def test_map_receive_extended_can_id(self):
        # Manually synthesized packets equivalent to:
        # oic can add rx 0x312 ChargeCurrent 31 -16 0.100000001 0 --extended
        # From a question relating to integrating a boostech bms v3
        # https://openinverter.org/forum/viewtopic.php?p=72768#p72768
        self.data = [
            (TX, b'\x23\x01\x30\x00\x12\x03\x00\x20'),
            (RX, b'\x60\x01\x30\x00\x12\x03\x00\x20'),
            (TX, b'\x23\x01\x30\x01\x04\x00\x1F\xF0'),
            (RX, b'\x60\x01\x30\x01\x04\x00\x1F\xF0'),
            (TX, b'\x23\x01\x30\x02\x64\x00\x00\x00'),
            (RX, b'\x60\x01\x30\x02\x64\x00\x00\x00')
        ]
        charge_current = OIVariable("ChargeCurrent", 4)
        self.node.add_can_map_entry(
            can_id=0x312,
            direction=Direction.RX,
            param_id=charge_current.id,
            position=31,
            length=-16,
            gain=0.100000001,
            offset=0,
            is_extended_frame=True)

    def test_map_transmit_extended_can_id(self):
        # Manually synthesized packets equivalent to:
        # oic can add tx 0x12345678 tmpm 0 8 1.0 0 --extended
        self.data = [
            (TX, b'\x23\x00\x30\x00\x78\x56\x34\x32'),
            (RX, b'\x60\x00\x30\x00\x00\x00\x00\x00'),
            (TX, b'\x23\x00\x30\x01\xE3\x07\x00\x08'),
            (RX, b'\x60\x00\x30\x01\xE3\x07\x00\x08'),
            (TX, b'\x23\x00\x30\x02\xE8\x03\x00\x00'),
            (RX, b'\x60\x00\x30\x02\xE8\x03\x00\x00')
        ]
        tmphs = OIVariable("tmphs", 2019)
        self.node.add_can_map_entry(
            can_id=0x12345678,
            direction=Direction.TX,
            param_id=tmphs.id,
            position=0,
            length=8,
            gain=1.0,
            offset=0,
            is_extended_frame=True)

    def test_map_param_out_of_range_extended_can_id(self):
        self.data = []

        with self.assertRaises(ValueError):
            self.node.add_can_map_entry(
                can_id=0x20000000,
                direction=Direction.TX,
                param_id=1,
                position=0,
                length=8,
                gain=1.0,
                offset=0,
                is_extended_frame=True)

    def test_list_tx_map_single_extended_can_id_message_and_single_param(self):
        # Synthesised CAN frame equivalent to the command:
        # oic can list
        # 0x12345678:
        # tx.0.0 param='tmphs' pos=24 length=8 gain=-1.0 offset=0
        self.data = [
            # First CAN ID
            (TX, b'\x40\x00\x31\x00\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x00\x78\x56\x34\x32'),

            # First CAN ID - first param: id, position and length
            (TX, b'\x40\x00\x31\x01\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x01\xE3\x07\x18\x08'),

            # First CAN ID - first param: gain and offset
            (TX, b'\x40\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x02\x18\xFC\xFF\x00'),

            # First CAN ID - second param: not present
            (TX, b'\x40\x00\x31\x03\x00\x00\x00\x00'),
            (RX, b'\x80\x00\x31\x03\x00\x00\x02\x06'),

            # Second CAN ID - not present
            (TX, b'\x40\x01\x31\x00\x00\x00\x00\x00'),
            (RX, b'\x80\x01\x31\x00\x00\x00\x02\x06')
        ]

        can_map = self.node.list_can_map(Direction.TX)

        assert len(can_map) == 1
        msg = can_map[0]

        assert msg.can_id == 0x12345678
        assert msg.is_extended_frame

        assert len(msg.params) == 1
        param = msg.params[0]

        assert param.param_id == 2019
        assert param.position == 24
        assert param.length == 8
        assert param.gain == -1.0
        assert param.offset == 0

    def test_list_tx_map_single_extended_can_id_with_short_id(self):
        # Synthesised CAN frame equivalent to the command:
        # oic can list
        # 0x00000101:
        # tx.0.0 param='tmphs' pos=24 length=8 gain=-1.0 offset=0
        self.data = [
            # First CAN ID
            (TX, b'\x40\x00\x31\x00\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x00\x01\x01\x00\x20'),

            # First CAN ID - first param: id, position and length
            (TX, b'\x40\x00\x31\x01\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x01\xE3\x07\x18\x08'),

            # First CAN ID - first param: gain and offset
            (TX, b'\x40\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x02\x18\xFC\xFF\x00'),

            # First CAN ID - second param: not present
            (TX, b'\x40\x00\x31\x03\x00\x00\x00\x00'),
            (RX, b'\x80\x00\x31\x03\x00\x00\x02\x06'),

            # Second CAN ID - not present
            (TX, b'\x40\x01\x31\x00\x00\x00\x00\x00'),
            (RX, b'\x80\x01\x31\x00\x00\x00\x02\x06')
        ]

        can_map = self.node.list_can_map(Direction.TX)

        assert len(can_map) == 1
        msg = can_map[0]

        assert msg.can_id == 0x101
        assert msg.is_extended_frame

        assert len(msg.params) == 1
        param = msg.params[0]

        assert param.param_id == 2019
        assert param.position == 24
        assert param.length == 8
        assert param.gain == -1.0
        assert param.offset == 0

    def test_add_mixing_extended_and_standard_messages_in_a_single_map(self):
        # Captured from running the command sequence:
        # oic can add tx 0x101 tmpm 0 8 little 1.0 0
        # oic can add tx 0x102 tmphs 32 32 little 2.0 0 --extended
        self.data = [
            (TX, b'\x23\x00\x30\x00\x01\x01\x00\x00'),
            (RX, b'\x60\x00\x30\x00\x01\x01\x00\x00'),
            (TX, b'\x23\x00\x30\x01\xE4\x07\x00\x08'),
            (RX, b'\x60\x00\x30\x01\xE4\x07\x00\x08'),
            (TX, b'\x23\x00\x30\x02\xE8\x03\x00\x00'),
            (RX, b'\x60\x00\x30\x02\xE8\x03\x00\x00'),
            (TX, b'\x23\x00\x30\x00\x02\x01\x00\x20'),
            (RX, b'\x60\x00\x30\x00\x02\x01\x00\x20'),
            (TX, b'\x23\x00\x30\x01\xE3\x07\x20\x20'),
            (RX, b'\x60\x00\x30\x01\xE3\x07\x20\x20'),
            (TX, b'\x23\x00\x30\x02\xD0\x07\x00\x00'),
            (RX, b'\x60\x00\x30\x02\xD0\x07\x00\x00')
        ]

        tmpm = OIVariable("tmpm", 2020)
        tmphs = OIVariable("tmphs", 2019)

        msg_map = [
            CanMessage(
                can_id=0x101,
                params=[MapEntry(tmpm.id, 0, 8,  1.0, 0)],
                is_extended_frame=False
            ),
            CanMessage(
                can_id=0x102,
                params=[MapEntry(tmphs.id, 32, 32, 2.0, 0)],
                is_extended_frame=True
            )
        ]

        self.node.add_can_map(Direction.TX, msg_map)


if __name__ == "__main__":
    unittest.main()
