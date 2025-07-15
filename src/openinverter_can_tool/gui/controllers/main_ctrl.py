from PySide6.QtCore import QObject, Slot

from ..model.model import Model


class MainController(QObject):
    """Control the behaviour of the application."""

    def __init__(self, model: Model):
        super().__init__()

        self._model = model

    @Slot(int)
    def change_amount(self, value: int):
        self._model.amount = value

        # calculate even or odd
        self._model.even_odd = 'odd' if value % 2 else 'even'

        # calculate button enabled state
        self._model.enable_reset = True if value else False
