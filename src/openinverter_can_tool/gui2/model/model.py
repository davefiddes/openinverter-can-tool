from typing import Dict, Optional

from PySide6.QtCore import QObject, Signal

from ...oi_node import OpenInverterNode
from .parameter_model import ParameterModel
from .spot_value_model import SpotValueModel


class Model(QObject):
    """Main application data model"""
    node_changed = Signal(OpenInverterNode)
    connected_changed = Signal(bool)
    parameter_changed = Signal(str, float)

    def __init__(self):
        super().__init__()
        self._node: Optional[OpenInverterNode] = None

        self.spot_value_model = SpotValueModel()
        self.parameter_changed.connect(self.spot_value_model.parameter_changed)

        self.param_model = ParameterModel()
        self.parameter_changed.connect(self.param_model.parameter_changed)

        self.param_values: Dict[str, float] = {}

    @property
    def node(self) -> Optional[OpenInverterNode]:
        return self._node

    @node.setter
    def node(self, value: Optional[OpenInverterNode]):
        self._node = value
        self.node_changed.emit(value)
        self.connected_changed.emit(value is not None)

    @property
    def connected(self) -> bool:
        """Check if the node is connected."""
        return self._node is not None

    def update_value(self, param_name: str, value: float):
        """Update the value of a parameter and emit the signal."""
        self.param_values[param_name] = value
        self.parameter_changed.emit(param_name, value)
