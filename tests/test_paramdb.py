"""
Unit test parameter database functions
"""
import filecmp
import json
import unittest
from pathlib import Path
from typing import cast

import canopen.objectdictionary
import pytest

from openinverter_can_tool.fpfloat import fixed_from_float
from openinverter_can_tool.paramdb import (OIVariable,
                                           import_cached_database,
                                           import_database,
                                           import_database_json,
                                           import_remote_database,
                                           value_to_str)

from .oi_sim import OISimulatedNode

TEST_DATA_DIR = Path(__file__).parent / "test_data" / "paramdb"

# Reduce test verbosity
# pylint: disable=missing-function-docstring


class OpeninverterVariable(unittest.TestCase):
    """
    Unit test the OIVariable class used to represent the not quite CANopen
    variable representation method used by openinverter
    """

    def test_zero_id(self):
        """ openinverter parameters all start with an index of 0x2100"""
        var = OIVariable("zero_id",  0)
        self.assertEqual(var.index, 0x2100)
        self.assertEqual(var.subindex, 0)

    def test_small_id(self):
        """ Check that ids < 0xff only affect the subindex byte"""
        var = OIVariable("id",  1)
        self.assertEqual(var.index, 0x2100)
        self.assertEqual(var.subindex, 1)

        var = OIVariable("id",  42)
        self.assertEqual(var.index, 0x2100)
        self.assertEqual(var.subindex, 42)

        var = OIVariable("id",  0xff)
        self.assertEqual(var.index, 0x2100)
        self.assertEqual(var.subindex, 0xff)

    def test_large_id(self):
        """ Check that larger IDs are split into the correct index/subindex"""
        var = OIVariable("large_id", 2015)
        self.assertEqual(var.index, 0x2107)
        self.assertEqual(var.subindex, 0xdf)

    def test_return_id(self):
        """ Check that the openinverter ID is stored as well as the CANopen
        index and sub-index. """
        var = OIVariable("id",  2015)
        self.assertEqual(var.id, 2015)
        self.assertEqual(var.index, 0x2107)
        self.assertEqual(var.subindex, 0xdf)

    def test_modify_index(self):
        """ Check that it is possible to modify the sub-index and have this
        reflected in the id returned """
        var = OIVariable("id",  2015)
        var.index = 0x2100
        var.subindex = 0xff
        self.assertEqual(var.id, 0xff)
        self.assertEqual(var.index, 0x2100)
        self.assertEqual(var.subindex, 0xff)


class DatabaseImport(unittest.TestCase):
    """
    Unit test the JSON parameter database import functionality
    """

    def test_invalid_db_filename(self):
        """Verify that a garbage filename fails with an exception"""
        with pytest.raises(FileNotFoundError):
            import_database(Path("not_a_real_file.json"))

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
        item = cast(OIVariable, database["param1"])
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
            item = cast(OIVariable, database[param["name"]])
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
        item = cast(OIVariable, database["param1"])
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
            item = cast(OIVariable, database[param["name"]])
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

        simulator = OISimulatedNode(13)
        simulator.LoadDatabase(TEST_DATA_DIR / "complex.json")

        database = import_remote_database(simulator.network, 13)

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
            item = cast(OIVariable, database[param["name"]])
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

    def test_remote_db_with_zero_bytes(self):
        """Due to a race condition in openinverter firmware the database can
        contain additional 0x00 bytes interspersed with the expected byte
        stream. Verify that these databases can be loaded correctly from a
        remote node."""

        simulator = OISimulatedNode(13)
        simulator.LoadDatabase(
            TEST_DATA_DIR / "complex-with-added-zero-bytes.json")

        database = import_remote_database(simulator.network, 13)

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
            item = cast(OIVariable, database[param["name"]])
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

    def test_remote_unicode_db_with_zero_bytes(self):
        """Due to a race condition in openinverter firmware the database can
        contain additional NUL or 0x00 bytes. Verify that a databases with
        unicode utf-8 sequences with extra zero bytes can be loaded correctly
        from a remote node."""

        simulator = OISimulatedNode(13)
        simulator.LoadDatabase(
            TEST_DATA_DIR / "unicode-with-added-zero-bytes.json")

        database = import_remote_database(simulator.network, 13)

        assert database["param1"]
        item = cast(OIVariable, database["param1"])
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
            assert isinstance(item, OIVariable)
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
            assert isinstance(item, OIVariable)
            self.assertFalse(item.value_descriptions)

            expected_bitfield = param["bitfield"]

            self.assertEqual(len(item.bit_definitions),
                             len(expected_bitfield))
            for value, description in expected_bitfield.items():
                self.assertEqual(
                    item.bit_definitions[value], description)

    def test_badly_punctuated_enum_missing_comma(self):
        """Extracted from issue #4 a badly punctuated enum should try
        to fix up the list in the same way as esp8266-web-interface
        """

        raw_json = {
            "Inverter": {
                # Note the lack of a comma between 7 and 8
                "unit": "0=None, 1=Leaf_Gen1, 2=GS450H, 3=UserCAN, 4=OpenI, "
                "5=Prius_Gen3, 6=Outlander, 7=GS300H 8=RearOutlander",
                "id": 5,
                "value": 0.00,
                "isparam": True,
                "minimum": 0.00,
                "maximum": 8.00,
                "default": 0.00,
                "category": "General Setup",
                "i": 0
            }}

        database = import_database_json(raw_json)

        expected_enums = {
            0: "None", 1: "Leaf_Gen1", 2: "GS450H", 3: "UserCAN", 4: "OpenI",
            5: "Prius_Gen3", 6: "Outlander", 7: "GS300H",  8: "RearOutlander"
        }

        assert len(database) == 1
        item = database["Inverter"]
        self.assertEqual(len(item.value_descriptions), len(expected_enums))
        for value, description in expected_enums.items():
            self.assertEqual(
                item.value_descriptions[value], description)

    def test_badly_punctuated_enum_full_stop_rather_than_comma(self):
        """Extracted from issue #4 a badly punctuated enum should try
        to fix up the list in the same way as esp8266-web-interface
        """

        raw_json = {
            "CAN3Speed": {
                "unit": "0=k33.3, 1=k500. 2=k100",
                "id": 77,
                "value": 0.00,
                "isparam": True,
                "minimum": 0.00,
                "maximum": 2.00,
                "default": 0.00,
                "category": "Communication",
                "i": 53
            }}

        database = import_database_json(raw_json)

        expected_enums = {
            0: "k33.3", 1: "k500.", 2: "k100"
        }

        assert len(database) == 1
        item = database["CAN3Speed"]

        self.assertEqual(len(item.value_descriptions), len(expected_enums))
        for value, description in expected_enums.items():
            self.assertEqual(
                item.value_descriptions[value], description)

    def test_badly_punctuated_enum_with_no_spaces(self):
        """Extracted from issue #4 a badly punctuated enum without any spaces
        should still be parsed fine
        """

        raw_json = {
            "Out1Func": {
                "unit": "0=None, 1=ChaDeMoAlw, 2=OBCEnable, 3=HeaterEnable, "
                "4=RunIndication, 5=WarnIndication,6=CoolantPump, "
                "7=NegContactor, 8=BrakeLight, 9=ReverseLight, 10=HeatReq, "
                "11=HVRequest,12=DCFCRequest, 13=BrakeVacPump, 14=PwmTim3",
                "id": 80,
                "value": 6.00,
                "isparam": True,
                "minimum": 0.00,
                "maximum": 13.00,
                "default": 6.00,
                "category": "General Purpose I/O",
                "i": 87
            }
        }

        database = import_database_json(raw_json)

        assert len(database) == 1
        item = database["Out1Func"]
        assert item.value_descriptions[11] == "HVRequest"
        assert item.value_descriptions[12] == "DCFCRequest"
        assert item.value_descriptions[13] == "BrakeVacPump"
        assert item.value_descriptions[14] == "PwmTim3"
        assert len(item.value_descriptions) == 15

    def test_badly_punctuated_enum_with_no_value_name(self):
        """Verify that a massively poorly formatted enum fails gracefully"""

        raw_json = {
            "Option": {
                "unit": "0=starts-ok, 1, 2=ends-well",
                "id": 77,
                "value": 0.00,
                "isparam": True,
                "minimum": 0.00,
                "maximum": 2.00,
                "default": 0.00,
                "category": "Communication",
                "i": 53
            }}

        database = import_database_json(raw_json)

        assert len(database) == 1
        item = database["Option"]
        assert item.unit == ("0=starts-ok, 1, 2=ends-well [DB FORMAT ERROR]")
        assert len(item.value_descriptions) == 0


class TestCachedDatabases:
    """
    Unit test caching of JSON parameter databases
    """

    def test_new_empty_cache_location(self, tmp_path: Path):
        simulator = OISimulatedNode(42)
        simulator.checksum = 12345678
        simulator.LoadDatabase(TEST_DATA_DIR / "single-param.json")

        cache = tmp_path / "empty-but-non-existent"
        assert not cache.is_dir()

        database = import_cached_database(simulator.network, 42, cache)

        assert cache.is_dir()

        assert database["param1"]

        cached_file = next(cache.iterdir(), None)
        assert cached_file
        assert cached_file.is_file()
        assert cached_file.stat().st_size > 0

    def test_long_new_cache_path(self, tmp_path: Path):
        simulator = OISimulatedNode(42)
        simulator.checksum = 12345678
        simulator.LoadDatabase(TEST_DATA_DIR / "single-param.json")

        cache = tmp_path / "a" / "deep" / "new" / "path"
        assert not cache.is_dir()

        database = import_cached_database(simulator.network, 42, cache)

        assert cache.is_dir()

        assert database["param1"]

    def test_empty_but_present_cache_location(self, tmp_path: Path):
        simulator = OISimulatedNode(42)
        simulator.checksum = 12345678
        simulator.LoadDatabase(TEST_DATA_DIR / "single-param.json")

        cache = tmp_path / "empty-but-exists"
        cache.mkdir()

        assert len(list(cache.iterdir())) == 0

        database = import_cached_database(simulator.network, 42, cache)

        assert database["param1"]
        item = cast(OIVariable, database["param1"])
        assert item.index == 0x2100
        assert item.subindex == 1
        assert item.unit == "km / h"
        assert item.min == fixed_from_float(0)
        assert item.max == fixed_from_float(100)
        assert item.default == fixed_from_float(5)
        assert item.factor == 32
        assert item.data_type == canopen.objectdictionary.INTEGER32
        assert item.isparam
        assert item.category == "Category"

        cached_file = next(cache.iterdir(), None)
        assert cached_file
        assert cached_file.is_file()
        assert cached_file.stat().st_size > 0

    def test_database_is_cached(self, tmp_path: Path):
        simulator = OISimulatedNode(42)
        simulator.checksum = 12345678
        simulator.LoadDatabase(TEST_DATA_DIR / "single-param.json")

        cache = tmp_path

        # prime the cache
        database = import_cached_database(simulator.network, 42, cache)

        assert database["param1"]

        # Load a completely different database but don't update the checksum
        simulator.LoadDatabase(TEST_DATA_DIR / "complex.json")

        # Load the database again which should load from the cache
        database = import_cached_database(simulator.network, 42, cache)

        # verify we still have the single parameter
        assert database["param1"]
        item = cast(OIVariable, database["param1"])
        assert item.index == 0x2100
        assert item.subindex == 1
        assert item.unit == "km / h"
        assert item.min == fixed_from_float(0)
        assert item.max == fixed_from_float(100)
        assert item.default == fixed_from_float(5)
        assert item.factor == 32
        assert item.data_type == canopen.objectdictionary.INTEGER32
        assert item.isparam
        assert item.category == "Category"

        # There should just be a single file in the cache
        cached_file = next(cache.iterdir(), None)
        assert cached_file
        assert cached_file.is_file()
        assert cached_file.stat().st_size > 0

        # verify that a parameters from the file we loaded to the remote node
        # is not present
        assert "curkp" not in database
        assert "dirmode" not in database
        assert "potmin" not in database
        assert "potmax" not in database
        assert "cpuload" not in database

    def test_cached_database_is_updated(self, tmp_path: Path):
        simulator = OISimulatedNode(42)
        simulator.checksum = 12345678
        simulator.LoadDatabase(TEST_DATA_DIR / "single-param.json")

        cache = tmp_path

        # prime the cache
        database = import_cached_database(simulator.network, 42, cache)

        assert database["param1"]

        # Load a completely different database and update the checksum on the
        # remote node
        simulator.LoadDatabase(TEST_DATA_DIR / "complex.json")
        simulator.checksum = 4567890

        # Load the database again which should update from the remote node
        database = import_cached_database(simulator.network, 42, cache)

        # verify we have parameters from the new database
        assert database["curkp"]
        assert database["dirmode"]
        assert database["potmin"]
        assert database["potmax"]
        assert database["cpuload"]

        # verify that nothing remains of the old parameters
        assert "param1" not in database

        # There should two cached files for each version of the database
        assert len(list(cache.iterdir())) == 2

    def test_multiple_nodes_generate_multiple_cached_databases(
            self,
            tmp_path: Path):
        cache = tmp_path

        # Set up up the first node
        simulator = OISimulatedNode(42)
        simulator.checksum = 12345678
        simulator.LoadDatabase(TEST_DATA_DIR / "single-param.json")

        # Load the database from the first node
        database = import_cached_database(simulator.network, 42, cache)

        assert database["param1"]

        # Set up a second node with the same database
        simulator = OISimulatedNode(99)
        simulator.checksum = 12345678
        simulator.LoadDatabase(TEST_DATA_DIR / "single-param.json")

        # Load the database from the second node
        database = import_cached_database(simulator.network, 99, cache)

        assert database["param1"]

        # There should two cached files for each node and they should be
        # identical
        cache_files = list(cache.iterdir())
        assert len(cache_files) == 2
        assert filecmp.cmp(cache_files[0], cache_files[1], shallow=False)


class ValueToString(unittest.TestCase):
    """
    Unit test the conversion of numeric values to user-facing strings using a
    OIVariable instance.
    """

    def test_numeric_value_is_converted_to_simple_string(self):
        param = OIVariable("numeric",  0)

        output = value_to_str(param, 123.45, symbolic=False)

        self.assertEqual(output, "123.45")

    def test_symbolic_doesnt_affect_numeric_value(self):
        param = OIVariable("numeric",  0)

        output = value_to_str(param, 123.45)

        self.assertEqual(output, "123.45")

    def test_simple_enum_value(self):
        param = OIVariable("enum",  0)
        param.value_descriptions = {0: "Off", 1: "On"}

        output = value_to_str(param, 1)

        self.assertEqual(output, "On")

    def test_enum_value_without_symbolic_display_returns_a_number(self):
        param = OIVariable("enum",  0)
        param.value_descriptions = {0: "Off", 1: "On"}

        output = value_to_str(param, 1, symbolic=False)

        self.assertEqual(output, "1")

    def test_enum_with_unknown_value_is_returned_with_annotation(self):
        param = OIVariable("enum",  0)
        param.value_descriptions = {0: "Off", 1: "On"}

        output = value_to_str(param, 2)

        self.assertEqual(output, "2 (Unknown value)")

    def test_bitfield_with_single_bit_set(self):
        param = OIVariable("canio",  2022)
        param.bit_definitions = {1: "Cruise", 2: "Start", 4: "Brake", 8: "Fwd",
                                 16: "Rev", 32: "Bms"}

        output = value_to_str(param, 4)

        self.assertEqual(output, "Brake")

    def test_bitfield_with_multiple_bits_set(self):
        param = OIVariable("canio",  2022)
        param.bit_definitions = {1: "Cruise", 2: "Start", 4: "Brake", 8: "Fwd",
                                 16: "Rev", 32: "Bms"}

        output = value_to_str(param, 21)

        self.assertEqual(output, "Cruise, Brake, Rev")

    def test_bitfield_with_zero_value_but_param_doesnt_define(self):
        param = OIVariable("canio",  2022)
        param.bit_definitions = {1: "Cruise", 2: "Start", 4: "Brake", 8: "Fwd",
                                 16: "Rev", 32: "Bms"}

        output = value_to_str(param, 0)

        self.assertEqual(output, "0")

    def test_bitfield_with_zero_value_where_param_defines_symbol(self):
        param = OIVariable("status",  2044)
        param.bit_definitions = {
            0: "None", 1: "UdcLow", 2: "UdcHigh",
            4: "UdcBelowUdcSw", 8: "UdcLim"
        }

        output = value_to_str(param, 0)

        self.assertEqual(output, "None")

    def test_bitfield_value_without_symbolic_display_returns_a_number(self):
        param = OIVariable("status",  2044)
        param.bit_definitions = {
            0: "None", 1: "UdcLow", 2: "UdcHigh",
            4: "UdcBelowUdcSw", 8: "UdcLim"
        }

        output = value_to_str(param, 15, symbolic=False)

        self.assertEqual(output, "15")


if __name__ == '__main__':
    unittest.main()
