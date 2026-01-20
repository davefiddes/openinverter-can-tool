"""
Unit tests for the MVC ParameterModel used to manage device parameters.
"""

import unittest
from typing import Optional
from unittest.mock import MagicMock

from PySide6.QtGui import QStandardItem

from openinverter_can_tool.fpfloat import fixed_from_float
from openinverter_can_tool.gui2.model.parameter_model import ParameterModel
from openinverter_can_tool.gui2.model.parameter_value_item import \
    ParameterValueItem
from openinverter_can_tool.paramdb import OIVariable


def find_parameter_name_item(
    model: ParameterModel, param_name: str
) -> Optional[QStandardItem]:
    """Helper function to find a parameter item by name."""
    for category_row in range(model.rowCount()):
        category_item = model.item(category_row, 0)
        for param_row in range(category_item.rowCount()):
            name_item = category_item.child(param_row, 0)
            if name_item.text() == param_name:
                return name_item
    return None


def find_parameter_value_item(
        model: ParameterModel, param_name: str
) -> Optional[ParameterValueItem]:
    """Helper function to find a ParameterValueItem by parameter name."""
    for category_row in range(model.rowCount()):
        category_item = model.item(category_row, 0)
        for param_row in range(category_item.rowCount()):
            name_item = category_item.child(param_row, 0)
            value_item = category_item.child(param_row, 1)
            if name_item.text() == param_name:
                return value_item  # type: ignore
    return None


class TestParameterModelInitialization(unittest.TestCase):
    """Tests for ParameterModel initialization."""

    def test_creates_with_correct_headers(self):
        model = ParameterModel()

        self.assertEqual(model.columnCount(), 2)
        self.assertEqual(model.horizontalHeaderItem(0).text(), "Name")
        self.assertEqual(model.horizontalHeaderItem(1).text(), "Value")

    def test_is_empty_initially(self):
        model = ParameterModel()

        self.assertEqual(model.rowCount(), 0)


class TestParameterModelPopulateFromDatabase(unittest.TestCase):
    """Tests for populating model from device database."""

    def setUp(self):
        self.model = ParameterModel()
        self.device_db = MagicMock()

    def test_clears_existing_data_when_populating(self):
        # Add an initial row
        self.model.appendRow([QStandardItem("Initial"), QStandardItem("Data")])
        initial_row_count = self.model.rowCount()
        self.assertGreater(initial_row_count, 0)

        # Populate with empty database
        self.device_db.names = {}
        self.model.populate_from_database(self.device_db)

        self.assertEqual(self.model.rowCount(), 0)

    def test_ignores_non_oivariable_entries(self):
        param = OIVariable("valid_param", 1)
        param.isparam = True
        param.category = "Test"

        self.device_db.names = {
            "valid_param": param,
            "invalid_entry": "not_a_variable",
            "another_invalid": 42,
        }

        self.model.populate_from_database(self.device_db)

        param_item = find_parameter_name_item(self.model, "valid_param")
        assert isinstance(param_item, QStandardItem)
        self.assertIn("valid_param", param_item.text())

    def test_ignores_non_parameter_variables(self):
        non_param = OIVariable("notparam", 1)
        non_param.isparam = False
        non_param.category = "Test"

        self.device_db.names = {"notparam": non_param}

        self.model.populate_from_database(self.device_db)

        param_item = find_parameter_name_item(self.model, "notparam")
        self.assertIsNone(param_item)

    def test_creates_category_for_parameter(self):
        param = OIVariable("testparam", 1)
        param.isparam = True
        param.category = "Motor Control"

        self.device_db.names = {"testparam": param}

        self.model.populate_from_database(self.device_db)

        category_items = self.model.findItems("Motor Control")
        self.assertEqual(len(category_items), 1)
        self.assertEqual(category_items[0].text(), "Motor Control")

    def test_uses_uncategorized_for_parameters_without_category(self):
        param = OIVariable("testparam", 1)
        param.isparam = True
        param.category = None

        self.device_db.names = {"testparam": param}

        self.model.populate_from_database(self.device_db)

        uncategorized = self.model.findItems("Uncategorized")
        self.assertEqual(len(uncategorized), 1)

    def test_adds_parameter_under_correct_category(self):
        param = OIVariable("testparam", 1)
        param.isparam = True
        param.category = "Motor"

        self.device_db.names = {"testparam": param}

        self.model.populate_from_database(self.device_db)

        category_row = self.model.findItems("Motor")[0]
        self.assertEqual(category_row.rowCount(), 1)
        self.assertEqual(category_row.child(0, 0).text(), "testparam")

    def test_groups_multiple_parameters_in_same_category(self):
        param1 = OIVariable("param1", 1)
        param1.isparam = True
        param1.category = "Motor"

        param2 = OIVariable("param2", 2)
        param2.isparam = True
        param2.category = "Motor"

        self.device_db.names = {"param1": param1, "param2": param2}

        self.model.populate_from_database(self.device_db)

        category_row = self.model.findItems("Motor")[0]
        self.assertEqual(category_row.rowCount(), 2)

    def test_creates_separate_categories_for_different_types(self):
        param1 = OIVariable("param1", 1)
        param1.isparam = True
        param1.category = "Motor"

        param2 = OIVariable("param2", 2)
        param2.isparam = True
        param2.category = "Thermal"

        self.device_db.names = {"param1": param1, "param2": param2}

        self.model.populate_from_database(self.device_db)

        motor_items = self.model.findItems("Motor")
        thermal_items = self.model.findItems("Thermal")
        self.assertEqual(len(motor_items), 1)
        self.assertEqual(len(thermal_items), 1)

    def test_parameter_value_item_is_editable(self):
        from PySide6.QtCore import Qt

        param = OIVariable("testparam", 1)
        param.isparam = True
        param.category = "Test"

        self.device_db.names = {"testparam": param}

        self.model.populate_from_database(self.device_db)

        value_item = find_parameter_value_item(self.model, "testparam")
        assert isinstance(value_item, ParameterValueItem)
        flags = value_item.flags()
        self.assertTrue(flags & Qt.ItemFlag.ItemIsEditable)

    def test_repopulating_model_replaces_old_data(self):
        param1 = OIVariable("param1", 1)
        param1.isparam = True
        param1.category = "Test"

        self.device_db.names = {"param1": param1}
        self.model.populate_from_database(self.device_db)

        # Populate again with different parameter
        param2 = OIVariable("param2", 2)
        param2.isparam = True
        param2.category = "Test"

        self.device_db.names = {"param2": param2}
        self.model.populate_from_database(self.device_db)

        self.assertIsNone(find_parameter_name_item(self.model, "param1"))
        self.assertIsNotNone(find_parameter_name_item(self.model, "param2"))


class TestParameterModelSetValue(unittest.TestCase):
    """Tests for setting parameter values."""

    def setUp(self):
        self.model = ParameterModel()
        self.device_db = MagicMock()

        param = OIVariable("testparam", 1)
        param.isparam = True
        param.category = "Test"
        param.min = fixed_from_float(0.0)
        param.max = fixed_from_float(100.0)

        self.device_db.names = {"testparam": param}
        self.model.populate_from_database(self.device_db)

    def test_ignores_set_value_for_nonexistent_parameter(self):
        # Should not raise
        self.model.set_value("unknown_param", 42.0)

    def test_emits_signal_when_externally_setting_the_value(self):
        signal_mock = MagicMock()
        self.model.parameter_changed.connect(signal_mock)

        self.model.set_value("testparam", 42.0)

        signal_mock.assert_called_with("testparam", 42.0)

    def test_emits_signal_when_value_item_is_edited(self):
        signal_mock = MagicMock()
        self.model.parameter_changed.connect(signal_mock)

        # Simulate user editing the value
        category_row = self.model.findItems("Test")[0]
        item = category_row.child(0, 1)
        assert isinstance(item, ParameterValueItem)
        item.value = 84.5

        signal_mock.assert_called_with("testparam", 84.5)


class TestParameterModelSerialization(unittest.TestCase):
    """Tests for JSON serialization"""

    def setUp(self):
        self.model = ParameterModel()
        self.device_db = MagicMock()

        param1 = OIVariable("param1", 1)
        param1.isparam = True
        param1.category = "Test"
        param1.min = fixed_from_float(0.0)
        param1.max = fixed_from_float(100.0)

        param2 = OIVariable("param2", 2)
        param2.isparam = True
        param2.category = "Test"
        param2.min = fixed_from_float(0.0)
        param2.max = fixed_from_float(100.0)

        self.device_db.names = {"param1": param1, "param2": param2}
        self.model.populate_from_database(self.device_db)

    def test_to_json_returns_dict(self):
        result = self.model.to_json()

        self.assertIsInstance(result, dict)

    def test_to_json_includes_all_parameters(self):
        self.model.set_value("param1", 10.0)
        self.model.set_value("param2", 20.0)

        result = self.model.to_json()

        self.assertIn("param1", result)
        self.assertIn("param2", result)

    def test_to_json_includes_correct_values(self):
        self.model.set_value("param1", 42.5)
        self.model.set_value("param2", 99.9)

        result = self.model.to_json()

        self.assertEqual(result["param1"], 42.5)
        self.assertEqual(result["param2"], 99.9)

    def test_to_json_returns_empty_dict_when_no_parameters(self):
        empty_model = ParameterModel()

        result = empty_model.to_json()

        self.assertEqual(result, {})


class TestParameterValueItemRangeCheckFloat(unittest.TestCase):
    """Tests for ParameterValueItem range checking with float parameters."""

    def test_initialise_valid_float_value_has_no_error(self):
        param = OIVariable("test_param", 1)
        param.min = fixed_from_float(0.0)
        param.max = fixed_from_float(100.0)

        item = ParameterValueItem(param, 60.0)

        self.assertEqual(item.error, "")

    def test_set_valid_float_value_has_no_error(self):
        param = OIVariable("test_param", 1)
        param.min = fixed_from_float(0.0)
        param.max = fixed_from_float(100.0)

        item = ParameterValueItem(param, 0.0)
        item.value = 75.5

        self.assertEqual(item.error, "")

    def test_initialise_float_value_too_large_sets_error(self):
        param = OIVariable("test_param", 1)
        param.min = fixed_from_float(0.0)
        param.max = fixed_from_float(100.0)

        item = ParameterValueItem(param, 155.5)

        expected_error = (
            "Value 155.5 is larger than the maximum value "
            "100 allowed for test_param"
        )
        self.assertEqual(item.error, expected_error)
        self.assertEqual(item.value, 155.5)

    def test_set_float_value_too_large_sets_error(self):
        param = OIVariable("test_param", 1)
        param.min = fixed_from_float(0.0)
        param.max = fixed_from_float(100.0)

        item = ParameterValueItem(param, 50)
        item.value = 155.5

        expected_error = (
            "Value 155.5 is larger than the maximum value "
            "100 allowed for test_param"
        )
        self.assertEqual(item.error, expected_error)
        self.assertEqual(item.value, 155.5)

    def test_set_float_value_too_small_sets_error(self):
        param = OIVariable("test_param", 1)
        param.min = fixed_from_float(0.0)
        param.max = fixed_from_float(100.0)

        item = ParameterValueItem(param, -10.0)

        expected_error = (
            "Value -10 is smaller than the minimum value "
            "0 allowed for test_param"
        )
        self.assertEqual(item.error, expected_error)
        self.assertEqual(item.value, -10.0)

    def test_float_out_of_range_error_with_different_param_name(self):
        param = OIVariable("my_param", 1)
        param.min = fixed_from_float(0.0)
        param.max = fixed_from_float(100.0)

        item = ParameterValueItem(param, 155.5)

        expected_error = (
            "Value 155.5 is larger than the maximum value "
            "100 allowed for my_param"
        )
        self.assertEqual(item.error, expected_error)


class TestParameterValueItemRangeCheckEnum(unittest.TestCase):
    """Tests for ParameterValueItem range checking with enum parameters."""

    def test_set_valid_enum_value_has_no_error(self):
        param = OIVariable("test_param", 1)
        param.value_descriptions = {1: "OptionA", 2: "OptionB"}

        item = ParameterValueItem(param, 1.0)

        self.assertEqual(item.error, "")

    def test_set_enum_value_that_doesnt_exist_sets_error(self):
        param = OIVariable("test_param", 1)
        param.value_descriptions = {1: "OptionA", 2: "OptionB"}

        item = ParameterValueItem(param, 3)

        expected_error = (
            "Unable to find value: '3' for parameter: test_param. "
            "Valid values are {1: 'OptionA', 2: 'OptionB'}"
        )
        self.assertEqual(item.error, expected_error)
        self.assertEqual(item.value, 3.0)


class TestParameterValueItemRangeCheckBitfield(unittest.TestCase):
    """Tests for ParameterValueItem range checking with bitfield parameters."""

    def test_set_valid_bitfield_value_has_no_error(self):
        param = OIVariable("test_param", 1)
        param.bit_definitions = {1: "BitA", 2: "BitB"}

        item = ParameterValueItem(param, 0x01 | 0x02)

        self.assertEqual(item.error, "")
        self.assertEqual(item.value, 3.0)

    def test_set_bitfield_value_that_doesnt_exist_sets_error(self):
        param = OIVariable("test_param", 1)
        param.bit_definitions = {1: "BitA", 2: "BitB"}

        item = ParameterValueItem(param, 4)

        expected_error = (
            "Unable to find bit: '4' for parameter: test_param. "
            "Valid bits are {1: 'BitA', 2: 'BitB'}"
        )
        self.assertEqual(item.error, expected_error)
        self.assertEqual(item.value, 4.0)

    def test_bitfield_zero_value_has_no_error(self):
        param = OIVariable("test_param", 1)
        param.bit_definitions = {1: "BitA", 2: "BitB"}

        item = ParameterValueItem(param, 0.0)

        self.assertEqual(item.error, "")


class TestParameterValueItemDisplay(unittest.TestCase):
    """Tests for ParameterValueItem display formatting."""

    def test_display_shows_value_and_unit(self):
        param = OIVariable("test_param", 1)
        param.unit = "km/h"
        param.min = fixed_from_float(0.0)
        param.max = fixed_from_float(100.0)

        item = ParameterValueItem(param, 42.5)

        self.assertEqual(item.text(), "42.5 km/h")

    def test_display_without_unit(self):
        param = OIVariable("test_param", 1)
        param.unit = ""
        param.min = fixed_from_float(0.0)
        param.max = fixed_from_float(100.0)

        item = ParameterValueItem(param, 42.5)

        self.assertEqual(item.text(), "42.5")

    def test_display_without_unit_for_enum(self):
        param = OIVariable("test_param", 1)
        param.unit = "km/h"
        param.value_descriptions = {1: "OptionA", 2: "OptionB"}

        item = ParameterValueItem(param, 1.0)

        self.assertEqual(item.text(), "OptionA")

    def test_display_without_unit_for_bitfield(self):
        param = OIVariable("test_param", 1)
        param.unit = "flags"
        param.bit_definitions = {1: "BitA", 2: "BitB"}

        item = ParameterValueItem(param, 3.0)

        self.assertEqual(item.text(), "BitA, BitB")

    def test_display_updates_when_value_changes(self):
        param = OIVariable("test_param", 1)
        param.unit = "V"
        param.min = fixed_from_float(0.0)
        param.max = fixed_from_float(100.0)

        item = ParameterValueItem(param, 10.0)
        self.assertEqual(item.text(), "10 V")

        item.value = 20.0
        self.assertEqual(item.text(), "20 V")


if __name__ == "__main__":
    unittest.main()
