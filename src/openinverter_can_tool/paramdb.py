"""
openinverter parameter database functions
"""


import json
from pathlib import Path
from typing import Dict, Optional

import canopen
import canopen.objectdictionary

from .fpfloat import fixed_from_float
from .remote_db import RemoteDatabaseNode


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

    def __init__(self, name: str, param_id: int):
        # assign dummy values to the index to allow creation of the parent
        # variable class
        super().__init__(name, 0, 0)

        # Assign the id to set the index and subindex
        self.id = param_id

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
        """The openinverter parameter identifier for this parameter or spot
        value"""
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
            try:
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

            except ValueError:
                # If something bad happens parsing the unit string just bail
                # out and make it a plain numerical value
                unit += " [DB FORMAT ERROR]"

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
    node = RemoteDatabaseNode(network, node_id)

    return import_database_json(
        json.loads(filter_zero_bytes(node.param_db())))


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

    if not cache_location.exists():
        cache_location.mkdir(parents=True)

    node = RemoteDatabaseNode(network, node_id)

    checksum = node.param_db_checksum()

    cache_file = cache_location / f"{node_id}-{checksum}.json"

    if cache_file.exists():
        dictionary = import_database(cache_file)
    else:
        param_db_str = filter_zero_bytes(node.param_db())

        dictionary = import_database_json(json.loads(param_db_str))

        # Only save the database in the cache when we have successfully
        # imported it
        with open(cache_file, "wt", encoding="utf-8") as param_db_file:
            param_db_file.write(param_db_str)

    return dictionary
