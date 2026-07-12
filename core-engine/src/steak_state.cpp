#include "../include/steak_state.h"
#include <cmath>
#include <set>
#include <algorithm>

namespace steak {

static float dist(float x1, float y1, float x2, float y2) {
  float dx = x1 - x2, dy = y1 - y2;
  return std::sqrt(dx * dx + dy * dy);
}

static float iou(const SteakPacket& a, const SteakPacket& b) {
  const float left = std::max(a.bbox_x1, b.bbox_x1);
  const float top = std::max(a.bbox_y1, b.bbox_y1);
  const float right = std::min(a.bbox_x2, b.bbox_x2);
  const float bottom = std::min(a.bbox_y2, b.bbox_y2);
  const float intersection = std::max(0.f, right - left) * std::max(0.f, bottom - top);
  const float area_a = std::max(0.f, a.bbox_x2 - a.bbox_x1) * std::max(0.f, a.bbox_y2 - a.bbox_y1);
  const float area_b = std::max(0.f, b.bbox_x2 - b.bbox_x1) * std::max(0.f, b.bbox_y2 - b.bbox_y1);
  const float total = area_a + area_b - intersection;
  return total > 0.f ? intersection / total : 0.f;
}

// --- Grill ------------------------------------------------------------------

Grill::Grill(int max_age) : next_id_(1), max_age_(max_age) {}

int Grill::add_steak(float cx, float cy, float conf, uint32_t frame) {
  int id = next_id_++;
  steaks_[id] = TrackedSteak{
      id, cx, cy, conf, frame, 0
  };
  return id;
}

void Grill::update_steak(int id, float cx, float cy, float conf, uint32_t frame) {
  auto it = steaks_.find(id);
  if (it == steaks_.end()) return;
  it->second.centroid_x = cx;
  it->second.centroid_y = cy;
  it->second.confidence = conf;
  it->second.last_seen_frame = frame;
  it->second.miss_count = 0;
}

void Grill::mark_missed(int id) {
  auto it = steaks_.find(id);
  if (it == steaks_.end()) return;
  it->second.miss_count++;
}

void Grill::prune() {
  for (auto it = steaks_.begin(); it != steaks_.end(); ) {
    if (it->second.miss_count > max_age_)
      it = steaks_.erase(it);
    else
      ++it;
  }
}

std::vector<TrackedSteak> Grill::get_steaks() const {
  std::vector<TrackedSteak> out;
  out.reserve(steaks_.size());
  for (const auto& p : steaks_)
    out.push_back(p.second);
  return out;
}

// --- SteakTracker -----------------------------------------------------------

SteakTracker::SteakTracker(Grill& grill, float match_distance, float dedupe_iou)
    : grill_(grill),
      match_distance_(match_distance),
      dedupe_iou_(dedupe_iou),
      last_frame_(0) {}

std::pair<size_t, size_t> SteakTracker::ingest(const std::vector<SteakPacket>& packets) {
  uint32_t frame = 0;
  for (const auto& p : packets)
    if (p.timestamp > frame) frame = p.timestamp;
  if (!packets.empty()) last_frame_ = frame;

  if (packets.empty()) {
    for (const auto& s : grill_.get_steaks())
      grill_.mark_missed(s.stable_id);
    grill_.prune();
    return {0, 0};
  }

  // Same-frame dedupe: merge overlapping boxes and keep the highest confidence.
  std::vector<SteakPacket> reps;
  std::vector<bool> used(packets.size(), false);
  for (size_t i = 0; i < packets.size(); ++i) {
    if (used[i]) continue;
    const SteakPacket* best = &packets[i];
    for (size_t j = i + 1; j < packets.size(); ++j) {
      if (used[j]) continue;
      if (iou(packets[i], packets[j]) >= dedupe_iou_) {
        used[j] = true;
        if (packets[j].confidence > best->confidence) best = &packets[j];
      }
    }
    reps.push_back(*best);
  }

  // Associate reps to existing steaks: greedy nearest within match_distance.
  std::set<int> matched;
  std::vector<std::pair<int, SteakPacket>> updates;  // (stable_id, packet)
  std::vector<SteakPacket> unassigned;

  for (const auto& p : reps) {
    int best_id = -1;
    float best_d = match_distance_ + 1.f;
    for (const auto& s : grill_.get_steaks()) {
      if (matched.count(s.stable_id)) continue;
      float d = dist(p.centroid_x, p.centroid_y, s.centroid_x, s.centroid_y);
      if (d < best_d && d <= match_distance_) {
        best_d = d;
        best_id = s.stable_id;
      }
    }
    if (best_id >= 0) {
      matched.insert(best_id);
      updates.push_back({best_id, p});
    } else {
      unassigned.push_back(p);
    }
  }

  // Apply updates for matched steaks.
  for (const auto& u : updates)
    grill_.update_steak(u.first, u.second.centroid_x, u.second.centroid_y,
                        u.second.confidence, u.second.timestamp);

  // Mark existing steaks that were not matched this frame, then prune.
  for (const auto& s : grill_.get_steaks())
    if (!matched.count(s.stable_id))
      grill_.mark_missed(s.stable_id);
  grill_.prune();

  // Create new steaks for unassigned packets (after prune so we don't mark them missed).
  for (const auto& p : unassigned)
    grill_.add_steak(p.centroid_x, p.centroid_y, p.confidence, p.timestamp);

  size_t deduped = packets.size() - reps.size();
  size_t new_steaks = unassigned.size();
  return {deduped, new_steaks};
}

}  // namespace steak
