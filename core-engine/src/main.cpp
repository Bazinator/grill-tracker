/*
 * Pipeline consumer: reads binary frames from stdin.
 * Wire format: count(4 bytes LE) + N x SteakPacket(36 bytes).
 * Build and run: python3 -u perception/testModel.py --pipe --video /path 2>/dev/null | ./steak_consumer
 * steak_state Grill + SteakTracker reduce dual detections and keep stable IDs.
 * STEAK_VERBOSE=1 prints packets and Grill state to stderr.
 * At EOF, emits STEAK_RUN_STATS JSON to stderr (or STEAK_STATS_PATH if set).
 */
#include <cstdint>
#include <cstdlib>
#include <cstdio>
#include <vector>
#include <cstring>
#include <algorithm>

#if defined(_WIN32) || defined(_WIN64)
#include <io.h>
#define STDIN_FILENO 0
#define read _read
#else
#include <unistd.h>
#endif

#include "../include/SteakPacket.h"
#include "../include/steak_state.h"

static bool read_exact(int fd, char* buf, size_t n) {
  size_t done = 0;
  while (done < n) {
    ssize_t r = read(fd, buf + done, n - done);
    if (r <= 0) return false;
    done += static_cast<size_t>(r);
  }
  return true;
}

static float env_float(const char* name, float fallback, float minimum, float maximum) {
  const char* value = std::getenv(name);
  if (!value) return fallback;
  char* end = nullptr;
  const float parsed = std::strtof(value, &end);
  return end != value && *end == '\0' && parsed >= minimum && parsed <= maximum
      ? parsed : fallback;
}

static int env_int(const char* name, int fallback, int minimum, int maximum) {
  const char* value = std::getenv(name);
  if (!value) return fallback;
  char* end = nullptr;
  const long parsed = std::strtol(value, &end, 10);
  return end != value && *end == '\0' && parsed >= minimum && parsed <= maximum
      ? static_cast<int>(parsed) : fallback;
}

// Run statistics structure
struct RunStats {
  uint64_t frames_processed = 0;
  uint64_t packets_total = 0;
  uint64_t dedupes_total = 0;
  size_t max_grill_size = 0;
};

static void emit_state(const RunStats& stats, const steak::SteakTracker& tracker, FILE* out) {
  if (!out) return;
  const auto steaks = tracker.get_steaks();
  std::fprintf(out, "{\"frame\":%llu,\"steaks\":[",
               (unsigned long long)stats.frames_processed);
  for (size_t i = 0; i < steaks.size(); ++i) {
    const auto& s = steaks[i];
    std::fprintf(out,
      "%s{\"stable_id\":%d,\"cx\":%.2f,\"cy\":%.2f,\"confidence\":%.3f,\"miss_count\":%d}",
      i ? "," : "", s.stable_id, (double)s.centroid_x, (double)s.centroid_y,
      (double)s.confidence, s.miss_count);
  }
  std::fprintf(out, "]}\n");
  std::fflush(out);
}

static void process_frame(std::vector<SteakPacket>& packets, steak::SteakTracker& tracker,
                          RunStats& stats, FILE* state_out) {
  auto [deduped, new_steaks] = tracker.ingest(packets);
  stats.frames_processed++;
  stats.packets_total += packets.size();
  stats.dedupes_total += deduped;
  stats.max_grill_size = std::max(stats.max_grill_size, tracker.get_steaks().size());
  emit_state(stats, tracker, state_out);

  const char* v = std::getenv("STEAK_VERBOSE");
  if (v && v[0] == '1') {
    std::fprintf(stderr, "packets=%zu deduped=%zu new=%zu\n", packets.size(), deduped, new_steaks);
    for (size_t i = 0; i < packets.size(); ++i) {
      const SteakPacket& p = packets[i];
      std::fprintf(stderr, "  raw steak_id=%d centroid=(%.2f,%.2f) conf=%.3f ts=%u\n",
                   (int)p.steak_id, (double)p.centroid_x, (double)p.centroid_y,
                   (double)p.confidence, (unsigned)p.timestamp);
    }
    std::vector<steak::TrackedSteak> st = tracker.get_steaks();
    std::fprintf(stderr, "grill steaks=%zu\n", st.size());
    for (const auto& s : st) {
      std::fprintf(stderr, "  stable_id=%d centroid=(%.2f,%.2f) conf=%.3f last_seen=%u miss=%d\n",
                   s.stable_id, (double)s.centroid_x, (double)s.centroid_y,
                   (double)s.confidence, (unsigned)s.last_seen_frame, s.miss_count);
    }
  }
}

static void emit_stats(const RunStats& stats, int cumulative_steaks) {
  const char* stats_path = std::getenv("STEAK_STATS_PATH");
  FILE* out = stderr;
  bool close_out = false;
  if (stats_path && stats_path[0]) {
    out = std::fopen(stats_path, "w");
    if (!out) out = stderr;
    else close_out = true;
  }
  std::fprintf(out,
    "{\"frames_processed\":%llu,\"packets_total\":%llu,\"dedupes_total\":%llu,"
    "\"max_grill_size\":%zu,\"cumulative_steaks\":%d}\n",
    (unsigned long long)stats.frames_processed,
    (unsigned long long)stats.packets_total,
    (unsigned long long)stats.dedupes_total,
    stats.max_grill_size,
    cumulative_steaks);
  if (close_out) std::fclose(out);
}

int main() {
  const float match_distance = env_float("STEAK_MATCH_DISTANCE", 90.f, 1.f, 10000.f);
  const float dedupe_iou = env_float("STEAK_DEDUPE_IOU", 0.2f, 0.f, 1.f);
  const int max_age = env_int("STEAK_MAX_AGE", 25, 0, 100000);
  steak::Grill grill(max_age);
  steak::SteakTracker tracker(grill, match_distance, dedupe_iou);
  RunStats stats;
  const char* state_path = std::getenv("STEAK_STATE_PATH");
  FILE* state_out = state_path && state_path[0] ? std::fopen(state_path, "w") : nullptr;

  char count_buf[4];
  while (read_exact(STDIN_FILENO, count_buf, 4)) {
    uint32_t count;
    count = static_cast<uint32_t>(static_cast<unsigned char>(count_buf[0]))
          | (static_cast<uint32_t>(static_cast<unsigned char>(count_buf[1])) << 8)
          | (static_cast<uint32_t>(static_cast<unsigned char>(count_buf[2])) << 16)
          | (static_cast<uint32_t>(static_cast<unsigned char>(count_buf[3])) << 24);

    if (count == 0) {
      std::vector<SteakPacket> empty;
      process_frame(empty, tracker, stats, state_out);
      continue;
    }

    const size_t want = count * sizeof(SteakPacket);
    std::vector<char> raw(want);
    if (!read_exact(STDIN_FILENO, raw.data(), want))
      break;

    std::vector<SteakPacket> packets(count);
    for (uint32_t i = 0; i < count; ++i)
      packets[i] = *reinterpret_cast<const SteakPacket*>(raw.data() + i * sizeof(SteakPacket));

    process_frame(packets, tracker, stats, state_out);
  }

  if (state_out) std::fclose(state_out);
  emit_stats(stats, tracker.cumulative_steaks());
  return 0;
}
