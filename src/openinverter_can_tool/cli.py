"""
OpenInverter CAN Tools main program
"""

import csv
import datetime
import functools
import glob
import json
import logging
import os
import re
import time
from ast import literal_eval
from pathlib import Path
from typing import List, Optional, cast

import appdirs
import can
import canopen
import canopen.objectdictionary
import click

from . import constants as oi
from .can_upgrade import CanUpgrader, Failure, State, StateUpdate
from .fpfloat import fixed_to_float
from .map_persistence import export_dbc_map, export_json_map, import_json_map
from .oi_node import CanMessage, Direction, OpenInverterNode
from .param_utils import ParamWriter
from .paramdb import (OIVariable, import_cached_database, import_database,
                      param_name_from_id, value_to_str)
from .scanner import scan_network


class CliSettings:
    """Simple class to store the common settings used for all commands"""

    def __init__(
            self,
            database_path: str,
            context: str,
            node_number: int,
            timeout: float,
            debug: bool) -> None:
        self.database_path = database_path
        self.context = context
        self.node_number = node_number
        self.network: Optional[canopen.Network] = None
        self.database = canopen.objectdictionary.ObjectDictionary()
        self.node: Optional[OpenInverterNode] = None
        self.timeout = timeout
        self.debug = debug


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

        # Ensure we always have something to return
        return_value = None

        try:
            if cli_settings.database_path:
                device_db = import_database(Path(cli_settings.database_path))
            else:
                # Fire up the CAN network just to grab the node parameter
                # database from the device
                with canopen.Network() as network:
                    network.connect(context=cli_settings.context)
                    network.check()

                    device_db = import_cached_database(
                        network,
                        cli_settings.node_number,
                        Path(appdirs.user_cache_dir(oi.APPNAME, oi.APPAUTHOR)))

            cli_settings.database = device_db

            # Return the command handler function if we've been successful
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

        return return_value

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

        try:
            # Start with creating a network representing one CAN bus
            with canopen.Network() as network:
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

        return return_value

    return wrapper_can_action


@click.group()
@click.option("-d", "--database",
              type=click.Path(exists=True, file_okay=True, dir_okay=False),
              help="Override the OpenInverter JSON parameter database to use")
@click.option("-c", "--context",
              default=None,
              show_default=True,
              type=click.STRING,
              help="Which python-can configuration context to use")
@click.option("-n", "--node",
              default=1,
              show_default=True,
              type=click.IntRange(1, 127),
              envvar="OIC_NODE",
              show_envvar=True,
              help="The CAN SDO node ID to communicate with")
@click.option("-t", "--timeout",
              default=1.0,
              show_default=True,
              type=click.FLOAT,
              help="Response timeout in seconds")
@click.option("--debug",
              is_flag=True,
              default=False,
              help="Enable detailed debugging messages")
@click.version_option()
@click.pass_context
def cli(ctx: click.Context,
        database: str,
        context: str,
        node: int,
        timeout: float,
        debug: bool) -> None:
    """OpenInverter CAN Tool allows querying and setting configuration of
    inverter parameters over a CAN connection"""

    if debug:
        logging.basicConfig(level=logging.DEBUG)

    ctx.obj = CliSettings(database, context, node, timeout, debug)


def print_param_def(item: OIVariable) -> None:
    """Output the definition of a single parameter definition"""
    click.echo(f"{item.name} [{item.unit}]", nl=False)

    if item.isparam:
        assert item.min is not None
        assert item.max is not None
        assert item.default is not None
        click.echo(
            f" - min: {fixed_to_float(item.min):g} "
            f"max: {fixed_to_float(item.max):g} "
            f"default: {fixed_to_float(item.default):g}")
    else:
        click.echo(" - read-only value")


@cli.command()
@click.argument("param", required=True)
@pass_cli_settings
@db_action
def listparam(cli_settings: CliSettings, param: str) -> None:
    """List the definition of PARAM"""

    if param in cli_settings.database.names:
        print_param_def(cli_settings.database.names[param])
    else:
        click.echo(f"Unknown parameter: {param}")


@cli.command()
@pass_cli_settings
@db_action
def listparams(cli_settings: CliSettings) -> None:
    """List all available parameters and values"""
    for item in cli_settings.database.names.values():
        print_param_def(item)


@cli.command()
@pass_cli_settings
@db_action
@can_action
def dumpall(cli_settings: CliSettings) -> None:
    """Dump the values of all available parameters and values"""

    node = cli_settings.node
    assert node
    for variable in cli_settings.database.names.values():
        value_str = value_to_str(
            variable,
            fixed_to_float(node.sdo[variable.name].raw))
        click.echo(f"{variable.name:20}: {value_str}")


@cli.command()
@click.argument("param", required=True)
@pass_cli_settings
@db_action
@can_action
def read(cli_settings: CliSettings, param: str) -> None:
    """Read the value of PARAM from the device"""

    if param in cli_settings.database.names:
        node = cli_settings.node
        assert node
        value_str = value_to_str(
            cli_settings.database.names[param],
            fixed_to_float(node.sdo[param].raw))
        click.echo(f"{param:20}: {value_str}")
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
@click.option("--symbolic/--numeric",
              show_default=True,
              default=True,
              help="Convert bit-field and enumerations to symbolic "
              "text values or leave as numbers")
@pass_cli_settings
@db_action
@can_action
def log(cli_settings: CliSettings,
        params: tuple,
        out_file: click.File,
        step: int,
        timestamp: bool,
        symbolic: bool) -> None:
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

    query_list: List[OIVariable] = []
    avail_names = cli_settings.database.names

    # special case wildcard parameter names
    if "ALL" in params:
        query_list = list(avail_names.values())

    elif "PARAMS" in params:
        query_list = [p for p in avail_names.values() if p.isparam]

    elif "VALUES" in params:
        query_list = [p for p in avail_names.values() if not p.isparam]

    else:
        # Validate the list of supplied parameters
        for param in params:
            if param in avail_names:
                query_list.append(avail_names[param])
            else:
                click.echo(f"Ignoring unknown parameter: {param}")

    # create a CSV writer to control the output in a format that LibreOffice
    # can open and graph easily
    if timestamp:
        header_list = ["timestamp"]
    else:
        header_list = []
    header_list += [p.name for p in query_list]

    writer = csv.DictWriter(
        out_file, fieldnames=header_list, quoting=csv.QUOTE_ALL)
    writer.writeheader()

    # Loop forever logging
    node = cli_settings.node
    assert node
    while True:
        row = {}
        if timestamp:
            row["timestamp"] = str(datetime.datetime.now())
        for param in query_list:
            row[param.name] = value_to_str(
                param,
                fixed_to_float(node.sdo[param.name].raw),
                symbolic)
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
    assert node
    for item in cli_settings.database.names.values():
        if item.isparam:
            doc[item.name] = fixed_to_float(node.sdo[item.name].raw)
            count += 1

    json.dump(doc, out_file, indent=4)

    click.echo(f"Saved {count} parameters")


@cli.command(context_settings={"ignore_unknown_options": True})
@click.argument("param")
@click.argument("value")
@pass_cli_settings
@db_action
@can_action
def write(cli_settings: CliSettings, param: str, value: str) -> None:
    """Write the value to the parameter PARAM on the device"""

    assert cli_settings.node

    writer = ParamWriter(cli_settings.node, cli_settings.database, click.echo)
    writer.write(param, value)


@cli.command()
@click.argument("in_file", type=click.File("r"))
@pass_cli_settings
@db_action
@can_action
def load(cli_settings: CliSettings, in_file: click.File) -> None:
    """Load all parameters from json IN_FILE"""

    assert cli_settings.node
    writer = ParamWriter(cli_settings.node, cli_settings.database, click.echo)
    doc = json.load(in_file)
    count = 0
    for param_name in doc:
        value = doc[param_name]

        # JSON parameter files from openinverter.org/parameters/ put values in
        # quotation marks which isn't technically valid but we can work around
        if isinstance(value, str):
            value = float(value)

        writer.write(param_name, value)
        count += 1

    click.echo(f"Loaded {count} parameters")


@cli.command()
@pass_cli_settings
@can_action
def serialno(cli_settings: CliSettings) -> None:
    """Read the device serial number. This can be useful to recover failed
    devices using the 'upgrade' command."""

    assert cli_settings.node
    serialno_data = cli_settings.node.serial_no()
    part_str = []
    for part in range(0, 12, 4):
        part = serialno_data[part:part+4]
        part_str.append("".join(format(x, "02X") for x in part))

    click.echo(f"Serial Number: {part_str[0]}:{part_str[1]}:{part_str[2]}")


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


def print_can_map(
        direction_str: str,
        cur_map: List[CanMessage],
        db: canopen.ObjectDictionary) -> None:
    """Helper function to print the contents of a CAN message map """

    msg_index = 0
    param_index = 0
    for msg in cur_map:
        if msg.is_extended_frame:
            click.echo(f"{msg.can_id:#010x}:")
        else:
            click.echo(f"{msg.can_id:#x}:")

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
@click.option("--standard", "is_extended_frame", flag_value=False,
              default=True, show_default=True,
              help="Use standard format CAN 2.0a frames with 11-bit addresses "
              "(0-2047) or (0x000-0x7ff)")
@click.option("--extended", "is_extended_frame", flag_value=True,
              help="Use extended format CAN 2.0b frames with 29-bit addresses "
              "(0-536870911) or (0x00000000-0x1fffffff)")
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
    offset: int,
    is_extended_frame: bool
) -> None:
    """Add a CAN message mapping for a specific parameter

    \b
    CAN_ID   - A valid CAN ID in decimal or hexadecimal (prefix with '0x')
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
    if is_extended_frame:
        if can_id_int < 0 or can_id_int >= 0x20000000:
            click.echo(f"can_id: {can_id} out of range for an extended CAN " +
                       "frame.\nExpected 0x00000000-0x1fffffff or 0-536870911")
            return
    else:
        if can_id_int < 0 or can_id_int >= 0x800:
            click.echo(f"can_id: {can_id} out of range for a standard CAN " +
                       "frame.\nExpected 0x000-0x7ff or 0-2047")
            return

    click.echo(f"Adding CAN {direction} mapping with ", nl=False)
    if is_extended_frame:
        click.echo(f"can_id={can_id_int:#010x} ", nl=False)
    else:
        click.echo(f"can_id={can_id_int:#x} ", nl=False)
    click.echo(f"param='{param}' position={position} " +
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
        offset,
        is_extended_frame)

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
@click.argument("direction",
                required=True, type=click.Choice(["tx", "rx", "all"]),
                default="all")
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
    if direction == "all":
        node.clear_map(Direction.TX)
        node.clear_map(Direction.RX)
    else:
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


@cli.command("errors")
@pass_cli_settings
@db_action
@can_action
def list_errors(cli_settings: CliSettings) -> None:
    """List all of the errors on a device"""

    assert cli_settings.node
    node = cli_settings.node

    errors = node.list_errors()

    if len(errors) > 0:
        for error in errors:
            error_time, error_string = error
            click.echo(f"{str(error_time):20}: {error_string}")
    else:
        click.echo("No errors")


@cli.command()
@pass_cli_settings
@can_action
def scan(cli_settings: CliSettings) -> None:
    """Scan the CAN bus for available nodes"""

    assert cli_settings.network is not None

    click.echo("Scanning for devices. Please wait...\n")

    node_list = scan_network(cli_settings.network)

    if node_list:
        for node_id in node_list:
            click.echo(f"Found possible OpenInverter node: {node_id}")
    else:
        click.echo("No nodes found")


@cli.command()
@pass_cli_settings
@can_action
@click.argument("firmware_file",
                type=click.Path(
                    file_okay=True,
                    dir_okay=False,
                    writable=False,
                    path_type=Path))
@click.option("-s", "--serial",
              default=None,
              type=click.STRING,
              help="The serial number of a specific device to recover. "
              "Only the first 8 digits of the serial number are required.")
@click.option("--recover",
              is_flag=True,
              help="Recover a device as it starts up.")
@click.option("--wait",
              default=5.0,
              show_default=True,
              type=click.FLOAT,
              help="Time to wait for a device to reset and start the upgrade "
              " process in seconds")
def upgrade(
        cli_settings: CliSettings,
        firmware_file: Path,
        serial: str,
        recover: bool,
        wait: float) -> None:
    """
    Upgrade the device firmware.

    For devices that are operating normally the process is fully automatic.

    It is possible to recover a faulty device. The upgrade process will wait
    until the device boots before starting the upgrade process. It is up to
    the user to boot the device, typically by powering it on.

    On a CAN network with more than one device it is recommended to specify
    the device serial number. The upgrade process will ensure that only this
    device is upgraded. If no serial number is provided the first device to
    boot will be upgraded.
    """

    failure_messages = {
        Failure.PROTOCOL_ERROR:
        "Unexpected CAN frame received from device",

        Failure.UPGRADE_IN_PROGRESS:
        "An upgrade is already in progress on the CAN bus",

        Failure.PAGE_CRC_ERROR:
        "Firmware upload data corruption detected"
    }

    def _print_progress(update: StateUpdate) -> None:
        if update.state == State.START:
            click.echo("Waiting for device to connect...", nl=False)

        elif update.state == State.HEADER:
            serialno_str = "".join(format(x, "02x") for x in update.serialno)
            click.echo(f"\rDevice upgrade started for {serialno_str}")

        elif update.state in (State.UPLOAD, State.CHECK_CRC):
            progress = update.progress
            click.echo(f"\rUpgrading: {progress:.1f}% complete", nl=False)

        elif update.state == State.WAIT_FOR_DONE:
            click.echo(
                "\rWaiting for device to complete upgrade", nl=False)

        elif update.state == State.FAILURE:
            if update.failure in failure_messages:
                click.echo(
                    f"Upgrade failed: {failure_messages[update.failure]}")
            else:
                click.echo(
                    f"Upgrade failed: Unknown failure - {update.failure}")

        elif update.state == State.COMPLETE:
            click.echo("\rUpgrade completed successfully!".ljust(40))

    assert cli_settings.network is not None
    if recover:
        if serial and len(serial) != 8:
            click.echo("Device serial numbers should be 8 hexadecimal digits")
            return

        if serial:
            recovery_serialno = bytes.fromhex(serial)
        else:
            recovery_serialno = None

        upgrader = CanUpgrader(cli_settings.network, recovery_serialno,
                               firmware_file, _print_progress)

    else:
        if serial:
            click.echo("Serial numbers do not need to be provided for normal "
                       "upgrades")
            return

        assert cli_settings.node
        node_serialno = cli_settings.node.serial_no()

        upgrader = CanUpgrader(cli_settings.network, node_serialno[:4],
                               firmware_file, _print_progress)

        try:
            if not cli_settings.debug:
                # suppress logging errors from the canopen library if the
                # device doesn't respond when asked to reset
                logging.disable(logging.ERROR)

            cli_settings.node.reset()
        except canopen.SdoCommunicationError:
            pass

    if not upgrader.run(wait):
        click.echo("\r\nUpgrade timed out")


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
