"""
Unit test parameter database functions
"""
import unittest
from pathlib import Path
import json
import pytest

from canopen import objectdictionary

from openinverter_can_tool.paramdb import index_from_id, import_database
from openinverter_can_tool.fpfloat import fixed_from_float

TEST_DATA_DIR = Path(__file__).parent / "test_data"


class TestIndexFromId(unittest.TestCase):
    """
    Unit test the index_from_id function used to convert openinverter parameter
    IDs into CANopen SDO index and sub-index tuples
    """

    def test_zero_id(self):
        """ openinverter parameters all start with an index of 0x2100"""
        self.assertTupleEqual(index_from_id(0), (0x2100, 0))

    def test_small_id(self):
        """ Check that ids < 0xff only affect the subindex byte"""
        self.assertTupleEqual(index_from_id(1), (0x2100, 1))
        self.assertTupleEqual(index_from_id(42), (0x2100, 42))
        self.assertTupleEqual(index_from_id(0xff), (0x2100, 0xff))

    def test_large_id(self):
        """ Check that larger IDs are split into the correct index/subindex"""
        self.assertTupleEqual(index_from_id(2015), (0x2107, 0xdf))


class TestDatabaseImport(unittest.TestCase):
    """
    Unit test the JSON parameter database import functionality
    """

    def test_invalid_db_filename(self):
        """Verify that a garbage filename fails with an exception"""
        with pytest.raises(FileNotFoundError):
            import_database("not_a_real_file.json")

    def test_zero_byte_db_file(self):
        """Verify that a zero length file raises a JSON parse exception"""
        with pytest.raises(json.decoder.JSONDecodeError):
            import_database(TEST_DATA_DIR / "zero-bytes.json")

    def test_empty_db_file(self):
        """Verify that an empty file loads but contains no entries"""
        self.assertCountEqual(import_database(
            TEST_DATA_DIR / "empty-but-valid.json"), [])

    def test_single_param(self):
        """Verify that a simple database with a single parameter
        loads correctly"""
        database = import_database(TEST_DATA_DIR / "single-param.json")
        assert database["param1"]
        item = database["param1"]
        self.assertEqual(item.index, 0x2100)
        self.assertEqual(item.subindex, 1)
        self.assertEqual(item.unit, "km / h")
        self.assertEqual(item.min, fixed_from_float(0))
        self.assertEqual(item.max, fixed_from_float(100))
        self.assertEqual(item.default, fixed_from_float(5))
        self.assertEqual(item.factor, 32)
        self.assertEqual(item.data_type, objectdictionary.INTEGER32)
        self.assertTrue(item.isparam)
        self.assertEqual(item.category, "Category")

    def test_complex_params(self):
        """Verify that a more complex database with a variety of parameters
        and some values loads correctly"""
        database = import_database(TEST_DATA_DIR / "complex.json")

        expected_params = [
            {"name": "curkp", "isparam": True, "unit": "",
             "min": 0, "max": 20000, "default": 32,
             "category": "Params",
             "index": 0x2100, "subindex": 107},
            {"name": "dirmode", "isparam": True,
             "unit": "0=Button, 1=Switch, 2=ButtonReversed, 3=SwitchReversed, "
                     "4=DefaultForward",
             "min": 0, "max": 4, "default": 1,
             "category": "Params",
             "index": 0x2100, "subindex": 95},
            {"name": "potmin", "isparam": True, "unit": "dig",
             "min": 0, "max": 4095, "default": 0,
             "category": "Throttle",
             "index": 0x2100, "subindex": 17},
            {"name": "potmax", "isparam": True, "unit": "dig",
             "min": 0, "max": 4095, "default": 4095,
             "category": "Throttle",
             "index": 0x2100, "subindex": 18},
            {"name": "cpuload", "isparam": False, "unit": "%",
             "index": 0x2107, "subindex": 0xF3}
        ]

        # Basic size check
        self.assertEqual(len(database.names), len(expected_params))

        # verify each of the exepected params exist
        for param in expected_params:
            item = database[param["name"]]
            self.assertEqual(item.index, param["index"])
            self.assertEqual(item.subindex, param["subindex"])
            self.assertEqual(item.unit, param["unit"])
            self.assertEqual(item.isparam, param["isparam"])

            # optional fields only present for params not values
            if item.isparam:
                self.assertEqual(item.min, fixed_from_float(param["min"]))
                self.assertEqual(item.max, fixed_from_float(param["max"]))
                self.assertEqual(
                    item.default, fixed_from_float(param["default"]))
                self.assertEqual(item.category, param["category"])
            else:
                self.assertEqual(item.min, None)
                self.assertEqual(item.max, None)
                self.assertEqual(item.default, None)
                self.assertEqual(item.category, None)

            self.assertEqual(item.factor, 32)
            self.assertEqual(item.data_type, objectdictionary.INTEGER32)


if __name__ == '__main__':
    unittest.main()
