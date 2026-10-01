"""Test transfers through the 24-bit bridge adapter installed by os_boundary.

Reads use debugger expressions without running guest code. Far writes follow
bridge_memory's paused bootstrap/IRQ-masked contract and preserve its borrowed
scratch. No observer may use the VBXE aperture or overwrite OS screen RAM.
"""


def transfer(bridge, source, destination, size, output):
    bridge.memload(destination, bridge.memdump(source, size))


def write(bridge, address, data, output):
    bridge.memload(address, data)


def read(bridge, address, size, output):
    return bridge.memdump(address, size)
