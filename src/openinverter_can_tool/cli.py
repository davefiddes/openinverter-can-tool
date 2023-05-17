"""
openinverter CAN Tools main program
"""

import functools
from typing import Optional, Union
import json
import csv
import time
import datetime
import glob
import os
import click
import can
import canopen
import appdirs
from .paramdb import import_database, import_cached_database
from .fpfloat import fixed_to_float, fixed_from_float
from . import constants as oi


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
        self.network = Optional[canopen.Network]
        self.database = canopen.objectdictionary.ObjectDictionary()
        self.node = Optional[canopen.Node]
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
            device_db = import_database(cli_settings.database_path)
        else:
            try:
                # Fire up the CAN network just to grab the node parameter
                # database from the device
                network = canopen.Network()
                network.connect(context=cli_settings.context)
                network.check()

                device_db = import_cached_database(
                    network,
                    cli_settings.node_number,
                    appdirs.user_cache_dir(oi.APPNAME, oi.APPAUTHOR))
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

        try:
            # Start with creating a network representing one CAN bus
            network = canopen.Network()

            # Connect to the CAN bus
            network.connect(context=cli_settings.context)

            network.check()

            node = canopen.BaseNode402(
                cli_settings.node_number, cli_settings.database)
            node.sdo.RESPONSE_TIMEOUT = cli_settings.timeout
            network.add_node(node)

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
              help="Override the openinverter JSON parameter database to use",
              type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.option("-c", "--context",
              default=None,
              show_default=True,
              type=click.STRING,
              help="Which python-can configuration context to use")
@click.option("-n", "--node",
              default=1,
              show_default=True,
              type=click.INT,
              help="The CAN SDO node ID to communicate with")
@click.option("-t", "--timeout",
              default=1.0,
              show_default=True,
              type=click.FLOAT,
              help="Response timeout in seconds")
@click.version_option()
@click.pass_context
def cli(ctx, database, context, node, timeout):
    """openinverter CAN Tool allows querying and setting configuration of
    inverter parameters over a CAN connection"""

    ctx.obj = CliSettings(database, context, node, timeout)


@cli.command()
@pass_cli_settings
@db_action
def listparams(cli_settings: CliSettings):
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


def print_param(
        variable: canopen.objectdictionary.Variable,
        value: float) -> str:
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
def dumpall(cli_settings: CliSettings):
    """Dump the values of all available parameters and values"""

    node = cli_settings.node
    for item in cli_settings.database.names.values():
        print_param(item, fixed_to_float(node.sdo[item.name].raw))


@cli.command()
@click.argument("param", required=True)
@pass_cli_settings
@db_action
@can_action
def read(cli_settings: CliSettings, param: str):
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
        timestamp: bool):
    """Log the value of PARAMS from the device periodically in CSV
    format. Multiple parameters may be specified separated by a space.
    OUT_FILE may be a filename or - to output to stdout."""

    # Validate the list of supplied parameters
    query_list = []
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
def save(cli_settings: CliSettings, out_file: click.File):
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
        param: canopen.objectdictionary.Variable,
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
        param: canopen.objectdictionary.Variable,
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
        param: canopen.objectdictionary.Variable,
        value: float) -> None:
    """Set a parameter with a floating point value over SDO"""

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
        value: Union[float, str]):
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


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("param")
@click.argument("value")
@pass_cli_settings
@db_action
@can_action
def write(cli_settings: CliSettings, param: str, value: str):
    """Write the value to the parameter PARAM on the device"""

    write_impl(cli_settings, param, value)


@cli.command()
@click.argument("in_file", type=click.File("r"))
@pass_cli_settings
@db_action
@can_action
def load(cli_settings: CliSettings, in_file: click.File):
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
def serialno(cli_settings: CliSettings):
    """Read the device serial number. This is required to load firmware over
    CAN"""

    # Fetch the serial number in 3 parts reversing from little-endian on the
    # wire into a reversed array where the LSB is first and MSB is last. This
    # is odd but mirrors the behaviour of the STM32 terminal "serial" command
    # for consistency.
    serialno_data = bytearray()
    for i in reversed(range(3)):
        serialno_data.extend(
            reversed(cli_settings.node.sdo.upload(oi.SERIALNO_INDEX, i)))

    # Print out the serial number array
    serialno_str = "".join(format(x, "02x") for x in serialno_data)
    click.echo(f"Serial Number: {serialno_str}")


@cli.group()
@pass_cli_settings
def cmd(cli_settings: CliSettings):
    """Execute a command on a device"""
    # We have to have cli_settings to allow the command hierarchy to work but
    # it is unused here so just pretend to use it
    _ = cli_settings


def send_command(
        cli_settings: CliSettings,
        command: int,
        arg: int = 0) -> None:
    """Send a command as a faked up SDO download """

    fake_var = canopen.objectdictionary.Variable(
        "command",
        oi.COMMAND_INDEX,
        command)
    fake_var.data_type = canopen.objectdictionary.UNSIGNED32
    cli_settings.database.add_object(fake_var)
    cli_settings.node.sdo["command"].raw = arg
    click.echo("Command sent successfully")


@cmd.command("save")
@pass_cli_settings
@can_action
def cmd_save(cli_settings: CliSettings):
    """Save device parameters and CAN map to flash"""
    send_command(cli_settings, oi.SAVE_COMMAND_SUBINDEX)


@cmd.command("load")
@pass_cli_settings
@can_action
def cmd_load(cli_settings: CliSettings):
    """Load device parameters and CAN map from flash"""
    send_command(cli_settings, oi.LOAD_COMMAND_SUBINDEX)


@cmd.command("reset")
@pass_cli_settings
@can_action
def cmd_reset(cli_settings: CliSettings):
    """Reset the device"""
    send_command(cli_settings, oi.RESET_COMMAND_SUBINDEX)


@cmd.command("defaults")
@pass_cli_settings
@can_action
def cmd_defaults(cli_settings: CliSettings):
    """Reset the device parameters to their built-in defaults"""
    send_command(cli_settings, oi.DEFAULTS_COMMAND_SUBINDEX)


@cmd.command("stop")
@pass_cli_settings
@can_action
def cmd_stop(cli_settings: CliSettings):
    """Stop the device from operating"""
    send_command(cli_settings, oi.STOP_COMMAND_SUBINDEX)


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
def cmd_start(cli_settings: CliSettings, mode):
    """Start the device in the specified mode"""
    mode_list = {
        "Normal": oi.START_MODE_NORMAL,
        "Manual": oi.START_MODE_MANUAL,
        "Boost": oi.START_MODE_BOOST,
        "Buck": oi.START_MODE_BUCK,
        "Sine": oi.START_MODE_SINE,
        "ACHeat": oi.START_MODE_ACHEAT
    }

    send_command(cli_settings, oi.START_COMMAND_SUBINDEX, mode_list[mode])


@cli.command()
@pass_cli_settings
@can_action
def scan(cli_settings: CliSettings):
    """Scan the CAN bus for available nodes"""

    # Maximum number of devices we are going to scan for
    limit = 20

    # Actively scan the bus for SDO nodes which might indicate something we
    # can talk to
    click.echo("Scanning for devices. Please wait...\n")
    cli_settings.network.scanner.search(limit)

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
def cache(cli_settings: CliSettings):
    """Parameter database cache management commands"""
    # We have to have cli_settings to allow the command hierarchy to work but
    # it is unused here so just pretend to use it
    _ = cli_settings


@cache.command("clean")
@pass_cli_settings
def cmd_clean(cli_settings: CliSettings):
    """Remove all entries from the parameter database cache"""

    # cli_settings is unused
    _ = cli_settings

    for file in glob.glob(
            os.path.join(
                appdirs.user_cache_dir(oi.APPNAME, oi.APPAUTHOR), "*.json")):
        click.echo(f"Removing {file}")
        os.remove(file)
