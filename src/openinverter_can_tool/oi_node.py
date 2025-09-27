"""
OpenInverter specific CANopen API
"""

import struct
from datetime import timedelta
from enum import IntEnum
from typing import List, Optional, Tuple

import canopen
from canopen.node.base import BaseNode
from canopen.sdo.client import SdoClient

from . import constants as oi
from .paramdb import OIVariable

# Common data type
UNSIGNED32 = struct.Struct("<L")


class Direction(IntEnum):
    """Direction for mapped parameters"""
    TX = 1
    RX = 2


MapListDirectionIndex = {
    Direction.TX: oi.CAN_MAP_LIST_TX_INDEX,
    Direction.RX: oi.CAN_MAP_LIST_RX_INDEX
}


def _validate_map_entry_parameters(
        position: int,
        length: int,
        gain: float,
        offset: int) -> None:
    """Common validation of map entry parameters"""
    if position not in range(0, 64):
        raise ValueError
    if abs(length) not in range(1, 33):
        raise ValueError
    if gain < -8388.608 or gain > 8388.607:
        raise ValueError
    if offset not in range(-128, 128):
        raise ValueError


class MapEntry:
    """Describe a OpenInverter parameter to CAN message mapping"""

    def __init__(
            self,
            param_id: int,
            position: int,
            length: int,
            gain: float,
            offset: int):

        _validate_map_entry_parameters(
            position,
            length,
            gain,
            offset
        )

        self.param_id = param_id
        self.position = position
        self.length = length
        self.gain = gain
        self.offset = offset

    def __eq__(self, other):
        if type(other) is type(self):
            return self.__dict__ == other.__dict__
        return False

    def __repr__(self) -> str:
        cls = self.__class__.__name__
        attrs = ", ".join(f"{k}={v}" for k, v in self.__dict__.items())
        return f"{cls}({attrs})"


def _validate_can_message_parameters(
        can_id: int,
        is_extended_frame: bool = False) -> None:
    if is_extended_frame:
        if can_id not in range(0, 0x20000000):
            raise ValueError
    else:
        if can_id not in range(0, 0x800):
            raise ValueError


class CanMessage:
    """
    A custom CAN message that maps OpenInverter parameters to a specific CAN ID
    """

    def __init__(
            self,
            can_id: int,
            params: List[MapEntry],
            is_extended_frame: bool = False) -> None:
        _validate_can_message_parameters(can_id, is_extended_frame)

        self.can_id = can_id
        self.params = params
        self.is_extended_frame = is_extended_frame

    def __eq__(self, other):
        if type(other) is type(self):
            return self.__dict__ == other.__dict__
        return False

    def __repr__(self) -> str:
        cls = self.__class__.__name__
        attrs = ", ".join(f"{k}={v}" for k, v in self.__dict__.items())
        return f"{cls}({attrs})"


class OpenInverterNode(BaseNode):
    """
    OpenInverter lightly abuses the CANopen SDO protocol to implement a series
    of command and control API end-points to manipulate and manage devices.
    This class wraps the raw protocol in a python API that masks the underlying
    complexities.
    """

    def __init__(self,
                 network: canopen.Network,
                 node_id: int,
                 object_dictionary: canopen.ObjectDictionary
                 ) -> None:
        """Create temporary SDO client and attach to the network """

        super().__init__(node_id, object_dictionary)
        self.network = network
        self.node_id = node_id
        self.sdo = SdoClient(0x600 + node_id,
                             0x580 + node_id,
                             object_dictionary)
        self.sdo.network = network  # type: ignore
        network.subscribe(0x580 + node_id, self.sdo.on_response)

    def serial_no(self) -> bytes:
        """Device unique serial number"""

        # Fetch the serial number in 3 parts reversing from little-endian on
        # the wire into a reversed array where the LSB is first and MSB is
        # last. This is odd but mirrors the behaviour of the STM32 terminal
        # "serial" command for consistency.
        serialno = bytearray()
        for i in reversed(range(3)):
            serialno.extend(
                reversed(self.sdo.upload(oi.SERIALNO_INDEX, i)))

        return serialno

    def save(self) -> None:
        """
        Request the remote node save its parameters to persistent storage
        """
        self.sdo.download(
            oi.COMMAND_INDEX, oi.SAVE_COMMAND_SUBINDEX, bytes(4))

    def load(self) -> None:
        """
        Request the remote node load its parameters from persistent storage
        """
        self.sdo.download(
            oi.COMMAND_INDEX, oi.LOAD_COMMAND_SUBINDEX, bytes(4))

    def reset(self) -> None:
        """Request the remote node reset/reboot"""
        self.sdo.download(
            oi.COMMAND_INDEX, oi.RESET_COMMAND_SUBINDEX, bytes(4))

    def load_defaults(self) -> None:
        """Request the remote node load its default parameters. Equivalent to
        a factory configuration reset."""
        self.sdo.download(
            oi.COMMAND_INDEX, oi.DEFAULTS_COMMAND_SUBINDEX, bytes(4))

    def start(self, mode: int = oi.START_MODE_NORMAL) -> None:
        """
        Request the remote node start normal operation

        :param mode: Device specific mode parameter
        """
        self.sdo.download(
            oi.COMMAND_INDEX,
            oi.START_COMMAND_SUBINDEX,
            UNSIGNED32.pack(mode))

    def stop(self) -> None:
        """Request the remote node stop normal operation"""
        self.sdo.download(
            oi.COMMAND_INDEX, oi.STOP_COMMAND_SUBINDEX, bytes(4))

    def add_can_map_entry(
            self,
            can_id: int,
            direction: Direction,
            param_id: int,
            position: int,
            length: int,
            gain: float,
            offset: int,
            is_extended_frame: bool = False) -> None:
        """
        Add a CAN map entry to transmit or receive the current value of a
        given parameter.

        :param can_id:    The CAN ID that will be transmitted.
                          [0,0x7ff] for standard frames
                          [0,0x1fffffff] for extended frames
        :param direction: The direction the parameter will be mapped, either
                          transmit or receive.
        :param param_id:  The OpenInverter parameter id to be mapped.
        :param position:  The bit position the parameter will start at. [0, 63]
        :param length:    The bit length the parameter will occupy. Positive
                          lengths indicate a little-endian length and negative
                          big-endian. [-32,-1][1, 32]
        :param gain:      The parameter is multiplied by the gain before being
                          inserted into the CAN frame. [-8388.608, 8388.607]
        :param offset:    The offset to be added to the parameter after the
                          gain is applied. [-128, 127]
        :param is_extended_frame: Does the can_id represent an extended CAN
                          frame id
        """
        _validate_can_message_parameters(can_id, is_extended_frame)
        _validate_map_entry_parameters(
            position,
            length,
            gain,
            offset
        )

        map_direction_index = {
            Direction.TX: oi.CAN_MAP_TX_INDEX,
            Direction.RX: oi.CAN_MAP_RX_INDEX
        }

        if direction in map_direction_index:
            cmd_index = map_direction_index[direction]
        else:
            raise ValueError

        # Fill out the SDO "variable" with the CAN ID we want to map
        if is_extended_frame:
            packed_can_id = can_id | oi.MAP_EXTENDED_FRAME_FLAG
        else:
            packed_can_id = can_id
        self.sdo.download(
            cmd_index,
            oi.MAP_CAN_ID_SUBINDEX,
            UNSIGNED32.pack(packed_can_id))

        # Fill out the SDO "variable" with the parameter ID to map and
        # the position and length they should take up in each CAN frame
        self.sdo.download(
            cmd_index,
            oi.MAP_PARAM_POS_LEN_SUBINDEX,
            struct.pack(
                "<HBb",
                param_id,
                position,
                length))

        # Finally fill out the SDO "variable" with the gain and offset
        # the parameter requires for the CAN frame. This will actually
        # cause the mapping to be created on the remote node
        gain_bytes = struct.pack("<i", int(gain * 1000))[:3]
        offset_bytes = struct.pack("<b", offset)
        self.sdo.download(
            cmd_index,
            oi.MAP_GAIN_OFFSET_SUBINDEX,
            gain_bytes + offset_bytes)

    def add_can_map(
            self,
            direction: Direction,
            msg_map: List[CanMessage]) -> None:
        """
        Add complete CAN map for a given direction. The map may be obtained
        from the list_can_map() method or manually constructed.

        :param direction: The direction the parameter will be mapped, either
                          transmit or receive.
        :param msg_map:  The list of CanMessage objects that comprise the map
        """
        for msg in msg_map:
            for param in msg.params:
                self.add_can_map_entry(
                    msg.can_id,
                    direction,
                    param.param_id,
                    param.position,
                    param.length,
                    param.gain,
                    param.offset,
                    msg.is_extended_frame
                )

    def _get_mapped_can_id(self, index: int) -> Optional[int]:
        """
        Get the can_id stored at a given index in a can message param map.

        :param index: Absolute CAN SDO index for the entry

        :return: The can_id at this map position or None if not present
        """
        try:
            can_id, = UNSIGNED32.unpack(
                self.sdo.upload(index, 0))
        except canopen.SdoAbortedError as err:
            if err.code == oi.SDO_ABORT_OBJECT_NOT_AVAILABLE:
                return None
            raise err

        return can_id

    def _get_map_entry(
            self,
            can_id_index: int,
            param_index: int) -> Optional[MapEntry]:
        """Retrieve the details of a specific parameter map entry"""
        # parameter mappings always occur in sequential pairs
        assert param_index % 2 == 1

        try:
            (param_id, position, length) = struct.unpack(
                "<HBb",
                self.sdo.upload(can_id_index, param_index))

            gain_offset_bytes = self.sdo.upload(
                can_id_index, param_index+1)

            # Sign-extend the 24-bit gain into a 32-bit signed integer
            gain_bytes = gain_offset_bytes[:3]
            neg_gain = (gain_bytes[2] & 0x80) > 0
            (gain,) = struct.unpack(
                "<i",
                gain_bytes + (b'\xff' if neg_gain else b'\x00'))

            # Scale fixed-point to a float
            gain = gain / 1000.0

            offset_bytes = gain_offset_bytes[3:4]
            (offset,) = struct.unpack("<b", offset_bytes)

            param = MapEntry(
                param_id,
                position,
                length,
                gain,
                offset)

        except canopen.SdoAbortedError as err:
            if err.code == oi.SDO_ABORT_OBJECT_NOT_AVAILABLE:
                return None
            raise err

        return param

    def _get_map_entries(
            self,
            can_id_index: int) -> List[MapEntry]:
        """List all of the parameter map entries for a specific CAN ID

        :param can_id_index: Absolute CAN SDO index for the message"""
        params = []

        param_index = 1
        while True:
            param = self._get_map_entry(can_id_index, param_index)

            if param is not None:
                params.append(param)
                param_index += 2
            else:
                break

        return params

    def list_can_map(self, direction: Direction) -> List[CanMessage]:
        """
        List all of the parameter to CAN frame mappings on the remote device.

        :param direction: The direction the map corresponds with.

        :return: A list of parameter to CAN message mappings.
        """

        if direction in MapListDirectionIndex:
            can_id_index = MapListDirectionIndex[direction]
        else:
            raise ValueError

        messages: List[CanMessage] = []
        while True:
            can_id = self._get_mapped_can_id(can_id_index)

            if can_id is not None:
                is_extended_frame = can_id & oi.MAP_EXTENDED_FRAME_FLAG > 0
                msg = CanMessage(
                    can_id & oi.MAP_EXTENDED_FRAME_MASK,
                    self._get_map_entries(can_id_index),
                    is_extended_frame)

                # Just ignore a message without any params
                if msg.params:
                    messages.append(msg)

                can_id_index += 1
            else:
                break

        return messages

    def remove_can_map_entry(
            self,
            direction: Direction,
            can_index: int,
            param_index: int) -> bool:
        """
        Remove a specific entry from a CAN parameter map.

        NOTE: This will invalidate the contents of a stored CAN map as the
        contents will be shuffled up automatically by the remote node.

        :param direction:   Which map direction to modify
        :param can_index:   The list index of the CAN ID to remove
        :param param_index: The list index of the param within the CanMessage
                            to remove

        :return: True if the removal was successful
        """

        if direction in MapListDirectionIndex:
            can_sdo_index = MapListDirectionIndex[direction]
        else:
            raise ValueError

        can_sdo_index += can_index

        # Removal is achieved by writing to the SDO index corresponding to the
        # param_id, position, offset parameter
        param_sdo_index = 2*(param_index+1)

        try:
            self.sdo.download(
                can_sdo_index, param_sdo_index, UNSIGNED32.pack(0))
        except canopen.SdoCommunicationError as err:
            err_str = str(err)
            if err_str in ("Unexpected response 0x20",
                           "Unexpected response 0x23"):
                return True
            raise err

        except canopen.SdoAbortedError as err:
            if err.code == oi.SDO_ABORT_OBJECT_NOT_AVAILABLE:
                return False
            raise err

        return True

    def clear_map(self, direction: Direction) -> None:
        """
        Remove all entries from the CAN message map

        :param direction:   Which map direction to clear
        """

        # Repeated removal of the 0th parameter of the 0th message will remove
        # everything as the device automatically shunts up existing parameters
        # into that position.
        while self.remove_can_map_entry(direction, 0, 0):
            _ = 1

    def list_errors(self) -> List[Tuple[timedelta, str]]:
        """
        List all of the errors on the remote device.

        :return: A list of errors and the time since device power on at which
          they occurred.
        """
        # We assume that a lasterr dictionary item is available to map our
        # error numbers to strings
        lasterr: Optional[OIVariable] = None
        if "lasterr" in self.object_dictionary:
            variable = self.object_dictionary["lasterr"]
            if isinstance(variable, OIVariable):
                lasterr = variable

        # Default to a 10ms tick duration if we can't determine it from the
        # "uptime" variable
        tick_duration = timedelta(milliseconds=10)

        # Infer the time base for error timestamps from the "uptime" spot
        # variable definition
        if "uptime" in self.object_dictionary:
            variable = self.object_dictionary["uptime"]
            if isinstance(variable, OIVariable):
                uptime = variable
                if uptime.unit == "sec":
                    tick_duration = timedelta(seconds=1)

        errors = []
        for index in range(0, 255):
            error_time, = UNSIGNED32.unpack(
                self.sdo.upload(oi.ERROR_TIME_INDEX, index))

            if error_time == 0:
                break
            error_time = error_time * tick_duration

            error_num, = UNSIGNED32.unpack(
                self.sdo.upload(oi.ERROR_NUM_INDEX, index))

            if lasterr is not None and error_num in lasterr.value_descriptions:
                errors.append(
                    (error_time, lasterr.value_descriptions[error_num]))
            else:
                errors.append((error_time, f"Unknown error {error_num}"))

        return errors
