from pathlib import Path

import appdirs
import canopen
from can.exceptions import CanOperationError
from canopen import SdoAbortedError, SdoCommunicationError
from PySide6.QtCore import QObject, Signal, Slot

from ... import constants as oi
from ...fpfloat import fixed_from_float, fixed_to_float
from ...oi_node import OpenInverterNode
from ...paramdb import import_cached_database, OIVariable
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

        self._model.param_model.parameter_changed.connect(
            self._on_parameter_changed)

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

            self._model.param_model.populate_from_database(device_db)
            self._model.spot_value_model.populate_from_database(device_db)

            self.refresh_values()

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

    @Slot()
    def refresh_values(self) -> None:
        """Fill the model with values from the node."""
        node = self._model.node
        assert node
        device_db = node.object_dictionary
        assert device_db

        try:
            # Disconnect parameter_changed while we refresh
            self._model.param_model.parameter_changed.disconnect(
                self._on_parameter_changed)

            for param_name in device_db.names:
                value = fixed_to_float(int(node.sdo[param_name].raw))

                param_item = device_db.names[param_name]
                if isinstance(param_item, OIVariable):
                    if param_item.isparam:
                        self._model.param_model.set_value(param_name, value)
                    else:
                        self._model.spot_value_model.set_value(
                            param_name, value)
        except CAN_EXCEPTIONS as e:
            self.can_error.emit(
                f"Failed to refresh parameter values: {e}")
        finally:
            self._model.param_model.parameter_changed.connect(
                self._on_parameter_changed)

    @Slot(str, float)
    def _on_parameter_changed(self, param_name: str, value: float) -> None:
        """Handle parameter changes and write them to the node."""

        if not self._model.connected or self._model.node is None:
            return

        try:
            node = self._model.node
            node.sdo[param_name].raw = fixed_from_float(value)
        except CAN_EXCEPTIONS as e:
            self.can_error.emit(
                f"Failed to write parameter {param_name}: {e}")
