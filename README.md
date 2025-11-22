# OpenInverter CAN tool

[![Build status](../../actions/workflows/test.yml/badge.svg)](../../actions/workflows/test.yml)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/openinverter-can-tool)
![PyPI - License](https://img.shields.io/pypi/l/openinverter-can-tool)

A tool to allow configuration and operating of OpenInverter systems for
electric vehicles over a CAN connection.

## Features

* Display all available modifiable parameters and read-only values supported by a given inverter firmware version
* Read a specified parameter/value
* Write a new value to a specified parameter
* Display the current value of each parameter/value on a given device
* Log a list of parameters to a CSV file at regular intervals
* Save and load all parameters to and from a JSON file
* Manage parameter to custom [CAN message mappings](https://github.com/davefiddes/openinverter-can-tool/blob/main/docs/can-mapping.md):
  * Create, remove and list parameter mappings on a device
  * Support maps with standard CAN 2.0a and extended CAN 2.0b frames
  * Export and import mappings to a local JSON file
  * Export mappings to DBC allowing easier debugging with [SavvyCAN](https://savvycan.com/)
* Upgrade firmware or recover devices over CAN
* Display the inverter serial number
* Command the inverter to:
  * Start
  * Stop
  * Load parameters from flash
  * Save parameters to flash
  * Revert parameters to their default values
  * Reset
* Display a device's error log
* Scan a CAN bus for possible nodes
* Runs on Linux, Windows and MacOS with python 3.9+
* Support [shell completion](https://github.com/davefiddes/openinverter-can-tool/blob/main/docs/shell-completion.md) for commands and options for bash, zsh and fish shells
* Works with any CAN adapter supported by [python-can](https://pypi.org/project/python-can/)
* Supports [stm32-sine](https://github.com/jsphuebner/stm32-sine) 5.24.R or later
* Automatic parameter database download and caching (requires stm32-sine 5.27.R or later)
* Works with [Foccci/Clara](https://github.com/uhi22/ccs32clara) CCS controller, [Stm32-vcu](https://github.com/damienmaguire/Stm32-vcu) (a.k.a. Zombieverter VCU) and [Flying ADC BMS](https://github.com/jsphuebner/FlyingAdcBms)

## Installation

To avoid any clashes with other software the tool is best is best installed using the [pipx](https://pipx.pypa.io/) package manager. Install this following the [pipx installation guide](https://pipx.pypa.io/stable/installation/) for your platform.

### Initial Install

The most recent release may be installed using:

```text
    pipx install openinverter_can_tool
```

### Upgrading

Upgrading to the most recent release is carried out using pip:

```text
    pipx upgrade openinverter_can_tool
```

## Configuration

Before the tool can be used the CAN interface adapter needs to be configured. To do this create `~/.canrc` on Linux and MacOS or `%USERPROFILE%/can.conf` on Windows. Details on interfaces supported and the configuration file format can be found in the [python-can](https://python-can.readthedocs.io/en/stable/configuration.html) documentation.

An example configuration file for a [SocketCAN](https://python-can.readthedocs.io/en/stable/interfaces/socketcan.html) compatible adapter on Linux would look like:

```text
[default]
interface = socketcan
channel = can0
bitrate = 500000
```

Note: Before the tool can on Linux run the SocketCAN network interface needs to be started. Read the [guide](https://github.com/davefiddes/openinverter-can-tool/blob/main/docs/socketcan-config.md) on how to do this.

An example configuration file for a [SLCAN](https://python-can.readthedocs.io/en/stable/interfaces/slcan.html) adapter such as [GVRET](https://github.com/collin80/GVRET) on Windows would look like:

```text
[default]
interface = slcan
channel = COM8
bitrate = 500000
```

### Tested interfaces

* [Innomaker USB2CAN](https://www.inno-maker.com/product/usb2can-cable/) in Linux using `socketcan`
* [GVRET](https://github.com/collin80/GVRET) in Linux using `slcan`
* [MKS CANable V2.0 Pro](https://github.com/makerbase-mks/CANable-MKS) in Windows and Linux using `slcan`
* [FYSETC UCAN](https://www.ebay.co.uk/itm/267167770235) in MacOS using `slcan`
* [Peak PCAN-USB](https://www.peak-system.com/PCAN-USB.199.0.html?L=1) in Linux using `socketcan`

Let me know if you have used a particular CAN interface successfully and I can expand this list.

The many CANable clone devices on eBay or AliExpress can be swapped from `socketcan` to `slcan` firmware (or vice versa) using the [web firmware updater](https://canable.io/updater/canable1.html).

### Incompatible interfaces

These python-can drivers are known to have problems with openinverter_can_tool:

* [Geschwister Schneider and candleLight](https://python-can.readthedocs.io/en/stable/interfaces/gs_usb.html) using `gs_usb` on Windows or Linux. This prevents Innomaker USB2CAN from working with Windows.

## Command Line Usage

To get the usage information for the tool run the `oic` command with no parameters:

```text
    Usage: oic [OPTIONS] COMMAND [ARGS]...

    OpenInverter CAN Tool allows querying and setting configuration of inverter
    parameters over a CAN connection

    Options:
    -d, --database FILE       Override the OpenInverter JSON parameter database
                                to use
    -c, --context TEXT        Which python-can configuration context to use
    -n, --node INTEGER RANGE  The CAN SDO node ID to communicate with  [env var:
                                OIC_NODE; default: 1; 1<=x<=127]
    -t, --timeout FLOAT       Response timeout in seconds  [default: 1.0]
    --debug                   Enable detailed debugging messages
    --version                 Show the version and exit.
    --help                    Show this message and exit.

    Commands:
    cache       Parameter database cache management commands
    can         Manage parameter to CAN message mappings on a device
    cmd         Execute a command on a device
    dumpall     Dump the values of all available parameters and values
    errors      List all of the errors on a device
    listparam   List the definition of PARAM
    listparams  List all available parameters and values
    load        Load all parameters from json IN_FILE
    log         Log the value of PARAMS from the device periodically in CSV...
    read        Read the value of PARAM from the device
    save        Save all parameters in json to OUT_FILE
    scan        Scan the CAN bus for available nodes
    serialno    Read the device serial number.
    upgrade     Upgrade the device firmware.
    write       Write the value to the parameter PARAM on the device
```

To scan for OpenInverter devices on a CAN network:

```text
    $ oic scan
    Scanning for devices. Please wait...

    Found possible OpenInverter node: 1
    Found possible OpenInverter node: 3
```

To read the current value of a parameter:

```text
    $ oic read brakeregen
    brakeregen          : -50
```

Values may be changed using symbolic names:

```text
    oic write potmode DualChannel
    oic write pinswap PWMOutput13,PWMOutput23
```

Firmware on devices may be easily upgraded:

```text
    $ oic upgrade stm32_sine.bin
    Device upgrade started for 87193029
    Upgrading: 15.3% complete
```

## Experimental GUI

An experimental GUI version of the tool exists which can be started by running the `oic-gui` command:

![Screenshot of the OpenInverter CAN Tool showing the Parameters tab on a Linux GNOME desktop](https://github.com/davefiddes/openinverter-can-tool/blob/main/docs/openinverter_can_tool_tkinter_gui_parameters.png)

Further details can be found in the [user documentation](https://github.com/davefiddes/openinverter-can-tool/blob/main/docs/gui-readme.md).

## Development and Contributing

If you are interested in contributing to the tool please check the [contributing guidelines](https://github.com/davefiddes/openinverter-can-tool/blob/main/docs/CONTRIBUTING.md).
