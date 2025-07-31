"""openinverter network scanner unit tests"""

import pytest
from openinverter_can_tool.scanner import scan_network
from tests.oi_sim import OISimulatedNode

import canopen


@pytest.fixture
def sim_node():
    node = OISimulatedNode(node_id=5)
    yield node
    del node


def test_scan_network_finds_sim_node(sim_node):
    # The simulated node is node_id=5
    # Send a scan and check if 5 is found
    found = scan_network(sim_node.network, wait_time=0)
    assert 5 in found


def test_scan_network_empty():
    # Create a network with no nodes
    network = canopen.Network()
    network.connect("test", bustype="virtual")
    found = scan_network(network, wait_time=0)
    assert found == []
    network.disconnect()


def test_scan_network_asserts_on_no_network():
    with pytest.raises(AssertionError):
        scan_network(None)
