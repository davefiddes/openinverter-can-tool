from typing import Optional

from PySide6.QtCore import QObject, Signal

from ...oi_node import OpenInverterNode
from .param_model import ParameterTableModel


class Model(QObject):
    """Main application data model"""
    node_changed = Signal(OpenInverterNode)
    connected_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self._node: Optional[OpenInverterNode] = None
        self.params = ParameterTableModel()

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
