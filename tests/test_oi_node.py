"""OpenInverter custom SDO protocol unit tests"""

import unittest
from datetime import timedelta

import canopen

from openinverter_can_tool import constants as oi
from openinverter_can_tool.oi_node import (CanMessage, Direction, MapEntry,
                                           OpenInverterNode)
from openinverter_can_tool.paramdb import OIVariable

from .network_test_case import NetworkTestCase

TX = 1
RX = 2

# Reduce test verbosity
# pylint: disable=missing-function-docstring, too-many-lines


class TestOpenInverterNode(NetworkTestCase):
    """
    Test the custom OpenInverter node protocol by example
    """

    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        self._node_type = OpenInverterNode

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
        assert not msg.is_extended_frame

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

    def test_list_tx_map_single_can_id_failed_to_get_id(self):
        # Manually synthesised can packets
        self.data = [
            # First CAN ID
            # General Failure
            (TX, b'\x40\x00\x31\x00\x00\x00\x00\x00'),
            (RX, b'\x80\x00\x31\x00\x00\x00\x00\x08'),
        ]

        with self.assertRaises(canopen.SdoAbortedError) as cm:
            self.node.list_can_map(Direction.TX)

        assert cm.exception.code == oi.SDO_ABORT_GENERAL_FAILURE

    def test_list_tx_map_single_can_id_failed_first_param_id(self):
        # Manually synthesised can packets
        self.data = [
            # First CAN ID
            (TX, b'\x40\x00\x31\x00\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x00\x01\x01\x00\x00'),

            # First CAN ID - first param: id, position and length
            # General Failure
            (TX, b'\x40\x00\x31\x01\x00\x00\x00\x00'),
            (RX, b'\x80\x00\x31\x01\x00\x00\x00\x08'),
        ]

        with self.assertRaises(canopen.SdoAbortedError) as cm:
            self.node.list_can_map(Direction.TX)

        assert cm.exception.code == oi.SDO_ABORT_GENERAL_FAILURE

    def test_list_tx_map_single_can_id_failed_first_param_gain(self):
        # Manually synthesised can packets
        self.data = [
            # First CAN ID
            (TX, b'\x40\x00\x31\x00\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x00\x01\x01\x00\x00'),

            # First CAN ID - first param: id, position and length
            (TX, b'\x40\x00\x31\x01\x00\x00\x00\x00'),
            (RX, b'\x43\x00\x31\x01\xE3\x07\x18\x08'),

            # First CAN ID - first param: gain and offset
            # General Failure
            (TX, b'\x40\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x80\x00\x31\x02\x00\x00\x00\x08'),
        ]

        with self.assertRaises(canopen.SdoAbortedError) as cm:
            self.node.list_can_map(Direction.TX)

        assert cm.exception.code == oi.SDO_ABORT_GENERAL_FAILURE

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
            (RX, b'\x60\x00\x31\x02\x00\x00\x00\x00')
        ]
        assert self.node.remove_can_map_entry(Direction.TX, 0, 0)

    def test_remove_fourth_param_from_second_can_messsage(self):
        # from a capture of the command:
        # oic can remove tx.1.3
        self.data = [
            (TX, b'\x23\x01\x31\x08\x00\x00\x00\x00'),
            (RX, b'\x60\x01\x31\x08\x00\x00\x00\x00')
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

    def test_remove_general_failure(self):
        # Manually synthesised can packets equivalent to a general failure
        # running:
        # oic can remove rx.5.5
        self.data = [
            (TX, b'\x23\x85\x31\x0C\x00\x00\x00\x00'),
            (RX, b'\x80\x85\x31\x0C\x00\x00\x00\x08')
        ]
        with self.assertRaises(canopen.SdoAbortedError) as cm:
            self.node.remove_can_map_entry(Direction.RX, 5, 5)

        assert cm.exception.code == oi.SDO_ABORT_GENERAL_FAILURE

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
            (RX, b'\x60\x00\x31\x02\x00\x00\x00\x00'),
            (TX, b'\x23\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x60\x00\x31\x02\x00\x00\x00\x00'),
            (TX, b'\x23\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x60\x00\x31\x02\x00\x00\x00\x00'),
            (TX, b'\x23\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x60\x00\x31\x02\x00\x00\x00\x00'),
            (TX, b'\x23\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x60\x00\x31\x02\x00\x00\x00\x00'),
            (TX, b'\x23\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x60\x00\x31\x02\x00\x00\x00\x00'),
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
            (RX, b'\x60\x80\x31\x02\x00\x00\x00\x00'),
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

    def test_remove_first_mapped_param_faulty_libopeninv(self):
        # from a capture of the command:
        # oic can remove tx.0.0
        # The response from the node is not compliant with the expected SDO
        # reply but should still succeed. This will generate an SDO Abort
        # frame which is ignored by the device.
        self.data = [
            (TX, b'\x23\x00\x31\x02\x00\x00\x00\x00'),
            (RX, b'\x20\x00\x31\x02\x00\x00\x00\x00'),
            (TX, b'\x80\x00\x00\x00\x01\x00\x04\x05')  # SDO Abort
        ]
        assert self.node.remove_can_map_entry(Direction.TX, 0, 0)

    def test_list_errors_on_device_that_does_not_know_how_to(self):
        self.data = [
            (TX, b'\x40\x04\x50\x00\x00\x00\x00\x00'),
            (RX, b'\x80\x00\x00\x00\x00\x00\x06\x02')  # SDO Abort
        ]

        with self.assertRaises(canopen.SdoAbortedError) as cm:
            _ = self.node.list_errors()
            assert cm.exception.code == oi.SDO_ABORT_OBJECT_NOT_AVAILABLE

    def test_list_errors_on_happy_device(self):
        self.data = [
            (TX, b'\x40\x04\x50\x00\x00\x00\x00\x00'),
            (RX, b'\x43\x04\x50\x00\x00\x00\x00\x00')
        ]
        errors = self.node.list_errors()
        assert len(errors) == 0

    def test_list_a_single_unknown_device_error(self):
        self.data = [
            # Error at 100 ticks (or 1 second with 10ms tick)
            (TX, b'\x40\x04\x50\x00\x00\x00\x00\x00'),
            (RX, b'\x43\x04\x50\x00\x64\x00\x00\x00'),

            # Error number "42"
            (TX, b'\x40\x03\x50\x00\x00\x00\x00\x00'),
            (RX, b'\x43\x03\x50\x00\x2a\x00\x00\x00'),

            # No more errors
            (TX, b'\x40\x04\x50\x01\x00\x00\x00\x00'),
            (RX, b'\x43\x04\x50\x01\x00\x00\x00\x00'),
        ]

        errors = self.node.list_errors()

        assert errors == [(timedelta(seconds=1), "Unknown error 42")]

    def test_list_a_single_error(self):
        self.data = [
            # Error at 0x12345678 ticks
            (TX, b'\x40\x04\x50\x00\x00\x00\x00\x00'),
            (RX, b'\x43\x04\x50\x00\x78\x56\x34\x12'),

            # Error number "66"
            (TX, b'\x40\x03\x50\x00\x00\x00\x00\x00'),
            (RX, b'\x43\x03\x50\x00\x42\x00\x00\x00'),

            # No more errors
            (TX, b'\x40\x04\x50\x01\x00\x00\x00\x00'),
            (RX, b'\x43\x04\x50\x01\x00\x00\x00\x00'),
        ]
        lasterr = OIVariable("lasterr", 2038)
        lasterr.value_descriptions = {66: "Ninety_nine_are_you_in_trouble"}
        self.node.object_dictionary.add_object(lasterr)

        errors = self.node.list_errors()

        assert errors == [
            (timedelta(days=35,
                       hours=8,
                       minutes=23,
                       seconds=18,
                       milliseconds=960),
             "Ninety_nine_are_you_in_trouble")
        ]

    def test_list_several_errors(self):
        self.data = [
            # Error at 1 ticks
            (TX, b'\x40\x04\x50\x00\x00\x00\x00\x00'),
            (RX, b'\x43\x04\x50\x00\x01\x00\x00\x00'),

            # Error number 11
            (TX, b'\x40\x03\x50\x00\x00\x00\x00\x00'),
            (RX, b'\x43\x03\x50\x00\x0B\x00\x00\x00'),

            # Error at 2 ticks
            (TX, b'\x40\x04\x50\x01\x00\x00\x00\x00'),
            (RX, b'\x43\x04\x50\x01\x02\x00\x00\x00'),

            # Error number 22
            (TX, b'\x40\x03\x50\x01\x00\x00\x00\x00'),
            (RX, b'\x43\x03\x50\x01\x16\x00\x00\x00'),

            # Error at 3 ticks
            (TX, b'\x40\x04\x50\x02\x00\x00\x00\x00'),
            (RX, b'\x43\x04\x50\x02\x03\x00\x00\x00'),

            # Error number 33
            (TX, b'\x40\x03\x50\x02\x00\x00\x00\x00'),
            (RX, b'\x43\x03\x50\x02\x21\x00\x00\x00'),

            # No more errors
            (TX, b'\x40\x04\x50\x03\x00\x00\x00\x00'),
            (RX, b'\x43\x04\x50\x03\x00\x00\x00\x00'),
        ]
        lasterr = OIVariable("lasterr", 2038)
        lasterr.value_descriptions = {
            11: "Eleven",
            22: "TwentyTwo",
            33: "ThirtyThree"
        }
        self.node.object_dictionary.add_object(lasterr)

        errors = self.node.list_errors()

        assert errors == [
            (timedelta(milliseconds=10), "Eleven"),
            (timedelta(milliseconds=20), "TwentyTwo"),
            (timedelta(milliseconds=30), "ThirtyThree"),
        ]

    def test_list_a_single_error_on_a_system_with_1_sec_ticks(self):
        self.data = [
            # Error at 3600 ticks (1 hour with 1 second tick)
            (TX, b'\x40\x04\x50\x00\x00\x00\x00\x00'),
            (RX, b'\x43\x04\x50\x00\x10\x0E\x00\x00'),

            # Error number "66"
            (TX, b'\x40\x03\x50\x00\x00\x00\x00\x00'),
            (RX, b'\x43\x03\x50\x00\x42\x00\x00\x00'),

            # No more errors
            (TX, b'\x40\x04\x50\x01\x00\x00\x00\x00'),
            (RX, b'\x43\x04\x50\x01\x00\x00\x00\x00'),
        ]
        lasterr = OIVariable("lasterr", 2038)
        lasterr.value_descriptions = {66: "Ninety_nine_are_you_in_trouble"}
        self.node.object_dictionary.add_object(lasterr)

        uptime = OIVariable("uptime", 2054)
        uptime.unit = "sec"
        self.node.object_dictionary.add_object(uptime)

        errors = self.node.list_errors()

        assert errors == [
            (timedelta(hours=1),
             "Ninety_nine_are_you_in_trouble")
        ]


if __name__ == "__main__":
    unittest.main()
