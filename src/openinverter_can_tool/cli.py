"""
openinverter CAN Tools main program
"""

import click
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


@click.group()
@click.option("-d", "--database",
              help="openinverter JSON parameter database to use",
              type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.version_option()
@click.pass_context
def cli(ctx, database):
    """openinverter CAN Tool allows querying and setting configuration of
    inverter parameters over a CAN connection"""
    if not database:
        raise click.BadParameter(
            'Parameter database filename not given', param_hint='-d')

    # ensure that ctx.obj exists and is a dict (in case `cli()` is called
    # by means other than the `if` block below)
    ctx.ensure_object(dict)

    ctx.obj['DATABASE'] = import_database(database)


@cli.command()
@click.pass_context
def listparams(ctx):
    """List all available parameters and values"""
    print_parameters(ctx.obj['DATABASE'])
