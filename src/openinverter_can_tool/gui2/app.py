import sys
from PySide6.QtWidgets import QApplication
import logging

from .controllers.main_ctrl import MainController
from .model.model import Model
from .views.main_view import MainView

from .resources import openinverter_can_tool_rc  # noqa: F401

logging.basicConfig(level=logging.DEBUG)


class App(QApplication):
    """OpenInverter CAN Tool application which owns the data model, main
    window and controller"""

    def __init__(self, sys_argv):
        super(App, self).__init__(sys_argv)
        self.model = Model()
        self.main_controller = MainController(self.model)
        self.main_view = MainView(self.model, self.main_controller)
        self.main_view.show()


def main() -> None:
    app = App(sys.argv)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
