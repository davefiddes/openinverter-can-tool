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

    for category in doc:
        for param in doc[category]:
            (index, subindex) = index_from_id(int(param['id']))
            var = objectdictionary.Variable(param['name'], index, subindex)

            # All openinverter params are 32-bit fixed float values
            # we will convert to float on presentation as required
            # but work with them as integers to keep the canopen
            # library happy
            var.factor = 32
            var.data_type = objectdictionary.INTEGER32

            # These parameter attributes are optional
            if "unit" in param:
                var.unit = param["unit"]
            if "min" in param:
                var.min = fixed_from_float(float(param["min"]))
            if "max" in param:
                var.max = fixed_from_float(float(param["max"]))
            if "def" in param:
                var.default = fixed_from_float(float(param["def"]))

            dictionary.add_object(var)

    return dictionary
