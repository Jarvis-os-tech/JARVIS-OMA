#include "webrtc_gain.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Use explicit checks so release builds with NDEBUG still exercise the DSP. */
#define CHECK(condition) do { \
    if (!(condition)) { \
        fprintf(stderr, "WebRTC gain self-test failed at line %d: %s\n", \
                __LINE__, #condition); \
        result = 1; goto cleanup; \
    } \
} while (0)

int jarvis_webrtc_gain_self_test(void) {
    int result = 0;
    struct jarvis_webrtc_gain *off = NULL, *on = NULL, *invalid = NULL;
    struct { int16_t before, pcm[JARVIS_WEBRTC_GAIN_SAMPLES], after; } frame;
    int16_t original[JARVIS_WEBRTC_GAIN_SAMPLES];
    uint64_t expected_count = 0;
    double input_energy = 0, output_energy = 0;
    int changed = 0, peak = 0;

    CHECK(jarvis_webrtc_gain_create(1, NULL) == JARVIS_WEBRTC_GAIN_INVALID);
    CHECK(jarvis_webrtc_gain_create(2, &invalid) == JARVIS_WEBRTC_GAIN_INVALID);
    CHECK(invalid == NULL);
    CHECK(jarvis_webrtc_gain_create(0, &off) == 0 && off != NULL);
    const int enabled_status = jarvis_webrtc_gain_create(1, &on);
    if (jarvis_webrtc_gain_available()) CHECK(enabled_status == 0 && on != NULL);
    else CHECK(enabled_status == JARVIS_WEBRTC_GAIN_UNAVAILABLE && on == NULL);
    CHECK(jarvis_webrtc_gain_process(NULL, frame.pcm, 160) == JARVIS_WEBRTC_GAIN_INVALID);
    CHECK(jarvis_webrtc_gain_process(off, NULL, 160) == JARVIS_WEBRTC_GAIN_INVALID);
    CHECK(jarvis_webrtc_gain_process(off, frame.pcm, 159) == JARVIS_WEBRTC_GAIN_INVALID);
    CHECK(jarvis_webrtc_gain_process(off, frame.pcm, 320) == JARVIS_WEBRTC_GAIN_INVALID);
    CHECK(jarvis_webrtc_gain_process(off, frame.pcm, 0) == JARVIS_WEBRTC_GAIN_INVALID);
    CHECK(jarvis_webrtc_gain_sample_count(off) == 0);

    /* Disabled processing must preserve even full-scale signed samples. */
    frame.before = 1234; frame.after = -1234;
    for (size_t i = 0; i < 160; ++i)
        original[i] = frame.pcm[i] = (int16_t)((int)i * 411 - 32768);
    CHECK(jarvis_webrtc_gain_process(off, frame.pcm, 160) == 0);
    CHECK(memcmp(original, frame.pcm, sizeof(original)) == 0);
    CHECK(jarvis_webrtc_gain_sample_count(off) == 160);
    CHECK(frame.before == 1234 && frame.after == -1234);
    if (!on) {
        puts("WebRTC gain unavailable: disabled passthrough and explicit enable-error self-tests passed; DSP not tested");
        goto cleanup;
    }

    /* A fresh enabled processor must not manufacture sound from silence. */
    for (int packet = 0; packet < 100; ++packet) {
        memset(frame.pcm, 0, sizeof(frame.pcm));
        CHECK(jarvis_webrtc_gain_process(on, frame.pcm, 160) == 0);
        expected_count += 160;
        for (size_t i = 0; i < 160; ++i) CHECK(frame.pcm[i] == 0);
    }

    /* Two seconds of quiet voiced-like input: prove actual linked gain work,
     * and that every 10 ms call preserves the frame boundaries and count. */
    for (int packet = 0; packet < 200; ++packet) {
        for (size_t i = 0; i < 160; ++i) {
            const double t = (packet * 160 + (int)i) / 16000.0;
            original[i] = frame.pcm[i] = (int16_t)(
                600 * sin(2 * 3.141592653589793 * 180 * t) +
                200 * sin(2 * 3.141592653589793 * 360 * t));
        }
        CHECK(jarvis_webrtc_gain_process(on, frame.pcm, 160) == 0);
        expected_count += 160;
        CHECK(frame.before == 1234 && frame.after == -1234);
        for (size_t i = 0; i < 160; ++i) {
            changed += frame.pcm[i] != original[i];
            input_energy += (double)original[i] * original[i];
            output_energy += (double)frame.pcm[i] * frame.pcm[i];
        }
    }
    CHECK(changed > 160);
    CHECK(output_energy > input_energy * 1.05);

    /* Sustained loud input must remain bounded without signed wrapping. */
    for (int packet = 0; packet < 200; ++packet) {
        for (size_t i = 0; i < 160; ++i) {
            const double t = (packet * 160 + (int)i) / 16000.0;
            original[i] = frame.pcm[i] = (int16_t)(
                32760 * sin(2 * 3.141592653589793 * 200 * t));
        }
        CHECK(jarvis_webrtc_gain_process(on, frame.pcm, 160) == 0);
        expected_count += 160;
        CHECK(frame.before == 1234 && frame.after == -1234);
        for (size_t i = 0; i < 160; ++i) {
            const int magnitude = abs((int)frame.pcm[i]);
            CHECK(magnitude < 32767);
            CHECK((int)original[i] * frame.pcm[i] >= 0);
            if (magnitude > peak) peak = magnitude;
        }
    }
    CHECK(peak > 1000);
    CHECK(jarvis_webrtc_gain_sample_count(on) == expected_count);
    printf("WebRTC gain self-test passed: off=bit-exact, on=%llu samples, "
           "quiet RMS gain=%.2f, loud peak=%d, AEC/NS disabled\n",
           (unsigned long long)expected_count,
           sqrt(output_energy / input_energy), peak);

cleanup:
    jarvis_webrtc_gain_destroy(off);
    jarvis_webrtc_gain_destroy(on);
    jarvis_webrtc_gain_destroy(invalid);
    jarvis_webrtc_gain_destroy(NULL);
    return result;
}
