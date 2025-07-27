from pathlib import Path
from typing import Optional

import appdirs
import can
import canopen
from PySide6.QtCore import QObject, Slot

from ... import constants as oi
from ...paramdb import import_cached_database
from ..model.model import Model


class MainController(QObject):
    """Control the behaviour of the application."""

    def __init__(self, model: Model):
        super().__init__()

        self._model = model
        self._node_id: int = 0
        self._network: Optional[canopen.Network] = None

    @Slot(int)
    def change_amount(self, value: int):
        self._model.amount = value

        # calculate even or odd
        self._model.even_odd = 'odd' if value % 2 else 'even'

        # calculate button enabled state
        self._model.enable_reset = True if value else False

    @Slot(int)
    def start_new_session(self, node_id: int):
        """Start a new session with the given node ID."""

        self._model.node_id = node_id

        if self._model.node_id > 0:
            if self._network is None:
                self._network = canopen.Network()
                self._network.connect()
            self._network.check()
            self._model.device_db = import_cached_database(
                self._network,
                self._model.node_id,
                Path(appdirs.user_cache_dir(oi.APPNAME, oi.APPAUTHOR))
            )
        else:
            self.stop_session()

    @Slot()
    def stop_session(self):
        """Stop the current CAN session."""
        if self._network is not None:
            try:
                self._network.disconnect()
            except can.exceptions.CanOperationError:
                pass
        self._network = None
        self._model.device_db = None
        self._model.node_id = 0
