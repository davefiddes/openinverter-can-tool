#!/usr/bin/env python3
"""
OpenInverter CAN Tool GUI
A graphical interface for the oic tool functionality
"""

import json
import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Optional

import appdirs
import canopen
from can.exceptions import CanOperationError
from canopen import SdoAbortedError, SdoCommunicationError

from . import constants as oi
from .can_upgrade import CanUpgrader, State
from .fpfloat import fixed_to_float
from .map_persistence import export_json_map, import_json_map
from .oi_node import Direction, OpenInverterNode
from .param_utils import ParamWriter
from .paramdb import import_cached_database, import_database, value_to_str
from .scanner import scan_network

# Define a constant for connection exceptions which we want to handle
# in lots of places
CONNECTION_EXCEPTIONS = (
    SdoAbortedError,
    SdoCommunicationError,
    CanOperationError,
    OSError)

# Disable docstring warnings as it would make the OICGui too verbose
# for little gain.
# pylint: disable=missing-function-docstring


def require_connection(func):
    """
    Decorator to ensure the node is connected before executing a function.
    """

    def wrapper(self, *args, **kwargs):
        if self.node is None:
            messagebox.showerror("Error", "Not connected")
            return
        return func(self, *args, **kwargs)
    return wrapper


class OICGui:
    """Main GUI class for the OpenInverter CAN Tool"""

    def __init__(self, root):
        self.root = root
        self.root.title("OpenInverter CAN Tool GUI")
        self.root.geometry("800x600")

        # Settings
        self.network = canopen.Network()
        self.node: Optional[OpenInverterNode] = None
        self.device_db: Optional[canopen.ObjectDictionary] = None

        # Create notebook for tabs
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Create frames for each tab
        self.connection_frame = ttk.Frame(self.notebook)
        self.parameters_frame = ttk.Frame(self.notebook)
        self.control_frame = ttk.Frame(self.notebook)
        self.can_mapping_frame = ttk.Frame(self.notebook)
        self.upgrade_frame = ttk.Frame(self.notebook)

        # Add tabs to notebook
        self.notebook.add(self.connection_frame, text="Connection")
        self.notebook.add(self.parameters_frame, text="Parameters")
        self.notebook.add(self.control_frame, text="Device Control")
        self.notebook.add(self.can_mapping_frame, text="CAN Mapping")
        self.notebook.add(self.upgrade_frame, text="Firmware Upgrade")

        # Initialize each tab
        self.init_connection_tab()
        self.init_parameters_tab()
        self.init_control_tab()
        self.init_can_mapping_tab()
        self.init_upgrade_tab()

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Not connected")
        self.status_bar = ttk.Label(
            root, textvariable=self.status_var, relief=tk.SUNKEN)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def init_connection_tab(self):
        # Connection settings
        connection_group = ttk.LabelFrame(
            self.connection_frame, text="Connection Settings", padding=10)
        connection_group.pack(fill='x', padx=10, pady=5)

        # CAN Context
        ttk.Label(connection_group, text="CAN Context:").grid(
            row=0, column=0, sticky='w', padx=5, pady=2)
        self.context_var = tk.StringVar()
        self.context_entry = ttk.Entry(
            connection_group, textvariable=self.context_var, width=30)
        self.context_entry.grid(row=0, column=1, padx=5, pady=2)

        # Node ID
        ttk.Label(connection_group, text="Node ID:").grid(
            row=1, column=0, sticky='w', padx=5, pady=2)
        self.node_id_var = tk.StringVar(value="1")
        self.node_id_entry = ttk.Entry(
            connection_group, textvariable=self.node_id_var, width=10)
        self.node_id_entry.grid(row=1, column=1, sticky='w', padx=5, pady=2)

        # Timeout
        ttk.Label(connection_group, text="Timeout (s):").grid(
            row=2, column=0, sticky='w', padx=5, pady=2)
        self.timeout_var = tk.StringVar(value="1.0")
        self.timeout_entry = ttk.Entry(
            connection_group, textvariable=self.timeout_var, width=10)
        self.timeout_entry.grid(row=2, column=1, sticky='w', padx=5, pady=2)

        # Database path
        ttk.Label(connection_group, text="Database:").grid(
            row=3, column=0, sticky='w', padx=5, pady=2)
        self.database_var = tk.StringVar()
        self.database_entry = ttk.Entry(
            connection_group, textvariable=self.database_var, width=40)
        self.database_entry.grid(row=3, column=1, padx=5, pady=2)
        ttk.Button(connection_group,
                   text="Browse",
                   command=self.browse_database).grid(
            row=3, column=2, padx=5, pady=2)

        # Connect/Disconnect buttons
        button_frame = ttk.Frame(connection_group)
        button_frame.grid(row=4, column=0, columnspan=3, pady=10)

        self.connect_btn = ttk.Button(
            button_frame, text="Connect", command=self.connect)
        self.connect_btn.pack(side='left', padx=5)

        self.disconnect_btn = ttk.Button(
            button_frame,
            text="Disconnect",
            command=self.disconnect,
            state='disabled')
        self.disconnect_btn.pack(side='left', padx=5)

        self.scan_btn = ttk.Button(
            button_frame, text="Scan for Nodes", command=self.scan_nodes)
        self.scan_btn.pack(side='left', padx=5)

        # Output area
        output_group = ttk.LabelFrame(
            self.connection_frame, text="Output", padding=10)
        output_group.pack(fill='both', expand=True, padx=10, pady=5)

        self.output_text = scrolledtext.ScrolledText(output_group, height=10)
        self.output_text.pack(fill='both', expand=True)

    def init_parameters_tab(self):
        # Parameter list
        list_frame = ttk.LabelFrame(
            self.parameters_frame, text="Parameters", padding=10)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # Treeview for parameters
        self.param_tree = ttk.Treeview(list_frame, columns=(
            'value', 'unit', 'range'), show='tree headings')
        self.param_tree.heading('#0', text='Parameter')
        self.param_tree.heading('value', text='Value')
        self.param_tree.heading('unit', text='Unit')
        self.param_tree.heading('range', text='Range')

        scrollbar = ttk.Scrollbar(
            list_frame, orient='vertical', command=self.param_tree.yview)
        self.param_tree.configure(yscrollcommand=scrollbar.set)

        self.param_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Parameter control frame
        control_frame = ttk.LabelFrame(
            self.parameters_frame, text="Parameter Control", padding=10)
        control_frame.pack(fill='x', padx=10, pady=5)

        # Read parameter
        ttk.Label(control_frame, text="Parameter:").grid(
            row=0, column=0, sticky='w', padx=5, pady=2)
        self.param_name_var = tk.StringVar()
        self.param_name_entry = ttk.Entry(
            control_frame, textvariable=self.param_name_var, width=20)
        self.param_name_entry.grid(row=0, column=1, padx=5, pady=2)

        ttk.Button(control_frame,
                   text="Read",
                   command=self.read_parameter).grid(
            row=0, column=2, padx=5, pady=2)

        # Write parameter
        ttk.Label(control_frame, text="Value:").grid(
            row=1, column=0, sticky='w', padx=5, pady=2)
        self.param_value_var = tk.StringVar()
        self.param_value_entry = ttk.Entry(
            control_frame, textvariable=self.param_value_var, width=20)
        self.param_value_entry.grid(row=1, column=1, padx=5, pady=2)

        ttk.Button(control_frame,
                   text="Write",
                   command=self.write_parameter).grid(
            row=1, column=2, padx=5, pady=2)

        # Refresh and dump buttons
        button_frame2 = ttk.Frame(control_frame)
        button_frame2.grid(row=2, column=0, columnspan=3, pady=10)

        ttk.Button(button_frame2, text="Refresh All",
                   command=self.refresh_parameters).pack(side='left', padx=5)
        ttk.Button(button_frame2, text="Load from File",
                   command=self.load_parameters).pack(side='left', padx=5)
        ttk.Button(button_frame2, text="Save to File",
                   command=self.save_parameters).pack(side='left', padx=5)

    def init_control_tab(self):
        # Device commands
        cmd_frame = ttk.LabelFrame(
            self.control_frame, text="Device Commands", padding=10)
        cmd_frame.pack(fill='x', padx=10, pady=5)

        # Start/Stop
        start_frame = ttk.Frame(cmd_frame)
        start_frame.pack(fill='x', pady=5)

        ttk.Label(start_frame, text="Start Mode:").pack(side='left', padx=5)
        self.start_mode_var = tk.StringVar(value="Normal")
        mode_combo = ttk.Combobox(
            start_frame,
            textvariable=self.start_mode_var,
            values=["Normal", "Manual", "Boost",
                    "Buck", "ACHeat", "Sine"],
            state="readonly", width=15)
        mode_combo.pack(side='left', padx=5)

        ttk.Button(start_frame, text="Start",
                   command=self.start_device).pack(side='left', padx=5)
        ttk.Button(start_frame, text="Stop", command=self.stop_device).pack(
            side='left', padx=5)

        # Save/Load/Reset
        ctrl_frame = ttk.Frame(cmd_frame)
        ctrl_frame.pack(fill='x', pady=5)

        ttk.Button(ctrl_frame, text="Save to Flash",
                   command=self.save_device).pack(side='left', padx=5)
        ttk.Button(ctrl_frame, text="Load from Flash",
                   command=self.load_device).pack(side='left', padx=5)
        ttk.Button(ctrl_frame, text="Load Defaults",
                   command=self.load_defaults).pack(side='left', padx=5)
        ttk.Button(ctrl_frame, text="Reset Device",
                   command=self.reset_device).pack(side='left', padx=5)

        # Serial number
        serial_frame = ttk.Frame(cmd_frame)
        serial_frame.pack(fill='x', pady=5)

        ttk.Button(serial_frame, text="Get Serial Number",
                   command=self.get_serial).pack(side='left', padx=5)
        self.serial_var = tk.StringVar()
        ttk.Label(serial_frame, textvariable=self.serial_var).pack(
            side='left', padx=10)

    def init_can_mapping_tab(self):
        # CAN mapping controls
        mapping_frame = ttk.LabelFrame(
            self.can_mapping_frame, text="CAN Mappings", padding=10)
        mapping_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # Current mappings display
        self.mapping_text = scrolledtext.ScrolledText(mapping_frame, height=15)
        self.mapping_text.pack(fill='both', expand=True, pady=5)

        # Control buttons
        button_frame = ttk.Frame(mapping_frame)
        button_frame.pack(fill='x', pady=5)

        ttk.Button(button_frame, text="List Mappings",
                   command=self.list_mappings).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Clear All",
                   command=self.clear_mappings).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Import",
                   command=self.import_mappings).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Export",
                   command=self.export_mappings).pack(side='left', padx=5)

    def init_upgrade_tab(self):
        # Firmware upgrade
        upgrade_frame = ttk.LabelFrame(
            self.upgrade_frame, text="Firmware Upgrade", padding=10)
        upgrade_frame.pack(fill='x', padx=10, pady=5)

        # Firmware file selection
        file_frame = ttk.Frame(upgrade_frame)
        file_frame.pack(fill='x', pady=5)

        ttk.Label(file_frame, text="Firmware File:").pack(side='left', padx=5)
        self.firmware_var = tk.StringVar()
        self.firmware_entry = ttk.Entry(
            file_frame, textvariable=self.firmware_var, width=40)
        self.firmware_entry.pack(side='left', padx=5, fill='x', expand=True)
        ttk.Button(file_frame, text="Browse",
                   command=self.browse_firmware).pack(side='left', padx=5)

        # Upgrade options
        options_frame = ttk.Frame(upgrade_frame)
        options_frame.pack(fill='x', pady=5)

        self.recover_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Recovery Mode",
                        variable=self.recover_var).pack(side='left', padx=5)

        ttk.Label(options_frame, text="Serial (for recovery):").pack(
            side='left', padx=5)
        self.upgrade_serial_var = tk.StringVar()
        ttk.Entry(options_frame, textvariable=self.upgrade_serial_var,
                  width=15).pack(side='left', padx=5)

        # Upgrade button
        ttk.Button(upgrade_frame, text="Start Upgrade",
                   command=self.start_upgrade).pack(pady=10)

        # Progress
        self.progress_var = tk.StringVar(value="Ready")
        ttk.Label(upgrade_frame, textvariable=self.progress_var).pack(pady=5)

        self.progress_bar = ttk.Progressbar(upgrade_frame, mode='determinate')
        self.progress_bar.pack(fill='x', pady=5)

    def log_output(self, message: str):
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)
        self.root.update_idletasks()

    def browse_database(self):
        filename = filedialog.askopenfilename(
            title="Select Parameter Database",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            self.database_var.set(filename)

    def browse_firmware(self):
        filename = filedialog.askopenfilename(
            title="Select Firmware File",
            filetypes=[("Binary files", "*.bin"), ("All files", "*.*")]
        )
        if filename:
            self.firmware_var.set(filename)

    def connect(self):
        assert self.network is not None
        assert self.node is None
        assert self.device_db is None

        try:
            context = self.context_var.get() or None
            node_id = int(self.node_id_var.get())
            timeout = float(self.timeout_var.get())
            database_path = self.database_var.get() or None

            # Connect to CAN
            self.network.connect(context=context)
            self.network.check()

            # Load database
            if database_path:
                self.device_db = import_database(Path(database_path))
            else:
                self.device_db = import_cached_database(
                    self.network,
                    node_id,
                    Path(appdirs.user_cache_dir(oi.APPNAME, oi.APPAUTHOR))
                )

            self.node = OpenInverterNode(self.network, node_id, self.device_db)
            self.node.sdo.RESPONSE_TIMEOUT = timeout

            self.status_var.set(f"Connected to node {node_id}")
            self.connect_btn.config(state='disabled')
            self.disconnect_btn.config(state='normal')

            self.log_output(f"Connected to node {node_id}")
            self.refresh_parameters()

        except CONNECTION_EXCEPTIONS as e:
            messagebox.showerror("Connection Error", str(e))
            self.log_output(f"Connection failed: {e}")

    def disconnect(self):
        assert self.network is not None
        assert self.node is not None
        assert self.device_db is not None

        try:
            self.node = None
            self.device_db = None
            self.network.disconnect()

            self.status_var.set("Not connected")
            self.connect_btn.config(state='normal')
            self.disconnect_btn.config(state='disabled')

            self.param_tree.delete(*self.param_tree.get_children())
            self.log_output("Disconnected")

        except CONNECTION_EXCEPTIONS as e:
            messagebox.showerror("Disconnect Error", str(e))

    def on_closing(self):
        """Disconnect cleanly when the window closes."""
        try:
            self.node = None
            self.device_db = None
            self.network.disconnect()
        except CanOperationError:
            pass

        self.root.destroy()

    def scan_nodes(self):
        def scan_thread():
            try:
                # If we are not connected the temporarily connect
                if self.node is None:
                    self.network.connect(
                        context=self.context_var.get() or None
                    )

                self.log_output("Scanning for nodes...")

                node_list = scan_network(self.network)

                if node_list:
                    for node_id in node_list:
                        self.log_output(
                            f"Found possible openinverter node: {node_id}")
                else:
                    self.log_output("No nodes found")

                # If we are not connected, disconnect now
                # to avoid leaving the network in an inconsistent state
                if self.node is None:
                    self.network.disconnect()

            except CONNECTION_EXCEPTIONS as e:
                self.log_output(f"Scan failed: {e}")
                if self.node is None:
                    self.network.disconnect()

        threading.Thread(target=scan_thread, daemon=True).start()

    @require_connection
    def refresh_parameters(self):

        def refresh_thread():
            try:
                self.param_tree.delete(*self.param_tree.get_children())

                for item in self.device_db.names.values():
                    try:
                        value_str = value_to_str(
                            item, fixed_to_float(self.node.sdo[item.name].raw))

                        range_str = ""
                        if (item.isparam and item.min is not None and
                                item.max is not None):
                            range_str = f"{fixed_to_float(item.min):g} - " + \
                                f"{fixed_to_float(item.max):g}"

                        self.param_tree.insert(
                            '', 'end', text=item.name,
                            values=(value_str, item.unit, range_str))

                    except CONNECTION_EXCEPTIONS as e:
                        self.param_tree.insert(
                            '', 'end', text=item.name,
                            values=(f"Error: {e}", item.unit, ""))

                self.log_output("Parameters refreshed")

            except CONNECTION_EXCEPTIONS as e:
                self.log_output(f"Failed to refresh parameters: {e}")

        threading.Thread(target=refresh_thread, daemon=True).start()

    @require_connection
    def read_parameter(self):

        param_name = self.param_name_var.get()
        if not param_name:
            messagebox.showerror("Error", "Please enter parameter name")
            return

        try:
            if param_name in self.device_db.names:
                param = self.device_db.names[param_name]
                value = fixed_to_float(self.node.sdo[param_name].raw)

                value_str = value_to_str(param, value)

                self.log_output(f"{param_name}: {value_str} [{param.unit}]")
                self.param_value_var.set(str(value))
            else:
                messagebox.showerror(
                    "Error", f"Unknown parameter: {param_name}")

        except CONNECTION_EXCEPTIONS as e:
            messagebox.showerror("Error", f"Failed to read parameter: {e}")

    @require_connection
    def write_parameter(self):
        param_name = self.param_name_var.get()
        param_value = self.param_value_var.get()

        if not param_name or not param_value:
            messagebox.showerror(
                "Error", "Please enter parameter name and value")
            return

        try:
            assert self.node
            writer = ParamWriter(self.node, self.device_db, self.log_output)
            writer.write(param_name, param_value)
            self.log_output(f"Written {param_name} = {param_value}")

        except CONNECTION_EXCEPTIONS as e:
            messagebox.showerror("Error", f"Failed to write parameter: {e}")

    @require_connection
    def load_parameters(self):
        filename = filedialog.askopenfilename(
            title="Load Parameters",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    doc = json.load(f)

                assert self.node
                writer = ParamWriter(
                    self.node, self.device_db, self.log_output)

                count = 0
                for param_name, value in doc.items():
                    if isinstance(value, str):
                        value = float(value)
                    writer.write(param_name, value)
                    count += 1

                self.log_output(f"Loaded {count} parameters from {filename}")

            except CONNECTION_EXCEPTIONS as e:
                messagebox.showerror(
                    "Error", f"Failed to load parameters: {e}")

    @require_connection
    def save_parameters(self):
        filename = filedialog.asksaveasfilename(
            title="Save Parameters",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            defaultextension=".json"
        )
        if filename:
            try:
                doc = {}
                count = 0
                for item in self.device_db.names.values():
                    if item.isparam:
                        doc[item.name] = fixed_to_float(
                            self.node.sdo[item.name].raw)
                        count += 1

                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(doc, f, indent=4)

                self.log_output(f"Saved {count} parameters to {filename}")

            except CONNECTION_EXCEPTIONS as e:
                messagebox.showerror(
                    "Error", f"Failed to save parameters: {e}")

    @require_connection
    def start_device(self):
        try:
            mode_map = {
                "Normal": oi.START_MODE_NORMAL,
                "Manual": oi.START_MODE_MANUAL,
                "Boost": oi.START_MODE_BOOST,
                "Buck": oi.START_MODE_BUCK,
                "Sine": oi.START_MODE_SINE,
                "ACHeat": oi.START_MODE_ACHEAT
            }

            mode = self.start_mode_var.get()
            self.node.start(mode_map[mode])
            self.log_output(f"Device started in {mode} mode")

        except CONNECTION_EXCEPTIONS as e:
            messagebox.showerror("Error", f"Failed to start device: {e}")

    @require_connection
    def stop_device(self):
        try:
            self.node.stop()
            self.log_output("Device stopped")

        except CONNECTION_EXCEPTIONS as e:
            messagebox.showerror("Error", f"Failed to stop device: {e}")

    @require_connection
    def save_device(self):
        try:
            self.node.save()
            self.log_output("Device parameters saved to flash")

        except CONNECTION_EXCEPTIONS as e:
            messagebox.showerror("Error", f"Failed to save to flash: {e}")

    @require_connection
    def load_device(self):
        try:
            self.node.load()
            self.log_output("Device parameters loaded from flash")

        except CONNECTION_EXCEPTIONS as e:
            messagebox.showerror("Error", f"Failed to load from flash: {e}")

    @require_connection
    def load_defaults(self):
        try:
            self.node.load_defaults()
            self.log_output("Device parameters reset to defaults")

        except CONNECTION_EXCEPTIONS as e:
            messagebox.showerror("Error", f"Failed to load defaults: {e}")

    @require_connection
    def reset_device(self):
        if messagebox.askyesno(
            "Confirm",
                "Are you sure you want to reset the device?"):
            try:
                self.node.reset()
                self.log_output("Device reset command sent")

            except CONNECTION_EXCEPTIONS as e:
                messagebox.showerror("Error", f"Failed to reset device: {e}")

    @require_connection
    def get_serial(self):
        try:
            serialno_data = self.node.serial_no()
            part_str = []
            for part in range(0, 12, 4):
                part_data = serialno_data[part:part+4]
                part_str.append("".join(format(x, "02X") for x in part_data))

            serial = f"{part_str[0]}:{part_str[1]}:{part_str[2]}"
            self.serial_var.set(serial)
            self.log_output(f"Serial Number: {serial}")

        except CONNECTION_EXCEPTIONS as e:
            messagebox.showerror("Error", f"Failed to get serial number: {e}")

    @require_connection
    def list_mappings(self):
        try:
            tx_map = self.node.list_can_map(Direction.TX)
            rx_map = self.node.list_can_map(Direction.RX)

            self.mapping_text.delete(1.0, tk.END)

            if not tx_map and not rx_map:
                self.mapping_text.insert(tk.END, "(no mappings)\n")
            else:
                self._print_can_map("tx", tx_map)
                self._print_can_map("rx", rx_map)

        except CONNECTION_EXCEPTIONS as e:
            messagebox.showerror("Error", f"Failed to list mappings: {e}")

    def _print_can_map(self, direction_str, can_map):
        msg_index = 0
        param_index = 0

        for msg in can_map:
            if msg.is_extended_frame:
                self.mapping_text.insert(tk.END, f"{msg.can_id:#010x}:\n")
            else:
                self.mapping_text.insert(tk.END, f"{msg.can_id:#x}:\n")

            for entry in msg.params:
                param_name = self._param_name_from_id(entry.param_id)
                self.mapping_text.insert(
                    tk.END,
                    f" {direction_str}.{msg_index}.{param_index} "
                    f"param='{param_name}' pos={entry.position} "
                    f"length={entry.length} gain={entry.gain} "
                    f"offset={entry.offset}\n")
                param_index += 1
            param_index = 0
            msg_index += 1

    def _param_name_from_id(self, param_id):
        for item in self.device_db.names.values():
            if hasattr(item, 'id') and item.id == param_id:
                return item.name
        return str(param_id)

    @require_connection
    def clear_mappings(self):
        if messagebox.askyesno("Confirm", "Clear all CAN mappings?"):
            try:
                self.node.clear_map(Direction.TX)
                self.node.clear_map(Direction.RX)
                self.log_output("All CAN mappings cleared")
                self.list_mappings()

            except CONNECTION_EXCEPTIONS as e:
                messagebox.showerror("Error", f"Failed to clear mappings: {e}")

    @require_connection
    def import_mappings(self):
        filename = filedialog.askopenfilename(
            title="Import CAN Mappings",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    tx_map, rx_map = import_json_map(f, self.device_db)

                self.node.add_can_map(Direction.TX, tx_map)
                self.node.add_can_map(Direction.RX, rx_map)

                self.log_output(f"CAN mappings imported from {filename}")
                self.list_mappings()

            except CONNECTION_EXCEPTIONS as e:
                messagebox.showerror(
                    "Error", f"Failed to import mappings: {e}")

    @require_connection
    def export_mappings(self):
        filename = filedialog.asksaveasfilename(
            title="Export CAN Mappings",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            defaultextension=".json"
        )
        if filename:
            try:
                tx_map = self.node.list_can_map(Direction.TX)
                rx_map = self.node.list_can_map(Direction.RX)

                with open(filename, 'w', encoding='utf-8') as f:
                    export_json_map(
                        tx_map, rx_map, self.device_db, f)

                self.log_output(f"CAN mappings exported to {filename}")

            except CONNECTION_EXCEPTIONS as e:
                messagebox.showerror(
                    "Error", f"Failed to export mappings: {e}")

    @require_connection
    def start_upgrade(self):
        firmware_file = self.firmware_var.get()
        if not firmware_file:
            messagebox.showerror("Error", "Please select firmware file")
            return

        if not os.path.exists(firmware_file):
            messagebox.showerror("Error", "Firmware file does not exist")
            return

        def upgrade_thread():
            try:
                def progress_callback(update):
                    if update.state == State.START:
                        self.progress_var.set("Waiting for device...")
                        self.progress_bar['value'] = 0

                    elif update.state == State.HEADER:
                        serialno_str = "".join(format(x, "02x")
                                               for x in update.serialno)
                        self.progress_var.set(
                            f"Upgrading device {serialno_str}")

                    elif update.state in (State.UPLOAD, State.CHECK_CRC):
                        progress = update.progress
                        self.progress_var.set(
                            f"Upgrading: {progress:.1f}% complete")
                        self.progress_bar['value'] = progress

                    elif update.state == State.WAIT_FOR_DONE:
                        self.progress_var.set("Waiting for completion...")

                    elif update.state == State.FAILURE:
                        self.progress_var.set(
                            f"Upgrade failed: {update.failure}")

                    elif update.state == State.COMPLETE:
                        self.progress_var.set(
                            "Upgrade completed successfully!")
                        self.progress_bar['value'] = 100

                recover = self.recover_var.get()
                serial = self.upgrade_serial_var.get() or None

                if recover and serial and len(serial) != 8:
                    messagebox.showerror(
                        "Error", "Serial number must be 8 hex digits")
                    return

                recovery_serialno = None
                if recover and serial:
                    recovery_serialno = bytes.fromhex(serial)
                elif not recover and self.node:
                    recovery_serialno = self.node.serial_no()[:4]

                upgrader = CanUpgrader(self.network, recovery_serialno,
                                       Path(firmware_file), progress_callback)

                if not recover and self.node:
                    try:
                        self.node.reset()
                    except canopen.SdoCommunicationError:
                        pass

                success = upgrader.run(5.0)
                if not success:
                    self.progress_var.set("Upgrade timed out")

            except CONNECTION_EXCEPTIONS as e:
                self.progress_var.set(f"Upgrade error: {e}")
                messagebox.showerror("Error", f"Upgrade failed: {e}")

        threading.Thread(target=upgrade_thread, daemon=True).start()


def main():
    root = tk.Tk()
    app = OICGui(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
