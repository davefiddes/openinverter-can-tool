"""Parameter View"""

from PySide6.QtCore import QAbstractItemModel
from PySide6.QtWidgets import QHeaderView, QTreeView


class ParamView(QTreeView):
    """A tree view representing all of the configurable parameters allowing
    them to be viewed and edited."""

    def __init__(self, parent=None):
        """Set the UI defaults for the table view."""

        super().__init__(parent)
        self.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTreeView.EditTrigger.DoubleClicked |
                             QTreeView.EditTrigger.SelectedClicked)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.setStyleSheet("QTreeView::item { padding: 5px }")

    def setModel(self, model: QAbstractItemModel | None) -> None:
        super().setModel(model)
        self.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
