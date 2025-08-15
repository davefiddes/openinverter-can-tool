"""Spot Value View"""

from typing import Optional

from PySide6.QtCore import QAbstractItemModel, Qt
from PySide6.QtWidgets import QHeaderView, QTableView


class SpotValueView(QTableView):
    """A table view for displaying spot values."""

    def __init__(self, parent=None):
        """Set the UI defaults for the table view."""

        super().__init__(parent)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.horizontalHeader().setHighlightSections(False)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(True)
        self.setGridStyle(Qt.PenStyle.SolidLine)
        self.setStyleSheet("QTableView::item { padding: 5px }")

    def setModel(self, model: Optional[QAbstractItemModel]) -> None:
        """When setting the model set the width of each column."""

        super().setModel(model)
        self.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
