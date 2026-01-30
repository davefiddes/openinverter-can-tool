"""
Pytest configuration and shared fixtures
"""

import canopen
import pytest

from .oi_sim import OISimulatedNode


@pytest.fixture
def test_network():
    """
    Fixture that provides a canopen.Network instance for testing.

    Creates a virtual CAN network connection for use by test cases.
    Automatically disconnects after the test completes.
    """
    network = canopen.Network()
    network.NOTIFIER_SHUTDOWN_TIMEOUT = 0.0
    network.connect("test", bustype="virtual")

    yield network

    # Cleanup: disconnect the network
    network.disconnect()


@pytest.fixture
def simulator():
    """
    Create a simulated OpenInverter node with a specific node ID for
    testing.
    """
    simulator = OISimulatedNode(42)

    yield simulator

    simulator.shutdown()
