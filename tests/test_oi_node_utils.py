"""
OpenInverter custom SDO protocol unit tests
Utility structure tests
"""

import unittest

from openinverter_can_tool.oi_node import CanMessage, MapEntry

# Reduce test verbosity
# pylint: disable=missing-function-docstring


class TestCanMessages(unittest.TestCase):
    """Verify the creation of CanMessage instances"""

    def test_can_message_with_negative_can_id_fails(self):
        with self.assertRaises(ValueError):
            CanMessage(-1, [], False)

    def test_can_message_with_too_big_standard_can_id_fails(self):
        with self.assertRaises(ValueError):
            CanMessage(0x800, [], False)

    def test_can_message_with_too_big_extended_can_id_fails(self):
        with self.assertRaises(ValueError):
            CanMessage(0x20000000, [], True)

    def test_can_message_with_zero_can_id_is_allowed(self):
        msg = CanMessage(0, [], False)
        assert msg.can_id == 0
        assert not msg.is_extended_frame

    def test_can_message_with_extended_can_id_is_allowed(self):
        msg = CanMessage(0x12345678, [], True)
        assert msg.can_id == 0x12345678
        assert msg.is_extended_frame

    def test_can_message_compared_with_invalid_type_reports_false(self):
        msg = CanMessage(0x123, [])
        assert msg != str()


class TestMapEntry(unittest.TestCase):
    """Verify the creation of MapEntry instances"""

    def test_map_entry_with_negative_position_fails(self):
        with self.assertRaises(ValueError):
            MapEntry(
                param_id=1,
                position=-1,
                length=1,
                gain=1,
                offset=0
            )

    def test_map_entry_with_position_beyond_frame_length_fails(self):
        with self.assertRaises(ValueError):
            MapEntry(
                param_id=1,
                position=64,
                length=1,
                gain=1,
                offset=0
            )

    def test_map_entry_with_zero_length_fails(self):
        with self.assertRaises(ValueError):
            MapEntry(
                param_id=1,
                position=0,
                length=0,
                gain=1,
                offset=0
            )

    def test_map_entry_with_length_larger_than_32_bit_word_fails(self):
        with self.assertRaises(ValueError):
            MapEntry(
                param_id=1,
                position=0,
                length=33,
                gain=1,
                offset=0
            )

    def test_map_entry_with_excessive_positive_gain_fails(self):
        with self.assertRaises(ValueError):
            MapEntry(
                param_id=1,
                position=0,
                length=1,
                gain=10000.0,
                offset=0
            )

    def test_map_entry_with_excessive_negative_gain_fails(self):
        with self.assertRaises(ValueError):
            MapEntry(
                param_id=1,
                position=0,
                length=1,
                gain=-10000.0,
                offset=0
            )

    def test_map_entry_with_excessive_positive_offset_fails(self):
        with self.assertRaises(ValueError):
            MapEntry(
                param_id=1,
                position=0,
                length=1,
                gain=1,
                offset=128
            )

    def test_map_entry_with_excessive_negative_offset_fails(self):
        with self.assertRaises(ValueError):
            MapEntry(
                param_id=1,
                position=0,
                length=1,
                gain=1,
                offset=-129
            )

    def test_map_entry_compared_with_invalid_type_reports_false(self):
        map_entry = MapEntry(
            param_id=1,
            position=0,
            length=1,
            gain=1,
            offset=0
        )

        assert map_entry != str()


if __name__ == "__main__":
    unittest.main()
