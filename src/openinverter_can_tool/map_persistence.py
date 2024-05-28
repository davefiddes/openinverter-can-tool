"""
Routines to allow CAN message maps to be persisted
"""

import json
from typing import IO, Dict, List

import canopen.objectdictionary

from .oi_node import CanMessage
from .paramdb import OIVariable


def convert_map_to_dict(msg_map: List[CanMessage],
                        db: canopen.ObjectDictionary) -> List[Dict]:
    """Convert the structured list of CanMessages into a raw list/dict and
    resolve the parameter IDs into names"""

    out_list = []
    for msg in msg_map:
        out_msg = {
            "can_id": msg.can_id
        }
        params = []
        for entry in msg.params:
            # Search inefficiently for the parameter name
            param_name = None
            for item in db.names.values():
                if isinstance(item, OIVariable) and item.id == entry.param_id:
                    param_name = item.name
                    break

            if param_name is None:
                raise KeyError(entry.param_id)

            param = {
                "param": param_name,
                "position": entry.position,
                "length": entry.length,
                "endian": entry.endian.name.lower(),
                "gain": entry.gain,
                "offset": entry.offset
            }
            params.append(param)
        out_msg["params"] = params
        out_list.append(out_msg)

    return out_list


def export_json_map(tx_map: List[CanMessage],
                    rx_map: List[CanMessage],
                    db: canopen.ObjectDictionary,
                    out_file: IO) -> None:
    """
    Export the provided CAN message maps encoded as JSON into the specified
    file

    :param tx_map:  The transmit CAN message map
    :param rx_map:  The receive CAN message map
    :param out_file: The writeable file object to output the encoded JSON to
    """

    doc = {
        "version": 1,
        "tx": convert_map_to_dict(tx_map, db),
        "rx": convert_map_to_dict(rx_map, db)
    }
    json.dump(doc, out_file, indent=4)
