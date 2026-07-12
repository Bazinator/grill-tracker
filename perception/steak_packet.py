"""
Wire format for SteakPacket: matches core-engine/include/SteakPacket.h.
Per-frame wire format: count(4 bytes LE) + N x SteakPacket(36 bytes).
"""
from __future__ import annotations

import struct
from typing import Any, List

# int32 id, bbox (4 floats), centroid (2 floats), confidence, uint32 frame.
PACKET_FORMAT = "<ifffffffI"
STEAK_PACKET_SIZE = 36


def pack_frame(state: List[dict]) -> bytes:
    """
    Pack a list of export_state-style dicts into one frame's wire bytes.
    Each dict must have: steak_id, bbox, conf, last_seen_frame.
    Centroid is computed from bbox as ((x1+x2)/2, (y1+y2)/2).
    """
    count = len(state)
    buf = struct.pack("<I", count)
    for s in state:
        bbox = s["bbox"]
        centroid_x = (bbox[0] + bbox[2]) / 2.0
        centroid_y = (bbox[1] + bbox[3]) / 2.0
        buf += struct.pack(
            PACKET_FORMAT,
            int(s["steak_id"]),
            *map(float, bbox),
            float(centroid_x),
            float(centroid_y),
            float(s["conf"]),
            int(s["last_seen_frame"]),
        )
    return buf
