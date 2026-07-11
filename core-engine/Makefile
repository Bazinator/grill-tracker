# core-engine: pipeline consumer (stdin) and file-based reader test
CXX ?= g++
# Include path: sources use "../include/SteakPacket.h" (relative to src/)
CXXFLAGS = -std=c++17 -Wall

STEAK_CONSUMER = steak_consumer
READER_TEST = reader_test

.PHONY: all clean test test-scenarios

all: $(STEAK_CONSUMER) $(READER_TEST)

$(STEAK_CONSUMER): src/main.cpp src/steak_state.cpp
	$(CXX) $(CXXFLAGS) -o $@ src/main.cpp src/steak_state.cpp

# reader_test reads from a file; live pipeline uses main.cpp + stdin
$(READER_TEST): src/reader_test.cpp
	$(CXX) $(CXXFLAGS) -o $@ src/reader_test.cpp

clean:
	rm -f $(STEAK_CONSUMER) $(READER_TEST)

test: all
	@cd .. && python3 perception/pulse_test.py
	@echo "--- C++ stdin test (single frame) ---" && STEAK_VERBOSE=1 ./$(STEAK_CONSUMER) < ../perception/steak_pulse_stream.bin 2>&1
	@echo "--- C++ stdin test (multi-frame) ---" && STEAK_VERBOSE=1 ./$(STEAK_CONSUMER) < ../perception/steak_pulse_stream_multi.bin 2>&1

test-scenarios: all
	@echo "=== Running synthetic test scenarios ==="
	@for s in stable flicker dual drift multi; do \
		echo "--- Scenario: $$s ---"; \
		cd .. && python3 perception/generate_test_stream.py $$s /tmp/test_$$s.bin --frames 50; \
		cd core-engine && ./$(STEAK_CONSUMER) < /tmp/test_$$s.bin 2>&1; \
	done
