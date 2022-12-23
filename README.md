# openinverter CAN tool

[![Build status](../../actions/workflows/test.yml/badge.svg)](../../actions/workflows/test.yml)

A tool to allow configuration and operating of openinverter systems for
electric vehicles over a CAN connection.

## Features

* Display all available modifiable parameters and read-only values supported by a given inverter firmware version
* Read a specified parameter/value
* Write a new value to a specified parameter
* Display the current value of each parameter/value on a given device
* Runs on Linux, Windows and MacOS with python 3.7+
* Works with any CAN adapter supported by [python-can](https://pypi.org/project/python-can/)
* Supports [stm32-sine](https://github.com/jsphuebner/stm32-sine) 5.24.R or later

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

Linux users may reduce the potential of package conflicts by installing python dependencies from their package manager. This should be done before running `pip`

#### Fedora

```text
    sudo dnf install python3-setuptools python3-pip python3-click python3-can
```

#### Ubuntu/Debian

```text
    sudo apt install python3-setuptools python3-pip python3-click python3-can
```

## Usage

So far the tool has only been tested with an [Innomaker USB2CAN](https://www.inno-maker.com/product/usb2can-cable/) CAN interface in Linux. It should work with any interface supported by the [python-can](https://python-can.readthedocs.io/en/stable/installation.html).

Before the tool can on Linux run the CAN network interface needs to be started:

```text
    sudo ip link set can0 up type can bitrate 500000
```

The parameters and values supported by a given openinverter firmware will often vary from release to release and by firmware type (e.g. Sine to Field Oriented Control(FOC)). The tool comes with a small collection of  parameter databases for recent openinverter releases. These can be found in the parameter-databases directory in the install location.

To get the usage information for the tool run the `oic` command with no parameters:

```text
    $ oic
    Usage: oic [OPTIONS] COMMAND [ARGS]...

      openinverter CAN Tool allows querying and setting configuration of inverter
      parameters over a CAN connection

    Options:
      -d, --database FILE  openinverter JSON parameter database to use
      -b, --bustype TEXT   Which python-can bus type to use  [default: socketcan]
      -c, --channel TEXT   Which python-can bus channel to use  [default: can0]
      -s, --speed INTEGER  The CAN bus speed. Typically 500kbps for openinverter
                           boards  [default: 500000]
      -n, --node INTEGER   The CAN SDO node ID to communicate with  [default: 1]
      --version            Show the version and exit.
      --help               Show this message and exit.

    Commands:
      dumpall     Dump the values of all available parameters and values
      listparams  List all available parameters and values
      read        Read the value of PARAM from the device
      write       Write the value to the parameter PARAM on the device
```

To read a specific parameter:

```text
    $ oic -d parameter-databases/stm32-sine.5.24.R-foc.json read brakeregen
    brakeregen: -13 [%]
```

To write a new value to a parameter:

```text
    oic -d parameter-databases/stm32-sine.5.24.R-foc.json write brakeregen -30.5
```

## Development

If you want to be able to change the code while using it, clone it then install
it in development mode:

```text
    git clone https://github.com/davefiddes/openinverter_can_tool.git
    cd openinverter_can_tool
    pip install -e .[dev,test]
```

Unit tests and python code linting can be run on all supported python versions using the `tox` test framework.

Code is written to conform to PEP8 conventions and enforced by `pylint` and `flake8` linting.
