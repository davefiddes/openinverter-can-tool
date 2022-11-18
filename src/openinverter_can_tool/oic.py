"""
openinverter CAN Tools main program
"""

import argparse
import sys
from canopen import objectdictionary
from .paramdb import import_database
from .fpfloat import fixed_to_float


def print_parameters(database: objectdictionary.ObjectDictionary) -> None:
    """Print out the currently loaded parameter database"""
    for item in database.names.values():
        print(
            f"{item.name} [{item.unit}]", end='')

        if item.min or item.max or item.default:
            print(
                f" - min: {fixed_to_float(item.min)} "
                f"max: {fixed_to_float(item.max)} "
                f"default: {fixed_to_float(item.default)}")
        else:
            print(" - read-only value")


def main() -> None:
    """Main program starts here"""
    parser = argparse.ArgumentParser(
        prog="oic",
        description="openinverter CAN Tool allows querying and setting "
        "configuration of inverter parameters over a CAN connection")
    parser.add_argument("-d", "--database",
                        help="openinverter JSON parameter database to use")

    args = parser.parse_args()

    if not args.database:
        parser.error('Parameter database filename not given')
        sys.exit(1)

    print_parameters(import_database(args.database))
