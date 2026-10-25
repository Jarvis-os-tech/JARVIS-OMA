CC ?= cc
CXX ?= c++
CFLAGS ?= -O2 -g -Wall -Wextra -Werror -std=c11
CXXFLAGS ?= -O2 -g -Wall -Wextra -Werror -std=c++17
PW_CFLAGS := $(shell pkg-config --cflags libpipewire-0.3)
PW_LIBS := $(shell pkg-config --libs libpipewire-0.3)
WITH_WEBRTC ?= $(shell pkg-config --exists webrtc-audio-processing-1 && echo 1 || echo 0)
ifeq ($(WITH_WEBRTC),1)
WEBRTC_CFLAGS := $(patsubst -I%,-isystem %,$(shell pkg-config --cflags webrtc-audio-processing-1 2>/dev/null))
WEBRTC_LIBS := $(shell pkg-config --libs webrtc-audio-processing-1 2>/dev/null)
WEBRTC_VERSION := $(shell pkg-config --modversion webrtc-audio-processing-1 2>/dev/null)
else ifneq ($(WITH_WEBRTC),0)
$(error WITH_WEBRTC must be 0 or 1)
endif

jarvis-audio: companion.o webrtc_gain.o webrtc_gain_test.o
	$(CXX) $(LDFLAGS) $^ -o $@ $(PW_LIBS) $(WEBRTC_LIBS) -lm -pthread

check-deps:
	@pkg-config --exists libpipewire-0.3 || \
		{ echo 'Native audio requires the libpipewire-0.3 development package.' >&2; exit 1; }
ifeq ($(WITH_WEBRTC),1)
	@pkg-config --exists webrtc-audio-processing-1 || \
		{ echo 'WITH_WEBRTC=1 requires the webrtc-audio-processing-1 development package.' >&2; exit 1; }
endif

# A changed package/feature configuration invalidates the wrapper object even
# if sources did not change. Keep the stamp timestamp unchanged otherwise.
.webrtc-build-config: FORCE
	@printf '%s\n' '$(WITH_WEBRTC)' '$(WEBRTC_VERSION)' '$(WEBRTC_CFLAGS)' '$(WEBRTC_LIBS)' > $@.tmp
	@cmp -s $@.tmp $@ || cp $@.tmp $@
	@rm -f $@.tmp

companion.o: companion.c webrtc_gain.h | check-deps
	$(CC) $(CPPFLAGS) $(CFLAGS) $(PW_CFLAGS) -c $< -o $@

webrtc_gain.o: webrtc_gain.cpp webrtc_gain.h .webrtc-build-config | check-deps
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $(WEBRTC_CFLAGS) -DJARVIS_HAVE_WEBRTC=$(WITH_WEBRTC) -DJARVIS_WEBRTC_VERSION='"$(WEBRTC_VERSION)"' -c $< -o $@

webrtc_gain_test.o: webrtc_gain_test.c webrtc_gain.h | check-deps
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

check: jarvis-audio
	./jarvis-audio --self-test
	./jarvis-audio --self-test-webrtc-gain

clean:
	rm -f jarvis-audio companion.o webrtc_gain.o webrtc_gain_test.o .webrtc-build-config .webrtc-build-config.tmp

.PHONY: check check-deps clean FORCE
