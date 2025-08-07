"""Parameter Table View"""

from typing import Optional

from PySide6.QtCore import Qt, QAbstractItemModel, QAbstractTableModel
from PySide6.QtWidgets import QTableView


class ParamTableView(QTableView):
    """A table view for displaying parameters."""

    def __init__(self, parent=None):
        """Set the UI defaults for the table view."""

        super().__init__(parent)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableView.EditTrigger.DoubleClicked |
                             QTableView.EditTrigger.SelectedClicked)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(True)
        self.setGridStyle(Qt.PenStyle.SolidLine)

    def setModel(self, model: Optional[QAbstractItemModel]) -> None:
        """When setting the model set the width of each column."""

        super().setModel(model)
        assert isinstance(model, QAbstractTableModel)
        for i in range(0, model.columnCount()):
            size = model.headerData(
                i, Qt.Orientation.Horizontal, Qt.ItemDataRole.SizeHintRole)
            self.setColumnWidth(i, size.width())
