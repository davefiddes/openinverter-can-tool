"""Model representing the parameters and their current value suitable for
displaying in a QTreeView"""

from typing import Dict

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QStandardItem, QStandardItemModel

from ...paramdb import OIVariable
from .parameter_value_item import ParameterValueItem

PARAMETER_HEADERS = ["Name", "Value"]

PARAMETER_FLAGS = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


class ParameterModel(QStandardItemModel):
    parameter_changed = Signal(str, float)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.setHorizontalHeaderLabels(PARAMETER_HEADERS)
        self._values: Dict[str, ParameterValueItem] = {}
        self.itemChanged.connect(self._on_item_changed)

    def populate_from_database(self, device_db):
        """Populate the model with parameters from the device database."""

        self.clear()
        self._values.clear()

        self.setHorizontalHeaderLabels(PARAMETER_HEADERS)

        self.beginResetModel()

        # Filter out only modifiable parameters we want
        params = {k: v for k, v in device_db.names.items(
        ) if isinstance(v, OIVariable) and v.isparam}

        for param_name, param in params.items():
            category_name = param.category or "Uncategorized"

            category_row = self.findItems(
                category_name, Qt.MatchFlag.MatchExactly, 0)
            if not category_row:
                category_item = QStandardItem(category_name)
                category_item.setFlags(PARAMETER_FLAGS)

                dummy_value_item = QStandardItem()
                dummy_value_item.setFlags(PARAMETER_FLAGS)

                category_row = [category_item, dummy_value_item]

                self.appendRow(category_row)

            name_item = QStandardItem(param_name)
            name_item.setFlags(PARAMETER_FLAGS)

            value_item = ParameterValueItem(param, 0.0)
            value_item.setFlags(PARAMETER_FLAGS | Qt.ItemFlag.ItemIsEditable)

            category_row[0].appendRow([name_item, value_item])
            self._values[param_name] = value_item

        self.endResetModel()

    @Slot(QStandardItem)
    def _on_item_changed(self, item: QStandardItem) -> None:
        """Handle item changes and emit parameter_changed signal."""
        for param_name, value_item in self._values.items():
            if value_item is item:
                self.parameter_changed.emit(param_name, value_item.value)
                return

    def set_value(self, param_name: str, value: float) -> None:
        """Set a parameter value but do not emit the changed signal."""
        if param_name in self._values:
            self._values[param_name].value = value

    def to_json(self) -> dict:
        """Create a JSON document based on the current model"""
        doc = {}
        for param_name, value_item in self._values.items():
            doc[param_name] = value_item.value
        return doc
