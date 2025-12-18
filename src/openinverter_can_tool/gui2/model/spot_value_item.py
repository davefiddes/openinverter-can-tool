"""Custom item for spot value display with units as suffix"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem

from ...paramdb import OIVariable, value_to_str


class SpotValueItem(QStandardItem):
    """
    Custom item for spot values. Combines value and units display
    like QDoubleSpinBox suffix.
    """

    def __init__(self, param: OIVariable, value: float):
        super().__init__()
        self.param = param
        self._value = value
        self.setTextAlignment(Qt.AlignmentFlag.AlignRight)
        self._update_display()

    def type(self) -> int:
        return self.ItemType.UserType + 2  # type: ignore

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, value: float) -> None:
        self._value = value
        self._update_display()

    def _update_display(self) -> None:
        """Update the text display with value and unit suffix."""
        value_str = value_to_str(self.param, self._value)

        # If there are bit definitions or value descriptions, don't add units
        if self.param.bit_definitions or self.param.value_descriptions:
            self.setText(value_str)
        else:
            # Add units as a suffix if they exist
            if self.param.unit:
                self.setText(f"{value_str} {self.param.unit}")
            else:
                self.setText(value_str)
