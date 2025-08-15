"""Model representing the parameters and their current value suitable for
displaying in a QTreeView"""

from typing import Dict

from PySide6.QtCore import QObject, Qt, Slot
from PySide6.QtGui import QStandardItem, QStandardItemModel

from ...paramdb import OIVariable

PARAMETER_HEADERS = ["Name", "Value", "Units"]

PARAMETER_FLAGS = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


class ParameterModel(QStandardItemModel):
    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.setHorizontalHeaderLabels(PARAMETER_HEADERS)
        self._values: Dict[str, QStandardItem] = {}

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

                dummy_units_item = QStandardItem()
                dummy_units_item.setFlags(PARAMETER_FLAGS)

                category_row = [category_item,
                                dummy_value_item,
                                dummy_units_item]

                self.appendRow(category_row)

            name_item = QStandardItem(param_name)
            name_item.setFlags(PARAMETER_FLAGS)

            value_item = QStandardItem("")
            value_item.setFlags(PARAMETER_FLAGS | Qt.ItemFlag.ItemIsEditable)

            if param.bit_definitions or param.value_descriptions:
                units_item = QStandardItem()
            else:
                units_item = QStandardItem(param.unit)
            units_item.setFlags(PARAMETER_FLAGS)

            category_row[0].appendRow([name_item, value_item, units_item])
            self._values[param_name] = value_item

        self.endResetModel()

    @Slot()
    def parameter_changed(self, param_name: str, value: float) -> None:
        if param_name in self._values:
            self._values[param_name].setText(str(value))
