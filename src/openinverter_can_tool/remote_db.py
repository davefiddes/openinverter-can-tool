"""
openinverter remote database access
"""

import struct

import canopen
import canopen.objectdictionary
from canopen.sdo import SdoClient

from . import constants as oi


class RemoteDatabaseNode:
    """A simplified CANopen SDO wrapper around the two indexes that implement
    the remote database definition."""

    def __init__(self, network: canopen.Network, node_id: int) -> None:
        """Create temporary SDO client and attach to the network """

        self.network = network
        self.node_id = node_id
        self.sdo_client = SdoClient(0x600 + node_id,
                                    0x580 + node_id,
                                    canopen.ObjectDictionary())
        self.sdo_client.network = network  # type: ignore

    def __enter__(self):
        """Context manager entry point"""
        self.network.subscribe(
            0x580 + self.node_id,
            self.sdo_client.on_response)

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Context manager exit point"""
        self.network.unsubscribe(can_id=0x580 + self.node_id)

    def param_db_checksum(self) -> int:
        """
        Read the parameter database checksum. If this is equal to a
        previously read value the bytes read from ParamDb() can be
        considered equal. A different value implies that any data read
        from the ParamDb() method should be discarded.
        """
        value, = struct.unpack("<L",
                               self.sdo_client.upload(
                                   oi.SERIALNO_INDEX,
                                   oi.PARAM_DB_CHECKSUM_SUBINDEX))

        return value

    def param_db(self) -> bytes:
        """Read the remote parameter database"""
        with self.sdo_client.open(oi.STRINGS_INDEX,
                                  oi.PARAM_DB_SUBINDEX,
                                  "rb") as param_db:
            return param_db.read()  # type: ignore
