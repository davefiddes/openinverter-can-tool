"""Model representing the spot values (i.e. read-only parameters)"""
from typing import Dict

import canopen
from PySide6.QtCore import QObject, Qt, Slot
from PySide6.QtGui import QStandardItem, QStandardItemModel

from ...paramdb import OIVariable
from .parameter_value_item import ParameterValueItem

SPOT_VALUE_HEADERS = ["Name", "Value", "Units"]

SPOT_VALUE_FLAGS = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


class SpotValueModel(QStandardItemModel):
    """Model for displaying spot values in a table."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.setHorizontalHeaderLabels(SPOT_VALUE_HEADERS)
        self._values: Dict[str, ParameterValueItem] = {}

    def populate_from_database(self, device_db: canopen.ObjectDictionary):
        """Populate the model with spot values from the device database."""

        self.clear()
        self._values.clear()

        self.setHorizontalHeaderLabels(SPOT_VALUE_HEADERS)

        self.beginResetModel()

        # Filter out only the spot values we want
        spot_values = {k: v for k, v in device_db.names.items(
        ) if isinstance(v, OIVariable) and not v.isparam}

        for param_name, param in spot_values.items():
            name_item = QStandardItem(param_name)
            name_item.setFlags(SPOT_VALUE_FLAGS)

            value_item = ParameterValueItem(param, 0.0)
            value_item.setFlags(SPOT_VALUE_FLAGS)

            if param.bit_definitions or param.value_descriptions:
                units_item = QStandardItem()
            else:
                units_item = QStandardItem(param.unit)
            units_item.setFlags(SPOT_VALUE_FLAGS)

            self.appendRow([name_item, value_item, units_item])
            self._values[param_name] = value_item

        self.endResetModel()

    @Slot()
    def parameter_changed(self, param_name: str, value: float) -> None:
        if param_name in self._values:
            self._values[param_name].value = value
