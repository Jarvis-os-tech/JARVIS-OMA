package com.jarvis.os.audio

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import android.os.Build
import android.util.Log
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Low-latency audio playback engine streaming 24,000 Hz 16-bit mono PCM chunks
 * directly to the audio subsystem, supporting click-free barge-in cancellation.
 */
class AudioPlaybackEngine(
    private val sampleRate: Int = SAMPLE_RATE_HZ
) {
    private var audioTrack: AudioTrack? = null
    private val isInitialized = AtomicBoolean(false)
    private val isPlaying = AtomicBoolean(false)

    init {
        initAudioTrack()
    }

    @Synchronized
    private fun initAudioTrack() {
        if (isInitialized.get() && audioTrack != null) return

        val channelConfig = AudioFormat.CHANNEL_OUT_MONO
        val audioFormat = AudioFormat.ENCODING_PCM_16BIT
        val minBufferSize = AudioTrack.getMinBufferSize(sampleRate, channelConfig, audioFormat)
        val bufferSize = maxOf(minBufferSize, 4096)

        try {
            val track = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                AudioTrack.Builder()
                    .setAudioAttributes(
                        AudioAttributes.Builder()
                            .setUsage(AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE)
                            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                            .build()
                    )
                    .setAudioFormat(
                        AudioFormat.Builder()
                            .setEncoding(audioFormat)
                            .setSampleRate(sampleRate)
                            .setChannelMask(channelConfig)
                            .build()
                    )
                    .setBufferSizeInBytes(bufferSize)
                    .setTransferMode(AudioTrack.MODE_STREAM)
                    .build()
            } else {
                @Suppress("DEPRECATION")
                AudioTrack(
                    AudioManager.STREAM_MUSIC,
                    sampleRate,
                    channelConfig,
                    audioFormat,
                    bufferSize,
                    AudioTrack.MODE_STREAM
                )
            }

            if (track.state == AudioTrack.STATE_INITIALIZED) {
                track.play()
                audioTrack = track
                isInitialized.set(true)
                isPlaying.set(true)
                Log.i(TAG, "AudioTrack initialized successfully at $sampleRate Hz")
            } else {
                Log.e(TAG, "AudioTrack failed to initialize")
                track.release()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Exception initializing AudioTrack: ${e.message}", e)
        }
    }

    /**
     * Play raw 24kHz mono PCM16 audio bytes.
     */
    @Synchronized
    fun playPcm(data: ByteArray): Int {
        if (!isInitialized.get() || audioTrack == null) {
            initAudioTrack()
        }

        val track = audioTrack ?: return -1

        try {
            if (track.playState != AudioTrack.PLAYSTATE_PLAYING) {
                track.play()
                isPlaying.set(true)
            }

            var written = 0
            while (written < data.size) {
                val res = track.write(data, written, data.size - written)
                if (res > 0) {
                    written += res
                } else {
                    Log.e(TAG, "AudioTrack write error: $res")
                    break
                }
            }
            return written
        } catch (e: Exception) {
            Log.e(TAG, "Exception during playPcm: ${e.message}", e)
            return -1
        }
    }

    /**
     * Instantly halt playback, flush buffers without pops/clicks, and reset state.
     * Crucial for conversational barge-in responsiveness.
     */
    @Synchronized
    fun cancel() {
        val track = audioTrack ?: return
        try {
            if (track.playState == AudioTrack.PLAYSTATE_PLAYING) {
                track.pause()
                track.flush()
            }
            isPlaying.set(false)
            Log.d(TAG, "AudioPlayback cancelled and flushed")
        } catch (e: Exception) {
            Log.e(TAG, "Error cancelling playback: ${e.message}", e)
        }
    }

    @Synchronized
    fun pause() {
        try {
            audioTrack?.pause()
            isPlaying.set(false)
        } catch (e: Exception) {
            Log.e(TAG, "Error pausing playback: ${e.message}", e)
        }
    }

    @Synchronized
    fun resume() {
        try {
            audioTrack?.play()
            isPlaying.set(true)
        } catch (e: Exception) {
            Log.e(TAG, "Error resuming playback: ${e.message}", e)
        }
    }

    @Synchronized
    fun release() {
        try {
            audioTrack?.apply {
                if (playState == AudioTrack.PLAYSTATE_PLAYING) {
                    stop()
                }
                flush()
                release()
            }
            audioTrack = null
            isInitialized.set(false)
            isPlaying.set(false)
            Log.i(TAG, "AudioPlaybackEngine released")
        } catch (e: Exception) {
            Log.e(TAG, "Error releasing AudioTrack: ${e.message}", e)
        }
    }

    companion object {
        private const val TAG = "AudioPlaybackEngine"
        const val SAMPLE_RATE_HZ = 24000
    }
}
