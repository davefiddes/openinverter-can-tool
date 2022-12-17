"""
openinverter CAN Tools main program
"""

import functools
from typing import Optional
import click
import canopen
from .paramdb import import_database
from .fpfloat import fixed_to_float, fixed_from_float


class CliSettings:
    """Simple class to store the common settings used for all commands"""

    def __init__(
            self,
            database: canopen.ObjectDictionary,
            bustype: str,
            channel: str,
            speed: int,
            node_number: int) -> None:
        self.database = database
        self.bustype = bustype
        self.channel = channel
        self.speed = speed
        self.node_number = node_number
        self.network = Optional[canopen.Network]
        self.node = Optional[canopen.Node]


pass_cli_settings = click.make_pass_decorator(CliSettings)


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
            network.connect(
                bustype=cli_settings.bustype,
                channel=cli_settings.channel,
                bitrate=cli_settings.speed)

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
              help="openinverter JSON parameter database to use",
              type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.option("-b", "--bustype",
              default="socketcan",
              show_default=True,
              type=click.STRING,
              help="Which python-can bus type to use")
@click.option("-c", "--channel",
              default="can0",
              show_default=True,
              type=click.STRING,
              help="Which python-can bus channel to use")
@click.option("-s", "--speed",
              default=500000,
              show_default=True,
              type=click.INT,
              help="The CAN bus speed. Typically 500kbps for openinverter "
              "boards")
@click.option("-n", "--node",
              default=1,
              show_default=True,
              type=click.INT,
              help="The CAN SDO node ID to communicate with")
@click.version_option()
@click.pass_context
def cli(ctx, database, bustype, channel, speed, node):
    """openinverter CAN Tool allows querying and setting configuration of
    inverter parameters over a CAN connection"""
    if not database:
        raise click.BadParameter(
            'Parameter database filename not given', param_hint='-d')

    ctx.obj = CliSettings(import_database(database),
                          bustype, channel, speed, node)


@cli.command()
@pass_cli_settings
def listparams(cli_settings: CliSettings):
    """List all available parameters and values"""
    for item in cli_settings.database.names.values():
        print(
            f"{item.name} [{item.unit}]", end='')

        if item.min or item.max or item.default:
            print(
                f" - min: {fixed_to_float(item.min):g} "
                f"max: {fixed_to_float(item.max):g} "
                f"default: {fixed_to_float(item.default):g}")
        else:
            print(" - read-only value")


@cli.command()
@pass_cli_settings
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


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("param")
@click.argument("value", type=float)
@pass_cli_settings
@can_action
def write(cli_settings: CliSettings, param: str, value: float):
    """Write the value to the parameter PARAM on the device"""

    if param in cli_settings.database.names:
        param_item = cli_settings.database.names[param]

        fixed_value = fixed_from_float(value)

        if fixed_value < param_item.min:
            click.echo(f"Value {value:g} is smaller than the minimum value "
                       f"{fixed_to_float(param_item.min):g} allowed for "
                       f"{param}")
        elif fixed_value > param_item.max:
            click.echo(f"Value {value:g} is larger than the maximum value "
                       f"{fixed_to_float(param_item.max):g} allowed for "
                       f"{param}")
        else:
            cli_settings.node.sdo[param].raw = fixed_value
    else:
        click.echo(f"Unknown parameter: {param}")
