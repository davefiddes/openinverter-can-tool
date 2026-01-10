"""Error View"""

from typing import Optional

from PySide6.QtCore import QAbstractItemModel, Qt
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import QHeaderView, QTableView


class ErrorView(QTableView):
    """A table view for displaying device error log entries."""

    def __init__(self, parent=None):
        """Set the UI defaults for the table view."""

        super().__init__(parent)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(False)
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
        # Connect to model changes to format placeholder rows
        if model is not None and isinstance(model, QStandardItemModel):
            model.rowsInserted.connect(self._format_placeholder_rows)
            # Format any existing placeholder rows
            self._format_placeholder_rows()

    def _format_placeholder_rows(self) -> None:
        """Format placeholder rows (no errors, not supported) with centered
        text and appropriate styling."""
        model = self.model()
        if model is None or not isinstance(model, QStandardItemModel):
            return

        # Check if this is a placeholder row (single item spanning columns)
        if model.rowCount() == 1:
            item = model.item(0, 0)
            item_pair = model.item(0, 1)

            if item is not None and item_pair is None:
                # Format the item as italic
                font = item.font()
                font.setItalic(True)
                item.setFont(font)
                # Span the item across all columns
                self.setSpan(0, 0, 1, 2)
