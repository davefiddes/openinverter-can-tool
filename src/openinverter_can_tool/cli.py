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
from ast import literal_eval
from .paramdb import import_database, import_cached_database, index_from_id
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
        self.network: Optional[canopen.Network] = None
        self.database = canopen.objectdictionary.ObjectDictionary()
        self.node: Optional[canopen.Node] = None
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

        network = None
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


def print_param(
        variable: canopen.objectdictionary.Variable,
        value: float) -> None:
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


@cli.command(context_settings=dict(ignore_unknown_options=True))
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
def cmd(cli_settings: CliSettings) -> None:
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
def cmd_save(cli_settings: CliSettings) -> None:
    """Save device parameters and CAN map to flash"""
    send_command(cli_settings, oi.SAVE_COMMAND_SUBINDEX)


@cmd.command("load")
@pass_cli_settings
@can_action
def cmd_load(cli_settings: CliSettings) -> None:
    """Load device parameters and CAN map from flash"""
    send_command(cli_settings, oi.LOAD_COMMAND_SUBINDEX)


@cmd.command("reset")
@pass_cli_settings
@can_action
def cmd_reset(cli_settings: CliSettings) -> None:
    """Reset the device"""
    send_command(cli_settings, oi.RESET_COMMAND_SUBINDEX)


@cmd.command("defaults")
@pass_cli_settings
@can_action
def cmd_defaults(cli_settings: CliSettings) -> None:
    """Reset the device parameters to their built-in defaults"""
    send_command(cli_settings, oi.DEFAULTS_COMMAND_SUBINDEX)


@cmd.command("stop")
@pass_cli_settings
@can_action
def cmd_stop(cli_settings: CliSettings) -> None:
    """Stop the device from operating"""
    send_command(cli_settings, oi.STOP_COMMAND_SUBINDEX)


@cli.group()
@pass_cli_settings
def can(cli_settings: CliSettings) -> None:
    """List and edit CAN mappings on a device"""
    # We have to have cli_settings to allow the command hierarchy to work but
    # it is unused here so just pretend to use it
    _ = cli_settings


class CanMapping:
    def __init__(self, sdo_index, sdo_subindex, rx, can_id, param_id, param_name, position, length, gain, offset):
        self.sdo_index = sdo_index
        self.sdo_subindex = sdo_subindex
        self.rx = rx
        self.can_id = can_id
        self.param_id = param_id
        self.param_name = param_name
        self.position = position
        self.length = length
        self.gain = gain
        self.offset = offset

    def __str__(self):
        return (
            ("rx" if self.rx else "tx")
            +" sdo_index="+str(self.sdo_index)
            +" sdo_subindex="+str(self.sdo_subindex)
            +" can_id="+hex(self.can_id)
            +(" param="+repr(self.param_name) if self.param_name
                else " param_id="+str(self.param_id))
            +" pos="+str(self.position)
            +" len="+str(self.length)
            +" gain="+str(self.gain)
            +" offset="+str(self.offset)
        )

@can.command("list")
@pass_cli_settings
@db_action
@can_action
def cmd_can_list(
    cli_settings: CliSettings,
) -> None:
    """List CAN mappings"""

    sdo_index = oi.CAN_MAP_LIST_TX_INDEX
    sdo_subindex = 0
    rx = False  # tx mappings come first, then rx

    mappings = []

    while True:
        # Request COB ID
        fake_var = canopen.objectdictionary.Variable(
                "command", sdo_index, 0)
        fake_var.data_type = canopen.objectdictionary.UNSIGNED32
        cli_settings.database.add_object(fake_var)
        try:
            can_id = cli_settings.node.sdo["command"].raw  # SDO read
            sdo_subindex += 1
        except canopen.SdoAbortedError as err:
            if err.code == oi.SDO_ABORT_OBJECT_NOT_AVAILABLE:
                if rx == False:
                    rx = True
                    sdo_index = oi.CAN_MAP_LIST_RX_INDEX
                    continue
                else:
                    break
            else:
                raise err

        while True:
            # Request Parameter id, position and length
            fake_var = canopen.objectdictionary.Variable(
                    "command", sdo_index, sdo_subindex)
            fake_var.data_type = canopen.objectdictionary.UNSIGNED32
            cli_settings.database.add_object(fake_var)
            try:
                dataposlen = cli_settings.node.sdo["command"].raw  # SDO read
            except canopen.SdoAbortedError as err:
                if err.code == oi.SDO_ABORT_OBJECT_NOT_AVAILABLE:
                    sdo_index += 1
                    sdo_subindex = 0
                    break
                else:
                    raise err

            # Request Gain and offset
            sdo_subindex += 1
            fake_var = canopen.objectdictionary.Variable(
                    "command", sdo_index, sdo_subindex)
            fake_var.data_type = canopen.objectdictionary.UNSIGNED32
            cli_settings.database.add_object(fake_var)
            try:
                gainofs = cli_settings.node.sdo["command"].raw  # SDO read
            except canopen.SdoAbortedError as err:
                if err.code == oi.SDO_ABORT_OBJECT_NOT_AVAILABLE:
                    break
                else:
                    raise err

            # Parse
            param_id = dataposlen & 0xffff
            position = (dataposlen >> 16) & 0xff
            length = (dataposlen >> 24) & 0xff
            gain = (gainofs & 0xffffff) / 1000
            offset = (gainofs >> 24) & 0xff

            # Get the parameter name by id from the cached database
            param_name = None
            (index, subindex) = index_from_id(param_id)
            for item in cli_settings.database.names.values():
                if item.index == index and item.subindex == subindex:
                    param_name = item.name

            mapping = CanMapping(sdo_index, sdo_subindex,
                    rx, can_id, param_id, param_name, position, length, gain, offset)

            mappings.append(mapping)

            sdo_subindex += 1

    if not mappings:
        click.echo("(none)")
    else:
        printed_can_id = None
        for mapping in mappings:
            if printed_can_id != mapping.can_id:
                printed_can_id = mapping.can_id
                click.echo(hex(printed_can_id)+":")
            click.echo(
                " "
                +("rx" if mapping.rx else "tx")
                +"."+str(mapping.sdo_index - (oi.CAN_MAP_LIST_RX_INDEX if mapping.rx
                    else oi.CAN_MAP_LIST_TX_INDEX))
                +"."+str(mapping.sdo_subindex // 2 - 1)
                +(" param="+repr(mapping.param_name) if mapping.param_name
                    else " param_id="+str(mapping.param_id))
                +" pos="+str(mapping.position)
                +" len="+str(mapping.length)
                +" gain="+str(mapping.gain)
                +" offset="+str(mapping.offset)
            )


@can.command("add")
@click.argument("txrx", required=True, type=click.Choice(["tx", "rx"]))
@click.argument("can_id", required=True)
@click.argument("param", required=True)
@click.argument("position", required=True, type=click.IntRange(0, 64))
@click.argument("length", required=True, type=click.IntRange(1, 64))
@click.argument("gain", type=click.FloatRange(0.0, 16777.215), default=1.0)
@click.argument("offset", type=int, default=0)
@pass_cli_settings
@db_action
@can_action
def cmd_can_add(
    cli_settings: CliSettings,
    txrx: str,
    can_id: int,
    param: str,
    position: int,
    length: int,
    gain: float,
    offset: int,
) -> None:
    """Add a CAN mapping

    \b
    Example:
    $ oic -n22 can add tx 0x101 temp3 32 8
    """

    if param[0:2] == '0x' or param.isnumeric():
        # Parse both hex as 0x1337 -> 4919 and decimal as 1337 -> 1337
        param_id = literal_eval(param)
    else:
        # Get the parameter id by name from the cached database
        param_id = None
        for item in cli_settings.database.names.values():
            if item.name == param:
                # Decode parameter id from index and subindex (see
                # index_from_id() in paramdb.py)
                param_id = ((item.index & ~0x2100) << 8) + item.subindex
        if param_id == None:
            click.echo("Parameter "+repr(param)+" not found in database")
            return
        click.echo("(Parameter id for "+repr(param)+" is "+str(param_id)+")")

    # Parse both hex as 0x1337 -> 4919 and decimal as 1337 -> 1337
    can_id = literal_eval(can_id)
    if can_id <= 0 or can_id >= 0x800:
        click.echo("can_id out of range")
        return

    click.echo("Adding CAN mapping with "+
            "can_id="+hex(can_id)+
            " param_id="+str(param_id)+
            " position="+str(position)+
            " length="+str(length)+
            " gain="+str(gain)+
            " offset="+str(offset))

    sdo_index = oi.CAN_MAP_TX_INDEX if txrx == "tx" else oi.CAN_MAP_RX_INDEX

    # Send COB id (CAN frame id)
    fake_var = canopen.objectdictionary.Variable(
            "command", sdo_index, 0x00)
    fake_var.data_type = canopen.objectdictionary.UNSIGNED32
    cli_settings.database.add_object(fake_var)
    cli_settings.node.sdo["command"].raw = can_id

    # Send Parameter id, position and length
    fake_var = canopen.objectdictionary.Variable(
            "command", sdo_index, 0x01)
    fake_var.data_type = canopen.objectdictionary.UNSIGNED32
    cli_settings.database.add_object(fake_var)
    cli_settings.node.sdo["command"].raw = (
            param_id | (position << 16) | (length << 24))

    # Send Gain and offset
    fake_var = canopen.objectdictionary.Variable(
            "command", sdo_index, 0x02)
    fake_var.data_type = canopen.objectdictionary.UNSIGNED32
    cli_settings.database.add_object(fake_var)
    cli_settings.node.sdo["command"].raw = (
            int(gain * 1000) | (offset << 24))

    click.echo("CAN mapping added succesfully.")


@can.command("remove")
@click.argument("listing_id", required=True, type=str)
@pass_cli_settings
@can_action
def cmd_can_remove(
    cli_settings: CliSettings,
    listing_id: str,
) -> None:
    """
    Remove a CAN mapping

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
    CAN mapping removed succesfully.
    $ oic can remove rx.0.0
    CAN mapping removed succesfully.
    $ oic can list
    0x203:
     rx.1.0 param='maxpower' pos=32 len=16 gain=1.0 offset=0
    """

    sub_ids = listing_id.split('.')
    txrx = sub_ids[0]
    mapping_index = sub_ids[1]
    mapping_subindex = sub_ids[2]

    if (txrx not in ["tx", "rx"] or not mapping_index.isnumeric() or
            not mapping_subindex.isnumeric()):
        click.echo('Invalid listing id: Correct format is "[tx/rx].<n>.<n>"')
        return

    mapping_index = int(mapping_index)
    mapping_subindex = int(mapping_subindex)

    sdo_index = mapping_index + (oi.CAN_MAP_LIST_RX_INDEX if txrx == "rx" else oi.CAN_MAP_LIST_TX_INDEX)
    sdo_subindex = (mapping_subindex + 1) * 2

    try:
        # Send COB id (CAN frame id)
        fake_var = canopen.objectdictionary.Variable(
                "command", sdo_index, sdo_subindex)
        fake_var.data_type = canopen.objectdictionary.UNSIGNED32
        cli_settings.database.add_object(fake_var)
        cli_settings.node.sdo["command"].raw = 0
    except canopen.SdoCommunicationError as err:
        if str(err) == "Unexpected response 0x23":
            # This is normal
            click.echo("CAN mapping removed succesfully.")
        else:
            raise err


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

    send_command(cli_settings, oi.START_COMMAND_SUBINDEX, mode_list[mode])


@cli.command()
@pass_cli_settings
@can_action
def scan(cli_settings: CliSettings) -> None:
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

    for file in glob.glob(
            os.path.join(
                appdirs.user_cache_dir(oi.APPNAME, oi.APPAUTHOR), "*.json")):
        click.echo(f"Removing {file}")
        os.remove(file)
