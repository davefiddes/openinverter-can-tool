"""
Useful classes for test fixtures
"""

from pathlib import Path

import canopen
import canopen.objectdictionary

from openinverter_can_tool import constants as oi


class OISimulatedNode:
    """
    Simulate an openinverter node with the various custom SDO interfaces it
    would export.
    """

    def __init__(self, node_id: int = 1) -> None:
        # Start a network connection for the simulated node
        self.server_network = canopen.Network()
        self.server_network.connect("test", bustype="virtual")

        # Manually create a dictionary for the custom SDO variables that an OI
        # node provides
        dictionary = canopen.ObjectDictionary()
        db_checksum = canopen.objectdictionary.Variable(
            "checksum",
            oi.SERIALNO_INDEX,
            oi.PARAM_DB_CHECKSUM_SUBINDEX)
        db_checksum.data_type = canopen.objectdictionary.UNSIGNED32
        dictionary.add_object(db_checksum)
        db_var = canopen.objectdictionary.Variable(
            'database', oi.STRINGS_INDEX, oi.PARAM_DB_SUBINDEX)
        db_var.data_type = canopen.objectdictionary.VISIBLE_STRING
        dictionary.add_object(db_var)

        self.server_node = canopen.LocalNode(node_id, dictionary)
        self.server_network.add_node(self.server_node)

        # Put together a network that is connected to the server for the code
        # under test to use
        self.network = canopen.Network()
        self.network.connect("test", bustype="virtual")

    def __del__(self):
        """Always ensure we disconnect from the two networks. Failing to do
        this results in communications failures when mulitple instances of the
        class are used in succession."""
        self.network.disconnect()
        self.server_network.disconnect()

    def LoadDatabase(self, db: Path) -> None:
        """Load a given database file onto the simulated node"""

        with open(db, mode="br") as file:
            self.server_node.sdo['database'].raw = file.read()

    @property
    def checksum(self) -> int:
        """The database checksum used to verify if the database has changed.
        On a real node this is tied to the database definition. That is not
        done here to allow it to be manipulated for testing."""
        return self.server_node.sdo["checksum"]

    @checksum.setter
    def checksum(self, value: int):
        self.server_node.sdo["checksum"].raw = value
