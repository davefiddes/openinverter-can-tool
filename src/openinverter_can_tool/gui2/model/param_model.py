"""Model representing the parameters and their current value"""

from dataclasses import dataclass
from enum import IntEnum
from typing import List, Any

from PySide6.QtCore import (QAbstractTableModel, QModelIndex,
                            QPersistentModelIndex, QSize, Qt)

from ...paramdb import OIVariable


class ParameterModelColumns(IntEnum):
    Name = 0
    Value = 1
    Count = 2


@dataclass
class ParamEntry:
    variable: OIVariable
    value: float


class ParameterTableModel(QAbstractTableModel):
    """Model for displaying parameters and their values in a table."""

    def __init__(self):
        super().__init__()
        self._params: List[ParamEntry] = []

    def rowCount(
        self,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        """Return the number of rows in the model."""
        return len(self._params)

    def columnCount(
        self,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        return 2

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole
    ):
        """Return the header data for the table."""

        if (role == Qt.ItemDataRole.DisplayRole and
                orientation == Qt.Orientation.Horizontal):
            if section == ParameterModelColumns.Name:
                return "Parameter"
            if section == ParameterModelColumns.Value:
                return "Value"

        if (role == Qt.ItemDataRole.SizeHintRole and
                orientation == Qt.Orientation.Horizontal):
            if section == ParameterModelColumns.Name:
                return QSize(200, 25)
            if section == ParameterModelColumns.Value:
                return QSize(130, 25)

        return None

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole
    ):
        """Return the data for the given index and role."""

        row = index.row()
        column = index.column()
        if (not index.isValid() or row >= len(self._params) or
                column >= ParameterModelColumns.Count):
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            if column == ParameterModelColumns.Name:
                return self._params[row].variable.name
            elif column == ParameterModelColumns.Value:
                return self._params[row].value
        elif role == Qt.ItemDataRole.EditRole:
            if column == ParameterModelColumns.Name:
                return self._params[row].variable.name
            elif column == ParameterModelColumns.Value:
                return self._params[row].value

        return None

    def setData(
        self,
        index: QModelIndex | QPersistentModelIndex,
        value: Any,
        role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        """Set the data for the given index and role."""
        if value is None or not isinstance(value, float):
            return False

        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False

        row = index.row()
        column = index.column()
        if row >= len(self._params) or column >= ParameterModelColumns.Count:
            return False

        if column == ParameterModelColumns.Value:
            self._params[row].value = value
            self.dataChanged.emit(index, index)
            return True

        return False

    def flags(self, index):
        """Return the flags which indicate the first column is not editable
        but the second is."""

        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == ParameterModelColumns.Value:
            flags |= Qt.ItemFlag.ItemIsEditable

        return flags

    def append_param(self, variable: OIVariable, value: float):
        """Append a new parameter to the model."""
        assert variable.isparam, "Only parameters can be added to this model"

        self.beginInsertRows(
            QModelIndex(),
            len(self._params),
            len(self._params))
        self._params.append(ParamEntry(variable, value))
        self.endInsertRows()
