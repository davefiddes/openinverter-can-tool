"""
openinverter parameter database functions
"""


import json
from typing import Dict, Optional
from pathlib import Path
import os.path
import canopen
import canopen.objectdictionary
from canopen.sdo import SdoClient
from .fpfloat import fixed_from_float
from . import constants as oi


def is_power_of_two(num: int) -> bool:
    """Use some clever bitwise anding and arithmetic to determine wether a
    number is a power of two"""
    return (num != 0) and (num & (num - 1) == 0)


def is_bitfield(values: Dict[int, str]) -> bool:
    """Try to figure out if the dictionary of values is a bitfield or an
    enumeration"""

    for value in values:
        # Ignore zero
        if (value != 0) and (not is_power_of_two(value)):
            return False

    # When we only have two non-zero values we assume it's an enum not a
    # bitfield
    if len(values) <= 3:
        return False
    else:
        return True


def filter_zero_bytes(database_bytes: bytes) -> str:
    """Remove any zero bytes before decoding as utf-8. This can be used to
    deal with erroneous data that can be sent by heavily loaded openinverter
    firmware."""
    database_bytes = database_bytes.replace(b"\x00", b"")
    database_str = database_bytes.decode(encoding="utf-8", errors="ignore")
    return database_str


class OIVariable(canopen.objectdictionary.Variable):
    """An openinverter parameter variable has several differences from a
    standard CANopen variable. This class wraps up those differences allowing
    parameters to be specified in an object database."""

    def __init__(self, name: str, id: int):
        # assign dummy values to the index to allow creation of the parent
        # variable class
        super().__init__(name, 0, 0)

        # Assign the id to set the index and subindex
        self.id = id

        # All openinverter params are 32-bit fixed float values
        # we will convert to float on presentation as required
        # but work with them as integers to keep the canopen
        # library happy
        self.factor = 32
        self.data_type = canopen.objectdictionary.INTEGER32

        self.isparam: bool = False
        self.category: Optional[str] = None

        # This replaces the parent's bit_definitions member
        self.bit_definitions: Dict[int, str] = {}

    @property
    def id(self) -> int:
        return ((self.index & ~0x2100) << 8) + self.subindex

    @id.setter
    def id(self, value: int):
        self.index = 0x2100 | (value >> 8)
        self.subindex = value & 0xFF


def import_database_json(
        paramdb_json: dict) -> canopen.ObjectDictionary:
    """Import an openinverter parameter database JSON.

    :param paramdb_json:
        A dictionary containing an openinverter parameter database

    :returns:
        The Object Dictionary.
    :rtype: canopen.ObjectDictionary
    """

    dictionary = canopen.ObjectDictionary()
    for param_name in paramdb_json:
        param = paramdb_json[param_name]

        # Ignore parameters without unique IDs
        if "id" not in param:
            continue

        var = OIVariable(param_name, int(param["id"]))

        # Common attributes for parameters and values
        var.unit = param["unit"]
        var.isparam = param["isparam"]

        if "category" in param:
            var.category = param["category"]

        # parse units containing enumerations or bitfields
        unit = param["unit"]
        if '=' in unit:
            # Some parameters like "lasterr" have trailing commas
            unit = unit.rstrip(",")

            values = {int(value): description for value, description in [
                item.split('=') for item in unit.split(',')]}

            # Infer if this a bitfield or an enumeration and store the
            # description in the appropriate dictionary
            if is_bitfield(values):
                var.bit_definitions = values
            else:
                var.value_descriptions = values

        # Store the unit text for all types of parameters
        var.unit = unit

        # Parameters have additional required attributes
        if var.isparam:
            var.min = fixed_from_float(float(param["minimum"]))
            var.max = fixed_from_float(float(param["maximum"]))
            var.default = fixed_from_float(float(param["default"]))

        dictionary.add_object(var)

    return dictionary


def import_database(paramdb: Path) -> canopen.ObjectDictionary:
    """Import an openinverter parameter database file.

    :param paramdb:
        A path to an openinverter parameter database file

    :returns:
        The Object Dictionary.
    :rtype: canopen.ObjectDictionary
    """

    with open(paramdb, encoding="utf-8") as file:
        doc = json.load(file)

    return import_database_json(doc)


def import_remote_database(
        network: canopen.Network,
        node_id: int) -> canopen.ObjectDictionary:
    """Import an openinverter parameter database from a remote node.

    :param network:
        The configured and started canopen.Network to use to communicate with
        the node.

    :param node_id:
        The openinverter node we wish to obtain the parameter database from.

    :returns:
        The Object Dictionary.
    :rtype: canopen.ObjectDictionary
    """

    # Create temporary SDO client and attach to the network
    sdo_client = SdoClient(0x600 + node_id,
                           0x580 + node_id,
                           canopen.ObjectDictionary())
    sdo_client.network = network
    network.subscribe(0x580 + node_id, sdo_client.on_response)

    # Create file like object to load the JSON from the remote
    # openinverter node
    try:
        with sdo_client.open(oi.STRINGS_INDEX,
                             oi.PARAM_DB_SUBINDEX,
                             "rb") as param_db:
            dictionary = import_database_json(
                json.loads(filter_zero_bytes(param_db.read())))
    finally:
        network.unsubscribe(0x580 + node_id)

    return dictionary


def import_cached_database(
        network: canopen.Network,
        node_id: int,
        cache_location: Path
) -> canopen.ObjectDictionary:
    """Import an openinverter parameter database from a remote node and cache
    it for quicker access in future.

    :param network:
        The configured and started canopen.Network to use to communicate with
        the node.

    :param node_id:
        The openinverter node we wish to obtain the parameter database from.

    :param cache_location:
        A directory containing the parameter database cache.

    :returns:
        The Object Dictionary.

    :rtype: canopen.ObjectDictionary
    """

    # Create temporary SDO client and attach to the network
    temp_dictionary = canopen.ObjectDictionary()
    sdo_client = SdoClient(0x600 + node_id, 0x580 + node_id, temp_dictionary)
    sdo_client.network = network
    network.subscribe(0x580 + node_id, sdo_client.on_response)

    try:
        checksum_var = canopen.objectdictionary.Variable(
            "checksum",
            oi.SERIALNO_INDEX,
            oi.PARAM_DB_CHECKSUM_SUBINDEX)
        checksum_var.data_type = canopen.objectdictionary.UNSIGNED32
        temp_dictionary.add_object(checksum_var)
        checksum = sdo_client["checksum"].raw

        if not os.path.exists(cache_location):
            os.mkdir(cache_location)

        cache_file = cache_location / Path(f"{node_id}-{checksum}.json")

        if os.path.exists(cache_file):
            dictionary = import_database(cache_file)
        else:
            # Create file like object to load the JSON from the remote
            # openinverter node
            with sdo_client.open(oi.STRINGS_INDEX,
                                 oi.PARAM_DB_SUBINDEX,
                                 "rb", encoding="utf-8") as param_db:
                param_db_str = filter_zero_bytes(param_db.read())

            dictionary = import_database_json(json.loads(param_db_str))

            # Only save the database in the cache when we have successfully
            # imported it
            with open(cache_file, "wt", encoding="utf-8") as param_db_file:
                param_db_file.write(param_db_str)
    finally:
        network.unsubscribe(0x580 + node_id)

    return dictionary
