"""Model representing error log entries"""
from datetime import timedelta
from typing import List, Tuple, Optional

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel

ERROR_HEADERS = ["Time", "Error Message"]

ERROR_FLAGS = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


class ErrorModel(QStandardItemModel):
    """Model for displaying device errors in a table."""

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.setHorizontalHeaderLabels(ERROR_HEADERS)
        self._add_no_error_banner()

    def _reset_model(self, add_items_func) -> None:
        """Helper to manage model reset during population.

        :param add_items_func: Callable that adds items to the model
        """
        self.clear()
        self.setHorizontalHeaderLabels(ERROR_HEADERS)
        self.beginResetModel()
        add_items_func()
        self.endResetModel()

    def _add_no_error_banner(self) -> None:
        """Helper to create a single model item used as a banner"""
        item = QStandardItem("No errors")
        item.setFlags(ERROR_FLAGS)
        self.appendRow([item])

    def populate(
            self,
            errors: List[Tuple[timedelta, str]]) -> None:
        """Populate the model with the current list of errors

        :param errors: List of (timedelta, error_message) tuples
        """
        def add_items():
            for error_time, error_message in errors:
                time_item = QStandardItem(str(error_time))
                time_item.setFlags(ERROR_FLAGS)
                message_item = QStandardItem(error_message)
                message_item.setFlags(ERROR_FLAGS)
                self.appendRow([time_item, message_item])

        if errors:
            self._reset_model(add_items)
        else:
            self._reset_model(self._add_no_error_banner)

    def set_not_supported(self) -> None:
        """Set the model to indicate error listing is not supported."""
        def add_banner():
            item = QStandardItem("Error listing not supported by device")
            item.setFlags(ERROR_FLAGS)
            self.appendRow([item])

        self._reset_model(add_banner)
