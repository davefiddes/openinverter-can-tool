"""
openinverter specific CANopen API
"""

import canopen
import canopen.objectdictionary
from canopen.sdo import SdoClient

from . import constants as oi


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
        db = canopen.ObjectDictionary()
        self.sdo_client = SdoClient(0x600 + node_id,
                                    0x580 + node_id,
                                    db)
        self.sdo_client.network = network
        network.subscribe(0x580 + node_id, self.sdo_client.on_response)

        # For reasons unknown it doesn't appear possible to specify the
        # index/subindex and read the raw data when required. To get around
        # this we define a hard-wired variable database that corresponds with
        # the non-string end-points.
        var = canopen.objectdictionary.Variable(
            "checksum",
            oi.SERIALNO_INDEX,
            oi.PARAM_DB_CHECKSUM_SUBINDEX)
        var.data_type = canopen.objectdictionary.UNSIGNED32
        db.add_object(var)

    def __del__(self) -> None:
        self.network.unsubscribe(0x580 + self.node_id)

    def ParamDbChecksum(self) -> int:
        """
        Read the parameter database checksum. If this is equal to a
        previously read value the bytes read from ParamDb() can be
        considered equal. A different value implies that any data read
        from the ParamDb() method should be discarded.
        """
        return self.sdo_client["checksum"].raw

    def ParamDb(self) -> bytes:
        """Read the remote parameter database"""
        with self.sdo_client.open(oi.STRINGS_INDEX,
                                  oi.PARAM_DB_SUBINDEX,
                                  "rb") as param_db:
            return param_db.read()
