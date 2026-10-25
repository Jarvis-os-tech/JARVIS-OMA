#include "webrtc_gain.h"

#if JARVIS_HAVE_WEBRTC
#include <modules/audio_processing/include/audio_processing.h>
#endif
#include <memory>

struct jarvis_webrtc_gain {
#if JARVIS_HAVE_WEBRTC
    rtc::scoped_refptr<webrtc::AudioProcessing> apm;
    webrtc::StreamConfig stream{16000, 1};
#endif
    uint64_t sample_count = 0;
};

extern "C" int jarvis_webrtc_gain_create(int enabled,
                                         struct jarvis_webrtc_gain **out) {
    if (!out) return JARVIS_WEBRTC_GAIN_INVALID;
    *out = nullptr;
    if (enabled != 0 && enabled != 1) return JARVIS_WEBRTC_GAIN_INVALID;
#if !JARVIS_HAVE_WEBRTC
    if (enabled) return JARVIS_WEBRTC_GAIN_UNAVAILABLE;
#endif
    try {
        auto gain = std::make_unique<jarvis_webrtc_gain>();
#if JARVIS_HAVE_WEBRTC
        if (enabled) {
            gain->apm = webrtc::AudioProcessingBuilder().Create();
            if (!gain->apm) return JARVIS_WEBRTC_GAIN_CREATE_FAILED;
            webrtc::AudioProcessing::Config config;
            config.echo_canceller.enabled = false;
            config.noise_suppression.enabled = false;
            config.high_pass_filter.enabled = false;
            config.pre_amplifier.enabled = false;
            config.transient_suppression.enabled = false;
            config.residual_echo_detector.enabled = false;
            config.gain_controller2.enabled = false;
            config.gain_controller1.enabled = true;
            config.gain_controller1.mode =
                webrtc::AudioProcessing::Config::GainController1::kAdaptiveDigital;
            config.gain_controller1.analog_gain_controller.enabled = false;
            config.gain_controller1.target_level_dbfs = 3;
            config.gain_controller1.compression_gain_db = 9;
            config.gain_controller1.enable_limiter = true;
            gain->apm->ApplyConfig(config);
            webrtc::ProcessingConfig streams;
            streams.input_stream() = gain->stream;
            streams.output_stream() = gain->stream;
            streams.reverse_input_stream() = gain->stream;
            streams.reverse_output_stream() = gain->stream;
            int result = gain->apm->Initialize(streams);
            if (result != webrtc::AudioProcessing::kNoError) return result;
            const auto actual = gain->apm->GetConfig();
            if (actual.echo_canceller.enabled || actual.noise_suppression.enabled ||
                actual.high_pass_filter.enabled || actual.gain_controller2.enabled ||
                !actual.gain_controller1.enabled ||
                !actual.gain_controller1.enable_limiter ||
                actual.gain_controller1.mode !=
                    webrtc::AudioProcessing::Config::GainController1::kAdaptiveDigital)
                return JARVIS_WEBRTC_GAIN_CONFIG_FAILED;
        }
#endif
        *out = gain.release();
        return 0;
    } catch (...) {
        return JARVIS_WEBRTC_GAIN_EXCEPTION;
    }
}

extern "C" void jarvis_webrtc_gain_destroy(struct jarvis_webrtc_gain *gain) {
    delete gain;
}

extern "C" int jarvis_webrtc_gain_process(struct jarvis_webrtc_gain *gain,
                                          int16_t *samples, size_t sample_count) {
    if (!gain || !samples || sample_count != JARVIS_WEBRTC_GAIN_SAMPLES)
        return JARVIS_WEBRTC_GAIN_INVALID;
    try {
#if JARVIS_HAVE_WEBRTC
        if (gain->apm) {
            const int result = gain->apm->ProcessStream(
                samples, gain->stream, gain->stream, samples);
            if (result != webrtc::AudioProcessing::kNoError) return result;
        }
#endif
        gain->sample_count += sample_count;
        return 0;
    } catch (...) {
        return JARVIS_WEBRTC_GAIN_EXCEPTION;
    }
}

extern "C" uint64_t jarvis_webrtc_gain_sample_count(
        const struct jarvis_webrtc_gain *gain) {
    return gain ? gain->sample_count : 0;
}

extern "C" int jarvis_webrtc_gain_available(void) {
    return JARVIS_HAVE_WEBRTC;
}

extern "C" const char *jarvis_webrtc_gain_version(void) {
#if JARVIS_HAVE_WEBRTC
    return JARVIS_WEBRTC_VERSION;
#else
    return "unavailable";
#endif
}
