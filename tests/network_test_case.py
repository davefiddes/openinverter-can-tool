"""A simple framework for sending CAN frames to test cases"""

import unittest
from typing import List, Tuple, Type
import inspect

import canopen

TX = 1
RX = 2

# Reduce test verbosity
# pylint: disable=missing-function-docstring


class NetworkTestCase(unittest.TestCase):
    """
    Test the custom openinverter node protocol by example
    """

    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        self._node_type: Type

    def _send_message(self, can_id, data, remote=False):
        """Will be used instead of the usual Network.send_message method.

        Checks that the message data is according to expected and answers
        with the provided data.
        """
        next_data = self.data.pop(0)
        self.assertEqual(next_data[0], TX, "No transmission was expected")
        self.assertSequenceEqual(data, next_data[1])
        self.assertEqual(can_id, 0x602)
        while self.data and self.data[0][0] == RX:
            self.network.notify(0x582, bytearray(self.data.pop(0)[1]), 0.0)

        # pretend to use remote
        _ = remote

    def setUp(self):
        network = canopen.Network()
        network.NOTIFIER_SHUTDOWN_TIMEOUT = 0.0
        network.send_message = self._send_message

        arg_spec = inspect.getfullargspec(self._node_type.__init__)
        if len(arg_spec.args) > 3:
            node = self._node_type(network, 2, canopen.ObjectDictionary())
        else:
            node = self._node_type(network, 2)
        if "sdo" in node.__dict__:
            node.sdo.RESPONSE_TIMEOUT = 0.01
        self.node = node
        self.network = network
        self.data: List[Tuple[int, bytes]] = []

    def tearDown(self) -> None:
        # At the end of every test all of the data data should have been
        # consumed by _send_message()
        assert len(self.data) == 0
