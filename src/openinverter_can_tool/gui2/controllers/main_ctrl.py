from pathlib import Path

import appdirs
import canopen
from can.exceptions import CanOperationError
from canopen import SdoAbortedError, SdoCommunicationError
from PySide6.QtCore import QObject, Signal, Slot

from ... import constants as oi
from ...oi_node import OpenInverterNode
from ...paramdb import import_cached_database, OIVariable
from ...fpfloat import fixed_to_float
from ..model.model import Model

# Define a constant for connection exceptions which we want to handle
# in lots of places
CAN_EXCEPTIONS = (
    SdoAbortedError,
    SdoCommunicationError,
    CanOperationError,
    OSError)


class MainController(QObject):
    """Control the behaviour of the application."""

    can_error = Signal(str)

    def __init__(self, model: Model):
        super().__init__()

        self._model = model
        self._network = canopen.Network()

    @Slot(int)
    def start_new_session(self, node_id: int):
        """Start a new session with the given node ID."""
        assert self._network is not None

        if node_id not in range(0, 128):
            raise ValueError("Node ID must be between 0 and 127.")

        try:
            if self._model.connected:
                self.stop_session()

            self._network.connect()
            self._network.check()

            device_db = import_cached_database(
                self._network,
                node_id,
                Path(appdirs.user_cache_dir(oi.APPNAME, oi.APPAUTHOR))
            )
            self._model.node = OpenInverterNode(
                self._network,
                node_id,
                device_db
            )
            self._model.node.sdo.RESPONSE_TIMEOUT = 1.0

            self._fill_model_from_node()
        except CAN_EXCEPTIONS as e:
            try:
                self._network.disconnect()
            except CanOperationError:
                # stifle any errors from disconnecting they may have happened
                # during the connect
                pass
            self._model.node = None
            self.can_error.emit(f"Error starting session: {e}")

    @Slot()
    def stop_session(self):
        """Stop the current CAN session."""
        try:
            self._network.disconnect()
            self._model.node = None
        except CAN_EXCEPTIONS as e:
            self.can_error.emit(f"Error stopping session: {e}")

    def _fill_model_from_node(self):
        """Fill the model with values from the node."""
        node = self._model.node
        assert node
        device_db = node.object_dictionary
        assert device_db

        for item in device_db.names.values():
            assert isinstance(item, OIVariable)
            if item.isparam:
                try:
                    value = fixed_to_float(int(node.sdo[item.name].raw))
                except SdoAbortedError as e:
                    self.can_error.emit(
                        f"Failed to read parameter {item.name}: {e}")
                    value = 0.0
                self._model.params.append_param(item, value)
