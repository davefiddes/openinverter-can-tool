"""CANopen network scanning"""

import time
import canopen


def scan_network(network: canopen.Network, wait_time: int = 5) -> list[int]:
    """Scan the CANopen network for nodes."""
    assert network is not None

    # Clear previous scan results
    network.scanner.reset()

    # Maximum number of devices we are going to scan for
    limit = 127

    # Canned SDO request we use to scan the bus with to find something
    # we can talk to
    sdo_req = b"\x40\x00\x10\x00\x00\x00\x00\x00"

    # Implement our own scanner rather than use
    # canopen.network.scanner.search() as this lets us rate limit the scan to
    # avoid exhausting local CAN network queues
    for node_id in range(1, limit + 1):
        network.send_message(0x600 + node_id, sdo_req)
        time.sleep(0.01)

    # Wait for any responses to show up
    time.sleep(wait_time)

    # filter out weird canopen internal node IDs that show up here and
    # nowhere else
    node_list = [id for id in network.scanner.nodes if id < limit]

    return node_list
