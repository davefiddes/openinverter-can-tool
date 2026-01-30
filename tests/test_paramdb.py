"""
Unit test parameter database functions
"""
import filecmp
import json
from pathlib import Path
from typing import cast

import canopen.objectdictionary
import pytest

from openinverter_can_tool.fpfloat import fixed_from_float
from openinverter_can_tool.paramdb import (OIVariable, import_cached_database,
                                           import_database,
                                           import_database_json,
                                           import_remote_database,
                                           param_name_from_id, value_to_str)

from .oi_sim import OISimulatedNode

TEST_DATA_DIR = Path(__file__).parent / "test_data" / "paramdb"

# Reduce test verbosity
# pylint: disable=missing-function-docstring


class TestOpenInverterVariable:
    """
    Unit test the OIVariable class used to represent the not quite CANopen
    variable representation method used by OpenInverter
    """

    def test_zero_id(self):
        """ OpenInverter parameters all start with an index of 0x2100"""
        var = OIVariable("zero_id",  0)
        assert var.index == 0x2100
        assert var.subindex == 0

    def test_small_id(self):
        """ Check that ids < 0xff only affect the subindex byte"""
        var = OIVariable("id",  1)
        assert var.index == 0x2100
        assert var.subindex == 1

        var = OIVariable("id",  42)
        assert var.index == 0x2100
        assert var.subindex == 42

        var = OIVariable("id",  0xff)
        assert var.index == 0x2100
        assert var.subindex == 0xff

    def test_large_id(self):
        """ Check that larger IDs are split into the correct index/subindex"""
        var = OIVariable("large_id", 2015)
        assert var.index == 0x2107
        assert var.subindex == 0xdf

    def test_return_id(self):
        """ Check that the OpenInverter ID is stored as well as the CANopen
        index and sub-index. """
        var = OIVariable("id",  2015)
        assert var.id == 2015
        assert var.index == 0x2107
        assert var.subindex == 0xdf

    def test_modify_index(self):
        """ Check that it is possible to modify the sub-index and have this
        reflected in the id returned """
        var = OIVariable("id",  2015)
        var.index = 0x2100
        var.subindex = 0xff
        assert var.id == 0xff
        assert var.index == 0x2100
        assert var.subindex == 0xff

    def test_repr(self):
        """ Check that the repr() method returns a useful string """
        var = OIVariable("id",  2015)
        assert repr(var) == "<OIVariable 'id' at 2015>"


class TestDatabaseImport:
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
        result = list(import_database(
            TEST_DATA_DIR / "empty-but-valid.json"))
        assert result == []

    def test_single_param(self):
        """Verify that a simple database with a single parameter
        loads correctly"""
        database = import_database(TEST_DATA_DIR / "single-param.json")
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
        assert len(database.names) == len(expected_params)

        # verify each of the exepected params exist
        for param in expected_params:
            item = cast(OIVariable, database[param["name"]])
            assert item.index == param["index"]
            assert item.subindex == param["subindex"]
            assert item.unit == param["unit"]
            assert item.isparam == param["isparam"]

            # optional fields only present for params not values
            if item.isparam:
                assert item.min == fixed_from_float(param["min"])
                assert item.max == fixed_from_float(param["max"])
                assert item.default == fixed_from_float(param["default"])
                assert item.category == param["category"]
            else:
                assert item.min is None
                assert item.max is None
                assert item.default is None
                assert item.category is None

            assert item.factor == 32
            assert item.data_type == canopen.objectdictionary.INTEGER32

    def test_unicode_param(self):
        """Verify that databases with Unicode work. We need this for degree
        symbols at least but emojis are just as fun."""
        database = import_database(TEST_DATA_DIR / "unicode.json")
        assert database["param1"]
        item = cast(OIVariable, database["param1"])
        assert item.index == 0x2100
        assert item.subindex == 1
        assert item.unit == "°"
        assert item.min == fixed_from_float(0)
        assert item.max == fixed_from_float(100)
        assert item.default == fixed_from_float(5)
        assert item.factor == 32
        assert item.data_type == canopen.objectdictionary.INTEGER32
        assert item.isparam
        assert item.category == "😬"

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
        assert len(database.names) == len(expected_params)

        # verify each of the expected params exist
        for param in expected_params:
            item = cast(OIVariable, database[param["name"]])
            assert item.index == param["index"]
            assert item.subindex == param["subindex"]
            assert item.unit == param["unit"]
            assert item.isparam == param["isparam"]

            # optional fields only present for params not values
            if item.isparam:
                assert item.min == fixed_from_float(param["min"])
                assert item.max == fixed_from_float(param["max"])
                assert item.default == fixed_from_float(param["default"])
                assert item.category == param["category"]
            else:
                assert item.min is None
                assert item.max is None
                assert item.default is None
                assert item.category is None

            assert item.factor == 32
            assert item.data_type == canopen.objectdictionary.INTEGER32

    def test_remote_db(self,
                       test_network: canopen.Network,
                       simulator: OISimulatedNode):
        """Verify that it is possible to load a database located on a remote
        CAN bus node."""

        simulator.LoadDatabase(TEST_DATA_DIR / "complex.json")

        database = import_remote_database(test_network, 42)

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
        assert len(database.names) == len(expected_params)

        # verify each of the expected params exist
        for param in expected_params:
            item = cast(OIVariable, database[param["name"]])
            assert item.index == param["index"]
            assert item.subindex == param["subindex"]
            assert item.unit == param["unit"]
            assert item.isparam == param["isparam"]

            # optional fields only present for params not values
            if item.isparam:
                assert item.min == fixed_from_float(param["min"])
                assert item.max == fixed_from_float(param["max"])
                assert item.default == fixed_from_float(param["default"])
                assert item.category == param["category"]
            else:
                assert item.min is None
                assert item.max is None
                assert item.default is None
                assert item.category is None

            assert item.factor == 32
            assert item.data_type == canopen.objectdictionary.INTEGER32

    def test_remote_db_with_zero_bytes(self,
                                       test_network: canopen.Network,
                                       simulator: OISimulatedNode):
        """Due to a race condition in OpenInverter firmware the database can
        contain additional 0x00 bytes interspersed with the expected byte
        stream. Verify that these databases can be loaded correctly from a
        remote node."""

        simulator.LoadDatabase(
            TEST_DATA_DIR / "complex-with-added-zero-bytes.json")

        database = import_remote_database(test_network, 42)

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
        assert len(database.names) == len(expected_params)

        # verify each of the expected params exist
        for param in expected_params:
            item = cast(OIVariable, database[param["name"]])
            assert item.index == param["index"]
            assert item.subindex == param["subindex"]
            assert item.unit == param["unit"]
            assert item.isparam == param["isparam"]

            # optional fields only present for params not values
            if item.isparam:
                assert item.min == fixed_from_float(param["min"])
                assert item.max == fixed_from_float(param["max"])
                assert item.default == fixed_from_float(param["default"])
                assert item.category == param["category"]
            else:
                assert item.min is None
                assert item.max is None
                assert item.default is None
                assert item.category is None

            assert item.factor == 32
            assert item.data_type == canopen.objectdictionary.INTEGER32

    def test_remote_unicode_db_with_zero_bytes(self,
                                               test_network: canopen.Network,
                                               simulator: OISimulatedNode):
        """Due to a race condition in OpenInverter firmware the database can
        contain additional NUL or 0x00 bytes. Verify that a databases with
        unicode utf-8 sequences with extra zero bytes can be loaded correctly
        from a remote node."""

        simulator.LoadDatabase(
            TEST_DATA_DIR / "unicode-with-added-zero-bytes.json")

        database = import_remote_database(test_network, 42)

        assert database["param1"]
        item = cast(OIVariable, database["param1"])
        assert item.index == 0x2100
        assert item.subindex == 1
        assert item.unit == "°"
        assert item.min == fixed_from_float(0)
        assert item.max == fixed_from_float(100)
        assert item.default == fixed_from_float(5)
        assert item.factor == 32
        assert item.data_type == canopen.objectdictionary.INTEGER32
        assert item.isparam
        assert item.category == "😬"

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
        assert len(database.names) == len(expected_params)

        # verify each of the expected params exist
        for param in expected_params:
            item = database[param["name"]]
            assert isinstance(item, OIVariable)
            assert not item.bit_definitions

            expected_enums = param["enums"]

            assert len(item.value_descriptions) == len(expected_enums)
            for value, description in expected_enums.items():
                assert item.value_descriptions[value] == description

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
        assert len(database.names) == len(expected_params)

        # verify each of the expected params exist
        for param in expected_params:
            item = database[param["name"]]
            assert isinstance(item, OIVariable)
            assert not item.value_descriptions

            expected_bitfield = param["bitfield"]

            assert len(item.bit_definitions) == len(expected_bitfield)
            for value, description in expected_bitfield.items():
                assert item.bit_definitions[value] == description

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
        assert isinstance(item, OIVariable)
        assert len(item.value_descriptions) == len(expected_enums)
        for value, description in expected_enums.items():
            assert item.value_descriptions[value] == description

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
        assert isinstance(item, OIVariable)

        assert len(item.value_descriptions) == len(expected_enums)
        for value, description in expected_enums.items():
            assert item.value_descriptions[value] == description

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
        assert isinstance(item, OIVariable)
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
        assert isinstance(item, OIVariable)
        assert item.unit == ("0=starts-ok, 1, 2=ends-well [DB FORMAT ERROR]")
        assert len(item.value_descriptions) == 0

    def test_small_digit_parameters_have_single_step_and_no_decimals(self):
        """Verify that small digit parameters with have a single step
        size of 1 and no decimal places"""

        raw_json = {
            "idcflt": {
                "unit": "dig",
                "id": 132,
                "isparam": True,
                "minimum": 0.00,
                "maximum": 11.00,
                "default": 9.00,
                "category": "Derating",
                "i": 59
            }}

        database = import_database_json(raw_json)

        assert len(database) == 1
        item = database["idcflt"]
        assert isinstance(item, OIVariable)
        assert item.decimals == 0
        assert item.step == 1

    def test_large_digit_parameters_have_single_step_and_no_decimals(self):
        """Verify that larger digit parameters have a step size in tens and no
        decimal places"""

        raw_json = {
            "potmax": {
                "unit": "dig",
                "id": 18,
                "isparam": True,
                "minimum": 0.00,
                "maximum": 3500.00,
                "default": 3500.00,
                "category": "Throttle",
            }}

        database = import_database_json(raw_json)

        assert len(database) == 1
        item = database["potmax"]
        assert isinstance(item, OIVariable)
        assert item.decimals == 0
        assert item.step == 10

    def test_parameter_that_start_dig_are_treated_as_digits(self):
        """Verify that parameters with units that start with 'dig' are treated
        as digit parameters even if they have extra text after 'dig'"""

        raw_json = {
            "il1gain": {"unit": "dig/A",
                        "id": 27,
                        "isparam": True,
                        "minimum": -100.00,
                        "maximum": 100.00,
                        "default": 4.68,
                        "category": "Inverter"
                        }}

        database = import_database_json(raw_json)

        assert len(database) == 1
        item = database["il1gain"]
        assert isinstance(item, OIVariable)
        assert item.decimals == 0
        assert item.step == 1

    def test_percentage_parameters_step_in_single_percent(self):
        """Verify that percentage parameters have a step size of 1%"""

        raw_json = {
            "max_charge_percent": {
                "unit": "%",
                "minimum": "0",
                "maximum": "100",
                "default": "80",
                "isparam": True,
                "category": "Charging",
                "id": "55"
            }}

        database = import_database_json(raw_json)

        assert len(database) == 1
        item = database["max_charge_percent"]
        assert isinstance(item, OIVariable)
        assert item.decimals == 2
        assert item.step == 1

    def test_voltage_parameters_step_in_volts(self):
        """Verify that voltage parameters have a step size of 1V"""

        raw_json = {
            "udclim": {
                "unit": "V",
                "id": 48,
                "value": 540.00,
                "isparam": True,
                "minimum": 0.00,
                "maximum": 1000.00,
                "default": 540.00,
                "category": "Inverter"
            }}

        database = import_database_json(raw_json)

        assert len(database) == 1
        item = database["udclim"]
        assert isinstance(item, OIVariable)
        assert item.decimals == 2
        assert item.step == 10

    def test_large_current_parameters_step_in_tens_of_amps(self):
        """Verify that large current parameters have a step size in tens of
        amps"""

        raw_json = {
            "idcmax": {
                "unit": "A",
                "id": 96,
                "isparam": True,
                "minimum": 0.00,
                "maximum": 5000.00,
                "default": 5000.00,
                "category": "Derating"
            }}

        database = import_database_json(raw_json)

        assert len(database) == 1
        item = database["idcmax"]
        assert isinstance(item, OIVariable)
        assert item.decimals == 2
        assert item.step == 10

    def test_params_with_negative_range_has_same_step_as_positive(self):
        """The steps size should match the previous test with a positive
        range."""

        raw_json = {
            "bidirectional_param": {
                "unit": "A",
                "id": 2001,
                "isparam": True,
                "minimum": -5000.00,
                "maximum": 0.00,
                "default": 0.00,
                "category": "Test"
            }}

        database = import_database_json(raw_json)

        assert len(database) == 1
        item = database["bidirectional_param"]
        assert isinstance(item, OIVariable)
        assert item.decimals == 2
        assert item.step == 10
        """A parameters with a positive and negative range will
        have a step size that matches the positive or negative only ranges."""

        raw_json = {
            "bidirectional_param": {
                "unit": "A",
                "id": 2001,
                "isparam": True,
                "minimum": -5000.00,
                "maximum": 5000.00,
                "default": 0.00,
                "category": "Test"
            }}

        database = import_database_json(raw_json)

        assert len(database) == 1
        item = database["bidirectional_param"]
        assert isinstance(item, OIVariable)
        assert item.decimals == 2
        assert item.step == 10
        """A parameters with a range biased away from zero should
        have a step size that matches a range of the same size around zero"""

        raw_json = {
            "bidirectional_param": {
                "unit": "A",
                "id": 2001,
                "isparam": True,
                "minimum": 5000.00,
                "maximum": 10000.00,
                "default": 0.00,
                "category": "Test"
            }}

        database = import_database_json(raw_json)

        assert len(database) == 1
        item = database["bidirectional_param"]
        assert isinstance(item, OIVariable)
        assert item.decimals == 2
        assert item.step == 10
        """Verify that huge dimensionless parameters have a large step size"""

        raw_json = {
            "huge_param": {
                "unit": "",
                "id": 2000,
                "isparam": True,
                "minimum": 0.00,
                "maximum": 100000.00,
                "default": 50000.00,
                "category": "Test"
            }}

        database = import_database_json(raw_json)

        assert len(database) == 1
        item = database["huge_param"]
        assert isinstance(item, OIVariable)
        assert item.decimals == 2
        assert item.step == 1000


class TestCachedDatabases:
    """
    Unit test caching of JSON parameter databases
    """

    def test_new_empty_cache_location(
            self,
            tmp_path: Path,
            test_network: canopen.Network,
            simulator: OISimulatedNode):

        simulator.checksum = 12345678
        simulator.LoadDatabase(TEST_DATA_DIR / "single-param.json")

        cache = tmp_path / "empty-but-non-existent"
        assert not cache.is_dir()

        database = import_cached_database(test_network, 42, cache)

        assert cache.is_dir()

        assert database["param1"]

        cached_file = next(cache.iterdir(), None)
        assert cached_file
        assert cached_file.is_file()
        assert cached_file.stat().st_size > 0

    def test_long_new_cache_path(self, tmp_path: Path,
                                 test_network: canopen.Network,
                                 simulator: OISimulatedNode):
        simulator.checksum = 12345678
        simulator.LoadDatabase(TEST_DATA_DIR / "single-param.json")

        cache = tmp_path / "a" / "deep" / "new" / "path"
        assert not cache.is_dir()

        database = import_cached_database(test_network, 42, cache)

        assert cache.is_dir()

        assert database["param1"]

    def test_empty_but_present_cache_location(self, tmp_path: Path,
                                              test_network: canopen.Network,
                                              simulator: OISimulatedNode):
        simulator.checksum = 12345678
        simulator.LoadDatabase(TEST_DATA_DIR / "single-param.json")

        cache = tmp_path / "empty-but-exists"
        cache.mkdir()

        assert len(list(cache.iterdir())) == 0

        database = import_cached_database(test_network, 42, cache)

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

    def test_database_is_cached(self, tmp_path: Path,
                                test_network: canopen.Network,
                                simulator: OISimulatedNode):
        simulator.checksum = 12345678
        simulator.LoadDatabase(TEST_DATA_DIR / "single-param.json")

        cache = tmp_path

        # prime the cache
        database = import_cached_database(test_network, 42, cache)

        assert database["param1"]

        # Load a completely different database but don't update the checksum
        simulator.LoadDatabase(TEST_DATA_DIR / "complex.json")

        # Load the database again which should load from the cache
        database = import_cached_database(test_network, 42, cache)

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

    def test_cached_database_is_updated(self, tmp_path: Path,
                                        test_network: canopen.Network,
                                        simulator: OISimulatedNode):
        simulator.checksum = 12345678
        simulator.LoadDatabase(TEST_DATA_DIR / "single-param.json")

        cache = tmp_path

        # prime the cache
        database = import_cached_database(test_network, 42, cache)

        assert database["param1"]

        # Load a completely different database and update the checksum on the
        # remote node
        simulator.LoadDatabase(TEST_DATA_DIR / "complex.json")
        simulator.checksum = 4567890

        # Load the database again which should update from the remote node
        database = import_cached_database(test_network, 42, cache)

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
            tmp_path: Path,
            test_network: canopen.Network,
            simulator: OISimulatedNode):
        cache = tmp_path

        # Set up up the first node
        simulator.checksum = 12345678
        simulator.LoadDatabase(TEST_DATA_DIR / "single-param.json")

        # Load the database from the first node
        database = import_cached_database(test_network, 42, cache)

        assert database["param1"]

        # Set up a second node with the same database
        simulator = OISimulatedNode(99)
        simulator.checksum = 12345678
        simulator.LoadDatabase(TEST_DATA_DIR / "single-param.json")

        # Load the database from the second node
        database = import_cached_database(test_network, 99, cache)

        assert database["param1"]

        # There should two cached files for each node and they should be
        # identical
        cache_files = list(cache.iterdir())
        assert len(cache_files) == 2
        assert filecmp.cmp(cache_files[0], cache_files[1], shallow=False)


class TestValueToString:
    """
    Unit test the conversion of numeric values to user-facing strings using a
    OIVariable instance.
    """

    def test_numeric_value_is_converted_to_simple_string(self):
        param = OIVariable("numeric",  0)

        output = value_to_str(param, 123.45, symbolic=False)

        assert output == "123.45"

    def test_symbolic_doesnt_affect_numeric_value(self):
        param = OIVariable("numeric",  0)

        output = value_to_str(param, 123.45)

        assert output == "123.45"

    def test_simple_enum_value(self):
        param = OIVariable("enum",  0)
        param.value_descriptions = {0: "Off", 1: "On"}

        output = value_to_str(param, 1)

        assert output == "On"

    def test_enum_value_without_symbolic_display_returns_a_number(self):
        param = OIVariable("enum",  0)
        param.value_descriptions = {0: "Off", 1: "On"}

        output = value_to_str(param, 1, symbolic=False)

        assert output == "1"

    def test_enum_with_unknown_value_is_returned_with_annotation(self):
        param = OIVariable("enum",  0)
        param.value_descriptions = {0: "Off", 1: "On"}

        output = value_to_str(param, 2)

        assert output == "2 (Unknown value)"

    def test_bitfield_with_single_bit_set(self):
        param = OIVariable("canio",  2022)
        param.bit_definitions = {1: "Cruise", 2: "Start", 4: "Brake", 8: "Fwd",
                                 16: "Rev", 32: "Bms"}

        output = value_to_str(param, 4)

        assert output == "Brake"

    def test_bitfield_with_multiple_bits_set(self):
        param = OIVariable("canio",  2022)
        param.bit_definitions = {1: "Cruise", 2: "Start", 4: "Brake", 8: "Fwd",
                                 16: "Rev", 32: "Bms"}

        output = value_to_str(param, 21)

        assert output == "Cruise, Brake, Rev"

    def test_bitfield_with_zero_value_but_param_doesnt_define(self):
        param = OIVariable("canio",  2022)
        param.bit_definitions = {1: "Cruise", 2: "Start", 4: "Brake", 8: "Fwd",
                                 16: "Rev", 32: "Bms"}

        output = value_to_str(param, 0)

        assert output == "0"

    def test_bitfield_with_zero_value_where_param_defines_symbol(self):
        param = OIVariable("status",  2044)
        param.bit_definitions = {
            0: "None", 1: "UdcLow", 2: "UdcHigh",
            4: "UdcBelowUdcSw", 8: "UdcLim"
        }

        output = value_to_str(param, 0)

        assert output == "None"

    def test_bitfield_value_without_symbolic_display_returns_a_number(self):
        param = OIVariable("status",  2044)
        param.bit_definitions = {
            0: "None", 1: "UdcLow", 2: "UdcHigh",
            4: "UdcBelowUdcSw", 8: "UdcLim"
        }

        output = value_to_str(param, 15, symbolic=False)

        assert output == "15"


@pytest.fixture
def param_name_from_id_db():
    """Create a dummy ObjectDictionary and add OIVariables"""
    db = canopen.ObjectDictionary()
    var1 = OIVariable("param1", 100)
    var2 = OIVariable("param2", 200)
    var3 = OIVariable("param3", 300)
    db.add_object(var1)
    db.add_object(var2)
    db.add_object(var3)
    return db


class TestParamNameFromId:
    """
    Unit tests for param_name_from_id function.
    """

    def test_existing_param_id_returns_name(self, param_name_from_id_db):
        # Should return the correct name for existing param IDs
        assert param_name_from_id(100, param_name_from_id_db) == "param1"
        assert param_name_from_id(200, param_name_from_id_db) == "param2"
        assert param_name_from_id(300, param_name_from_id_db) == "param3"

    def test_nonexistent_param_id_returns_id_as_string(
            self, param_name_from_id_db):
        # Should return the param_id as string if not found
        assert param_name_from_id(999, param_name_from_id_db) == "999"
        assert param_name_from_id(-1, param_name_from_id_db) == "-1"

    def test_empty_database_returns_id_as_string(self):
        # Should return the param_id as string if db is empty
        empty_db = canopen.ObjectDictionary()
        assert param_name_from_id(100, empty_db) == "100"

    def test_database_with_non_oivariable_objects(self, param_name_from_id_db):
        # Should ignore non-OIVariable objects in db.names
        param_name_from_id_db.add_object(
            canopen.objectdictionary.ODVariable(
                "not_an_oi_param", 123, 456))
        assert param_name_from_id(100, param_name_from_id_db) == "param1"
        assert param_name_from_id(999, param_name_from_id_db) == "999"
