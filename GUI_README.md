# OpenInverter CAN Tool GUI

A graphical user interface for the OpenInverter CAN Tool, providing an easy-to-use interface for configuring and monitoring OpenInverter devices.

## Features

The GUI provides access to all major functionality of the CLI tool through a tabbed interface:

### Connection Tab
- Configure CAN connection settings (context, node ID, timeout)
- Load parameter database files
- Connect/disconnect from devices
- Scan for available nodes on the CAN bus

### Parameters Tab
- View all device parameters in a tree view with current values, units, and ranges
- Read individual parameter values
- Write parameter values with validation
- Load parameters from JSON files
- Save parameters to JSON files
- Refresh all parameter values

### Device Control Tab
- Start/stop the device with different operating modes (Normal, Manual, Boost, Buck, ACHeat, Sine)
- Save parameters to device flash memory
- Load parameters from device flash memory
- Reset parameters to factory defaults
- Reset the device
- Read device serial number

### CAN Mapping Tab
- List current CAN message mappings
- Clear all mappings
- Import/export mappings from/to JSON files
- View TX and RX mappings with parameter details

### Firmware Upgrade Tab
- Select firmware binary files
- Perform normal or recovery mode upgrades
- Monitor upgrade progress with progress bar
- Specify serial numbers for recovery mode

## Installation

The GUI is automatically installed when you install the openinverter-can-tool package:

```bash
pip install openinverter-can-tool
```

## Usage

### Command Line
After installation, you can launch the GUI with:

```bash
oic-gui
```

### Direct Execution
You can also run the GUI directly from the source directory:

```bash
./oic-gui
```

Or with Python:

```bash
python3 -m openinverter_can_tool.gui
```

## Requirements

The GUI requires the same dependencies as the CLI tool plus tkinter (which is included with most Python installations):

- Python 3.8+
- tkinter (usually included with Python)
- canopen
- python-can[serial]
- click
- appdirs
- cantools

## GUI Layout

The interface is organized into tabs for different functions:

1. **Connection**: Set up CAN connection and scan for devices
2. **Parameters**: View and modify device parameters
3. **Device Control**: Send commands to the device
4. **CAN Mapping**: Manage parameter-to-CAN message mappings
5. **Firmware Upgrade**: Update device firmware

## Usage Tips

1. **Connection**: Start by configuring your CAN interface in the Connection tab. If you don't specify a context, the tool will use the default python-can configuration.

2. **Parameter Database**: You can either load a specific parameter database file or let the tool automatically download it from the device.

3. **Threading**: Network operations run in background threads to prevent the GUI from freezing. Progress is shown in the output area.

4. **Error Handling**: Errors are displayed in message boxes and logged to the output area for debugging.

5. **File Operations**: Use the Browse buttons to select parameter files, firmware files, and CAN mapping files.

## Troubleshooting

- **Connection Issues**: Check your CAN interface configuration and ensure the device is powered and accessible
- **Parameter Errors**: Verify parameter names match those in the device database
- **GUI Freezing**: The GUI uses background threads, but very slow CAN operations might still cause temporary unresponsiveness
- **File Errors**: Ensure you have read/write permissions for the directories you're working with

## Development

The GUI is built using Python's tkinter library for maximum compatibility. Key files:

- `src/openinverter_can_tool/gui.py`: Main GUI implementation
- `oic-gui`: Launcher script

The GUI reuses much of the logic from the CLI implementation in `cli.py`, ensuring consistent behavior between the two interfaces.