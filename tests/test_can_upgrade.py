"""Test cases relating to CAN upgrade of devices"""

import csv
import unittest
from pathlib import Path
from typing import List, Tuple

import canopen
import pytest

from openinverter_can_tool.can_upgrade import (CanUpgrader, CheckCrcState,
                                               CompleteState, Failure,
                                               FailureState, HeaderState,
                                               StartState, UploadState)

TOOL = 0x7DD
DEVICE = 0x7DE

UPGRADE_DATA_DIR = Path(__file__).parent / "test_data" / "upgrade"

EMPTY_FIRMWARE = UPGRADE_DATA_DIR / "empty-firmware.bin"
MINIMAL_FIRMWARE = UPGRADE_DATA_DIR / "minimal-firmware.bin"
ONE_PAGE_FIRMWARE = UPGRADE_DATA_DIR / "one-page-firmware.bin"
TWO_PAGE_FIRMWARE = UPGRADE_DATA_DIR / "two-page-firmware.bin"

# Reduce test verbosity
# pylint: disable=missing-function-docstring


class TestFirmwareLoading:
    """Firmware loading specific tests that don't need a CAN network"""

    def test_non_existent_firmware_file_fails_to_initialise(self):
        with pytest.raises(FileNotFoundError):
            CanUpgrader(
                canopen.Network(),
                None,
                UPGRADE_DATA_DIR / "non-existent-file.bin")

    def test_sub_page_firmware_reports_page_count_of_one(self, tmp_path: Path):
        firmware = tmp_path / "firmware.bin"
        with open(firmware, "wb") as f:
            f.write(bytes(1023))

        upgrader = CanUpgrader(canopen.Network(), None, firmware)

        assert len(upgrader.pages) == 1

    def test_exact_page_size_firmware_reports_integer_page(
            self, tmp_path: Path):
        firmware = tmp_path / "firmware.bin"
        with open(firmware, "wb") as f:
            f.write(bytes(4096))

        upgrader = CanUpgrader(canopen.Network(), None, firmware)

        assert len(upgrader.pages) == 4

    def test_max_size_firmware_successfully_loads(
            self, tmp_path: Path):
        firmware = tmp_path / "firmware.bin"
        with open(firmware, "wb") as f:
            f.write(bytes(255*1024))

        upgrader = CanUpgrader(canopen.Network(), None, firmware)

        assert len(upgrader.pages) == 255

    def test_over_max_size_firmware_fails_to_load(
            self, tmp_path: Path):
        firmware = tmp_path / "firmware.bin"
        with open(firmware, "wb") as f:
            f.write(bytes(255*1024+1))

        with pytest.raises(ValueError, match="Firmware image too large"):
            CanUpgrader(canopen.Network(), None, firmware)

    def test_firmware_contents_are_padded_to_page_size_with_zeros(self):
        upgrader = CanUpgrader(canopen.Network(), None, MINIMAL_FIRMWARE)

        assert len(upgrader.pages) == 1
        assert upgrader.pages[0].data[0] == 0xa5
        assert upgrader.pages[0].data[1] == 0
        assert upgrader.pages[0].data[1023] == 0

    def test_firmware_with_exact_size_has_no_padding(self):
        upgrader = CanUpgrader(canopen.Network(), None, TWO_PAGE_FIRMWARE)

        assert len(upgrader.pages) == 2
        assert upgrader.pages[0].data[0] == 0x55
        assert upgrader.pages[1].data[1023] == 0xaa

    def test_minimal_firmware_crc_is_the_same_as_stm32_bootloader(self):
        upgrader = CanUpgrader(canopen.Network(), None, MINIMAL_FIRMWARE)

        # From a CAN capture of can-upgrader.py loading this firmware to
        # a real device
        assert upgrader.pages[0].crc == 0xF1B78CE3

    def test_one_page_firmware_crc_is_the_same_as_stm32_bootloader(self):
        upgrader = CanUpgrader(canopen.Network(), None, ONE_PAGE_FIRMWARE)

        # From a CAN capture of can-upgrader.py loading this firmware to
        # a real device
        assert upgrader.pages[0].crc == 0x8ADA4578

    def test_two_page_firmware_crc_is_the_same_as_stm32_bootloader(self):
        upgrader = CanUpgrader(canopen.Network(), None, TWO_PAGE_FIRMWARE)

        # From a CAN capture of can-upgrader.py loading this firmware to
        # a real device
        assert upgrader.pages[0].crc == 0x41B309C3
        assert upgrader.pages[1].crc == 0x1AB9F829


class TestCANUpgrade(unittest.TestCase):
    """
    Test the CAN upgrade state machine by example
    """

    def _send_message(self, can_id, data, remote=False):
        """Will be used instead of the usual Network.send_message method.

        Checks that the message data is as expected.
        """
        next_data = self.data.pop(0)
        self.assertEqual(next_data[0], TOOL, "No transmission was expected")
        self.assertSequenceEqual(data, next_data[1])
        self.assertEqual(can_id, TOOL)

        # pretend to use remote
        _ = remote

    def setUp(self):
        network = canopen.Network()
        network.send_message = self._send_message
        self.network = network
        self.data: List[Tuple[int, bytes]] = []

    def tearDown(self) -> None:
        # At the end of every test all of the data data should have been
        # consumed by _send_message()
        assert len(self.data) == 0

    def send_device_frames(self) -> None:
        """Send the CAN frames from the device(s). Replies are processed
        through the _send_message() hook"""
        while self.data and self.data[0][0] == DEVICE:
            self.network.notify(DEVICE, bytearray(self.data.pop(0)[1]), 0.0)

    def load_capture(self, capture: str) -> None:
        """Load a CAN capture from SavvyCAN in CSV format into the data"""
        with open(UPGRADE_DATA_DIR / capture,
                  newline="", encoding="utf-8") as capture_file:
            reader = csv.DictReader(capture_file)

            for row in reader:
                frame_id = int(row["ID"], 16)

                frame = ""
                for i in range(int(row["LEN"])):
                    frame += row[f"D{i+1}"]

                self.data.append((frame_id, bytes.fromhex(frame)))

    def test_unknown_device_is_ignored(self):
        self.data = [
            (DEVICE, b'\x33\x00\x00\x00\x29\x30\x19\x87')
        ]

        upgrader = CanUpgrader(self.network,
                               b"\x12\x34\x56\x78",
                               EMPTY_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, StartState)
        assert upgrader.serialno is None

    def test_recognise_specific_device_and_start_upgrade_process(self):
        self.data = [
            (DEVICE, b'\x33\x00\x00\x00\x29\x30\x19\x87'),
            (TOOL, b'\x29\x30\x19\x87')
        ]

        upgrader = CanUpgrader(self.network,
                               b"\x87\x19\x30\x29",
                               EMPTY_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, HeaderState)
        assert upgrader.serialno == b"\x87\x19\x30\x29"

    def test_ignore_reserved_bytes_and_start_upgrade_process(self):
        self.data = [
            # Note: bytes 1, 2 and 3 have data in them rather than zero
            (DEVICE, b'\x33\x12\x34\x56\x29\x30\x19\x87'),
            (TOOL, b'\x29\x30\x19\x87')
        ]

        upgrader = CanUpgrader(self.network,
                               b"\x87\x19\x30\x29",
                               EMPTY_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, HeaderState)
        assert upgrader.serialno == b"\x87\x19\x30\x29"

    def test_start_to_recover_the_next_device_to_boot(self):
        self.data = [
            (DEVICE, b'\x33\x00\x00\x00\x29\x30\x19\x87'),
            (TOOL, b'\x29\x30\x19\x87')
        ]

        upgrader = CanUpgrader(self.network, None, EMPTY_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, HeaderState)
        assert upgrader.serialno == b"\x87\x19\x30\x29"

    def test_recognise_device_in_herd_and_start_upgrade_process(self):
        self.data = [
            (DEVICE, b'\x33\x00\x00\x00\x78\x56\x34\x12'),
            (DEVICE, b'\x33\x00\x00\x00\x29\x30\x19\x87'),
            (TOOL, b'\x29\x30\x19\x87'),
            (DEVICE, b'\x33\x00\x00\x00\x12\x34\x56\x78')
        ]
        upgrader = CanUpgrader(self.network,
                               b"\x87\x19\x30\x29",
                               EMPTY_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, HeaderState)
        assert upgrader.serialno == b"\x87\x19\x30\x29"

    def test_zero_length_data_in_hello_frame_triggers_error_state(self):
        self.data = [(DEVICE, b'')]

        upgrader = CanUpgrader(self.network, None, EMPTY_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, FailureState)
        assert upgrader.state.failure == Failure.PROTOCOL_ERROR

    def test_random_data_in_hello_frame_triggers_error_state(self):
        self.data = [(DEVICE, b'\x12\x34\x56')]

        upgrader = CanUpgrader(self.network, None, EMPTY_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, FailureState)
        assert upgrader.state.failure == Failure.PROTOCOL_ERROR

    def test_unusually_short_hello_header_triggers_error_state(self):
        self.data = [(DEVICE, b'\x33')]

        upgrader = CanUpgrader(self.network, None, EMPTY_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, FailureState)
        assert upgrader.state.failure == Failure.PROTOCOL_ERROR

    def test_start_frame_indicates_upgrade_in_progress_error(self):
        self.data = [(DEVICE, b'\x53')]

        upgrader = CanUpgrader(self.network, None, EMPTY_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, FailureState)
        assert upgrader.state.failure == Failure.UPGRADE_IN_PROGRESS

    def test_page_frame_indicates_upgrade_in_progress_error(self):
        self.data = [(DEVICE, b'\x50')]

        upgrader = CanUpgrader(self.network, None, EMPTY_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, FailureState)
        assert upgrader.state.failure == Failure.UPGRADE_IN_PROGRESS

    def test_checksum_frame_indicates_upgrade_in_progress_error(self):
        self.data = [(DEVICE, b'\x43')]

        upgrader = CanUpgrader(self.network, None, EMPTY_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, FailureState)
        assert upgrader.state.failure == Failure.UPGRADE_IN_PROGRESS

    def test_done_frame_indicates_upgrade_in_progress_error(self):
        self.data = [(DEVICE, b'\x44')]

        upgrader = CanUpgrader(self.network, None, EMPTY_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, FailureState)
        assert upgrader.state.failure == Failure.UPGRADE_IN_PROGRESS

    def test_specific_device_reports_that_it_has_started(self):
        self.data = [
            (DEVICE, b'\x33\x00\x00\x00\x29\x30\x19\x87'),
            (TOOL, b'\x29\x30\x19\x87'),
            (DEVICE, b'S'),
            (TOOL, b'\x01')
        ]

        upgrader = CanUpgrader(self.network, None, MINIMAL_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, UploadState)

    def test_another_device_starting_during_start_request_is_ignored(self):
        self.data = [
            (DEVICE, b'\x33\x00\x00\x00\x29\x30\x19\x87'),
            (TOOL, b'\x29\x30\x19\x87'),
            (DEVICE, b'\x33\x00\x00\x00\x12\x34\x56\x78'),  # Extra HELLO
            (DEVICE, b'S'),
            (TOOL, b'\x01')
        ]

        upgrader = CanUpgrader(self.network, None, MINIMAL_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, UploadState)

    def test_device_send_empty_frame_instead_of_size_request(self):
        self.data = [
            (DEVICE, b'\x33\x00\x00\x00\x29\x30\x19\x87'),
            (TOOL, b'\x29\x30\x19\x87'),
            (DEVICE, b'')  # This is an invalid response from the device
        ]

        upgrader = CanUpgrader(self.network, None, MINIMAL_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, FailureState)
        assert upgrader.state.failure == Failure.PROTOCOL_ERROR

    def test_device_receives_first_8_bytes_of_firmware(self):
        self.data = [
            (DEVICE, b'\x33\x00\x00\x00\x29\x30\x19\x87'),
            (TOOL, b'\x29\x30\x19\x87'),
            (DEVICE, b'S'),
            (TOOL, b'\x01'),
            (DEVICE, b'P'),
            (TOOL, b'\xa5\x00\x00\x00\x00\x00\x00\x00')
        ]

        upgrader = CanUpgrader(self.network, None, MINIMAL_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, UploadState)

    def test_another_device_starting_during_page_request_is_ignored(self):
        self.data = [
            (DEVICE, b'\x33\x00\x00\x00\x29\x30\x19\x87'),
            (TOOL, b'\x29\x30\x19\x87'),
            (DEVICE, b'S'),
            (TOOL, b'\x01'),
            (DEVICE, b'\x33\x00\x00\x00\x12\x34\x56\x78'),  # Extra HELLO
            (DEVICE, b'P'),
            (TOOL, b'\xa5\x00\x00\x00\x00\x00\x00\x00')
        ]

        upgrader = CanUpgrader(self.network, None, MINIMAL_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, UploadState)

    def test_device_sends_empty_frame_instead_of_page_request(self):
        self.data = [
            (DEVICE, b'\x33\x00\x00\x00\x29\x30\x19\x87'),
            (TOOL, b'\x29\x30\x19\x87'),
            (DEVICE, b'S'),
            (TOOL, b'\x01'),
            (DEVICE, b'')  # This is an invalid response from the device
        ]

        upgrader = CanUpgrader(self.network, None, MINIMAL_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, FailureState)
        assert upgrader.state.failure == Failure.PROTOCOL_ERROR

    def test_device_sends_extra_data_in_page_request(self):
        self.data = [
            (DEVICE, b'\x33\x00\x00\x00\x29\x30\x19\x87'),
            (TOOL, b'\x29\x30\x19\x87'),
            (DEVICE, b'S'),
            (TOOL, b'\x01'),
            # This is unexpected so probably indicates a new incompatible
            # protocol we can't be expected to deal with
            (DEVICE, b'P\xaa')
        ]

        upgrader = CanUpgrader(self.network, None, MINIMAL_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, FailureState)
        assert upgrader.state.failure == Failure.PROTOCOL_ERROR

    def test_device_receives_complete_page_of_firmware(self):
        self.load_capture("minimal-firmware-upload-page.csv")

        upgrader = CanUpgrader(self.network, None, MINIMAL_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, CheckCrcState)

    def test_device_receives_an_extra_page_data_request_which_fails(self):
        self.load_capture("minimal-firmware-over-request-page-data.csv")

        upgrader = CanUpgrader(self.network, None, MINIMAL_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, FailureState)
        assert upgrader.state.failure == Failure.PROTOCOL_ERROR

    def test_device_receives_crc_request_earlier_than_expected(self):
        self.load_capture("minimal-firmware-early-crc-request.csv")

        upgrader = CanUpgrader(self.network, None, MINIMAL_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, FailureState)
        assert upgrader.state.failure == Failure.PROTOCOL_ERROR

    def test_device_receives_page_of_firmware_but_fails_crc_check(self):
        self.load_capture("minimal-firmware-invalid-page-crc.csv")

        upgrader = CanUpgrader(self.network, None, MINIMAL_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, FailureState)
        assert upgrader.state.failure == Failure.PAGE_CRC_ERROR

    def test_device_completes_minimal_firmware_upgrade(self):
        self.load_capture("minimal-firmware.csv")

        upgrader = CanUpgrader(self.network, None, MINIMAL_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, CompleteState)

    def test_another_device_starting_during_checksum_request_is_ignored(self):
        self.load_capture("minimal-firmware-crc-extra-hello.csv")

        upgrader = CanUpgrader(self.network, None, MINIMAL_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, CompleteState)

    def test_another_device_starting_during_done_request_is_ignored(self):
        self.load_capture("minimal-firmware-done-extra-hello.csv")

        upgrader = CanUpgrader(self.network, None, MINIMAL_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, CompleteState)

    def test_successful_upgrade_of_device_with_one_page_firmware(self):
        self.load_capture("successful-one-page-upgrade.csv")

        upgrader = CanUpgrader(self.network, None, ONE_PAGE_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, CompleteState)

    def test_successful_upgrade_of_device_with_two_page_firmware(self):
        self.load_capture("successful-two-page-upgrade.csv")

        upgrader = CanUpgrader(self.network, None, TWO_PAGE_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, CompleteState)

    def test_zero_length_firmware_succeeds_and_sends_no_pages(self):
        self.data = [
            (DEVICE, b'\x33\x00\x00\x00\x29\x30\x19\x87'),
            (TOOL, b'\x29\x30\x19\x87'),
            (DEVICE, b'S'),
            (TOOL, b'\x00'),
            (DEVICE, b'D'),
        ]

        upgrader = CanUpgrader(self.network, None, EMPTY_FIRMWARE)

        self.send_device_frames()

        assert isinstance(upgrader.state, CompleteState)
