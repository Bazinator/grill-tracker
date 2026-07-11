"""
Wire format for SteakPacket: matches core-engine/include/SteakPacket.h.
Per-frame wire format: count(4 bytes LE) + N × SteakPacket(20 bytes).
"""
from __future__ import annotations

import struct
from typing import Any, List

# Layout for one packet: int32_t, float, float, float, uint32_t (20 bytes)
PACKET_FORMAT = "<ifffI"
STEAK_PACKET_SIZE = 20


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
            float(centroid_x),
            float(centroid_y),
            float(s["conf"]),
            int(s["last_seen_frame"]),
        )
    return buf
