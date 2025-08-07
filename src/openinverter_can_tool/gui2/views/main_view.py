from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (QInputDialog, QLabel, QMainWindow, QMessageBox,
                               QTabWidget)

from ..controllers.main_ctrl import MainController
from ..model.model import Model
from ..views.param_view import ParamTableView


class MainView(QMainWindow):
    """Main application window and view of the application data"""

    def __init__(self, model: Model, main_controller: MainController):
        super().__init__()

        self._model = model
        self._main_controller = main_controller
        self._main_controller.can_error.connect(self._on_can_error)

        # construct the UI
        self.setWindowTitle("OpenInverter CAN Tool")
        self.resize(800, 600)

        self.create_central_widget()
        self.create_actions()
        self.create_menus()
        self.create_tool_bars()
        self.create_status_bar()

        # listen for model event signals
        self._model.connected_changed.connect(self.on_connected_changed)

        # set a default value
        self.on_connected_changed(False)

    def closeEvent(self, event):
        """
        Handle the close event to ensure any ongoing CAN session is properly
        cleaned up.
        """
        self._main_controller.can_error.disconnect()
        self._main_controller.stop_session()
        event.accept()

    @Slot(bool)
    def on_connected_changed(self, connected: bool):
        if connected:
            assert self._model.node is not None
            self._connected_status.setText(f"Node ID: {self._model.node.id}")
        else:
            self._connected_status.setText("Disconnected")

        self._close_act.setEnabled(connected)
        self._load_act.setEnabled(connected)
        self._save_act.setEnabled(connected)
        self._upgrade_act.setEnabled(connected)
        self._refresh_act.setEnabled(connected)

    @Slot()
    def _on_about(self) -> None:
        QMessageBox.about(
            self,
            "About OpenInverter CAN Tool",
            "A tool to allow configuration and operating of OpenInverter "
            "systems for electric vehicles over a CAN connection.")

    @Slot()
    def _on_not_implemented(self) -> None:
        QMessageBox.critical(self, "Unimplemented Error",
                             "This function has not been implemented yet")

    @Slot()
    def _on_can_error(self, message: str) -> None:
        QMessageBox.critical(self, "CAN Error", message)

    @Slot()
    def _on_new_session(self) -> None:
        node_id, ok = QInputDialog.getInt(
            self, "New Session", "Enter the node ID for the new session:",
            value=1, minValue=1, maxValue=127)

        if ok:
            self._main_controller.start_new_session(node_id)

    def create_actions(self):
        icon = QIcon(':/icons/window-new.png')
        self._new_act = QAction(
            icon, "&New Session...", self,
            statusTip="Start a new configuration session with a device",
            shortcut=QKeySequence(QKeySequence.StandardKey.New)
        )
        self._new_act.triggered.connect(self._on_new_session)

        self._close_act = QAction(
            "Disconnect", self,
            statusTip="Disconnect from the current configuration session",
            shortcut=QKeySequence(QKeySequence.StandardKey.Close)
        )
        self._close_act.triggered.connect(self._main_controller.stop_session)

        icon = QIcon(':/icons/document-open.png')
        self._load_act = QAction(
            icon, "&Load Parameters...", self,
            statusTip="Load a set of parameters onto a device",
            shortcut=QKeySequence(QKeySequence.StandardKey.Open)
        )
        self._load_act.triggered.connect(self._on_not_implemented)

        icon = QIcon(':/icons/document-save-as.png')
        self._save_act = QAction(
            icon, "&Save Parameters...", self,
            statusTip="Save the current parameters to disk",
            shortcut=QKeySequence(QKeySequence.StandardKey.Save)
        )
        self._save_act.triggered.connect(self._on_not_implemented)

        icon = QIcon(':/icons/go-up.png')
        self._upgrade_act = QAction(
            icon, "&Upgrade Firmware...", self,
            statusTip="Upgrade the firmware on a device to a new version",
            shortcut=QKeySequence(
                Qt.Modifier.CTRL | Qt.Key.Key_U)  # type: ignore
        )
        self._upgrade_act.triggered.connect(self._on_not_implemented)

        self._exit_act = QAction(
            "E&xit", self,
            statusTip="Exit the application",
            shortcut=QKeySequence(QKeySequence.StandardKey.Quit)
        )
        self._exit_act.triggered.connect(self.close)

        icon = QIcon(':/icons/view-refresh.png')
        self._refresh_act = QAction(
            icon, "&Refresh", self,
            statusTip="Refresh the parameters downloaded from the device",
            shortcut=QKeySequence(QKeySequence.StandardKey.Refresh)
        )
        self._refresh_act.triggered.connect(self._on_not_implemented)

        self._auto_refresh_act = QAction(
            "&Auto Refresh", self, checkable=True, checked=False,
            statusTip="Enable or disable the automatic refresh of parameters "
            "and spot values"
        )
        self._auto_refresh_act.triggered.connect(self._on_not_implemented)

        self._about_act = QAction(
            "&About", self,
            statusTip="Show the application's About box"
        )
        self._about_act.triggered.connect(self._on_about)

    def create_menus(self):
        self._file_menu = self.menuBar().addMenu("&File")
        self._file_menu.addAction(self._new_act)
        self._file_menu.addAction(self._close_act)
        self._file_menu.addSeparator()
        self._file_menu.addAction(self._load_act)
        self._file_menu.addAction(self._save_act)
        self._file_menu.addAction(self._upgrade_act)
        self._file_menu.addSeparator()
        self._file_menu.addAction(self._exit_act)

        self._device_menu = self.menuBar().addMenu("&View")
        self._device_menu.addAction(self._refresh_act)
        self._device_menu.addAction(self._auto_refresh_act)

        self.menuBar().addSeparator()

        self._help_menu = self.menuBar().addMenu("&Help")
        self._help_menu.addAction(self._about_act)

    def create_tool_bars(self):
        self._file_tool_bar = self.addToolBar("File")
        self._file_tool_bar.addAction(self._new_act)
        self._file_tool_bar.addAction(self._load_act)
        self._file_tool_bar.addAction(self._save_act)
        self._file_tool_bar.addAction(self._upgrade_act)

        self._device_tool_bar = self.addToolBar("View")
        self._device_tool_bar.addAction(self._refresh_act)

    def create_status_bar(self):
        self.statusBar().showMessage("Ready")
        self._connected_status = QLabel()
        self.statusBar().addPermanentWidget(self._connected_status)

    def create_central_widget(self):
        """Create the central widget for the main window."""
        # Create tab widget
        tab_widget = QTabWidget()

        # Parameters tab
        param_table_view = ParamTableView()
        param_table_view.setModel(self._model.params)
        tab_widget.addTab(param_table_view, "Parameters")

        self.setCentralWidget(tab_widget)
