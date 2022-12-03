"""
openinverter CAN Tools main program
"""

import functools
import click
import canopen
from .paramdb import import_database
from .fpfloat import fixed_to_float


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

            # Call the command handler function with the CAN SDO node
            # object
            return_value = func(node, *args, **kwargs)

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
                f" - min: {fixed_to_float(item.min)} "
                f"max: {fixed_to_float(item.max)} "
                f"default: {fixed_to_float(item.default)}")
        else:
            print(" - read-only value")


@cli.command()
@pass_cli_settings
@can_action
def dumpall(node: canopen.Node,
            cli_settings: CliSettings):
    """Dump the values of all available parameters and values"""

    for item in cli_settings.database.names.values():
        click.echo(
            f"{item.name:20}: {fixed_to_float(node.sdo[item.name].raw):g}")
