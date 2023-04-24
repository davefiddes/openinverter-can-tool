"""
Unit test parameter database functions
"""
import unittest
from pathlib import Path
import json
import pytest

import canopen

from openinverter_can_tool.fpfloat import fixed_from_float
from openinverter_can_tool.paramdb import index_from_id
from openinverter_can_tool.paramdb import import_database
from openinverter_can_tool.paramdb import import_database_json
from openinverter_can_tool.paramdb import import_remote_database
from openinverter_can_tool import constants as oi

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
        self.assertEqual(item.data_type, canopen.objectdictionary.INTEGER32)
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
            self.assertEqual(
                item.data_type, canopen.objectdictionary.INTEGER32)

    def test_unicode_param(self):
        """Verify that databases with Unicode work. We need this for degree
        symbols at least but emojis are just as fun."""
        database = import_database(TEST_DATA_DIR / "unicode.json")
        assert database["param1"]
        item = database["param1"]
        self.assertEqual(item.index, 0x2100)
        self.assertEqual(item.subindex, 1)
        self.assertEqual(item.unit, "°")
        self.assertEqual(item.min, fixed_from_float(0))
        self.assertEqual(item.max, fixed_from_float(100))
        self.assertEqual(item.default, fixed_from_float(5))
        self.assertEqual(item.factor, 32)
        self.assertEqual(item.data_type, canopen.objectdictionary.INTEGER32)
        self.assertTrue(item.isparam)
        self.assertEqual(item.category, "😬")

    def test_raw_json_dict(self):
        """Verify that it is possible to parse a raw JSON dictionary without
        requiring a file. Include extraneous attributes on parameters that are
        present on stm32-sine from 5.25-R onwards. Also include a parameter
        without any ID which should be ignored."""

        raw_json = {
            "curkp": {"unit": "", "minimum": "0", "maximum": "20000",
                      "default": "32", "isparam": True, "category": "Motor",
                      "id": "107", "i": 0},
            "dirmode": {"unit": "0=Button, 1=Switch, 2=ButtonReversed, "
                        "3=SwitchReversed, 4=DefaultForward", "id": 95,
                        "value": 1.00, "isparam": True, "minimum": 0.00,
                        "maximum": 4.00, "default": 1.00,
                        "category": "Motor", "i": 15},
            "serial": {"unit": "", "value": "87193029", "isparam": False}
        }

        database = import_database_json(raw_json)

        expected_params = [
            {"name": "curkp", "isparam": True, "unit": "",
             "min": 0, "max": 20000, "default": 32,
             "category": "Motor",
             "index": 0x2100, "subindex": 107},
            {"name": "dirmode", "isparam": True,
             "unit": "0=Button, 1=Switch, 2=ButtonReversed, 3=SwitchReversed, "
                     "4=DefaultForward",
             "min": 0, "max": 4, "default": 1,
             "category": "Motor",
             "index": 0x2100, "subindex": 95}
        ]

        # Basic size check
        self.assertEqual(len(database.names), len(expected_params))

        # verify each of the expected params exist
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
            self.assertEqual(item.data_type,
                             canopen.objectdictionary.INTEGER32)

    def test_remote_db(self):
        """Verify that it is possible to load a database located on a remote
        CAN bus node."""

        # Put together an SDO server that pretends to be a remote openinverter
        # node
        network1 = canopen.Network()
        network1.connect("test", bustype="virtual")

        dictionary = canopen.ObjectDictionary()
        db_var = canopen.objectdictionary.Variable(
            'database', oi.STRINGS_INDEX, oi.PARAM_DB_SUBINDEX)
        db_var.data_type = canopen.objectdictionary.VISIBLE_STRING
        dictionary.add_object(db_var)

        servernode = canopen.LocalNode(13, dictionary)
        network1.add_node(servernode)

        with open(TEST_DATA_DIR / "complex.json", encoding="utf-8") as file:
            servernode.sdo['database'].raw = file.read()

        # Put together a network that is connected to the server for the code
        # under test
        network2 = canopen.Network()
        network2.connect("test", bustype="virtual")

        database = import_remote_database(network2, 13)

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

        # verify each of the expected params exist
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
            self.assertEqual(
                item.data_type, canopen.objectdictionary.INTEGER32)

    def test_enum_dict(self):
        """Provide a dictionary with a variety of enumeration parameters.
        Verify that these are correctly parsed.
        """

        raw_json = {
            "dirmode": {"unit": "0=Button, 1=Switch, 2=ButtonReversed, "
                        "3=SwitchReversed, 4=DefaultForward", "id": 95,
                        "value": 1.00, "isparam": True, "minimum": 0.00,
                        "maximum": 4.00, "default": 1.00,
                        "category": "Motor", "i": 15},
            "snsm": {"unit": "12=KTY83-110, 13=KTY84-130, 14=Leaf, "
                     "15=KTY81-110, 16=Toyota, 21=OutlanderFront, "
                     "22=EpcosB57861-S, 23=ToyotaGen2", "minimum": "12",
                     "maximum": "23", "default": "12", "isparam": True,
                     "category": "Motor", "id": "46"},
            "dir": {"unit": "-1=Reverse, 0=Neutral, 1=Forward",
                    "isparam": False, "id": "2018"},
            "din_mprot": {"unit": "0=Error, 1=Ok, 2=na", "isparam": False,
                          "id": "2026"},

            # Note trailing comma
            "lasterr": {"unit": "0=NONE, 1=OVERCURRENT, 2=THROTTLE1, "
                        "3=THROTTLE2, 4=CANTIMEOUT, 5=EMCYSTOP, 6=MPROT, "
                        "7=DESAT, 8=OVERVOLTAGE, 9=ENCODER, 10=PRECHARGE, "
                        "11=TMPHSMAX, 12=CURRENTLIMIT, 13=PWMSTUCK, "
                        "14=HICUROFS1, 15=HICUROFS2, 16=HIRESOFS, "
                        "17=LORESAMP, 18=TMPMMAX,",
                        "isparam": False, "id": "2038"},

            "version": {"unit": "4=5.24.R-foc", "isparam": False, "id": "2039"}
        }

        database = import_database_json(raw_json)

        expected_params = [
            {"name": "dirmode",
             "enums": {0: "Button", 1: "Switch", 2: "ButtonReversed",
                       3: "SwitchReversed", 4: "DefaultForward"}},
            {"name": "snsm",
             "enums": {12: "KTY83-110", 13: "KTY84-130", 14: "Leaf",
                       15: "KTY81-110", 16: "Toyota", 21: "OutlanderFront",
                       22: "EpcosB57861-S", 23: "ToyotaGen2"}},
            {"name": "dir",
             "enums": {-1: "Reverse", 0: "Neutral", 1: "Forward"}},
            {"name": "din_mprot",
             "enums": {0: "Error", 1: "Ok", 2: "na"}},
            {"name": "lasterr",
             "enums": {0: "NONE", 1: "OVERCURRENT", 2: "THROTTLE1",
                       3: "THROTTLE2", 4: "CANTIMEOUT", 5: "EMCYSTOP",
                       6: "MPROT", 7: "DESAT", 8: "OVERVOLTAGE", 9: "ENCODER",
                       10: "PRECHARGE", 11: "TMPHSMAX", 12: "CURRENTLIMIT",
                       13: "PWMSTUCK", 14: "HICUROFS1", 15: "HICUROFS2",
                       16: "HIRESOFS", 17: "LORESAMP", 18: "TMPMMAX"}},
            {"name": "version",
             "enums": {4: "5.24.R-foc"}},
        ]

        # Basic size check
        self.assertEqual(len(database.names), len(expected_params))

        # verify each of the expected params exist
        for param in expected_params:
            item = database[param["name"]]
            self.assertFalse(item.bit_definitions)

            expected_enums = param["enums"]

            self.assertEqual(len(item.value_descriptions), len(expected_enums))
            for value, description in expected_enums.items():
                self.assertEqual(
                    item.value_descriptions[value], description)

    def test_bitfield_dict(self):
        """Provide a dictionary with a variety of bitfield parameters.
        Verify that these are correctly parsed.
        """

        raw_json = {
            "canio": {"unit": "1=Cruise, 2=Start, 4=Brake, 8=Fwd, 16=Rev, "
                      "32=Bms",
                      "isparam": False, "id": "2022"},
            "status": {"unit": "0=None, 1=UdcLow, 2=UdcHigh, 4=UdcBelowUdcSw, "
                       "8=UdcLim, 16=EmcyStop, 32=MProt, 64=PotPressed, "
                       "128=TmpHs, 256=WaitStart", "isparam": False,
                       "id": "2044"}
        }

        database = import_database_json(raw_json)

        expected_params = [
            {"name": "canio",
             "bitfield": {1: "Cruise", 2: "Start", 4: "Brake", 8: "Fwd",
                          16: "Rev", 32: "Bms"}},
            {"name": "status",
             "bitfield": {0: "None", 1: "UdcLow", 2: "UdcHigh",
                          4: "UdcBelowUdcSw", 8: "UdcLim", 16: "EmcyStop",
                          32: "MProt", 64: "PotPressed", 128: "TmpHs",
                          256: "WaitStart"}},
        ]

        # Basic size check
        self.assertEqual(len(database.names), len(expected_params))

        # verify each of the expected params exist
        for param in expected_params:
            item = database[param["name"]]
            self.assertFalse(item.value_descriptions)

            expected_bitfield = param["bitfield"]

            self.assertEqual(len(item.bit_definitions),
                             len(expected_bitfield))
            for value, description in expected_bitfield.items():
                self.assertEqual(
                    item.bit_definitions[value], description)


if __name__ == '__main__':
    unittest.main()
