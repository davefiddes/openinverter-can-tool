"""
openinverter parameter database functions
"""


import json
from typing import Tuple
from canopen import objectdictionary
from .fpfloat import fixed_from_float


def index_from_id(param_identifier: int) -> Tuple[int, int]:
    """Generate an index, subindex tuple from an openinverter parameter id"""
    index = 0x2100 | (param_identifier >> 8)
    subindex = param_identifier & 0xFF
    return (index, subindex)


def import_database(paramdb) -> objectdictionary.ObjectDictionary:
    """Import an openinverter parameter database file.

    :param paramdb:
        A path to an openinverter parameter database file

    :returns:
        The Object Dictionary.
    :rtype: canopen.ObjectDictionary
    """
    dictionary = objectdictionary.ObjectDictionary()

    with open(paramdb, encoding="utf-8") as file:
        doc = json.load(file)

    for param_name in doc:
        param = doc[param_name]
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
