package com.jarvis.os.service

import android.app.Notification
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Binder
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import com.jarvis.os.JarvisApplication
import com.jarvis.os.audio.AudioCaptureEngine
import com.jarvis.os.audio.AudioPlaybackEngine
import com.jarvis.os.audio.LocalFillerMixer
import com.jarvis.os.audio.VadDetector
import com.jarvis.os.audio.VadState
import com.jarvis.os.gemini.ConversationState
import com.jarvis.os.overlay.OverlayUiState
import com.jarvis.os.overlay.OverlayWindowManager
import com.jarvis.os.net.GeminiLiveClient
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Core ambient foreground daemon for JARVIS Mobile.
 * Coordinates audio capture, voice activity detection, local filler reflex,
 * full-duplex Gemini Live streaming, and Siri-style floating HUD overlay visibility.
 */
class JarvisVoiceService : Service() {

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var wakeLock: PowerManager.WakeLock? = null
    private val binder = LocalBinder()

    private val captureEngine = AudioCaptureEngine()
    private val playbackEngine = AudioPlaybackEngine()
    private val vadDetector = VadDetector()
    private val fillerMixer = LocalFillerMixer()
    private val geminiClient = GeminiLiveClient()
    private var overlayManager: OverlayWindowManager? = null

    private val _currentState = MutableStateFlow(ConversationState.IDLE)
    val currentState: StateFlow<ConversationState> = _currentState.asStateFlow()

    private var idleTimeoutJob: Job? = null

    inner class LocalBinder : Binder() {
        fun getService(): JarvisVoiceService = this@JarvisVoiceService
    }

    override fun onBind(intent: Intent?): IBinder = binder

    override fun onCreate() {
        super.onCreate()
        Log.i(TAG, "JarvisVoiceService onCreate")
        acquireWakeLock()
        setupGeminiCallbacks()
        try {
            overlayManager = OverlayWindowManager(this).apply {
                attach()
            }
        } catch (e: Exception) {
            Log.w(TAG, "Unable to initialize overlay window: ${e.message}")
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val action = intent?.action ?: ACTION_START
        Log.i(TAG, "JarvisVoiceService onStartCommand action=$action")

        when (action) {
            ACTION_START -> {
                startForeground(NOTIFICATION_ID, buildNotification("JARVIS Ambient Assistant is active"))
                startVoicePipeline()
            }
            ACTION_STOP -> {
                stopVoicePipeline()
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
            }
            ACTION_TOGGLE -> {
                if (captureEngine.isCapturing) {
                    stopVoicePipeline()
                } else {
                    startVoicePipeline()
                }
            }
        }

        return START_STICKY
    }

    private fun acquireWakeLock() {
        try {
            val pm = getSystemService(Context.POWER_SERVICE) as? PowerManager
            wakeLock = pm?.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "JARVIS::VoiceServiceWakeLock")?.apply {
                acquire(24 * 60 * 60 * 1000L) // 24 hours max
            }
        } catch (e: Exception) {
            Log.w(TAG, "Failed to acquire wake lock: ${e.message}")
        }
    }

    private fun releaseWakeLock() {
        try {
            if (wakeLock?.isHeld == true) {
                wakeLock?.release()
            }
            wakeLock = null
        } catch (e: Exception) {
            Log.w(TAG, "Error releasing wake lock: ${e.message}")
        }
    }

    private fun setupGeminiCallbacks() {
        geminiClient.onAudioReceived = { rawPcm ->
            // Route through LocalFillerMixer to execute smooth Raised-Cosine crossfade
            val mixedPcm = fillerMixer.feedGeminiAudio(rawPcm)
            playbackEngine.playPcm(mixedPcm)

            if (_currentState.value != ConversationState.SPEAKING) {
                updateState(ConversationState.SPEAKING)
            }
        }

        geminiClient.onTurnComplete = {
            Log.d(TAG, "Model turn complete")
            scheduleIdleDissolve(delayMs = 1500)
        }

        geminiClient.onInterrupted = {
            Log.d(TAG, "Model response interrupted (barge-in)")
            playbackEngine.cancel()
            fillerMixer.cancel()
            updateState(ConversationState.LISTENING)
        }

        geminiClient.onToolCall = { call ->
            if (call.name == "play_local_filler") {
                val contextType = call.args["context_type"] ?: "general"
                val fillerAudio = fillerMixer.triggerFiller(contextType)
                playbackEngine.playPcm(fillerAudio)
                geminiClient.sendToolResponse(call.id, call.name, "{\"status\":\"filler_active\"}")
            }
        }
    }

    private fun startVoicePipeline() {
        // Connect to Gemini Live if not already connected
        val apiKey = getSharedPreferences("jarvis_prefs", Context.MODE_PRIVATE)
            .getString("gemini_api_key", "") ?: ""

        if (apiKey.isNotBlank() && !geminiClient.connected) {
            geminiClient.connect(apiKey = apiKey)
        }

        captureEngine.startCapture(serviceScope) { chunk ->
            // Voice activity detection
            val vadResult = vadDetector.process(chunk)

            when (vadResult.state) {
                VadState.SPEECH -> {
                    idleTimeoutJob?.cancel()
                    if (_currentState.value == ConversationState.SPEAKING) {
                        // User barged in while model was speaking
                        playbackEngine.cancel()
                        fillerMixer.cancel()
                    }
                    if (_currentState.value != ConversationState.LISTENING) {
                        updateState(ConversationState.LISTENING)
                    }
                    geminiClient.sendAudio(chunk)
                }

                VadState.HANGOVER -> {
                    // Still within speech continuation window
                    geminiClient.sendAudio(chunk)
                }

                VadState.SILENCE -> {
                    if (_currentState.value == ConversationState.LISTENING) {
                        // User finished speaking, now waiting for response
                        updateState(ConversationState.THINKING)
                    }
                }

                VadState.ATTACK -> {
                    // Attack onset, buffer or stream
                    geminiClient.sendAudio(chunk)
                }
            }
        }
    }

    private fun stopVoicePipeline() {
        captureEngine.stopCapture()
        playbackEngine.cancel()
        playbackEngine.release()
        fillerMixer.cancel()
        geminiClient.disconnect()
        updateState(ConversationState.IDLE)
    }

    private fun updateState(newState: ConversationState, rms: Float = 0f) {
        _currentState.value = newState
        val uiState = when (newState) {
            ConversationState.IDLE -> OverlayUiState.Idle
            ConversationState.LISTENING -> OverlayUiState.Listening(rms)
            ConversationState.THINKING -> OverlayUiState.Thinking("Reasoning...")
            ConversationState.SPEAKING -> OverlayUiState.Speaking(rms)
            ConversationState.ERROR -> OverlayUiState.Idle
        }
        overlayManager?.updateState(uiState)
        updateNotification("JARVIS: ${newState.name.lowercase().replaceFirstChar { it.uppercase() }}")
    }

    private fun scheduleIdleDissolve(delayMs: Long) {
        idleTimeoutJob?.cancel()
        idleTimeoutJob = serviceScope.launch {
            delay(delayMs)
            updateState(ConversationState.IDLE)
        }
    }

    private fun buildNotification(statusText: String): Notification {
        val launchIntent = packageManager.getLaunchIntentForPackage(packageName)
        val pendingIntent = if (launchIntent != null) {
            PendingIntent.getActivity(this, 0, launchIntent, PendingIntent.FLAG_IMMUTABLE)
        } else {
            null
        }

        val builder = NotificationCompat.Builder(this, JarvisApplication.CHANNEL_ID_VOICE)
            .setContentTitle("JARVIS Ambient Voice")
            .setContentText(statusText)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)

        if (pendingIntent != null) {
            builder.setContentIntent(pendingIntent)
        }

        return builder.build()
    }

    private fun updateNotification(statusText: String) {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager
        nm?.notify(NOTIFICATION_ID, buildNotification(statusText))
    }

    override fun onDestroy() {
        super.onDestroy()
        Log.i(TAG, "JarvisVoiceService onDestroy")
        stopVoicePipeline()
        overlayManager?.detach()
        overlayManager = null
        releaseWakeLock()
        serviceScope.cancel()
    }

    companion object {
        private const val TAG = "JarvisVoiceService"
        const val NOTIFICATION_ID = 1001
        const val ACTION_START = "com.jarvis.os.action.START"
        const val ACTION_STOP = "com.jarvis.os.action.STOP"
        const val ACTION_TOGGLE = "com.jarvis.os.action.TOGGLE"
    }
}
