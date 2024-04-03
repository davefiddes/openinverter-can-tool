"""
openinverter specific CANopen API
"""

import struct
from enum import IntEnum
from typing import List, Optional

import canopen
import canopen.objectdictionary
from canopen.sdo import SdoClient

from . import constants as oi

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


class MapEntry:
    """Describe a openinverter parameter to CAN message mapping"""

    def __init__(
            self,
            param_id: int,
            position: int,
            length: int,
            gain: float,
            offset: int):

        self.param_id = param_id
        self.position = position
        self.length = length
        self.gain = gain
        self.offset = offset


class CanMessage:
    """
    A custom CAN message that maps openinverter parameters to a specific CAN ID
    """

    def __init__(
            self,
            can_id: int,
            params: List[MapEntry]) -> None:
        self.can_id = can_id
        self.params = params


class OpenInverterNode:
    """
    openinverter lightly abuses the CANopen SDO protocol to implement a series
    of command and control API end-points to manipulate and manage devices.
    This class wraps the raw protocol in a python API that masks the underlying
    complexities.
    """

    def __init__(self, network: canopen.Network, node_id: int) -> None:
        """Create temporary SDO client and attach to the network """

        self.network = network
        self.node_id = node_id
        self.sdo_client = SdoClient(0x600 + node_id,
                                    0x580 + node_id,
                                    canopen.ObjectDictionary())
        self.sdo_client.network = network  # type: ignore
        network.subscribe(0x580 + node_id, self.sdo_client.on_response)

    def __del__(self) -> None:
        self.network.unsubscribe(0x580 + self.node_id)

    def ParamDbChecksum(self) -> int:
        """
        Read the parameter database checksum. If this is equal to a
        previously read value the bytes read from ParamDb() can be
        considered equal. A different value implies that any data read
        from the ParamDb() method should be discarded.
        """
        value, = UNSIGNED32.unpack(
            self.sdo_client.upload(
                oi.SERIALNO_INDEX,
                oi.PARAM_DB_CHECKSUM_SUBINDEX))

        return value

    def ParamDb(self) -> bytes:
        """Read the remote parameter database"""
        with self.sdo_client.open(oi.STRINGS_INDEX,
                                  oi.PARAM_DB_SUBINDEX,
                                  "rb") as param_db:
            return param_db.read()  # type: ignore

    def SerialNo(self) -> bytes:
        """Device unique serial number"""

        # Fetch the serial number in 3 parts reversing from little-endian on
        # the wire into a reversed array where the LSB is first and MSB is
        # last. This is odd but mirrors the behaviour of the STM32 terminal
        # "serial" command for consistency.
        serialno = bytearray()
        for i in reversed(range(3)):
            serialno.extend(
                reversed(self.sdo_client.upload(oi.SERIALNO_INDEX, i)))

        return serialno

    def Save(self) -> None:
        """
        Request the remote node save its parameters to persistent storage
        """
        self.sdo_client.download(
            oi.COMMAND_INDEX, oi.SAVE_COMMAND_SUBINDEX, bytes(4))

    def Load(self) -> None:
        """
        Request the remote node load its parameters from persistent storage
        """
        self.sdo_client.download(
            oi.COMMAND_INDEX, oi.LOAD_COMMAND_SUBINDEX, bytes(4))

    def Reset(self) -> None:
        """Request the remote node reset/reboot"""
        self.sdo_client.download(
            oi.COMMAND_INDEX, oi.RESET_COMMAND_SUBINDEX, bytes(4))

    def LoadDefaults(self) -> None:
        """Request the remote node load its default parameters. Equivalent to
        a factory configuration reset."""
        self.sdo_client.download(
            oi.COMMAND_INDEX, oi.DEFAULTS_COMMAND_SUBINDEX, bytes(4))

    def Start(self, mode: int = oi.START_MODE_NORMAL) -> None:
        """
        Request the remote node start normal operation

        :param mode: Device specific mode parameter
        """
        self.sdo_client.download(
            oi.COMMAND_INDEX,
            oi.START_COMMAND_SUBINDEX,
            UNSIGNED32.pack(mode))

    def Stop(self) -> None:
        """Request the remote node stop normal operation"""
        self.sdo_client.download(
            oi.COMMAND_INDEX, oi.STOP_COMMAND_SUBINDEX, bytes(4))

    def MapParamToCan(
            self,
            can_id: int,
            direction: Direction,
            param_id: int,
            position: int,
            length: int,
            gain: float,
            offset: int) -> None:
        """
        Add a CAN map entry to transmit the current value of a given parameter.

        :param can_id:    The CAN ID that will be transmitted. [1,0x7ff]
        :param direction: The direction the parameter will be mapped, either
                          transmit or receive.
        :param param_id:  The openinverter parameter id to be mapped.
        :param position:  The bit position the parameter will start at. [0, 63]
        :param length:    The bit length the parameter will occupy. [1, 32]
        :param gain:      The parameter is multiplied by the gain before being
                          inserted into the CAN frame. [-8388.608, 8388.607]
        :param offset:    The offset to be added to the parameter after the
                          gain is applied. [-128, 127]

        """
        if can_id not in range(1, 0x800):
            raise ValueError
        if position not in range(0, 64):
            raise ValueError
        if length not in range(1, 33):
            raise ValueError
        if gain < -8388.608 or gain > 8388.607:
            raise ValueError
        if offset not in range(-128, 128):
            raise ValueError

        MapDirectionIndex = {
            Direction.TX: oi.CAN_MAP_TX_INDEX,
            Direction.RX: oi.CAN_MAP_RX_INDEX
        }

        if direction in MapDirectionIndex:
            cmd_index = MapDirectionIndex[direction]
        else:
            raise ValueError

        # Fill out the SDO "variable" with the CAN ID we want to map
        self.sdo_client.download(
            cmd_index,
            oi.MAP_CAN_ID_SUBINDEX,
            UNSIGNED32.pack(can_id))

        # Fill out the SDO "variable" with the parameter ID to map and
        # the position and length they should take up in each CAN frame
        self.sdo_client.download(
            cmd_index,
            oi.MAP_PARAM_POS_LEN_SUBINDEX,
            struct.pack("<HBB", param_id, position, length))

        # Finally fill out the SDO "variable" with the gain and offset
        # the parameter requires for the CAN frame. This will actually
        # cause the mapping to be created on the remote node
        gain_bytes = struct.pack("<i", int(gain * 1000))[:3]
        offset_bytes = struct.pack("<b", offset)
        self.sdo_client.download(
            cmd_index,
            oi.MAP_GAIN_OFFSET_SUBINDEX,
            gain_bytes + offset_bytes)

    def _GetMappedCanId(self, index: int) -> Optional[int]:
        """
        Get the can_id stored at a given index in a can message param map.

        :param index: Absolute CAN SDO index for the entry

        :return: The can_id at this map position or None if not present
        """
        try:
            can_id, = UNSIGNED32.unpack(
                self.sdo_client.upload(index, 0))
        except canopen.SdoAbortedError as err:
            if err.code == oi.SDO_ABORT_OBJECT_NOT_AVAILABLE:
                return None
            else:
                raise err

        return can_id

    def _GetMapEntry(
            self,
            can_id_index: int,
            param_index: int) -> Optional[MapEntry]:
        """Retrieve the details of a specific parameter map entry"""
        # parameter mappings always occur in sequential pairs
        assert param_index % 2 == 1

        try:
            (param_id, position, length) = struct.unpack(
                "<HBB",
                self.sdo_client.upload(can_id_index, param_index))

            gain_offset_bytes = self.sdo_client.upload(
                can_id_index, param_index+1)
            gain_bytes = gain_offset_bytes[:3]

            # Sign-extend the 24-bit gain into a 32-bit signed integer
            neg_gain = (gain_bytes[2] & 0x80) > 0
            (gain,) = struct.unpack(
                "<i",
                gain_bytes + (b'\xff' if neg_gain else b'\x00'))

            # Scale fixed-point to a float
            gain = gain / 1000.0

            (offset,) = struct.pack("<b", gain_offset_bytes[3])

            param = MapEntry(param_id, position, length, gain, offset)

        except canopen.SdoAbortedError as err:
            if err.code == oi.SDO_ABORT_OBJECT_NOT_AVAILABLE:
                return None
            else:
                raise err

        return param

    def _GetMapEntries(
            self,
            can_id_index: int) -> List[MapEntry]:
        """List all of the parameter map entries for a specific CAN ID

        :param can_id_index: Absolute CAN SDO index for the message"""
        params = []

        param_index = 1
        while True:
            param = self._GetMapEntry(can_id_index, param_index)

            if param is not None:
                params.append(param)
                param_index += 2
            else:
                break

        return params

    def ListParamCanMap(self, direction: Direction) -> List[CanMessage]:
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
            can_id = self._GetMappedCanId(can_id_index)

            if can_id is not None:
                msg = CanMessage(can_id, self._GetMapEntries(can_id_index))
                messages.append(msg)
                can_id_index += 1
            else:
                break

        return messages

    def RemoveCanMapEntry(
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
            self.sdo_client.download(
                can_sdo_index, param_sdo_index, UNSIGNED32.pack(0))
        except canopen.SdoCommunicationError as err:
            if str(err) == "Unexpected response 0x23":
                return True
            else:
                raise err

        except canopen.SdoAbortedError as err:
            if err.code == oi.SDO_ABORT_OBJECT_NOT_AVAILABLE:
                return False
            else:
                raise err

        return False