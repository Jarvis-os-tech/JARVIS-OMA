#ifndef JARVIS_WEBRTC_GAIN_H
#define JARVIS_WEBRTC_GAIN_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Control-thread-only C ABI for the system's standalone WebRTC APM library.
 * PipeWire already supplies AEC/NS. This stage adds digital gain only, without
 * an analog mixer dependency or a second echo canceller/noise suppressor. */
struct jarvis_webrtc_gain;
enum {
    JARVIS_WEBRTC_GAIN_SAMPLES = 160, /* 10 ms, mono, 16 kHz PCM16 */
    JARVIS_WEBRTC_GAIN_INVALID = -1000,
    JARVIS_WEBRTC_GAIN_CREATE_FAILED = -1001,
    JARVIS_WEBRTC_GAIN_EXCEPTION = -1002,
    JARVIS_WEBRTC_GAIN_CONFIG_FAILED = -1003,
    JARVIS_WEBRTC_GAIN_UNAVAILABLE = -1004
};

/* enabled must be 0 or 1. Success returns 0 and a non-NULL handle. Failure
 * returns an error and leaves *out NULL; it never silently disables AGC. */
int jarvis_webrtc_gain_create(int enabled, struct jarvis_webrtc_gain **out);
void jarvis_webrtc_gain_destroy(struct jarvis_webrtc_gain *gain);

/* Exactly one 10 ms frame, modified in place. Disabled handles are bit-exact
 * pass-through. A failed frame must be discarded by the caller. */
int jarvis_webrtc_gain_process(struct jarvis_webrtc_gain *gain,
                              int16_t *samples, size_t sample_count);
uint64_t jarvis_webrtc_gain_sample_count(const struct jarvis_webrtc_gain *gain);
int jarvis_webrtc_gain_available(void);
const char *jarvis_webrtc_gain_version(void);

/* Deterministic linked synthetic checks; never opens an audio device. */
int jarvis_webrtc_gain_self_test(void);

#ifdef __cplusplus
}
#endif
#endif
