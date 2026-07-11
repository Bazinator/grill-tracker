#ifndef STEAK_STATE_H
#define STEAK_STATE_H

#include <cstddef>
#include <cstdint>
#include <unordered_map>
#include <vector>

#include "SteakPacket.h"

namespace steak {

// One logical steak on the grill. Stable id, last position, confidence, last-seen frame, miss count.
struct TrackedSteak {
  int stable_id;
  float centroid_x;
  float centroid_y;
  float confidence;
  uint32_t last_seen_frame;
  int miss_count;
};

// Stores all steaks by stable_id. Add/update/prune by id; O(1) lookup.
// Tuning: max_age (frames without match before removal), e.g. 20--30.
class Grill {
 public:
  explicit Grill(int max_age = 25);

  int add_steak(float cx, float cy, float conf, uint32_t frame);
  void update_steak(int id, float cx, float cy, float conf, uint32_t frame);
  void mark_missed(int id);
  void prune();

  std::vector<TrackedSteak> get_steaks() const;
  size_t size() const { return steaks_.size(); }
  int cumulative_steaks() const { return next_id_ - 1; }

 private:
  std::unordered_map<int, TrackedSteak> steaks_;
  int next_id_;
  int max_age_;
};

// Deduplicates same-frame detections, associates packets to steaks by position, updates Grill.
// Tuning: match_distance (px, e.g. 80--100), dedupe_distance (px, e.g. 30--50), max_age (frames).
class SteakTracker {
 public:
  SteakTracker(Grill& grill,
              float match_distance = 90.f,
              float dedupe_distance = 40.f,
              int max_age = 25);

  // Returns (deduped_count, new_steaks_created) for stats collection
  std::pair<size_t, size_t> ingest(const std::vector<SteakPacket>& packets);
  std::vector<TrackedSteak> get_steaks() const { return grill_.get_steaks(); }
  int cumulative_steaks() const { return grill_.cumulative_steaks(); }

 private:
  Grill& grill_;
  float match_distance_;
  float dedupe_distance_;
  int max_age_;
  uint32_t last_frame_;
};

}  // namespace steak

#endif /* STEAK_STATE_H */
