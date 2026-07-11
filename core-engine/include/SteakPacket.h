#ifndef STEAK_PACKET_H
#define STEAK_PACKET_H
#include <cstdint>

// Wire format: count(4 bytes LE) + N × SteakPacket(20 bytes). See perception/pulse_test.py and packing helpers.
struct SteakPacket {
  // All 4 bytes each; layout matches Python "<ifffI"
  int32_t steak_id;
  float centroid_x;
  float centroid_y;
  float confidence;
  uint32_t timestamp;
};  // Total 20 bytes
static_assert(sizeof(SteakPacket) == 20, "SteakPacket must match wire format (20 bytes)");
#endif /* STEAK_PACKET_H */