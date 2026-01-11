"""
Unit tests for MVC ErrorModel used to enumerate device errors
"""

import unittest
from datetime import timedelta

from src.openinverter_can_tool.gui2.model.error_model import ErrorModel


# Reduce test verbosity
# pylint: disable=missing-function-docstring

class TestErrorModelInitialization(unittest.TestCase):
    """Tests for ErrorModel initialization."""

    def test_creates_with_correct_headers(self):
        model = ErrorModel()

        self.assertEqual(model.columnCount(), 2)
        self.assertEqual(model.horizontalHeaderItem(0).text(), "Time")
        self.assertEqual(model.horizontalHeaderItem(1).text(), "Error Message")

    def test_shows_no_error_banner_initially(self):
        model = ErrorModel()

        self.assertEqual(model.rowCount(), 1)
        self.assertEqual(model.item(0, 0).text(), "No errors")
        self.assertEqual(model.item(0, 1), None)


class TestErrorModelPopulateEmpty(unittest.TestCase):
    """Tests for populating model with empty error list."""

    def test_shows_no_error_banner_when_populated_empty(self):
        model = ErrorModel()
        model.populate([])

        self.assertEqual(model.rowCount(), 1)
        self.assertEqual(model.item(0, 0).text(), "No errors")

    def test_clears_existing_errors_when_populated_empty(self):
        model = ErrorModel()
        # Add some errors first
        model.populate([(timedelta(seconds=1), "Error 1")])
        self.assertEqual(model.rowCount(), 1)

        # Populate with empty list
        model.populate([])

        self.assertEqual(model.rowCount(), 1)
        self.assertEqual(model.item(0, 0).text(), "No errors")


class TestErrorModelPopulateSingleError(unittest.TestCase):
    """Tests for populating model with single error."""

    def test_displays_single_error(self):
        model = ErrorModel()
        error_time = timedelta(seconds=10)
        error_msg = "Motor timeout"

        model.populate([(error_time, error_msg)])

        self.assertEqual(model.rowCount(), 1)

    def test_displays_error_time(self):
        model = ErrorModel()
        error_time = timedelta(seconds=30, milliseconds=33)

        model.populate([(error_time, "Test error")])

        self.assertEqual(model.item(0, 0).text(), "0:00:30.033000")

    def test_displays_error_message(self):
        model = ErrorModel()
        error_msg = "Temperature exceeded"

        model.populate([(timedelta(seconds=5), error_msg)])

        self.assertEqual(model.item(0, 1).text(), error_msg)

    def test_removes_no_error_banner_when_populated_with_error(self):
        model = ErrorModel()
        self.assertEqual(model.item(0, 0).text(), "No errors")

        model.populate([(timedelta(seconds=1), "Error")])

        self.assertNotEqual(model.item(0, 0).text(), "No errors")


class TestErrorModelPopulateMultipleErrors(unittest.TestCase):
    """Tests for populating model with multiple errors."""

    def test_displays_multiple_errors(self):
        model = ErrorModel()
        errors = [
            (timedelta(seconds=1), "Error 1"),
            (timedelta(seconds=2), "Error 2"),
            (timedelta(seconds=3), "Error 3"),
        ]

        model.populate(errors)

        self.assertEqual(model.rowCount(), 3)

    def test_displays_errors_in_order(self):
        model = ErrorModel()
        errors = [
            (timedelta(seconds=5), "First error"),
            (timedelta(seconds=10), "Second error"),
            (timedelta(seconds=15), "Third error"),
        ]

        model.populate(errors)

        self.assertEqual(model.item(0, 1).text(), "First error")
        self.assertEqual(model.item(1, 1).text(), "Second error")
        self.assertEqual(model.item(2, 1).text(), "Third error")

    def test_displays_correct_times_for_multiple_errors(self):
        model = ErrorModel()
        errors = [
            (timedelta(seconds=10), "Error 1"),
            (timedelta(seconds=20), "Error 2"),
            (timedelta(seconds=30), "Error 3"),
        ]

        model.populate(errors)

        self.assertEqual(model.item(0, 0).text(), "0:00:10")
        self.assertEqual(model.item(1, 0).text(), "0:00:20")
        self.assertEqual(model.item(2, 0).text(), "0:00:30")


class TestErrorModelRepopulation(unittest.TestCase):
    """Tests for repopulating model with different data."""

    def test_replaces_errors_on_repopulation(self):
        model = ErrorModel()
        model.populate([(timedelta(seconds=1), "Old error")])

        model.populate([(timedelta(seconds=2), "New error")])

        self.assertEqual(model.rowCount(), 1)
        self.assertEqual(model.item(0, 1).text(), "New error")

    def test_replaces_multiple_errors_with_single_error(self):
        model = ErrorModel()
        model.populate([
            (timedelta(seconds=1), "Error 1"),
            (timedelta(seconds=2), "Error 2"),
        ])

        model.populate([(timedelta(seconds=3), "Single error")])

        self.assertEqual(model.rowCount(), 1)
        self.assertEqual(model.item(0, 1).text(), "Single error")

    def test_replaces_single_error_with_multiple_errors(self):
        model = ErrorModel()
        model.populate([(timedelta(seconds=1), "Single error")])

        model.populate([
            (timedelta(seconds=2), "Error 1"),
            (timedelta(seconds=3), "Error 2"),
        ])

        self.assertEqual(model.rowCount(), 2)

    def test_replaces_errors_with_no_error_banner(self):
        model = ErrorModel()
        model.populate([(timedelta(seconds=1), "Error")])

        model.populate([])

        self.assertEqual(model.rowCount(), 1)
        self.assertEqual(model.item(0, 0).text(), "No errors")


class TestErrorModelNotSupported(unittest.TestCase):
    """Tests for not-supported state."""

    def test_shows_not_supported_message(self):
        model = ErrorModel()
        model.set_not_supported()

        self.assertEqual(model.rowCount(), 1)
        self.assertEqual(
            model.item(0, 0).text(),
            "Error listing not supported by device"
        )

    def test_clears_errors_when_set_not_supported(self):
        model = ErrorModel()
        model.populate([(timedelta(seconds=1), "Error")])

        model.set_not_supported()

        self.assertEqual(model.rowCount(), 1)
        self.assertNotEqual(
            model.item(0, 0).text(),
            "Error"
        )

    def test_replaces_no_error_with_not_supported(self):
        model = ErrorModel()

        model.set_not_supported()

        self.assertEqual(
            model.item(0, 0).text(),
            "Error listing not supported by device"
        )


class TestErrorModelEdgeCases(unittest.TestCase):
    """Tests for edge cases and boundary conditions."""

    def test_handles_empty_error_message(self):
        model = ErrorModel()

        model.populate([(timedelta(seconds=1), "")])

        self.assertEqual(model.rowCount(), 1)
        self.assertEqual(model.item(0, 1).text(), "")

    def test_handles_duplicate_error_messages(self):
        model = ErrorModel()
        errors = [
            (timedelta(seconds=1), "Same error"),
            (timedelta(seconds=2), "Same error"),
            (timedelta(seconds=3), "Same error"),
        ]

        model.populate(errors)

        self.assertEqual(model.rowCount(), 3)
        self.assertEqual(model.item(0, 1).text(), "Same error")
        self.assertEqual(model.item(1, 1).text(), "Same error")
        self.assertEqual(model.item(2, 1).text(), "Same error")

    def test_handles_errors_with_identical_timestamps(self):
        model = ErrorModel()
        same_time = timedelta(seconds=5)
        errors = [
            (same_time, "Error 1"),
            (same_time, "Error 2"),
        ]

        model.populate(errors)

        self.assertEqual(model.rowCount(), 2)
        self.assertEqual(model.item(0, 0).text(), "0:00:05")
        self.assertEqual(model.item(1, 0).text(), "0:00:05")

    def test_multiple_set_not_supported_calls(self):
        model = ErrorModel()
        model.set_not_supported()
        model.set_not_supported()

        self.assertEqual(model.rowCount(), 1)
        self.assertEqual(
            model.item(0, 0).text(),
            "Error listing not supported by device"
        )

    def test_alternating_populate_and_not_supported(self):
        model = ErrorModel()

        model.populate([(timedelta(seconds=1), "Error")])
        self.assertEqual(model.rowCount(), 1)
        self.assertNotEqual(
            model.item(0, 0).text(),
            "Error listing not supported by device"
        )

        model.set_not_supported()
        self.assertEqual(model.rowCount(), 1)
        self.assertEqual(
            model.item(0, 0).text(),
            "Error listing not supported by device"
        )

        model.populate([(timedelta(seconds=2), "New error")])
        self.assertEqual(model.rowCount(), 1)
        self.assertNotEqual(
            model.item(0, 0).text(),
            "Error listing not supported by device"
        )


if __name__ == "__main__":
    unittest.main()
