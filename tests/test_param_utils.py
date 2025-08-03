"""Unit tests for the param_utils module"""
import canopen
import pytest

from openinverter_can_tool.fpfloat import fixed_from_float
from openinverter_can_tool.param_utils import ParamWriter
from openinverter_can_tool.paramdb import OIVariable

# Reduce test verbosity
# pylint: disable=missing-function-docstring,missing-class-docstring

# Stop pytest fixtures from tripping up pylint
# pylint: disable=redefined-outer-name


class DummyParam(OIVariable):
    def __init__(
        self,
            name,
            isparam=True,
            min_value=0,
            max_value=100,
            value_desc=None,
            bit_defs=None):
        super().__init__(name, 42)
        self.isparam = isparam
        self.min = fixed_from_float(min_value)
        self.max = fixed_from_float(max_value)
        self.value_descriptions = value_desc or {}
        self.bit_definitions = bit_defs or {}


class DummySdo:
    def __init__(self):
        self._values = {}

    def __getitem__(self, key):
        return self

    @property
    def raw(self):
        return self._values.get('raw', 0)

    @raw.setter
    def raw(self, value):
        self._values['raw'] = value


class DummyNode:
    def __init__(self):
        self.sdo = DummySdo()


@pytest.fixture
def log():
    return []


@pytest.fixture
def logger(log):
    def _log(msg):
        log.append(msg)
    return _log


@pytest.fixture
def node():
    return DummyNode()


def make_db(params):
    db = canopen.ObjectDictionary()
    for p in params:
        db.add_object(p)
    return db


def test_write_float_param(node, logger, log):
    db = make_db([
        DummyParam('foo', min_value=0, max_value=10)
    ])

    writer = ParamWriter(node, db, logger)
    writer.write('foo', 5.0)

    assert node.sdo['foo'].raw == 160  # 5.0 in fixed-point representation
    assert not log


def test_write_float_param_out_of_range_too_big(node, logger, log):
    db = make_db([
        DummyParam('foo', min_value=0, max_value=10)
    ])
    writer = ParamWriter(node, db, logger)
    writer.write('foo', 20.0)

    assert log and 'larger than the maximum' in log[0]
    assert node.sdo['foo'].raw == 0


def test_write_float_param_out_of_range_too_small(node, logger, log):
    db = make_db([
        DummyParam('foo', min_value=0, max_value=10)
    ])

    writer = ParamWriter(node, db, logger)
    writer.write('foo', -20.0)

    assert log and 'smaller than the minimum' in log[0]
    assert node.sdo['foo'].raw == 0


def test_write_float_param_with_random_characters(node, logger, log):
    db = make_db([
        DummyParam('foo', min_value=0, max_value=10)
    ])

    writer = ParamWriter(node, db, logger)
    writer.write('foo', 'forty-two')

    assert node.sdo['foo'].raw == 0
    assert log and 'Invalid value' in log[0]


def test_write_enum_param(node, logger, log):
    db = make_db([
        DummyParam('bar', value_desc={1: 'A', 2: 'B'})
    ])

    writer = ParamWriter(node, db, logger)
    writer.write('bar', 'A')

    assert node.sdo['bar'].raw == 32
    assert not log


def test_write_enum_param_that_doesnt_exist(node, logger, log):
    db = make_db([
        DummyParam('bar', value_desc={1: 'A', 2: 'B'})
    ])

    writer = ParamWriter(node, db, logger)
    writer.write('bar', 'C')

    assert node.sdo['bar'].raw == 0
    assert log and "Unable to find value: 'C' for parameter: bar" in log[0]


def test_write_bitfield_param(node, logger, log):
    db = make_db([
        DummyParam('baz', bit_defs={1: 'X', 2: 'Y'})
    ])

    writer = ParamWriter(node, db, logger)
    writer.write('baz', 'X,Y')

    assert node.sdo['baz'].raw == 96
    assert not log


def test_write_bitfield_param_that_doesnt_exist(node, logger, log):
    db = make_db([
        DummyParam('baz', bit_defs={1: 'X', 2: 'Y'})
    ])

    writer = ParamWriter(node, db, logger)
    writer.write('baz', 'Z')

    assert node.sdo['baz'].raw == 0
    assert log and "Unable to find bit name: 'Z' for parameter: baz" in log[0]


def test_write_unknown_param_should_fail(node, logger, log):
    db = make_db([])

    writer = ParamWriter(node, db, logger)
    writer.write('nope', 1.0)

    assert log and 'Unknown parameter' in log[0]


def test_write_spot_value_should_fail(node, logger, log):
    db = make_db([
        DummyParam('spot', isparam=False)
    ])

    writer = ParamWriter(node, db, logger)
    writer.write('spot', 1.0)

    assert log and 'read-only' in log[0]
