# openinverter CAN tool

[![Build status](../../actions/workflows/test.yml/badge.svg)](../../actions/workflows/test.yml)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/openinverter-can-tool)
![PyPI - License](https://img.shields.io/pypi/l/openinverter-can-tool)

A tool to allow configuration and operating of openinverter systems for
electric vehicles over a CAN connection.

## Features

* Display all available modifiable parameters and read-only values supported by a given inverter firmware version
* Read a specified parameter/value
* Write a new value to a specified parameter
* Display the current value of each parameter/value on a given device
* Log a list of parameters to a CSV file at regular intervals
* Save and load all parameters to and from a JSON file
* Manage parameter to custom CAN message mappings:
  * Create, remove and list parameter mappings on a device
  * Export and import mappings to a local JSON file
  * Export mappings to DBC allowing easier debugging with [SavvyCAN](https://savvycan.com/)
* Display the inverter serial number
* Command the inverter to:
  * Start
  * Stop
  * Load parameters from flash
  * Save parameters to flash
  * Revert parameters to their default values
  * Reset
* Scan a CAN bus for possible nodes
* Runs on Linux, Windows and MacOS with python 3.8+
* Works with any CAN adapter supported by [python-can](https://pypi.org/project/python-can/)
* Supports [stm32-sine](https://github.com/jsphuebner/stm32-sine) 5.24.R or later
* Automatic parameter database download and caching (requires stm32-sine 5.27.R or later)
* Works with [Foccci/Clara](https://github.com/uhi22/ccs32clara) CCS controller and [Stm32-vcu](https://github.com/damienmaguire/Stm32-vcu) (a.k.a Zombieverter VCU)

## Installation

The most recent release may be installed using pip:

```text
    pip install openinverter_can_tool
```

To install directly from github:

```text
    git clone https://github.com/davefiddes/openinverter_can_tool.git
    cd openinverter_can_tool
    pip install -e .
```

### Linux

Linux users may reduce the potential of package conflicts by installing python dependencies from their package manager. This should be done before running `pip`.

#### Fedora

```text
    sudo dnf install python3-setuptools python3-pip python3-click python3-can python3-appdirs
```

#### Ubuntu/Debian

```text
    sudo apt install python3-setuptools python3-pip python3-click python3-can python3-appsdirs
```

## Configuration

Before the tool can be used the CAN interface adapter needs to be configured. To do this create `~/.canrc` on Linux or `%USERPROFILE%/can.conf` on Windows. Details on interfaces supported and the configuration file format can be found in the [python-can](https://python-can.readthedocs.io/en/stable/installation.html) documentation.

An example configuration file for a [SocketCAN](https://python-can.readthedocs.io/en/stable/interfaces/socketcan.html) compatible adapter on Linux would look like:

```text
[default]
interface = socketcan
channel = can0
bitrate = 500000
```

Note: Before the tool can on Linux run the SocketCAN network interface needs to be started:

```text
    sudo ip link set can0 up type can bitrate 500000
```

An example configuration file for a [SLCAN](https://python-can.readthedocs.io/en/stable/interfaces/slcan.html) adapter such as [GVRET](https://github.com/collin80/GVRET) on Windows would look like:

```text
[default]
interface = slcan
channel = COM8
bitrate = 500000
```

Tested interfaces:

* [Innomaker USB2CAN](https://www.inno-maker.com/product/usb2can-cable/) CAN interface in Linux.
* [GVRET](https://github.com/collin80/GVRET) CAN interface using `slcan` in Linux

Let me know if you have used a particular CAN interface successfully and I can expand this list.

## Usage

The parameters and values supported by a given openinverter firmware will often vary from release to release and by firmware type (e.g. Sine to Field Oriented Control(FOC)). The tool comes with a small collection of  parameter databases for recent openinverter releases. These can be found in the parameter-databases directory in the install location. Versions of stm32-sine from 5.25.R and onwards support automatic download of parameter databases and the database option does not need to be specified.

To get the usage information for the tool run the `oic` command with no parameters:

```text
    Usage: oic [OPTIONS] COMMAND [ARGS]...

    openinverter CAN Tool allows querying and setting configuration of inverter
    parameters over a CAN connection

    Options:
    -d, --database FILE  Override the openinverter JSON parameter database to
                        use
    -c, --context TEXT   Which python-can configuration context to use
    -n, --node INTEGER   The CAN SDO node ID to communicate with  [env var:
                        OIC_NODE; default: 1]
    -t, --timeout FLOAT  Response timeout in seconds  [default: 1.0]
    --version            Show the version and exit.
    --help               Show this message and exit.

    Commands:
    cache       Parameter database cache management commands
    can         Manage parameter to CAN message mappings on a device
    cmd         Execute a command on a device
    dumpall     Dump the values of all available parameters and values
    listparams  List all available parameters and values
    load        Load all parameters from json IN_FILE
    log         Log the value of PARAMS from the device periodically in CSV...
    read        Read the value of PARAM from the device
    save        Save all parameters in json to OUT_FILE
    scan        Scan the CAN bus for available nodes
    serialno    Read the device serial number.
    write       Write the value to the parameter PARAM on the device
```

To read a specific parameter from 5.24.R firmware:

```text
    $ oic -d parameter-databases/stm32-sine.5.24.R-foc.json read brakeregen
    brakeregen: -13 [%]
```

To write a new value to a parameter with 5.27.R or later firmware with automatic database download:

```text
    oic write brakeregen -30.5
```

Values may be changed using symbolic names:

```text
    oic write potmode DualChannel
    oic write pinswap PWMOutput13,PWMOutput23
```

The list of allowed values for a given parameter can be found using the `listparams` command.

## Development

If you want to be able to change the code while using it, clone it then install
it in development mode:

```text
    git clone https://github.com/davefiddes/openinverter_can_tool.git
    cd openinverter_can_tool
    virtualenv venv
    . venv/bin/activate
    pip install -e .[dev,test]
    pre-commit install
```

To exit the virtualenv environment use use the system installed `oic` run `dectivate`. To resume development operation the virtualenv can be restarted by running:

```text
    . venv/bin/activate
```

Unit tests and python code linting can be run on all supported python versions using the `tox` test framework.

Code is written to conform to PEP8 conventions and enforced by `pylint` and `flake8` linting.

Contributions are most welcome. Before raising a pull request please install and use the pre-commit git hooks provided to ensure code conforms to the project style. Thanks!
