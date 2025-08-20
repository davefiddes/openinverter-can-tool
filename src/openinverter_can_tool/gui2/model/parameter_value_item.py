"""Custom item for PySide6 view models"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem

from ...paramdb import OIVariable, value_to_str


class ParameterValueItem(QStandardItem):
    """
    Custom item for parameter values. Handles the formatting of parameters.
    """

    def __init__(self, param: OIVariable, value: float):
        super().__init__()
        self.param = param
        self._value = value
        self.setTextAlignment(Qt.AlignmentFlag.AlignRight)

    def type(self) -> int:
        return self.ItemType.UserType + 1  # type: ignore

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, value: float) -> None:
        self._value = value
        self.setText(value_to_str(self.param, self._value))
