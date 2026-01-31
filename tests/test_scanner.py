"""OpenInverter network scanner unit tests"""

import canopen
import pytest

from openinverter_can_tool.scanner import scan_network
from .oi_sim import OISimulatedNode

# Reduce test verbosity
# pylint: disable=missing-function-docstring

# Stop pytest fixtures from tripping up pylint
# pylint: disable=redefined-outer-name


def test_scan_network_finds_sim_node(test_network: canopen.Network,
                                     simulator: OISimulatedNode):
    # The simulated node is node_id=42
    _ = simulator
    # Send a scan and check if 42 is found
    found = scan_network(test_network, wait_time=0)
    assert 42 in found


def test_scan_network_empty():
    # Create a network with no nodes
    network = canopen.Network()
    network.connect("empty", bustype="virtual")
    found = scan_network(network, wait_time=0)
    assert found == []
    network.disconnect()


def test_scan_network_asserts_on_no_network():
    with pytest.raises(AssertionError):
        scan_network(None)  # type: ignore
