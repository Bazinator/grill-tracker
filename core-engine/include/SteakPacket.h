#ifndef STEAK_PACKET_H
#define STEAK_PACKET_H
#include <cstdint>

// Wire format: count(4 bytes LE) + N x SteakPacket(36 bytes).
struct SteakPacket {
  // All fields are 4 bytes; layout matches Python "<ifffffffI".
  int32_t steak_id;
  float bbox_x1;
  float bbox_y1;
  float bbox_x2;
  float bbox_y2;
  float centroid_x;
  float centroid_y;
  float confidence;
  uint32_t timestamp;
};
static_assert(sizeof(SteakPacket) == 36, "SteakPacket must match wire format (36 bytes)");
#endif /* STEAK_PACKET_H */
