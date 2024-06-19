"""
openinverter CAN Tools main program
"""

import csv
import datetime
import functools
import glob
import json
import os
import re
import time
from ast import literal_eval
from pathlib import Path
from typing import List, Optional, Union, cast

import appdirs
import can
import canopen
import canopen.objectdictionary
import click

from . import constants as oi
from .fpfloat import fixed_from_float, fixed_to_float
from .map_persistence import export_json_map, import_json_map, export_dbc_map
from .oi_node import CanMessage, Direction, OpenInverterNode
from .paramdb import OIVariable, import_cached_database, import_database


class CliSettings:
    """Simple class to store the common settings used for all commands"""

    def __init__(
            self,
            database_path: str,
            context: str,
            node_number: int,
            timeout: float) -> None:
        self.database_path = database_path
        self.context = context
        self.node_number = node_number
        self.network: Optional[canopen.Network] = None
        self.database = canopen.objectdictionary.ObjectDictionary()
        self.node: Optional[OpenInverterNode] = None
        self.timeout = timeout


pass_cli_settings = click.make_pass_decorator(CliSettings)


def db_action(func):
    """Figure out what parameter database we are to use and allow the wrapped
    function to access it. This decorator should be specified prior to the
    can_action decorator to allow the SDO node to be created.
    """
    @functools.wraps(func)
    def wrapper_db_action(*args, **kwargs):

        # Assume that the first argument exists and is a CliSettings
        cli_settings: CliSettings = args[0]

        if cli_settings.database_path:
            device_db = import_database(Path(cli_settings.database_path))
        else:
            network = None
            try:
                # Fire up the CAN network just to grab the node parameter
                # database from the device
                network = canopen.Network()
                network.connect(context=cli_settings.context)
                network.check()

                device_db = import_cached_database(
                    network,
                    cli_settings.node_number,
                    Path(appdirs.user_cache_dir(oi.APPNAME, oi.APPAUTHOR)))
            finally:
                if network:
                    network.disconnect()

        cli_settings.database = device_db

        # Call the command handler function
        return func(*args, **kwargs)

    return wrapper_db_action


def can_action(func):
    """Establish a CAN connection and allow the wrapped function to access
     the configured CAN SDO node
     """
    @functools.wraps(func)
    def wrapper_can_action(*args, **kwargs):

        # Assume that the first argument exists and is a CliSettings
        cli_settings: CliSettings = args[0]

        # Ensure we always have something to return
        return_value = None

        network = None
        try:
            # Start with creating a network representing one CAN bus
            network = canopen.Network()

            # Connect to the CAN bus
            network.connect(context=cli_settings.context)

            network.check()

            node = OpenInverterNode(
                network,
                cli_settings.node_number,
                cli_settings.database)
            node.sdo.RESPONSE_TIMEOUT = cli_settings.timeout

            # store the network and node objects in the context
            cli_settings.network = network
            cli_settings.node = node

            # Call the command handler function
            return_value = func(*args, **kwargs)

        except canopen.SdoAbortedError as err:
            if err.code == oi.SDO_ABORT_OBJECT_NOT_AVAILABLE:
                click.echo("Command or parameter not supported")
            else:
                click.echo(f"Unexpected SDO Abort: {err}")

        except canopen.SdoCommunicationError as err:
            click.echo(f"SDO communication error: {err}")

        except can.exceptions.CanOperationError as err:
            click.echo(f"CAN error: {err}")

        except OSError as err:
            click.echo(f"OS error: {err}")

        finally:
            if network:
                network.disconnect()

        return return_value

    return wrapper_can_action


@click.group()
@click.option("-d", "--database",
              type=click.Path(exists=True, file_okay=True, dir_okay=False),
              help="Override the openinverter JSON parameter database to use")
@click.option("-c", "--context",
              default=None,
              show_default=True,
              type=click.STRING,
              help="Which python-can configuration context to use")
@click.option("-n", "--node",
              default=1,
              show_default=True,
              type=click.INT,
              envvar="OIC_NODE",
              show_envvar=True,
              help="The CAN SDO node ID to communicate with")
@click.option("-t", "--timeout",
              default=1.0,
              show_default=True,
              type=click.FLOAT,
              help="Response timeout in seconds")
@click.version_option()
@click.pass_context
def cli(ctx: click.Context,
        database: str,
        context: str,
        node: int,
        timeout: float) -> None:
    """openinverter CAN Tool allows querying and setting configuration of
    inverter parameters over a CAN connection"""

    ctx.obj = CliSettings(database, context, node, timeout)


@cli.command()
@pass_cli_settings
@db_action
def listparams(cli_settings: CliSettings) -> None:
    """List all available parameters and values"""
    for item in cli_settings.database.names.values():
        print(
            f"{item.name} [{item.unit}]", end="")

        if item.isparam:
            print(
                f" - min: {fixed_to_float(item.min):g} "
                f"max: {fixed_to_float(item.max):g} "
                f"default: {fixed_to_float(item.default):g}")
        else:
            print(" - read-only value")


def print_param(variable: OIVariable, value: float) -> None:
    """Print out the value of a parameter or outputs the enumeration value or
    bits in a bitfield"""

    click.echo(f"{variable.name:20}: ", nl=False)

    if variable.value_descriptions:
        if value in variable.value_descriptions:
            click.echo(f"{variable.value_descriptions[value]}")
        else:
            click.echo(f"{value:g} (Unknown value)")
    elif variable.bit_definitions:
        value = int(value)
        bit_str = ""
        for bit, description in variable.bit_definitions.items():
            if bit & value:
                bit_str = bit_str + description + ", "
        bit_str = bit_str.removesuffix(", ")

        if len(bit_str) == 0:
            bit_str = "0"

        click.echo(f"{bit_str}")
    else:
        click.echo(
            f"{value:g} [{variable.unit}]")


@cli.command()
@pass_cli_settings
@db_action
@can_action
def dumpall(cli_settings: CliSettings) -> None:
    """Dump the values of all available parameters and values"""

    node = cli_settings.node
    for item in cli_settings.database.names.values():
        print_param(item, fixed_to_float(node.sdo[item.name].raw))


@cli.command()
@click.argument("param", required=True)
@pass_cli_settings
@db_action
@can_action
def read(cli_settings: CliSettings, param: str) -> None:
    """Read the value of PARAM from the device"""

    if param in cli_settings.database.names:
        node = cli_settings.node
        print_param(
            cli_settings.database.names[param],
            fixed_to_float(node.sdo[param].raw))
    else:
        click.echo(f"Unknown parameter: {param}")


@cli.command()
@click.argument("params", required=True, nargs=-1)
@click.argument("out_file", type=click.File("w"))
@click.option("-s", "--step",
              default=1,
              show_default=True,
              type=click.IntRange(1, 3600),
              help="Time to wait before querying for new data in seconds")
@click.option("--timestamp/--no-timestamp",
              show_default=True,
              default=True,
              help="Include a timestamp on each row of the log")
@pass_cli_settings
@db_action
@can_action
def log(cli_settings: CliSettings,
        params: tuple,
        out_file: click.File,
        step: int,
        timestamp: bool) -> None:
    """
    Log the value of PARAMS from the device periodically in CSV
    format. Multiple parameters may be specified separated by a space.
    OUT_FILE may be a filename or - to output to stdout.

    Special wild card parameter names can be used:

    \b
    ALL    - Logs all parameters and spot values on the device
    PARAMS - Logs all the parameters on the device
    VALUES - Logs all spot values on the device

    The wildcards are case-sensitive.
    """

    query_list = []

    # special case wildcard parameter names
    if "ALL" in params:
        for param in cli_settings.database.names:
            query_list.append(param)

    elif "PARAMS" in params:
        for param in cli_settings.database.names.values():
            if param.isparam:
                query_list.append(param.name)

    elif "VALUES" in params:
        for param in cli_settings.database.names.values():
            if not param.isparam:
                query_list.append(param.name)

    else:
        # Validate the list of supplied parameters
        for param in params:
            if param in cli_settings.database.names:
                query_list.append(param)
            else:
                click.echo(f"Unknown parameter: {param}")

    # create a CSV writer to control the output in a format that LibreOffice
    # can open and graph easily
    if timestamp:
        header_list = ["timestamp"] + query_list
    else:
        header_list = query_list
    writer = csv.DictWriter(
        out_file, fieldnames=header_list, quoting=csv.QUOTE_ALL)
    writer.writeheader()

    # Loop forever logging
    node = cli_settings.node
    while True:
        row = {}
        if timestamp:
            row["timestamp"] = str(datetime.datetime.now())
        for param in query_list:
            row[param] = f"{fixed_to_float(node.sdo[param].raw):g}"
        writer.writerow(row)
        out_file.flush()

        time.sleep(step)


@cli.command()
@click.argument("out_file", type=click.File("w"))
@pass_cli_settings
@db_action
@can_action
def save(cli_settings: CliSettings, out_file: click.File) -> None:
    """Save all parameters in json to OUT_FILE"""

    doc = {}
    count = 0
    node = cli_settings.node
    for item in cli_settings.database.names.values():
        if item.isparam:
            doc[item.name] = fixed_to_float(node.sdo[item.name].raw)
            count += 1

    json.dump(doc, out_file, indent=4)

    click.echo(f"Saved {count} parameters")


def set_enum_value(
        node: canopen.Node,
        param: OIVariable,
        value: str) -> None:
    """Set a enumeration parameter over SDO by looking up its symbolic value"""

    result = None
    for key, description in param.value_descriptions.items():
        if description.lower() == value.lower():
            result = key

    if result is not None:
        node.sdo[param.name].raw = fixed_from_float(result)
    else:
        click.echo(f"Unable to find value: '{value}' for parameter: "
                   f"{param.name}. Valid values are "
                   f"{param.value_descriptions}")


def set_bitfield_value(
        node: canopen.Node,
        param: OIVariable,
        value: str) -> None:
    """Set a bitfield parameter over SDO by looking up its symbolic values. The
      value should be a comma separated list"""

    result = 0
    for bit_name in value.split(','):
        bit_name = bit_name.strip()
        for key, description in param.bit_definitions.items():
            if description.lower() == bit_name.lower():
                result |= key

    node.sdo[param.name].raw = fixed_from_float(result)


def set_float_value(
        node: canopen.Node,
        param: OIVariable,
        value: float) -> None:
    """Set a parameter with a floating point value over SDO"""

    # pre-conditions that should always be
    assert param.isparam
    assert param.min is not None
    assert param.max is not None

    fixed_value = fixed_from_float(value)

    if fixed_value < param.min:
        click.echo(f"Value {value:g} is smaller than the minimum "
                   f"value {fixed_to_float(param.min):g} allowed "
                   f"for {param.name}")
    elif fixed_value > param.max:
        click.echo(f"Value {value:g} is larger than the maximum value "
                   f"{fixed_to_float(param.max):g} allowed for "
                   f"{param.name}")
    else:
        node.sdo[param.name].raw = fixed_value


def write_impl(
        cli_settings: CliSettings,
        param: str,
        value: Union[float, str]) -> None:
    """Implementation of the single parameter write command. Separated from
    the command so the logic can be shared with loading all parameters from
    json."""

    if param in cli_settings.database.names:
        param_item = cli_settings.database.names[param]

        # Check if we are a modifiable parameter
        if param_item.isparam:
            if isinstance(value, float):
                set_float_value(cli_settings.node, param_item, value)
            else:
                # Assume the value is a float to start with
                try:
                    set_float_value(
                        cli_settings.node,
                        param_item,
                        float(value))
                except ValueError:
                    if param_item.value_descriptions:
                        set_enum_value(cli_settings.node, param_item, value)
                    elif param_item.bit_definitions:
                        set_bitfield_value(
                            cli_settings.node, param_item, value)
                    else:
                        click.echo(f"Invalid value: '{value}' for parameter: "
                                   f"{param}")
        else:
            click.echo(f"{param} is a spot value parameter. "
                       "Spot values are read-only.")
    else:
        click.echo(f"Unknown parameter: {param}")


@cli.command(context_settings={"ignore_unknown_options": True})
@click.argument("param")
@click.argument("value")
@pass_cli_settings
@db_action
@can_action
def write(cli_settings: CliSettings, param: str, value: str) -> None:
    """Write the value to the parameter PARAM on the device"""

    write_impl(cli_settings, param, value)


@cli.command()
@click.argument("in_file", type=click.File("r"))
@pass_cli_settings
@db_action
@can_action
def load(cli_settings: CliSettings, in_file: click.File) -> None:
    """Load all parameters from json IN_FILE"""

    doc = json.load(in_file)
    count = 0
    for param_name in doc:
        value = doc[param_name]

        # JSON parameter files from openinverter.org/parameters/ put values in
        # quotation marks which isn't technically valid but we can work around
        if isinstance(value, str):
            value = float(value)

        write_impl(cli_settings, param_name, value)
        count += 1

    click.echo(f"Loaded {count} parameters")


@cli.command()
@pass_cli_settings
@can_action
def serialno(cli_settings: CliSettings) -> None:
    """Read the device serial number. This is required to load firmware over
    CAN"""

    assert cli_settings.node
    serialno_data = cli_settings.node.serial_no()
    serialno_str = "".join(format(x, "02x") for x in serialno_data)
    click.echo(f"Serial Number: {serialno_str}")


@cli.group()
@pass_cli_settings
def cmd(cli_settings: CliSettings) -> None:
    """Execute a command on a device"""
    # We have to have cli_settings to allow the command hierarchy to work but
    # it is unused here so just pretend to use it
    _ = cli_settings


@cmd.command("save")
@pass_cli_settings
@can_action
def cmd_save(cli_settings: CliSettings) -> None:
    """Save device parameters and CAN map to flash"""
    assert cli_settings.node
    cli_settings.node.save()
    click.echo("Command sent successfully")


@cmd.command("load")
@pass_cli_settings
@can_action
def cmd_load(cli_settings: CliSettings) -> None:
    """Load device parameters and CAN map from flash"""
    assert cli_settings.node
    cli_settings.node.load()
    click.echo("Command sent successfully")


@cmd.command("reset")
@pass_cli_settings
@can_action
def cmd_reset(cli_settings: CliSettings) -> None:
    """Reset the device"""
    assert cli_settings.node
    cli_settings.node.reset()
    click.echo("Command sent successfully")


@cmd.command("defaults")
@pass_cli_settings
@can_action
def cmd_defaults(cli_settings: CliSettings) -> None:
    """Reset the device parameters to their built-in defaults"""
    assert cli_settings.node
    cli_settings.node.load_defaults()
    click.echo("Command sent successfully")


@cmd.command("start")
@click.option("--mode",
              type=click.Choice(["Normal",
                                 "Manual",
                                 "Boost",
                                 "Buck",
                                 "ACHeat",
                                 "Sine"],
                                case_sensitive=False),
              default="Normal",
              show_default=True)
@pass_cli_settings
@can_action
def cmd_start(cli_settings: CliSettings, mode: str) -> None:
    """Start the device in the specified mode"""
    mode_list = {
        "Normal": oi.START_MODE_NORMAL,
        "Manual": oi.START_MODE_MANUAL,
        "Boost": oi.START_MODE_BOOST,
        "Buck": oi.START_MODE_BUCK,
        "Sine": oi.START_MODE_SINE,
        "ACHeat": oi.START_MODE_ACHEAT
    }

    assert cli_settings.node
    cli_settings.node.start(mode_list[mode])
    click.echo("Command sent successfully")


@cmd.command("stop")
@pass_cli_settings
@can_action
def cmd_stop(cli_settings: CliSettings) -> None:
    """Stop the device from operating"""
    assert cli_settings.node
    cli_settings.node.stop()
    click.echo("Command sent successfully")


@cli.group("can")
@pass_cli_settings
def can_map(cli_settings: CliSettings) -> None:
    """Manage parameter to CAN message mappings on a device"""
    # We have to have cli_settings to allow the command hierarchy to work but
    # it is unused here so just pretend to use it
    _ = cli_settings


def param_name_from_id(param_id: int, db: canopen.ObjectDictionary) -> str:
    """Return the name of a parameter based on the openinverter parameter ID.
    If it is not in the database the number is returned."""

    # This is not evenly remotely efficient
    param_name = None
    for item in db.names.values():
        if isinstance(item, OIVariable) and item.id == param_id:
            param_name = item.name
            break

    if param_name is None:
        return f"{param_id}"
    else:
        return f"{param_name}"


def print_can_map(
        direction_str: str,
        cur_map: List[CanMessage],
        db: canopen.ObjectDictionary) -> None:
    """Helper function to print the contents of a CAN message map """

    msg_index = 0
    param_index = 0
    for msg in cur_map:
        click.echo(f"0x{msg.can_id:x}:")
        for entry in msg.params:
            click.echo(
                f" {direction_str}.{msg_index}.{param_index}" +
                f" param='{param_name_from_id(entry.param_id, db)}'" +
                f" pos={entry.position} length={entry.length}" +
                f" gain={entry.gain} offset={entry.offset}"
            )
            param_index += 1
        param_index = 0
        msg_index += 1


@can_map.command("list")
@pass_cli_settings
@db_action
@can_action
def cmd_can_list(
    cli_settings: CliSettings,
) -> None:
    """List parameter to CAN message mappings"""

    assert cli_settings.node
    node = cli_settings.node

    tx_map = node.list_can_map(Direction.TX)
    rx_map = node.list_can_map(Direction.RX)

    if not tx_map and not rx_map:
        click.echo("(none)")
    else:
        print_can_map(
            "tx",
            tx_map,
            cli_settings.database)

        print_can_map(
            "rx",
            rx_map,
            cli_settings.database)


@can_map.command("add", context_settings={"ignore_unknown_options": True})
@click.argument("direction", required=True, type=click.Choice(["tx", "rx"]))
@click.argument("can_id", required=True)
@click.argument("param", required=True)
@click.argument("position", required=True, type=click.IntRange(0, 63))
@click.argument("length", required=True, type=click.IntRange(-32, 32))
@click.argument("gain",
                type=click.FloatRange(-8388.608, 8388.607),
                default=1.0)
@click.argument("offset", type=click.IntRange(-128, 127), default=0)
@pass_cli_settings
@db_action
@can_action
def cmd_can_add(
    cli_settings: CliSettings,
    direction: str,
    can_id: str,
    param: str,
    position: int,
    length: int,
    gain: float,
    offset: int
) -> None:
    """Add a CAN message mapping for a specific parameter

    \b
    CAN_ID   - A valid CAN ID in decimal (0-2047) or hexadecimal (0x000-0x7ff)
    PARAM    - The parameter name to map
    POSITION - The starting bit position (0-63)
    LENGTH   - The number of bits the value will take up (-32,-1) or (1,32)
    GAIN     - The gain to multiply the value (-8388.608, 8388.607)
    OFFSET   - The offset to add (-128, 127)

    For transmit mappings the parameter value is multiplied by the GAIN before
    adding the OFFSET. The value is then mapped into the specified bits.

    For receive mappings the value is identified in the CAN frame, the OFFSET
    subtracted before dividing by the GAIN.

    Positive LENGTH values indicate a little-endian mapping. The bits count
    up from the start POSITION.

    Negative LENGTH values indicate a big-endian mapping. The bits count down
    from the end POSITION.

    \b
    Example:
    $ oic -n22 can add tx 0x101 temp3 32 8
    """

    if length == 0:
        click.echo("Map length cannot be 0")
        return

    # Get the parameter id by name from the cached database
    if param in cli_settings.database.names:
        param_id = cast(OIVariable, cli_settings.database.names[param]).id
    else:
        click.echo(f"Parameter {param} not found in database")
        return

    # Parse both hex as 0x1337 -> 4919 and decimal as 1337 -> 1337
    can_id_int = literal_eval(can_id)
    if can_id_int < 0 or can_id_int >= 0x800:
        click.echo(f"can_id: {can_id} out of range. " +
                   "Expected 0x000-0x7ff or 0-2047")
        return

    click.echo(f"Adding CAN {direction} mapping with " +
               f"can_id={can_id_int:#x} param='{param}' position={position} " +
               f"length={length} gain={gain} offset={offset}")

    assert cli_settings.node
    node = cli_settings.node
    node.add_can_map_entry(
        can_id_int,
        Direction[direction.upper()],
        param_id,
        position,
        length,
        gain,
        offset)

    click.echo("CAN mapping added successfully.")


@can_map.command("remove")
@click.argument("listing_id", required=True, type=str)
@pass_cli_settings
@can_action
def cmd_can_remove(
    cli_settings: CliSettings,
    listing_id: str,
) -> None:
    """
    Remove a parameter to CAN message mapping

    Mapping is referred to by an id in the format [tx/rx].<n>.<n>.

    \b
    Example:
    $ oic can list
    0x202:
     rx.0.0 param='soc' pos=16 len=8 gain=1.0 offset=0
    0x203:
     rx.1.0 param='maxpower' pos=32 len=16 gain=1.0 offset=0
     rx.1.2 param='maxcur' pos=16 len=16 gain=1.0 offset=0
    $ oic can remove rx.1.2
    CAN mapping removed successfully.
    $ oic can remove rx.0.0
    CAN mapping removed successfully.
    $ oic can list
    0x203:
     rx.1.0 param='maxpower' pos=32 len=16 gain=1.0 offset=0
    """

    listing_parts = re.match(
        r"^(tx|rx)\.(\d{1,2})\.(\d{1,2})$",
        listing_id,
        flags=re.IGNORECASE)

    if not listing_parts:
        click.echo('Invalid listing id: Correct format is "[tx/rx].<n>.<n>"')
        return

    direction = Direction[listing_parts[1].upper()]
    msg_index = int(listing_parts[2])
    param_index = int(listing_parts[3])

    assert cli_settings.node
    node = cli_settings.node
    if node.remove_can_map_entry(
            direction,
            msg_index,
            param_index):
        click.echo("CAN mapping removed successfully.")
    else:
        click.echo("Unable to find CAN map entry.")


@can_map.command("clear")
@click.argument("direction", required=True, type=click.Choice(["tx", "rx"]))
@pass_cli_settings
@can_action
def cmd_can_clear(
    cli_settings: CliSettings,
    direction: str,
) -> None:
    """
    Clear all parameter to CAN message mappings for the specified direction
    """

    assert cli_settings.node
    node = cli_settings.node
    node.clear_map(Direction[direction.upper()])

    click.echo(f"CAN {direction} mapping removed successfully.")


@can_map.command("export")
@click.argument("out_file",
                type=click.Path(
                    file_okay=True,
                    dir_okay=False,
                    writable=True,
                    path_type=Path))
@click.option("--format",
              type=click.Choice(["json",
                                 "dbc"],
                                case_sensitive=False),
              default="json",
              show_default=True)
@pass_cli_settings
@db_action
@can_action
def cmd_can_export(
    cli_settings: CliSettings,
    out_file: Path,
    format: str  # pylint: disable=redefined-builtin
) -> None:
    """Export all parameter to CAN message mappings to OUT_FILE"""

    assert cli_settings.node
    node = cli_settings.node

    tx_map = node.list_can_map(Direction.TX)
    rx_map = node.list_can_map(Direction.RX)

    if format == "json":
        with open(out_file, "wt", encoding="utf-8") as json_file:
            export_json_map(tx_map, rx_map, cli_settings.database, json_file)

    elif format == "dbc":
        export_dbc_map(f"node{cli_settings.node_number}",
                       tx_map, rx_map, cli_settings.database, out_file)

    click.echo("Parameter CAN message map exported")


@can_map.command("import")
@click.argument("in_file", type=click.File("r"))
@click.option("--clear/--no-clear",
              show_default=True,
              default=True,
              help="Clear any existing CAN message map")
@pass_cli_settings
@db_action
@can_action
def cmd_can_import(cli_settings: CliSettings,
                   in_file: click.File,
                   clear: bool) -> None:
    """Import a CAN message map from a json IN_FILE"""

    assert cli_settings.node
    node = cli_settings.node

    if clear:
        node.clear_map(Direction.TX)
        node.clear_map(Direction.RX)
        click.echo("Existing CAN message map cleared")

    (tx_map, rx_map) = import_json_map(in_file, cli_settings.database)

    node.add_can_map(Direction.TX, tx_map)
    click.echo("Transmit CAN message map configured")

    node.add_can_map(Direction.RX, rx_map)
    click.echo("Receive CAN message map configured")


@cli.command()
@pass_cli_settings
@can_action
def scan(cli_settings: CliSettings) -> None:
    """Scan the CAN bus for available nodes"""

    assert cli_settings.network is not None

    # Maximum number of devices we are going to scan for
    limit = 127

    # Canned SDO request we use to scan the bus with to find something
    # we can talk to
    sdo_req = b"\x40\x00\x10\x00\x00\x00\x00\x00"

    click.echo("Scanning for devices. Please wait...\n")

    # Implement our own scanner rather than use
    # canopen.network.scanner.search() as this lets us rate limit the scan to
    # avoid exhausting local CAN network queues
    for node_id in range(1, limit + 1):
        cli_settings.network.send_message(0x600 + node_id, sdo_req)
        time.sleep(0.01)

    # Wait for any responses to show up
    time.sleep(5)

    # filter out weird canopen internal node IDs that show up here and
    # nowhere else
    node_list = [id for id in cli_settings.network.scanner.nodes if id < limit]

    if node_list:
        for node_id in node_list:
            click.echo(f"Found possible openinverter node: {node_id}")
    else:
        click.echo("No nodes found")


@cli.group()
@pass_cli_settings
def cache(cli_settings: CliSettings) -> None:
    """Parameter database cache management commands"""
    # We have to have cli_settings to allow the command hierarchy to work but
    # it is unused here so just pretend to use it
    _ = cli_settings


@cache.command("clean")
@pass_cli_settings
def cmd_clean(cli_settings: CliSettings) -> None:
    """Remove all entries from the parameter database cache"""

    # cli_settings is unused
    _ = cli_settings

    count = 0
    for file in glob.glob(
            os.path.join(
                appdirs.user_cache_dir(oi.APPNAME, oi.APPAUTHOR), "*.json")):
        click.echo(f"Removing {file}")
        os.remove(file)
        count += 1

    if count == 0:
        click.echo("No cache entries found")
