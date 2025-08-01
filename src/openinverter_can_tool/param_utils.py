"""Helper functions to write parameter values to openinverter nodes"""

from typing import Union, Callable

import canopen

from .fpfloat import fixed_from_float, fixed_to_float
from .oi_node import OpenInverterNode
from .paramdb import OIVariable


class ParamWriter:
    """
    Encapsulate the logic to write a parameter value to an openinverter node
    """

    def __init__(
            self,
            node: OpenInverterNode,
            db: canopen.ObjectDictionary,
            log_func: Callable[[str], None]) -> None:
        self.node = node
        self.db = db
        self.log = log_func

    def write(self, param: str, value: Union[float, str]) -> None:
        """Write a parameter value to the node. The value can be a float or a
        string. If a string is provided it is assumed to be an enumeration or
        bitfield value. If the parameter is not found in the database, an error
        message is printed."""

        # Check if the parameter is in the database
        if param in self.db.names:
            param_item = self.db.names[param]

            # Check if we are a modifiable parameter
            if param_item.isparam:
                if isinstance(value, float):
                    self.set_float_value(param_item, value)
                else:
                    # Assume the value is a float to start with
                    try:
                        self.set_float_value(param_item, float(value))
                    except ValueError:
                        if param_item.value_descriptions:
                            self.set_enum_value(param_item, str(value))
                        elif param_item.bit_definitions:
                            self.set_bitfield_value(param_item, str(value))
                        else:
                            self.log(
                                f"Invalid value: '{value}' for parameter: "
                                f"{param}")
            else:
                self.log(f"{param} is a spot value parameter. "
                         "Spot values are read-only.")
        else:
            self.log(f"Unknown parameter: {param}")

    def set_enum_value(
            self,
            param: OIVariable,
            value: str) -> None:
        """import canopen
        Set a enumeration parameter over SDO by looking up its symbolic value
        """

        result = None
        for key, description in param.value_descriptions.items():
            if description.lower() == value.lower():
                result = key

        if result is not None:
            self.node.sdo[param.name].raw = fixed_from_float(result)
        else:
            self.log(f"Unable to find value: '{value}' for parameter: "
                     f"{param.name}. Valid values are "
                     f"{param.value_descriptions}")

    def set_bitfield_value(
            self,
            param: OIVariable,
            value: str) -> None:
        """
        Set a bitfield parameter over SDO by looking up its symbolic values.
        The value should be a comma separated list.
        """

        result = 0
        for bit_name in value.split(','):
            bit_name = bit_name.strip()

            found = False
            for key, description in param.bit_definitions.items():
                if description.lower() == bit_name.lower():
                    result |= key
                    found = True

            if not found:
                self.log(f"Unable to find bit name: '{bit_name}' for "
                         f"parameter: {param.name}. Valid bits are "
                         f"{param.bit_definitions}")
                return

        self.node.sdo[param.name].raw = fixed_from_float(result)

    def set_float_value(
            self,
            param: OIVariable,
            value: float) -> None:
        """Set a parameter with a floating point value over SDO"""

        # pre-conditions that should always be
        assert param.isparam
        assert param.min is not None
        assert param.max is not None

        fixed_value = fixed_from_float(value)

        if fixed_value < param.min:
            self.log(f"Value {value:g} is smaller than the minimum "
                     f"value {fixed_to_float(param.min):g} allowed "
                     f"for {param.name}")
        elif fixed_value > param.max:
            self.log(f"Value {value:g} is larger than the maximum value "
                     f"{fixed_to_float(param.max):g} allowed for "
                     f"{param.name}")
        else:
            self.node.sdo[param.name].raw = fixed_value
