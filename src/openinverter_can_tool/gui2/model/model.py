from typing import Optional

import canopen
from PySide6.QtCore import QObject, Signal


class Model(QObject):
    """Main application data model"""
    amount_changed = Signal(int)
    even_odd_changed = Signal(str)
    enable_reset_changed = Signal(bool)
    node_id_changed = Signal(int)
    device_db_changed = Signal(canopen.ObjectDictionary)

    @property
    def amount(self) -> int:
        return self._amount

    @amount.setter
    def amount(self, value: int):
        self._amount = value
        self.amount_changed.emit(value)

    @property
    def even_odd(self) -> str:
        return self._even_odd

    @even_odd.setter
    def even_odd(self, value: str):
        self._even_odd = value
        self.even_odd_changed.emit(value)

    @property
    def enable_reset(self) -> bool:
        return self._enable_reset

    @enable_reset.setter
    def enable_reset(self, value: bool):
        self._enable_reset = value
        self.enable_reset_changed.emit(value)

    @property
    def node_id(self) -> int:
        return self._node_id

    @node_id.setter
    def node_id(self, value: int):
        self._node_id = value
        self.node_id_changed.emit(value)

    @property
    def device_db(self) -> Optional[canopen.ObjectDictionary]:
        return self._device_db

    @device_db.setter
    def device_db(self, value: Optional[canopen.ObjectDictionary]):
        self._device_db = value
        self.device_db_changed.emit(value)
