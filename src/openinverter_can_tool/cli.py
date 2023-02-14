"""
openinverter CAN Tools main program
"""

import functools
from typing import Optional
import json
import click
import canopen
from .paramdb import import_database, import_remote_database
from .fpfloat import fixed_to_float, fixed_from_float
from . import constants as oi


class CliSettings:
    """Simple class to store the common settings used for all commands"""

    def __init__(
            self,
            database_path: str,
            context: str,
            node_number: int) -> None:
        self.database_path = database_path
        self.context = context
        self.node_number = node_number
        self.network = Optional[canopen.Network]
        self.database = canopen.objectdictionary.ObjectDictionary()
        self.node = Optional[canopen.Node]


pass_cli_settings = click.make_pass_decorator(CliSettings)


def db_action(func):
    """Figure out what parameter database we are to use and allow the wrapped
    function to access it. This decorator should be specified prior to the
    can_action decorator to allow the SDO node to be created.
    """
    @functools.wraps(func)
    def wrapper_can_action(*args, **kwargs):

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

                device_db = import_remote_database(
                    network, cli_settings.node_number)
            finally:
                if network:
                    network.disconnect()

        cli_settings.database = device_db

        # Call the command handler function
        return func(*args, **kwargs)

    return wrapper_can_action


def can_action(func):
    """Establish a CAN connection and allow the wrapped function to access
     the configured CAN SDO node
     """
    @functools.wraps(func)
    def wrapper_can_action(*args, **kwargs):

        # Assume that the first argument exists and is a CliSettings
        cli_settings: CliSettings = args[0]

        try:
            # Start with creating a network representing one CAN bus
            network = canopen.Network()

            # Connect to the CAN bus
            network.connect(context=cli_settings.context)

            network.check()

            node = canopen.BaseNode402(
                cli_settings.node_number, cli_settings.database)
            network.add_node(node)

            # store the network and node objects in the context
            cli_settings.network = network
            cli_settings.node = node

            # Call the command handler function
            return_value = func(*args, **kwargs)

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
@click.version_option()
@click.pass_context
def cli(ctx, database, context, node):
    """openinverter CAN Tool allows querying and setting configuration of
    inverter parameters over a CAN connection"""

    ctx.obj = CliSettings(database, context, node)


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


@cli.command()
@pass_cli_settings
@db_action
@can_action
def dumpall(cli_settings: CliSettings):
    """Dump the values of all available parameters and values"""

    node = cli_settings.node
    for item in cli_settings.database.names.values():
        click.echo(
            f"{item.name:20}: {fixed_to_float(node.sdo[item.name].raw):10g} "
            f"[{item.unit}]")


@cli.command()
@click.argument("param", required=True)
@pass_cli_settings
@db_action
@can_action
def read(cli_settings: CliSettings, param: str):
    """Read the value of PARAM from the device"""

    if param in cli_settings.database.names:
        node = cli_settings.node
        click.echo(
            f"{param}: {fixed_to_float(node.sdo[param].raw):g} "
            f"[{cli_settings.database.names[param].unit}]")
    else:
        click.echo(f"Unknown parameter: {param}")


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


def write_impl(cli_settings: CliSettings, param: str, value: float):
    """Implementation of the single parameter write command. Separated from
    the command so the logic can be shared with loading all parameters from
    json."""

    if param in cli_settings.database.names:
        param_item = cli_settings.database.names[param]

        # Check if we are a modifiable parameter
        if param_item.isparam:
            fixed_value = fixed_from_float(value)

            if fixed_value < param_item.min:
                click.echo(f"Value {value:g} is smaller than the minimum "
                           f"value {fixed_to_float(param_item.min):g} allowed "
                           f"for {param}")
            elif fixed_value > param_item.max:
                click.echo(f"Value {value:g} is larger than the maximum value "
                           f"{fixed_to_float(param_item.max):g} allowed for "
                           f"{param}")
            else:
                cli_settings.node.sdo[param].raw = fixed_value
        else:
            click.echo(f"{param} is a spot value parameter. "
                       "Spot values are read-only.")
    else:
        click.echo(f"Unknown parameter: {param}")


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("param")
@click.argument("value", type=float)
@pass_cli_settings
@db_action
@can_action
def write(cli_settings: CliSettings, param: str, value: float):
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
    try:
        cli_settings.node.sdo["command"].raw = arg
        click.echo("Command sent successfully")
    except canopen.SdoAbortedError as e:
        if e.code == oi.SDO_ABORT_OBJECT_NOT_AVAILABLE:
            click.echo("Command not supported")
        else:
            click.echo(f"Unexpected error: {e}")


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
              default="Normal")
@pass_cli_settings
@can_action
def cmd_start(cli_settings: CliSettings, mode):
    """Start the device in the specified mode"""
    Modes = {
        "Normal": oi.START_MODE_NORMAL,
        "Manual": oi.START_MODE_MANUAL,
        "Boost": oi.START_MODE_BOOST,
        "Buck": oi.START_MODE_BUCK,
        "Sine": oi.START_MODE_SINE,
        "ACHeat": oi.START_MODE_ACHEAT
    }

    send_command(cli_settings, oi.DEFAULTS_COMMAND_SUBINDEX, Modes[mode])
