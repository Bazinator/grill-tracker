# Uses shared wire format: steak_packet matches core-engine SteakPacket.h
import os
import sys

_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)
from steak_packet import PACKET_FORMAT, pack_frame

import struct

# Single packet fixture: id, box, centroid, confidence, frame.
packed_data = struct.pack(
    PACKET_FORMAT, 7, 100.0, 250.2, 141.0, 350.2, 120.5, 300.2, 0.98, 1600
)
print(f"Packed data size: {len(packed_data)} bytes")
print(f"Hex Dump: {packed_data.hex(' ')}")
with open(os.path.join(_dir, "steak_pulse_test.bin"), "wb") as f:
    f.write(packed_data)

# Streaming format: count(4) + N x SteakPacket(36) for C++ stdin tests
# centroid (120.5, 300.2) from bbox (x1+x2)/2, (y1+y2)/2
state = [{"steak_id": 7, "bbox": [100.0, 250.2, 141.0, 350.2], "conf": 0.98, "last_seen_frame": 1600}]
stream_bytes = pack_frame(state)
stream_path = os.path.join(_dir, "steak_pulse_stream.bin")
with open(stream_path, "wb") as f:
    f.write(stream_bytes)
print(f"Stream file: {stream_path} ({len(stream_bytes)} bytes, count=1 + 1 packet)")

# Multi-frame stream for E2E: frame0 empty, frame1 one packet, frame2 empty
multi = struct.pack("<I", 0) + stream_bytes + struct.pack("<I", 0)
multi_path = os.path.join(_dir, "steak_pulse_stream_multi.bin")
with open(multi_path, "wb") as f:
    f.write(multi)
print(f"Multi-frame stream: {multi_path} (3 frames: 0, 1, 0 packets)")

  
