from PySide6.QtCore import Slot
from PySide6.QtWidgets import (QLabel, QMainWindow, QPushButton, QSpinBox,
                               QVBoxLayout, QWidget)

from ..controllers.main_ctrl import MainController
from ..model.model import Model


class MainView(QMainWindow):
    """Main application window and view of the application data"""

    def __init__(self, model: Model, main_controller: MainController):
        super().__init__()

        self._model = model
        self._main_controller = main_controller

        # construct the UI
        self.setWindowTitle("openinverter CAN Tool")

        widget = QWidget()
        self.setCentralWidget(widget)

        layout = QVBoxLayout(widget)

        self._spinBox_amount = QSpinBox()
        layout.addWidget(self._spinBox_amount)

        self._label_even_odd = QLabel()
        layout.addWidget(self._label_even_odd)

        self._pushButton_reset = QPushButton("reset")
        layout.addWidget(self._pushButton_reset)

        # connect widgets to controller
        self._spinBox_amount.valueChanged.connect(
            self._main_controller.change_amount)
        self._pushButton_reset.clicked.connect(
            lambda: self._main_controller.change_amount(0))

        # listen for model event signals
        self._model.amount_changed.connect(self.on_amount_changed)
        self._model.even_odd_changed.connect(self.on_even_odd_changed)
        self._model.enable_reset_changed.connect(self.on_enable_reset_changed)

        # set a default value
        self._main_controller.change_amount(42)

    @Slot(int)
    def on_amount_changed(self, value: int):
        self._spinBox_amount.setValue(value)

    @Slot(str)
    def on_even_odd_changed(self, value: str):
        self._label_even_odd.setText(value)

    @Slot(bool)
    def on_enable_reset_changed(self, value: bool):
        self._pushButton_reset.setEnabled(value)
