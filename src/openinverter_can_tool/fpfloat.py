"""
Functions to manipulate OpenInverter fixed point values
"""

FACTOR = int(2**5)


def fixed_from_float(value: float) -> int:
    """convert a floating point value to a 32-bit/5-bit fixed point value"""
    return int(value * FACTOR)


def fixed_to_float(value: int) -> float:
    """convert a 32-bit/5-bit fixed point value to fixed point value"""
    return float(value / float(FACTOR))
