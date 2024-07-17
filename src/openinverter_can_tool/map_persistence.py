"""
Routines to allow CAN message maps to be persisted
"""

import json
from collections import OrderedDict
from pathlib import Path
from typing import IO, Dict, List, Tuple, Optional

import canopen.objectdictionary
import cantools
import cantools.database

from .fpfloat import fixed_to_float
from .oi_node import CanMessage, MapEntry
from .paramdb import OIVariable


def export_json_map(tx_map: List[CanMessage],
                    rx_map: List[CanMessage],
                    db: canopen.ObjectDictionary,
                    out_file: IO) -> None:
    """
    Export the provided CAN message maps encoded as JSON into the specified
    file

    :param tx_map:  The transmit CAN message map
    :param rx_map:  The receive CAN message map
    :param db:      The object database to convert parameter IDs to names with
    :param out_file: The writeable file object to output the encoded JSON to
    """

    def _convert_map_to_dict(msg_map: List[CanMessage]) -> List[Dict]:
        out_list = []
        for msg in msg_map:
            out_params = []
            out_msg = {
                "can_id": msg.can_id,
                "params": out_params,
                "is_extended_frame": msg.is_extended_frame
            }
            for entry in msg.params:
                # Search inefficiently for the parameter name
                param_name = None
                for item in db.names.values():
                    if isinstance(item, OIVariable) and \
                            item.id == entry.param_id:
                        param_name = item.name
                        break

                if param_name is None:
                    raise KeyError(entry.param_id)

                out_params.append({
                    "param": param_name,
                    "position": entry.position,
                    "length": entry.length,
                    "gain": entry.gain,
                    "offset": entry.offset
                })
            out_list.append(out_msg)

        return out_list

    doc = {
        "version": 1,
        "tx": _convert_map_to_dict(tx_map),
        "rx": _convert_map_to_dict(rx_map)
    }
    json.dump(doc, out_file, indent=4)


def import_json_map(in_file: IO,
                    db: canopen.ObjectDictionary,
                    ) -> Tuple[List[CanMessage],
                               List[CanMessage]]:
    """
    Import a CAN message map from the supplied JSON file.

    :param in_file: The JSON file with the CAN message map to import
    :param db:      The object database to resolve parameter names with

    :returns: Tuple with the transmit and receive CAN message maps
    """

    def _parse_map_entries(params_doc) -> List[MapEntry]:
        params = []
        for param in params_doc:
            param_id = db.names[param["param"]].id
            params.append(
                MapEntry(
                    param_id,
                    param["position"],
                    param["length"],
                    param["gain"],
                    param["offset"],
                ))

        return params

    def _parse_can_messages(msg_doc) -> List[CanMessage]:
        msg_list = []
        for msg in msg_doc:
            if "is_extended_frame" in msg:
                is_extended_frame = msg["is_extended_frame"]
            else:
                is_extended_frame = False
            msg_list.append(
                CanMessage(msg["can_id"],
                           _parse_map_entries(msg["params"]),
                           is_extended_frame))
        return msg_list

    doc = json.load(in_file)

    if "version" not in doc or "tx" not in doc or "rx" not in doc:
        raise RuntimeError("Invalid file format")

    version = doc["version"]
    if version != 1:
        raise RuntimeError(f"Unsupported version: {version}")

    tx_map = _parse_can_messages(doc["tx"])
    rx_map = _parse_can_messages(doc["rx"])

    return (tx_map, rx_map)


# cantools don't export the Database properly but it is safe to use this type
# pyright: reportPrivateImportUsage=false

def transform_map_to_canopen_db(
        node_prefix: Optional[str],
        tx_map: List[CanMessage],
        rx_map: List[CanMessage],
        db: canopen.ObjectDictionary) -> cantools.database.can.Database:
    """
    Transform the provided CAN message maps to a canopen database

    :param node_prefix: An optional string prefix that is added to each db node
    :param tx_map:      The transmit CAN message map
    :param rx_map:      The receive CAN message map
    :param db:          The object database to convert parameter IDs to names
                        with

    :returns: The canopen database representing the two maps
    """

    def _find_param(param_id: int) -> OIVariable:
        """Search inefficiently for the parameter given the openinverter
        internal id"""

        for item in db.names.values():
            if isinstance(item, OIVariable) and item.id == param_id:
                return item

        # Didn't find the parameter
        raise KeyError(param_id)

    def _convert_param_to_signal(
        param_name: str,
        param: OIVariable,
        entry: MapEntry
    ) -> cantools.database.can.signal.Signal:
        if entry.length > 0:
            byte_order = "little_endian"
            start_bit = entry.position
            bit_length = entry.length
        else:
            byte_order = "big_endian"
            start_bit = entry.position + entry.length + 8
            bit_length = -entry.length

        signal = cantools.database.can.signal.Signal(
            name=param_name,
            start=start_bit,
            length=bit_length,
            byte_order=byte_order
        )

        if param.value_descriptions:
            values = OrderedDict()
            for value, description in param.value_descriptions.items():
                values[value] = description
            signal.choices = values
            signal.is_signed = False

        elif param.bit_definitions:
            bits = OrderedDict()
            for value, description in param.bit_definitions.items():
                bits[value] = description
            signal.choices = bits
            signal.is_signed = False

        else:
            # dbc files scale and offset are the inverse of openinverter
            # gain and offset
            signal.scale = 1.0 / entry.gain
            signal.offset = -entry.offset
            signal.is_signed = True

            if param.isparam:
                signal.unit = param.unit

        if param.isparam:
            if param.min:
                signal.minimum = fixed_to_float(param.min)
            if param.max:
                signal.maximum = fixed_to_float(param.max)

        return signal

    def _convert_map_to_messages(
            msg_map: List[CanMessage],
            node_name: str,
            msg_prefix: str
    ) -> List[cantools.database.can.message.Message]:
        out_list = []
        msg_no = 1
        for msg in msg_map:
            signals = []
            signal_names = {}
            for entry in msg.params:
                param = _find_param(entry.param_id)

                # Ensure we don't have duplicate signal names
                param_name = param.name
                if param_name in signal_names:
                    signal_names[param_name] += 1
                    param_name = f"{param_name}_{signal_names[param_name]}"
                else:
                    signal_names[param_name] = 0

                signals.append(
                    _convert_param_to_signal(param_name, param, entry)
                )

            out_msg = cantools.database.can.message.Message(
                name=f"{msg_prefix}_msg{msg_no}",
                frame_id=msg.can_id,
                is_extended_frame=msg.is_extended_frame,
                length=8,
                signals=signals,
                senders=[node_name]
            )
            out_list.append(out_msg)
            msg_no += 1

        return out_list

    tx_node = cantools.database.can.node.Node(
        f"{node_prefix}_tx" if node_prefix else "tx"
    )
    rx_node = cantools.database.can.node.Node(
        f"{node_prefix}_rx" if node_prefix else "rx"
    )

    nodes = []
    if tx_map:
        nodes.append(tx_node)
    if rx_map:
        nodes.append(rx_node)

    messages = _convert_map_to_messages(tx_map, tx_node.name, "tx")
    messages += _convert_map_to_messages(rx_map, rx_node.name, "rx")

    return cantools.database.can.Database(messages, nodes)


def export_dbc_map(
        node_prefix: Optional[str],
        tx_map: List[CanMessage],
        rx_map: List[CanMessage],
        db: canopen.ObjectDictionary,
        out_file: Path) -> None:
    """
    Export the provided CAN message maps to a DBC

    :param node_prefix: An optional string prefix that is added to each db node
    :param tx_map:      The transmit CAN message map
    :param rx_map:      The receive CAN message map
    :param db:          The object database to convert parameter IDs to names
                        with
    :param out_file:    The file path to output the DBC to
    """
    cantools_db = transform_map_to_canopen_db(node_prefix, tx_map, rx_map, db)

    cantools.database.dump_file(cantools_db, out_file)
