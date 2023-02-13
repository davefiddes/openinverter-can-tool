"""
openinverter parameter database functions
"""


import json
from typing import Tuple
from canopen import objectdictionary, Network
from canopen.sdo import SdoClient
from .fpfloat import fixed_from_float
from . import constants as oi


def index_from_id(param_identifier: int) -> Tuple[int, int]:
    """Generate an index, subindex tuple from an openinverter parameter id"""
    index = 0x2100 | (param_identifier >> 8)
    subindex = param_identifier & 0xFF
    return (index, subindex)


def import_database_json(
        paramdb_json: dict) -> objectdictionary.ObjectDictionary:
    """Import an openinverter parameter database JSON.

    :param paramdb_json:
        A dictionary containing an openinverter parameter database

    :returns:
        The Object Dictionary.
    :rtype: canopen.ObjectDictionary
    """

    dictionary = objectdictionary.ObjectDictionary()
    for param_name in paramdb_json:
        param = paramdb_json[param_name]

        # Ignore parameters without unique IDs
        if "id" not in param:
            continue

        (index, subindex) = index_from_id(int(param["id"]))
        var = objectdictionary.Variable(param_name, index, subindex)

        # All openinverter params are 32-bit fixed float values
        # we will convert to float on presentation as required
        # but work with them as integers to keep the canopen
        # library happy
        var.factor = 32
        var.data_type = objectdictionary.INTEGER32

        # Common attributes for parameters and values
        # "isparam" and "category" are not normal member variables in the
        # objectdictionary.Variable class. We add them here.
        var.unit = param["unit"]
        var.isparam = param["isparam"]

        if "category" in param:
            var.category = param["category"]
        else:
            var.category = None

        # Parameters have additional required attributes
        if var.isparam:
            var.min = fixed_from_float(float(param["minimum"]))
            var.max = fixed_from_float(float(param["maximum"]))
            var.default = fixed_from_float(float(param["default"]))

        dictionary.add_object(var)

    return dictionary


def import_database(paramdb: str) -> objectdictionary.ObjectDictionary:
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
        network: Network,
        node_id: int) -> objectdictionary.ObjectDictionary:
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
    sdo_client = SdoClient(0x600 + node_id, 0x580 + node_id,
                           objectdictionary.ObjectDictionary())
    sdo_client.network = network
    network.subscribe(0x580 + node_id, sdo_client.on_response)

    # Create file like object to load the JSON from the remote
    # openinverter node
    try:
        with sdo_client.open(oi.STRINGS_INDEX, oi.PARAM_DB_SUBINDEX,
                             "rt", encoding="utf-8") as param_db:
            dictionary = import_database_json(json.load(param_db))
    finally:
        network.unsubscribe(0x580 + node_id)

    return dictionary
