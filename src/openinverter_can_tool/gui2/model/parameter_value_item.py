"""Custom item for parameter value display with units as suffix"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem

from ...fpfloat import fixed_to_float
from ...paramdb import OIVariable, value_to_str


class ParameterValueItem(QStandardItem):
    """
    Custom item for parameter values. Combines value and units display.
    """

    def __init__(self, param: OIVariable, value: float):
        super().__init__()
        self.param = param
        self._value = value
        self._error = ""
        self.setTextAlignment(Qt.AlignmentFlag.AlignRight)
        self._update_display()

    def type(self) -> int:
        return self.ItemType.UserType + 1  # type: ignore

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, value: float) -> None:
        self._value = value
        self._update_display()

    @property
    def error(self) -> str:
        """If there is an error associated with this value, return it.
        """
        return self._error

    def _update_display(self) -> None:
        """
        Update the text display with value and unit suffix and range check.
        """
        self._error = ""
        value_str = value_to_str(self.param, self._value)

        if self.param.value_descriptions:
            self.setText(value_str)
            self._range_check_enum(self._value)
        elif self.param.bit_definitions:
            self.setText(value_str)
            self._range_check_bitfield(self._value)
        else:
            # Add units as a suffix if they exist
            if self.param.unit:
                self.setText(f"{value_str} {self.param.unit}")
            else:
                self.setText(value_str)
            self._range_check_float(self._value)

    def _range_check_float(self, value):
        """Check if the float value is within the allowed range."""
        if (self.param.max is not None and
                value > fixed_to_float(self.param.max)):
            self._error = (
                f"Value {value:g} is larger than the maximum value "
                f"{fixed_to_float(self.param.max):g} allowed for "
                f"{self.param.name}")
        if (self.param.min is not None and
                value < fixed_to_float(self.param.min)):
            self._error = (
                f"Value {value:g} is smaller than the minimum value "
                f"{fixed_to_float(self.param.min):g} allowed for "
                f"{self.param.name}")

    def _range_check_enum(self, value):
        """Check if the enum value is valid."""
        int_value = int(value)
        valid_keys = self.param.value_descriptions.keys()
        if int_value not in valid_keys:
            self._error = (
                f"Unable to find value: '{int_value}' for parameter: "
                f"{self.param.name}. Valid values are "
                f"{self.param.value_descriptions}")

    def _range_check_bitfield(self, value):
        """Check if the bitfield value is valid."""
        int_value = int(value)
        if int_value == 0:
            return

        found = False
        for key in self.param.bit_definitions.keys():
            if int_value & key:
                found = True
        if not found:
            self._error = (
                f"Unable to find bit: '{int_value}' for "
                f"parameter: {self.param.name}. Valid bits are "
                f"{self.param.bit_definitions}"
            )
