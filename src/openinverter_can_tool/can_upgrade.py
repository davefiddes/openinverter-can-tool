"""openinverter CAN upgrade module"""

from __future__ import annotations

import array
import struct
from abc import ABC, abstractmethod
from enum import IntEnum
from pathlib import Path
from typing import List, Optional

import canopen

DEVICE_CAN_ID = 0x7DE
UPGRADER_CAN_ID = 0x7DD

PAGE_SIZE = 1024

MAX_PAGES = 255  # Most we can fit in the single-byte response to 'S'


class DevicePacket(IntEnum):
    """Different upgrade packet signatures sent by devices"""
    HELLO = 0x33  # '3'
    START = 0x53  # 'S'
    PAGE = 0x50   # 'P'
    CRC = 0x43    # 'C'
    DONE = 0x44   # 'D'
    ERROR = 0x45  # 'E'


def stm_crc(data: bytes):
    """
    Compute the CRC-32 expected by the stm32-CANBootloader firmware.

    This requires:
     - mapping the data to little-endian unsigned integers
     - Using the CRC-32/MPEG-2 with:
       - width=32
       - poly=0x04c11db7
       - init=0xffffffff
       - refin=false
       - refout=false
    """

    crc = 0xffffffff
    data_array = array.array("I", data)
    for word in data_array:
        crc = crc ^ word

        for _ in range(32):
            if crc & 0x80000000:
                # Polynomial used in STM32
                crc = ((crc << 1) ^ 0x04C11DB7) & 0xffffffff
            else:
                crc = (crc << 1) & 0xffffffff
    return crc


class Page:
    """A firmware page"""

    def __init__(self, data: bytes) -> None:
        assert len(data) <= PAGE_SIZE

        self.data = data
        padding = PAGE_SIZE - len(data) % PAGE_SIZE
        if padding != PAGE_SIZE:
            self.data += bytes(padding)

        self.crc = stm_crc(self.data)


class CanUpgrader:

    """Class to manage upgrading the firmware of open inverter devices over a
    CAN bus connection"""

    _state: State

    def __init__(
            self,
            network: canopen.Network,
            serialno: Optional[bytes],
            firmware: Path) -> None:
        self._network = network
        self._target_serialno = serialno
        self._serialno: Optional[bytes] = None
        self._pages: List[Page] = []

        with open(firmware, "rb") as firmware_file:
            while True:
                data = firmware_file.read(PAGE_SIZE)

                if data:
                    self.pages.append(Page(data))
                    if len(self.pages) > MAX_PAGES:
                        raise ValueError("Firmware image too large")
                else:
                    break

        self._current_page = 0

        self.transition_to(StartState())

        network.subscribe(DEVICE_CAN_ID, self.process)

    def transition_to(self, state: State) -> None:
        """
        Allow states to transition to a new state
        """
        self._state = state
        self._state.upgrader = self

    @property
    def state(self) -> State:
        """Retrieve the current state of the upgrade process"""
        return self._state

    @property
    def serialno(self) -> Optional[bytes]:
        """Retrieve the serial number of the current device being upgraded"""
        return self._serialno

    @serialno.setter
    def serialno(self, serialno: bytes) -> None:
        self._serialno = serialno

    @property
    def target_serialno(self) -> Optional[bytes]:
        """
        Retrieve the target serial number the upgrade process is directed
        towards
        """
        return self._target_serialno

    @property
    def pages(self) -> List[Page]:
        """The list of loaded firmware pages to be uploaded to the device"""
        return self._pages

    @property
    def current_page(self) -> Page:
        """Return the current firmware page. May raise IndexError"""
        return self._pages[self._current_page]

    def advance_page(self) -> None:
        """Move to the next firmware page"""
        self._current_page += 1

    def process(self, can_id: int, data: bytearray, timestamp: float) -> None:
        """Process an incoming CAN packet"""
        assert can_id == DEVICE_CAN_ID
        _ = timestamp
        self._state.process(bytes(data))

    def reply(self, data: bytes) -> None:
        """Send a reply to the device"""
        self._network.send_message(UPGRADER_CAN_ID, data)


class State(ABC):
    """
    The base State class declares methods that all concrete states should
    implement and also provides a backreference to the CanUpgrader object,
    associated with the State. This backreference can be used by States to
    transition the CanUpgrader to another State.
    """
    upgrader: CanUpgrader

    @abstractmethod
    def process(self, data: bytes) -> None:
        """Process a new CAN message"""


class StartState(State):
    """Waiting for a valid magic frame indicating a device is booting"""

    def process(self, data: bytes) -> None:
        # Recognise valid HELLO frames
        if len(data) == 8 and data[0] == DevicePacket.HELLO:
            # Reverse the bytes on the wire before
            device_serialno = data[7:3:-1]
            if (self.upgrader.target_serialno is None or
                    device_serialno == self.upgrader.target_serialno):
                self.upgrader.serialno = device_serialno
                self.upgrader.transition_to(HeaderState())
                self.upgrader.reply(data[4:8])

        # Explicitly reject any frames that could come from a device in the
        # middle of an upgrade process
        elif len(data) == 1 and data[0] in (DevicePacket.START,
                                            DevicePacket.PAGE,
                                            DevicePacket.CRC,
                                            DevicePacket.DONE):
            self.upgrader.transition_to(
                FailureState(Failure.UPGRADE_IN_PROGRESS))
        else:
            # Any other data on this CAN ID indicates a device which might
            # corrupt the upgrade process
            self.upgrader.transition_to(FailureState(Failure.PROTOCOL_ERROR))


class HeaderState(State):
    """Wait for the device to request details of the firmware image"""

    def process(self, data: bytes) -> None:
        if len(data) == 1 and data[0] == DevicePacket.START:
            try:
                self.upgrader.transition_to(
                    UploadState(self.upgrader.current_page))
            except IndexError:
                self.upgrader.transition_to(WaitForDoneState())

            self.upgrader.reply(
                struct.pack("B", len(self.upgrader.pages)))
        elif len(data) == 8 and data[0] == DevicePacket.HELLO:
            pass
        else:
            self.upgrader.transition_to(FailureState(Failure.PROTOCOL_ERROR))


class UploadState(State):
    """Wait for the device to request a new page of firmware data to upload"""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.pos = 0

    def process(self, data: bytes) -> None:
        if len(data) == 1 and data[0] == DevicePacket.PAGE:
            if self.pos < PAGE_SIZE:
                self.upgrader.reply(self.page.data[self.pos:self.pos+8])
                self.pos += 8

                if self.pos == PAGE_SIZE:
                    self.upgrader.transition_to(CheckCrcState(self.page.crc))
            else:
                self.upgrader.transition_to(
                    FailureState(Failure.PROTOCOL_ERROR))

        elif len(data) == 1 and data[0] == DevicePacket.ERROR:
            self.upgrader.transition_to(FailureState(Failure.PAGE_CRC_ERROR))

        elif len(data) == 8 and data[0] == DevicePacket.HELLO:
            pass
        else:
            self.upgrader.transition_to(FailureState(Failure.PROTOCOL_ERROR))


class CheckCrcState(State):
    """Waiting for the device to validate the CRC of a completed page"""

    def __init__(self, crc: int) -> None:
        self.crc = crc

    def process(self, data: bytes) -> None:
        if len(data) == 1 and data[0] == DevicePacket.CRC:
            self.upgrader.reply(struct.pack("<I", self.crc))

            self.upgrader.advance_page()
            try:
                self.upgrader.transition_to(
                    UploadState(self.upgrader.current_page))
            except IndexError:
                self.upgrader.transition_to(WaitForDoneState())

        elif len(data) == 8 and data[0] == DevicePacket.HELLO:
            pass
        else:
            self.upgrader.transition_to(FailureState(Failure.PROTOCOL_ERROR))


class Failure(IntEnum):
    """Failure code for the upgrade process"""
    PROTOCOL_ERROR = 1
    UPGRADE_IN_PROGRESS = 2
    PAGE_CRC_ERROR = 3


class FailureState(State):
    """The firmware upgrade process has failed"""

    def __init__(self, failure: Failure) -> None:
        self.failure = failure

    def process(self, data: bytes) -> None:
        pass


class WaitForDoneState(State):
    """Waiting until the device confirms completion of the upgrade"""

    def process(self, data: bytes) -> None:
        if len(data) == 1 and data[0] == DevicePacket.DONE:
            self.upgrader.transition_to(CompleteState())

        elif len(data) == 1 and data[0] == DevicePacket.ERROR:
            self.upgrader.transition_to(FailureState(Failure.PAGE_CRC_ERROR))

        elif len(data) == 8 and data[0] == DevicePacket.HELLO:
            pass
        else:
            self.upgrader.transition_to(FailureState(Failure.PROTOCOL_ERROR))


class CompleteState(State):
    """The firmware upgrade process is complete"""

    def process(self, data: bytes) -> None:
        pass
