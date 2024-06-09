"""openinverter custom SDO protocol unit tests"""

import unittest
from typing import List, Tuple

import canopen

from openinverter_can_tool import constants as oi
from openinverter_can_tool.oi_node import (CanMessage, Direction,
                                           MapEntry, OpenInverterNode)
from openinverter_can_tool.paramdb import OIVariable

TX = 1
RX = 2

# Reduce test verbosity
# pylint: disable=missing-function-docstring


class TestOpenInverterNode(unittest.TestCase):
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

    def test_serialno(self):
        self.data = [
            (TX, b'\x40\x00\x50\x02\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x50\x02\x29\x30\x19\x87'),
            (TX, b'\x40\x00\x50\x01\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x50\x01\x48\x86\x49\x49'),
            (TX, b'\x40\x00\x50\x00\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x50\x00\x54\xFF\x70\x06')
        ]
        serialno = self.node.serial_no()

        # "serial" command returns:
        # 87193029:49498648:670FF54
        assert serialno == b'\x87\x19\x30\x29\x49\x49\x86\x48\x06\x70\xff\x54'

    def test_save_command(self):
        self.data = [
            (TX, b'\x23\x02\x50\x00\x00\x00\x00\x00'),
            (RX, b'\x60\x02\x50\x00\x00\x00\x00\x00')
        ]
        self.node.save()

    def test_load_command(self):
        self.data = [
            (TX, b'\x23\x02\x50\x01\x00\x00\x00\x00'),
            (RX, b'\x60\x02\x50\x01\x00\x00\x00\x00')
        ]
        self.node.load()

    def test_reset_command(self):
        self.data = [
            (TX, b'\x23\x02\x50\x02\x00\x00\x00\x00'),
            (RX, b'\x60\x02\x50\x02\x00\x00\x00\x00')
        ]
        self.node.reset()

    def test_defaults_command(self):
        self.data = [
            (TX, b'\x23\x02\x50\x03\x00\x00\x00\x00'),
            (RX, b'\x60\x02\x50\x03\x00\x00\x00\x00')
        ]
        self.node.load_defaults()

    def test_normal_start_command(self):
        self.data = [
            (TX, b'\x23\x02\x50\x04\x01\x00\x00\x00'),
            (RX, b'\x60\x02\x50\x04\x01\x00\x00\x00')
        ]
        self.node.start()

    def test_manual_start_command(self):
        self.data = [
            (TX, b'\x23\x02\x50\x04\x02\x00\x00\x00'),
            (RX, b'\x60\x02\x50\x04\x02\x00\x00\x00')
        ]
        self.node.start(mode=oi.START_MODE_MANUAL)

    def test_stop_command(self):
        self.data = [
            (TX, b'\x23\x02\x50\x05\x00\x00\x00\x00'),
            (RX, b'\x60\x02\x50\x05\x00\x00\x00\x00')
        ]
        self.node.stop()

    def test_list_empty_tx_and_rx_map(self):
        self.data = [
            (TX, b'\x40\x00\x31\x00\x00\x00\x00\x00'),
            (RX, b'\x80\x00\x31\x00\x00\x00\x02\x06'),
            (TX, b'\x40\x80\x31\x00\x00\x00\x00\x00'),
            (RX, b'\x80\x80\x31\x00\x00\x00\x02\x06')
        ]

        # The original capture covers both TX followed by RX listing of the map
        # but the API separates these two operations. Combine the requests into
        # a single test.
        tx_map = self.node.list_can_map(Direction.TX)
        assert not tx_map

        rx_map = self.node.list_can_map(Direction.RX)
        assert not rx_map

    def test_list_tx_map_single_message_and_single_param(self):
        # From a capture of the command:
        # oic can list
        # 0x101:
        # tx.0.0 param='tmphs' pos=24 length=8 gain=-1.0 offset=0
        self.data = [
            # First CAN ID
            (TX, b'\x40\x00\x31\x00\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x00\x01\x01\x00\x00'),

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

        assert len(msg.params) == 1
        param = msg.params[0]

        assert param.param_id == 2019
        assert param.position == 24
        assert param.length == 8
        assert param.gain == -1.0
        assert param.offset == 0

    def test_list_tx_map_single_can_id_two_params(self):
        # From a capture of the command:
        # oic can list
        # 0x101:
        # tx.0.0 param='tmphs' pos=24 length=8 gain=-1.0 offset=0
        # tx.0.1 param='tmpm' pos=0 length=8 gain=1.0 offset=0
        self.data = [
            # First CAN ID
            (TX, b'\x40\x00\x31\x00\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x00\x01\x01\x00\x00'),

            # First CAN ID - first param: id, position and length
            (TX, b'\x40\x00\x31\x01\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x01\xE3\x07\x18\x08'),

            # First CAN ID - first param: gain and offset
            (TX, b'\x40\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x02\x18\xFC\xFF\x00'),

            # First CAN ID - second param: id, position and length
            (TX, b'\x40\x00\x31\x03\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x03\xE4\x07\x00\x08'),

            # First CAN ID - second param: gain and offset
            (TX, b'\x40\x00\x31\x04\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x04\xE8\x03\x00\x00'),

            # First CAN ID - third param: not present
            (TX, b'\x40\x00\x31\x05\x00\x00\x00\x00'),
            (RX, b'\x80\x00\x31\x05\x00\x00\x02\x06'),

            # Second CAN ID - not present
            (TX, b'\x40\x01\x31\x00\x00\x00\x00\x00'),
            (RX, b'\x80\x01\x31\x00\x00\x00\x02\x06'),
        ]

        can_map = self.node.list_can_map(Direction.TX)

        assert len(can_map) == 1
        msg = can_map[0]

        assert msg.can_id == 0x101

        assert len(msg.params) == 2

        param = msg.params[0]
        assert param.param_id == 2019
        assert param.position == 24
        assert param.length == 8
        assert param.gain == -1.0
        assert param.offset == 0

        param = msg.params[1]
        assert param.param_id == 2020
        assert param.position == 0
        assert param.length == 8
        assert param.gain == 1.0
        assert param.offset == 0

    def test_list_tx_map_two_can_ids_single_param(self):
        # Manually synthesised CAN packets equivalent to:
        # oic can list
        # 0x001:
        # tx.0.0 param='tmphs' pos=24 length=8 gain=-1.0 offset=0
        # 0x7ff:
        # tx.1.0 param='tmpm' pos=0 length=8 gain=1.0 offset=0
        self.data = [
            # First CAN ID
            (TX, b'\x40\x00\x31\x00\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x00\x01\x00\x00\x00'),

            # First CAN ID - first param: id, position and length
            (TX, b'\x40\x00\x31\x01\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x01\xE3\x07\x18\x08'),

            # First CAN ID - first param: gain and offset
            (TX, b'\x40\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x02\x18\xFC\xFF\x00'),

            # First CAN ID - second param: not present
            (TX, b'\x40\x00\x31\x03\x00\x00\x00\x00'),
            (RX, b'\x80\x00\x31\x03\x00\x00\x02\x06'),

            # Second CAN ID
            (TX, b'\x40\x01\x31\x00\x00\x00\x00\x00'),
            (RX, b'\x43\x01\x31\x00\xff\x07\x00\x00'),

            # Second CAN ID - first param: id, position, length
            (TX, b'\x40\x01\x31\x01\x00\x00\x00\x00'),
            (RX, b'\x43\x01\x31\x01\xE4\x07\x00\x08'),

            # Second CAN ID - first param: gain and offset
            (TX, b'\x40\x01\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x43\x01\x31\x02\xE8\x03\x00\x00'),

            # Second CAN ID - second param: not present
            (TX, b'\x40\x01\x31\x03\x00\x00\x00\x00'),
            (RX, b'\x80\x01\x31\x03\x00\x00\x02\x06'),

            # Third CAN ID - not present
            (TX, b'\x40\x02\x31\x00\x00\x00\x00\x00'),
            (RX, b'\x80\x02\x31\x00\x00\x00\x02\x06'),
        ]

        can_map = self.node.list_can_map(Direction.TX)

        assert len(can_map) == 2
        msg = can_map[0]

        assert msg.can_id == 0x001

        assert len(msg.params) == 1
        param = msg.params[0]
        assert param.param_id == 2019
        assert param.position == 24
        assert param.length == 8
        assert param.gain == -1.0
        assert param.offset == 0

        msg = can_map[1]
        assert msg.can_id == 0x7ff

        assert len(msg.params) == 1
        param = msg.params[0]
        assert param.param_id == 2020
        assert param.position == 0
        assert param.length == 8
        assert param.gain == 1.0
        assert param.offset == 0

    def test_list_tx_map_negative_gain_offset(self):
        # From a capture of the command:
        # oic can list
        # 0x101:
        # tx.0.0 param='tmphs' pos=24 length=8 gain=-8388.608 offset=-128
        self.data = [
            # First CAN ID
            (TX, b'\x40\x00\x31\x00\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x00\x01\x01\x00\x00'),

            # First CAN ID - first param: id, position and length
            (TX, b'\x40\x00\x31\x01\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x01\xE3\x07\x18\x08'),

            # First CAN ID - first param: gain and offset
            (TX, b'\x40\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x02\x00\x00\x80\x80'),

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

        assert len(msg.params) == 1
        param = msg.params[0]

        assert param.param_id == 2019
        assert param.position == 24
        assert param.length == 8
        assert param.gain == -8388.608
        assert param.offset == -128

    def test_list_tx_map_big_endian(self):
        # Manually synthesised CAN packets equivalent to:
        # oic can list
        # 0x103:
        # tx.0.0 param='tmpm' pos=7 length=-8 gain=1.0 offset=0
        self.data = [
            # First CAN ID
            (TX, b'\x40\x00\x31\x00\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x00\x03\x01\x00\x00'),

            # First CAN ID - first param: id, position and length
            (TX, b'\x40\x00\x31\x01\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x01\xE4\x07\x07\xF8'),

            # First CAN ID - first param: gain and offset
            (TX, b'\x40\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x02\xE8\x03\x00\x00'),

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

        assert msg.can_id == 0x103

        assert len(msg.params) == 1
        param = msg.params[0]

        assert param.param_id == 2020
        assert param.position == 7
        assert param.length == -8
        assert param.gain == 1.0
        assert param.offset == 0

    def test_list_tx_map_single_can_id_corrupt_param(self):
        # Manually synthesised CAN packets with the gain/offset fields not
        # provided
        self.data = [
            # First CAN ID
            (TX, b'\x40\x00\x31\x00\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x00\x01\x00\x00\x00'),

            # First CAN ID - first param: id, position and length
            (TX, b'\x40\x00\x31\x01\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x01\xE3\x07\x18\x08'),

            # First CAN ID - first param: gain and offset not-present
            (TX, b'\x40\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x80\x00\x31\x02\x00\x00\x02\x06'),

            # Second CAN ID - not-present
            (TX, b'\x40\x01\x31\x00\x00\x00\x00\x00'),
            (RX, b'\x80\x01\x31\x00\x00\x00\x02\x06')
        ]

        can_map = self.node.list_can_map(Direction.TX)

        assert len(can_map) == 0

    def test_list_tx_map_single_can_id_no_params(self):
        # Manually synthesised CAN packets with no param fields at all
        self.data = [
            # First CAN ID
            (TX, b'\x40\x00\x31\x00\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x00\x01\x00\x00\x00'),

            # First CAN ID - first param: id, position and length not-present
            (TX, b'\x40\x00\x31\x01\x00\x00\x00\x00'),
            (RX, b'\x80\x00\x31\x01\x00\x00\x02\x06'),

            # Second CAN ID - not-present
            (TX, b'\x40\x01\x31\x00\x00\x00\x00\x00'),
            (RX, b'\x80\x01\x31\x00\x00\x00\x02\x06')
        ]

        can_map = self.node.list_can_map(Direction.TX)

        assert len(can_map) == 0

    def test_list_tx_map_single_can_id_corrupt_second_param(self):
        # Synthesised CAN frame equivalent to the command:
        # oic can list
        # 0x101:
        # tx.0.0 param='tmphs' pos=24 length=8 gain=-1.0 offset=0
        self.data = [
            # First CAN ID
            (TX, b'\x40\x00\x31\x00\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x00\x01\x01\x00\x00'),

            # First CAN ID - first param: id, position and length
            (TX, b'\x40\x00\x31\x01\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x01\xE3\x07\x18\x08'),

            # First CAN ID - first param: gain and offset
            (TX, b'\x40\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x02\x18\xFC\xFF\x00'),

            # First CAN ID - second param: id, position and length
            (TX, b'\x40\x00\x31\x03\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x03\xE4\x07\x00\x08'),

            # First CAN ID - second param: gain and offset - not-present
            (TX, b'\x40\x00\x31\x04\x00\x00\x00\x00'),
            (RX, b'\x80\x00\x31\x04\x00\x00\x02\x06'),

            # Second CAN ID - not present
            (TX, b'\x40\x01\x31\x00\x00\x00\x00\x00'),
            (RX, b'\x80\x01\x31\x00\x00\x00\x02\x06'),
        ]

        can_map = self.node.list_can_map(Direction.TX)

        assert len(can_map) == 1
        msg = can_map[0]

        assert msg.can_id == 0x101

        assert len(msg.params) == 1

        param = msg.params[0]
        assert param.param_id == 2019
        assert param.position == 24
        assert param.length == 8
        assert param.gain == -1.0
        assert param.offset == 0

    def test_map_transmit_parameter_successfully(self):
        # from a capture of the command:
        # oic can add tx 0x101 tmpm 0 8 1.0 0
        self.data = [
            (TX, b'\x23\x00\x30\x00\x01\x01\x00\x00'),
            (RX, b'\x60\x00\x30\x00\x01\x01\x00\x00'),
            (TX, b'\x23\x00\x30\x01\xE3\x07\x00\x08'),
            (RX, b'\x60\x00\x30\x01\xE3\x07\x00\x08'),
            (TX, b'\x23\x00\x30\x02\xE8\x03\x00\x00'),
            (RX, b'\x60\x00\x30\x02\xE8\x03\x00\x00')
        ]
        tmphs = OIVariable("tmphs", 2019)
        self.node.add_can_map_entry(
            can_id=0x101,
            direction=Direction.TX,
            param_id=tmphs.id,
            position=0,
            length=8,
            gain=1.0,
            offset=0)

    def test_map_transmit_param_with_negative_unity_gain(self):
        # from a capture of the command:
        # oic can add tx 0x101 tmphs 24 8 -1.0 0
        self.data = [
            (TX, b'\x23\x00\x30\x00\x01\x01\x00\x00'),
            (RX, b'\x60\x00\x30\x00\x01\x01\x00\x00'),
            (TX, b'\x23\x00\x30\x01\xE3\x07\x18\x08'),
            (RX, b'\x60\x00\x30\x01\xE3\x07\x18\x08'),
            (TX, b'\x23\x00\x30\x02\x18\xFC\xFF\x00'),
            (RX, b'\x60\x00\x30\x02\x18\xFC\xFF\x00')
        ]
        tmphs = OIVariable("tmphs", 2019)
        self.node.add_can_map_entry(
            can_id=0x101,
            direction=Direction.TX,
            param_id=tmphs.id,
            position=24,
            length=8,
            gain=-1.0,
            offset=0)

    def test_map_transmit_parameter_max_negative_offset(self):
        # manually synthesised can packets
        self.data = [
            # can_id request
            (TX, b'\x23\x00\x30\x00\x01\x01\x00\x00'),
            (RX, b'\x60\x00\x30\x00\x01\x01\x00\x00'),

            # param, position and length request
            (TX, b'\x23\x00\x30\x01\xE3\x07\x00\x08'),
            (RX, b'\x60\x00\x30\x01\xE3\x07\x00\x08'),

            # gain and offset request
            (TX, b'\x23\x00\x30\x02\xE8\x03\x00\x80'),
            (RX, b'\x60\x00\x30\x02\xE8\x03\x00\x80')
        ]
        tmphs = OIVariable("tmphs", 2019)
        self.node.add_can_map_entry(
            can_id=0x101,
            direction=Direction.TX,
            param_id=tmphs.id,
            position=0,
            length=8,
            gain=1.0,
            offset=-128)

    def test_map_transmit_parameter_max_gain(self):
        # manually synthesised can packets
        self.data = [
            # can_id request
            (TX, b'\x23\x00\x30\x00\x01\x01\x00\x00'),
            (RX, b'\x60\x00\x30\x00\x01\x01\x00\x00'),

            # param, position and length request
            (TX, b'\x23\x00\x30\x01\xE3\x07\x00\x08'),
            (RX, b'\x60\x00\x30\x01\xE3\x07\x00\x08'),

            # gain and offset request
            (TX, b'\x23\x00\x30\x02\xff\xff\x7f\x00'),
            (RX, b'\x60\x00\x30\x02\xff\xff\x7f\x00')
        ]
        tmphs = OIVariable("tmphs", 2019)
        self.node.add_can_map_entry(
            can_id=0x101,
            direction=Direction.TX,
            param_id=tmphs.id,
            position=0,
            length=8,
            gain=8388.607,
            offset=0)

    def test_map_transmit_parameter_max_negative_gain(self):
        # manually synthesised can packets
        self.data = [
            # can_id request
            (TX, b'\x23\x00\x30\x00\x01\x01\x00\x00'),
            (RX, b'\x60\x00\x30\x00\x01\x01\x00\x00'),

            # param, position and length request
            (TX, b'\x23\x00\x30\x01\xE3\x07\x00\x08'),
            (RX, b'\x60\x00\x30\x01\xE3\x07\x00\x08'),

            # gain and offset request
            (TX, b'\x23\x00\x30\x02\x00\x00\x80\x00'),
            (RX, b'\x60\x00\x30\x02\x00\x00\x80\x00')
        ]
        tmphs = OIVariable("tmphs", 2019)
        self.node.add_can_map_entry(
            can_id=0x101,
            direction=Direction.TX,
            param_id=tmphs.id,
            position=0,
            length=8,
            gain=-8388.608,
            offset=0)

    def test_map_receive_max_all_arguments(self):
        # manually synthesised can packets
        self.data = [
            # can_id request
            (TX, b'\x23\x01\x30\x00\xff\x07\x00\x00'),
            (RX, b'\x60\x01\x30\x00\xff\x07\x00\x00'),

            # param, position and length request
            (TX, b'\x23\x01\x30\x01\xff\x7f\x3f\x20'),
            (RX, b'\x60\x01\x30\x01\xff\x7f\x3f\x20'),

            # gain and offset request
            (TX, b'\x23\x01\x30\x02\xff\xff\x7f\x7f'),
            (RX, b'\x60\x01\x30\x02\xff\xff\x7f\x7f')
        ]
        big_param = OIVariable("fiction", 32767)
        self.node.add_can_map_entry(
            can_id=0x7ff,
            direction=Direction.RX,
            param_id=big_param.id,
            position=63,
            length=32,
            gain=8388.607,
            offset=127)

    def test_map_transmit_big_endian_successfully(self):
        # Manually synthesized equivalent to the command:
        # oic can add tx 0x101 tmpm 7 -8 1.0 0
        self.data = [
            (TX, b'\x23\x00\x30\x00\x01\x01\x00\x00'),
            (RX, b'\x60\x00\x30\x00\x01\x01\x00\x00'),
            (TX, b'\x23\x00\x30\x01\xE3\x07\x07\xF8'),
            (RX, b'\x60\x00\x30\x01\xE3\x07\x07\xF8'),
            (TX, b'\x23\x00\x30\x02\xE8\x03\x00\x00'),
            (RX, b'\x60\x00\x30\x02\xE8\x03\x00\x00')
        ]
        tmphs = OIVariable("tmphs", 2019)
        self.node.add_can_map_entry(
            can_id=0x101,
            direction=Direction.TX,
            param_id=tmphs.id,
            position=7,
            length=-8,
            gain=1.0,
            offset=0)

    def test_map_transmit_zero_can_id(self):
        # Manually synthesized packets equivalent to:
        # oic can add tx 0 tmpm 0 8 1.0 0
        self.data = [
            (TX, b'\x23\x00\x30\x00\x00\x00\x00\x00'),
            (RX, b'\x60\x00\x30\x00\x00\x00\x00\x00'),
            (TX, b'\x23\x00\x30\x01\xE3\x07\x00\x08'),
            (RX, b'\x60\x00\x30\x01\xE3\x07\x00\x08'),
            (TX, b'\x23\x00\x30\x02\xE8\x03\x00\x00'),
            (RX, b'\x60\x00\x30\x02\xE8\x03\x00\x00')
        ]
        tmphs = OIVariable("tmphs", 2019)
        self.node.add_can_map_entry(
            can_id=0,
            direction=Direction.TX,
            param_id=tmphs.id,
            position=0,
            length=8,
            gain=1.0,
            offset=0)

    def test_map_param_out_of_range_can_id(self):
        self.data = []

        with self.assertRaises(ValueError):
            self.node.add_can_map_entry(
                can_id=0x800,
                direction=Direction.TX,
                param_id=1,
                position=0,
                length=8,
                gain=1.0,
                offset=0)

        with self.assertRaises(ValueError):
            self.node.add_can_map_entry(
                can_id=-1,
                direction=Direction.TX,
                param_id=1,
                position=0,
                length=8,
                gain=1.0,
                offset=0)

    def test_map_param_out_of_range_direction(self):
        self.data = []

        with self.assertRaises(ValueError):
            self.node.add_can_map_entry(
                can_id=0x101,
                direction=Direction(42),
                param_id=1,
                position=0,
                length=8,
                gain=1.0,
                offset=0)

    def test_map_param_out_of_range_position(self):
        self.data = []

        with self.assertRaises(ValueError):
            self.node.add_can_map_entry(
                can_id=0x101,
                direction=Direction.TX,
                param_id=1,
                position=-1,
                length=8,
                gain=1.0,
                offset=0)

        with self.assertRaises(ValueError):
            self.node.add_can_map_entry(
                can_id=0x101,
                direction=Direction.TX,
                param_id=1,
                position=64,
                length=8,
                gain=1.0,
                offset=0)

    def test_map_param_out_of_range_length(self):
        self.data = []

        with self.assertRaises(ValueError):
            self.node.add_can_map_entry(
                can_id=0x101,
                direction=Direction.TX,
                param_id=1,
                position=0,
                length=0,
                gain=1.0,
                offset=0)

        with self.assertRaises(ValueError):
            self.node.add_can_map_entry(
                can_id=0x101,
                direction=Direction.TX,
                param_id=1,
                position=0,
                length=33,
                gain=1.0,
                offset=0)

    def test_map_param_out_of_range_gain(self):
        self.data = []

        with self.assertRaises(ValueError):
            self.node.add_can_map_entry(
                can_id=0x101,
                direction=Direction.TX,
                param_id=1,
                position=0,
                length=8,
                gain=-10000.0,
                offset=0)

        with self.assertRaises(ValueError):
            self.node.add_can_map_entry(
                can_id=0x101,
                direction=Direction.TX,
                param_id=1,
                position=0,
                length=8,
                gain=10000.0,
                offset=0)

    def test_map_param_out_of_range_offset(self):
        self.data = []

        with self.assertRaises(ValueError):
            self.node.add_can_map_entry(
                can_id=0x101,
                direction=Direction.TX,
                param_id=1,
                position=0,
                length=8,
                gain=1.0,
                offset=-129)

        with self.assertRaises(ValueError):
            self.node.add_can_map_entry(
                can_id=0x101,
                direction=Direction.TX,
                param_id=1,
                position=0,
                length=8,
                gain=1.0,
                offset=128)

    def test_remove_first_mapped_param(self):
        # from a capture of the command:
        # oic can remove tx.0.0
        self.data = [
            (TX, b'\x23\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x23\x00\x31\x02\x00\x00\x00\x00')
        ]
        assert self.node.remove_can_map_entry(Direction.TX, 0, 0)

    def test_remove_fourth_param_from_second_can_messsage(self):
        # from a capture of the command:
        # oic can remove tx.1.3
        self.data = [
            (TX, b'\x23\x01\x31\x08\x00\x00\x00\x00'),
            (RX, b'\x23\x01\x31\x08\x00\x00\x00\x00')
        ]
        assert self.node.remove_can_map_entry(Direction.TX, 1, 3)

    def test_remove_not_present_rx_mapping(self):
        # from a capture of the command:
        # oic can remove rx.5.5
        # with no RX map defined
        self.data = [
            (TX, b'\x23\x85\x31\x0C\x00\x00\x00\x00'),
            (RX, b'\x80\x85\x31\x0C\x00\x00\x02\x06')
        ]
        assert not self.node.remove_can_map_entry(Direction.RX, 5, 5)

    def test_clear_map_tx_no_mappings_present(self):
        # From a capture of running:
        # oic can remove rx.0.0
        self.data = [
            (TX, b'\x23\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x80\x00\x31\x02\x00\x00\x02\x06')
        ]
        assert not self.node.clear_map(Direction.TX)

    def test_clear_map_tx_large_map(self):
        # From a capture of running:
        # oic can remove tx.0.0
        # until it reports "Unable to find CAN map entry."
        self.data = [
            (TX, b'\x23\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x23\x00\x31\x02\x00\x00\x00\x00'),
            (TX, b'\x23\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x23\x00\x31\x02\x00\x00\x00\x00'),
            (TX, b'\x23\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x23\x00\x31\x02\x00\x00\x00\x00'),
            (TX, b'\x23\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x23\x00\x31\x02\x00\x00\x00\x00'),
            (TX, b'\x23\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x23\x00\x31\x02\x00\x00\x00\x00'),
            (TX, b'\x23\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x23\x00\x31\x02\x00\x00\x00\x00'),
            (TX, b'\x23\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x80\x00\x31\x02\x00\x00\x02\x06')
        ]
        assert not self.node.clear_map(Direction.TX)

    def test_clear_map_rx_single_message_single_param_map(self):
        # From a capture of running:
        # oic can remove rx.0.0
        # until it reports "Unable to find CAN map entry."
        self.data = [
            (TX, b'\x23\x80\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x23\x80\x31\x02\x00\x00\x00\x00'),
            (TX, b'\x23\x80\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x80\x80\x31\x02\x00\x00\x02\x06')
        ]
        assert not self.node.clear_map(Direction.RX)

    def test_add_multiple_messages_in_a_single_map(self):
        # Captured from running the command sequence:
        # oic can add tx 0x101 tmpm 0 8 little 1.0 0
        # oic can add tx 0x102 tmphs 32 32 little 2.0 0
        self.data = [
            (TX, b'\x23\x00\x30\x00\x01\x01\x00\x00'),
            (RX, b'\x60\x00\x30\x00\x01\x01\x00\x00'),
            (TX, b'\x23\x00\x30\x01\xE4\x07\x00\x08'),
            (RX, b'\x60\x00\x30\x01\xE4\x07\x00\x08'),
            (TX, b'\x23\x00\x30\x02\xE8\x03\x00\x00'),
            (RX, b'\x60\x00\x30\x02\xE8\x03\x00\x00'),
            (TX, b'\x23\x00\x30\x00\x02\x01\x00\x00'),
            (RX, b'\x60\x00\x30\x00\x02\x01\x00\x00'),
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
                params=[MapEntry(tmpm.id, 0, 8,  1.0, 0)]
            ),
            CanMessage(
                can_id=0x102,
                params=[MapEntry(tmphs.id, 32, 32, 2.0, 0)]
            )
        ]

        self.node.add_can_map(Direction.TX, msg_map)

        if __name__ == "__main__":
            unittest.main()
