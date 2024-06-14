"""
Routines to allow CAN message maps to be persisted
"""

import json
from typing import IO, Dict, List, Tuple

import canopen.objectdictionary

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
                "params": out_params
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
            msg_list.append(
                CanMessage(msg["can_id"],
                           _parse_map_entries(msg["params"])))
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
