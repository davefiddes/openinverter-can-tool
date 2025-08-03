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
