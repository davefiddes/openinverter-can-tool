"""Delegate for parameter editing with type-specific editors"""

from typing import Union, cast

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox,
                               QDoubleSpinBox, QFrame, QPushButton,
                               QStyledItemDelegate, QVBoxLayout, QWidget)

from ...paramdb import OIVariable
from .parameter_value_item import ParameterValueItem


class BitfieldPopup(QFrame):
    """Popup widget for bitfield selection with checkboxes."""

    def __init__(
        self, parent: QWidget, param: OIVariable, editor: 'BitfieldEditor'
    ) -> None:
        super().__init__(parent)
        self.param = param
        self.editor = editor
        self.checkboxes: dict[int, QCheckBox] = {}

        flags = Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        self.setWindowFlags(flags)
        self.setFrameShape(QFrame.Shape.Box)
        self.setFrameShadow(QFrame.Shadow.Plain)

        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Create checkboxes for each bit definition (filtering out 0)
        for bit_value, bit_name in sorted(param.bit_definitions.items()):
            if bit_value != 0:
                checkbox = QCheckBox(bit_name)
                self.checkboxes[bit_value] = checkbox
                layout.addWidget(checkbox)

        # Add done button
        done_button = QPushButton("Done")
        done_button.clicked.connect(self._on_done_clicked)
        layout.addSpacing(8)
        layout.addWidget(done_button)

        self.setLayout(layout)

    def _on_done_clicked(self) -> None:
        """Handle Done button click by closing the editor."""
        self._value = self.get_value()
        self.editor.hidePopup()

    def get_value(self) -> int:
        """Get the combined bitfield value from checked checkboxes."""
        result = 0
        for bit_value, checkbox in self.checkboxes.items():
            if checkbox.isChecked():
                result |= bit_value
        return result

    def set_value(self, value: int) -> None:
        """Set which checkboxes are checked based on the bitfield value."""
        for bit_value, checkbox in self.checkboxes.items():
            checkbox.setChecked(bool(bit_value & value))


class BitfieldEditor(QComboBox):
    """Custom dropdown editor for bitfield parameters with checkboxes."""

    def __init__(self, parent: QWidget, param: OIVariable) -> None:
        super().__init__(parent)
        self.param = param
        self.popup_widget: BitfieldPopup | None = None
        self._value = 0
        self._popup_shown = False

        # Add a placeholder item
        self.addItem("Select bits...")
        self.setCurrentIndex(0)

    def showEvent(self, event) -> None:
        """Show popup automatically when editor becomes visible."""
        super().showEvent(event)
        if not self._popup_shown:
            self._popup_shown = True
            self.showPopup()

    def showPopup(self) -> None:
        """Show the custom checkbox popup."""
        if self.popup_widget is None:
            self.popup_widget = BitfieldPopup(self, self.param, self)
            self.popup_widget.set_value(self._value)

        # Position popup below the combobox
        pos = self.mapToGlobal(self.rect().bottomLeft())
        self.popup_widget.move(pos)
        self.popup_widget.show()

    def hidePopup(self) -> None:
        """Hide the custom popup and close the editor."""
        if self.popup_widget:
            self._value = self.popup_widget.get_value()
            self.popup_widget.hide()
        # Force focus away to trigger editor close
        self.clearFocus()

    def get_value(self) -> int:
        """Get the current bitfield value."""
        if self.popup_widget:
            return self.popup_widget.get_value()
        return self._value

    def set_value(self, value: int) -> None:
        """Set the bitfield value."""
        self._value = value
        if self.popup_widget:
            self.popup_widget.set_value(value)


class ParameterDelegate(QStyledItemDelegate):
    """
    Custom delegate for editing parameters with type-specific editors.
    """

    def createEditor(
        self,
        parent: QWidget,
        option,
        index: Union[QModelIndex, QPersistentModelIndex],
    ) -> QWidget:
        """Create the appropriate editor based on parameter type."""
        # Get the model from the parent view
        view = cast(QAbstractItemView, self.parent())
        model = cast(QStandardItemModel, view.model())

        item = model.itemFromIndex(index)

        if not isinstance(item, ParameterValueItem):
            return super().createEditor(parent, option, index)

        param: OIVariable = item.param

        # Handle bit definitions - checkboxes for each bit
        if param.bit_definitions:
            return self._create_bitfield_editor(parent, param)

        # Handle value descriptions - dropdown
        if param.value_descriptions:
            return self._create_enum_editor(parent, param)

        # Handle regular numeric parameters
        return self._create_numeric_editor(parent, param)

    def _create_numeric_editor(
        self, parent: QWidget, param: OIVariable
    ) -> QDoubleSpinBox:
        """Create a QDoubleSpinBox editor for numeric parameters."""
        editor = QDoubleSpinBox(parent)

        # Set some defaults for the spin box based on parameter metadata
        assert param.min is not None and param.max is not None
        editor.setRange(param.min, param.max)
        editor.setSingleStep(1.0)
        editor.setDecimals(2)

        # Set unit as suffix if available
        if param.unit:
            editor.setSuffix(f" {param.unit}")

        return editor

    def _create_enum_editor(
        self, parent: QWidget, param: OIVariable
    ) -> QComboBox:
        """Create a QComboBox editor for enum parameters."""
        editor = QComboBox(parent)

        # Add items from value descriptions
        for value, description in param.value_descriptions.items():
            editor.addItem(description, userData=value)

        return editor

    def _create_bitfield_editor(
        self, parent: QWidget, param: OIVariable
    ) -> BitfieldEditor:
        """Create a BitfieldEditor widget for bitfield parameters."""
        return BitfieldEditor(parent, param)

    def setEditorData(
        self, editor: QWidget, index: Union[QModelIndex, QPersistentModelIndex]
    ) -> None:
        """Set the editor data from the model."""
        view = cast(QAbstractItemView, self.parent())
        model = cast(QStandardItemModel, view.model())

        item = model.itemFromIndex(index)

        if not isinstance(item, ParameterValueItem):
            super().setEditorData(editor, index)
            return

        current_value = item.value

        if isinstance(editor, QDoubleSpinBox):
            editor.setValue(current_value)
        elif isinstance(editor, BitfieldEditor):
            editor.set_value(int(current_value))
        elif isinstance(editor, QComboBox):
            # Find the index of current value
            for i in range(editor.count()):
                if editor.itemData(i) == current_value:
                    editor.setCurrentIndex(i)
                    break
        else:
            super().setEditorData(editor, index)

    def setModelData(
        self,
        editor: QWidget,
        model,
        index: Union[QModelIndex, QPersistentModelIndex],
    ) -> None:
        """Set the model data from the editor."""
        std_model = cast(QStandardItemModel, model)
        item = std_model.itemFromIndex(index)

        if not isinstance(item, ParameterValueItem):
            super().setModelData(editor, model, index)
            return

        if isinstance(editor, QDoubleSpinBox):
            item.value = editor.value()
        elif isinstance(editor, BitfieldEditor):
            item.value = editor.get_value()
        elif isinstance(editor, QComboBox):
            item.value = editor.currentData()
        else:
            super().setModelData(editor, model, index)
