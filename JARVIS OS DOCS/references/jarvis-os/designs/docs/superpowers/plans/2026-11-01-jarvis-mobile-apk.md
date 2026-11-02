# JARVIS Mobile Android Client & Cloud Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete, production-grade native Android APK (`mobile/`) featuring persistent background voice interaction with Gemini Live, a zero-latency local conversational filler engine, a Siri-style floating Halo Orb and Dynamic Island overlay, and QR-code pairing with Google Cloud asynchronous memory synchronization.

**Architecture:** A native Kotlin Android 14+ application using an Android `ForegroundService` with `FOREGROUND_SERVICE_TYPE_MICROPHONE` for continuous ambient voice processing. A system-level floating overlay using `WindowManager` and Jetpack Compose provides an iridescent Siri-style Halo Orb that remains completely hidden and touch-transparent when idle, expanding into a top-docked Dynamic Island during turns. The client streams full-duplex PCM16 audio to Gemini Live, executes local vocal fillers via a 50ms Raised-Cosine ducking mixer, and synchronizes memory deltas asynchronously with project `jarvis-os-508612`.

**Tech Stack:** Kotlin 1.9+, Android SDK 34 (minSdk 26), Jetpack Compose, OkHttp 4.12+ (WebSockets), Kotlinx Coroutines & Serialization, AndroidX Room & Lifecycle, CameraX (QR scanning), Android WindowManager (`TYPE_APPLICATION_OVERLAY`).

**Spec:** [`docs/superpowers/specs/2026-11-01-jarvis-mobile-apk-design.md`](../specs/2026-11-01-jarvis-mobile-apk-design.md)

## Global Constraints
- Target SDK: 34 (Android 14), Min SDK: 26 (Android 8.0).
- Audio Input: 16,000 Hz, 16-bit mono PCM, 20ms frames (640 bytes).
- Audio Output: 24,000 Hz, 16-bit mono PCM, 20ms frames (960 bytes).
- Ducking Window: Exactly 50 ms (1,200 samples) with Raised-Cosine curve ($w_{\text{out}} = \frac{1}{2}(1 + \cos(\pi t / T))$, $w_{\text{in}} = 1 - w_{\text{out}}$).
- Idle Overlay Policy: 0% opacity, `FLAG_NOT_FOCUSABLE | FLAG_NOT_TOUCHABLE`, zero screen footprint.
- Cloud Sync Project: `jarvis-os-508612` (Firestore / Cloud Storage event mailbox).

---

### Task 1: Android Project Scaffolding & Gradle Configuration

**Files:**
- Create: `mobile/settings.gradle.kts`
- Create: `mobile/build.gradle.kts`
- Create: `mobile/app/build.gradle.kts`
- Create: `mobile/app/src/main/AndroidManifest.xml`
- Create: `mobile/app/src/main/java/com/jarvis/os/JarvisApplication.kt`

**Interfaces:**
- Produces: Base Android package `com.jarvis.os`, application context container, and build targets.

- [ ] **Step 1: Create `mobile/settings.gradle.kts`**
```kotlin
rootProject.name = "jarvis-mobile"
include(":app")
```

- [ ] **Step 2: Create root `mobile/build.gradle.kts`**
```kotlin
plugins {
    id("com.android.application") version "8.2.2" apply false
    id("org.jetbrains.kotlin.android") version "1.9.22" apply false
    id("org.jetbrains.kotlin.plugin.serialization") version "1.9.22" apply false
}
```

- [ ] **Step 3: Create `mobile/app/build.gradle.kts`**
Configure Android app module with dependencies: Jetpack Compose, OkHttp, Coroutines, Serialization, CameraX, and AndroidX Security.

- [ ] **Step 4: Create `mobile/app/src/main/AndroidManifest.xml`**
Declare permissions: `RECORD_AUDIO`, `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_MICROPHONE`, `SYSTEM_ALERT_WINDOW`, `INTERNET`, `POST_NOTIFICATIONS`, `RECEIVE_BOOT_COMPLETED`, and `CAMERA`.

- [ ] **Step 5: Create `JarvisApplication.kt`**
Initialize notification channels and dependency singletons.

- [ ] **Step 6: Commit**
```bash
git add mobile/
git commit -m "feat(mobile): scaffold Android Gradle project structure and manifest"
```

---

### Task 2: Audio Engine (Capture, Playback, and VAD)

**Files:**
- Create: `mobile/app/src/main/java/com/jarvis/os/audio/AudioCaptureEngine.kt`
- Create: `mobile/app/src/main/java/com/jarvis/os/audio/AudioPlaybackEngine.kt`
- Create: `mobile/app/src/main/java/com/jarvis/os/audio/VadDetector.kt`
- Create: `mobile/app/src/test/java/com/jarvis/os/audio/AudioPcmTest.kt`

**Interfaces:**
- Produces: `AudioCaptureEngine.startCapture(onChunk: (ByteArray) -> Unit)`, `AudioPlaybackEngine.playPcm(data: ByteArray)`, `AudioPlaybackEngine.cancel()`.

- [ ] **Step 1: Write unit test `AudioPcmTest.kt`**
Test PCM frame slicing and amplitude calculations.

- [ ] **Step 2: Implement `AudioCaptureEngine.kt`**
Use `AudioRecord` with 16,000 Hz, `CHANNEL_IN_MONO`, `ENCODING_PCM_16BIT`, reading 640-byte chunks on an IO coroutine.

- [ ] **Step 3: Implement `AudioPlaybackEngine.kt`**
Use `AudioTrack` with 24,000 Hz, `CHANNEL_OUT_MONO`, `ENCODING_PCM_16BIT` in streaming mode with click-free cancellation.

- [ ] **Step 4: Implement `VadDetector.kt`**
Energy-based and zero-crossing boundary detector with Silero VAD parameter fallback.

- [ ] **Step 5: Run tests and commit**
```bash
git add mobile/app/src/main/java/com/jarvis/os/audio/ mobile/app/src/test/
git commit -m "feat(mobile): implement AudioCaptureEngine and AudioPlaybackEngine"
```

---

### Task 3: Local Filler Reflex & Raised-Cosine Ducking Mixer

**Files:**
- Create: `mobile/app/src/main/java/com/jarvis/os/audio/LocalFillerMixer.kt`
- Create: `mobile/app/src/test/java/com/jarvis/os/audio/LocalFillerMixerTest.kt`

**Interfaces:**
- Consumes: Audio buffers from `AudioPlaybackEngine`.
- Produces: `LocalFillerMixer.triggerFiller(contextType: String)`, `LocalFillerMixer.feedGeminiAudio(data: ByteArray): ByteArray`.

- [ ] **Step 1: Write test `LocalFillerMixerTest.kt`**
Validate the Raised-Cosine ducking cross-fade mathematics: $w_{\text{out}}(t) + w_{\text{in}}(t) = 1.0$ everywhere, with zero DC jumps.

- [ ] **Step 2: Implement `LocalFillerMixer.kt`**
Maintain RAM-cached PCM clips ("humm", "let's see...", "wait a sec", "give me a moment"). Upon receiving Gemini audio, cross-fade the trailing filler over 50 ms ($N = 1,200$ samples) into pure synthesized speech.

- [ ] **Step 3: Run test to verify it passes**
- [ ] **Step 4: Commit**
```bash
git add mobile/app/src/main/java/com/jarvis/os/audio/LocalFillerMixer.kt mobile/app/src/test/
git commit -m "feat(mobile): implement LocalFillerMixer with Raised-Cosine ducking"
```

---

### Task 4: Gemini Live Bidirectional WebSocket Client

**Files:**
- Create: `mobile/app/src/main/java/com/jarvis/os/net/GeminiLiveClient.kt`
- Create: `mobile/app/src/main/java/com/jarvis/os/net/LiveSessionModels.kt`
- Create: `mobile/app/src/test/java/com/jarvis/os/net/GeminiLiveClientTest.kt`

**Interfaces:**
- Consumes: `AudioCaptureEngine` PCM chunks.
- Produces: `GeminiLiveClient.connect(apiKey: String, model: String)`, `GeminiLiveClient.sendAudio(chunk: ByteArray)`, `onAudioReceived(data: ByteArray)`, `onToolCall(call: ToolCall)`.

- [ ] **Step 1: Write test `GeminiLiveClientTest.kt`**
Test message serialization, audio chunk wrapping in `realtime_input`, and tool call event parsing.

- [ ] **Step 2: Implement `LiveSessionModels.kt`**
Data classes matching Gemini Live API JSON/Protobuf schemas (`BidiGenerateContentClientContent`, `FunctionCall`, `FunctionResponse`).

- [ ] **Step 3: Implement `GeminiLiveClient.kt`**
OkHttp WebSocket connection with heartbeat, barge-in synchronization, and immediate `play_local_filler` interception.

- [ ] **Step 4: Run tests and commit**
```bash
git add mobile/app/src/main/java/com/jarvis/os/net/ mobile/app/src/test/
git commit -m "feat(mobile): implement GeminiLiveClient full-duplex transport"
```

---

### Task 5: Persistent Android Foreground Service

**Files:**
- Create: `mobile/app/src/main/java/com/jarvis/os/service/JarvisVoiceService.kt`
- Create: `mobile/app/src/main/java/com/jarvis/os/service/BootReceiver.kt`

**Interfaces:**
- Consumes: `AudioCaptureEngine`, `AudioPlaybackEngine`, `GeminiLiveClient`, `OverlayWindowManager`.
- Produces: System-wide ambient daemon lifecycle.

- [ ] **Step 1: Implement `JarvisVoiceService.kt`**
Start foreground service with ongoing notification, attach wake-lock, manage ambient listening loop, and control overlay states.

- [ ] **Step 2: Implement `BootReceiver.kt`**
BroadcastReceiver listening for `ACTION_BOOT_COMPLETED` to restore service on device reboot.

- [ ] **Step 3: Commit**
```bash
git add mobile/app/src/main/java/com/jarvis/os/service/
git commit -m "feat(mobile): implement JarvisVoiceService foreground daemon"
```

---

### Task 6: Siri-Style Floating Overlay (Halo Orb & Dynamic Island)

**Files:**
- Create: `mobile/app/src/main/java/com/jarvis/os/overlay/OverlayWindowManager.kt`
- Create: `mobile/app/src/main/java/com/jarvis/os/overlay/OverlayState.kt`
- Create: `mobile/app/src/main/java/com/jarvis/os/overlay/HaloOrbComposeView.kt`
- Create: `mobile/app/src/main/java/com/jarvis/os/overlay/DynamicIslandComposeView.kt`

**Interfaces:**
- Produces: `OverlayWindowManager.show()`, `OverlayWindowManager.updateState(state: OverlayState)`, `OverlayWindowManager.hide()`.

- [ ] **Step 1: Implement `OverlayState.kt`**
Define enum and UI state: `IDLE`, `LISTENING(rms)`, `THINKING(fillerText)`, `SPEAKING(waveform)`.

- [ ] **Step 2: Implement `HaloOrbComposeView.kt`**
Iridescent glowing particle shader in Jetpack Compose reacting dynamically to user voice input.

- [ ] **Step 3: Implement `DynamicIslandComposeView.kt`**
Top pill morph animation, breathing light, and 3-bar audio visualizer.

- [ ] **Step 4: Implement `OverlayWindowManager.kt`**
Manage `WindowManager.addView` using `TYPE_APPLICATION_OVERLAY`. Toggle `FLAG_NOT_TOUCHABLE` when idle, and animate smooth alpha transitions.

- [ ] **Step 5: Commit**
```bash
git add mobile/app/src/main/java/com/jarvis/os/overlay/
git commit -m "feat(mobile): implement Siri-style Halo Orb and Dynamic Island overlay"
```

---

### Task 7: QR Code Pairing & Cloud Sync Engine

**Files:**
- Create: `scripts/jarvis_pair.py`
- Modify: `bin/jarvis`
- Create: `mobile/app/src/main/java/com/jarvis/os/sync/QrPairingScanner.kt`
- Create: `mobile/app/src/main/java/com/jarvis/os/sync/CloudMemorySyncWorker.kt`
- Create: `mobile/app/src/test/java/com/jarvis/os/sync/SyncPayloadTest.kt`

**Interfaces:**
- Produces: Desktop `jarvis pair` terminal QR generator, mobile CameraX scanner, and out-of-town event-sourcing sync worker.

- [ ] **Step 1: Implement `scripts/jarvis_pair.py` & wire to `bin/jarvis pair`**
Generates ASCII terminal QR code with AES-256 encrypted configuration (project `jarvis-os-508612`, channel ID, auth token).

- [ ] **Step 2: Implement `QrPairingScanner.kt`**
CameraX barcode scanner to capture and store pairing credentials in `EncryptedSharedPreferences`.

- [ ] **Step 3: Implement `CloudMemorySyncWorker.kt`**
Firestore / GCS delta pusher and receiver for out-of-town memory synchronization.

- [ ] **Step 4: Commit**
```bash
git add scripts/jarvis_pair.py bin/jarvis mobile/app/src/main/java/com/jarvis/os/sync/
git commit -m "feat: implement QR code pairing and cloud memory sync worker"
```

---

### Task 8: MainActivity, APK Assembly & Verification

**Files:**
- Create: `mobile/app/src/main/java/com/jarvis/os/ui/MainActivity.kt`
- Create: `mobile/app/src/main/res/values/themes.xml`
- Create: `mobile/app/src/main/res/values/strings.xml`
- Create: `mobile/Makefile`

**Interfaces:**
- Produces: Complete, installable `jarvis-mobile-release.apk` (or debug APK) verified via build automation.

- [ ] **Step 1: Implement `MainActivity.kt`**
UI for granting `RECORD_AUDIO` and `SYSTEM_ALERT_WINDOW` permissions, launching QR scanner, and service toggle.

- [ ] **Step 2: Add resources and theme definitions**

- [ ] **Step 3: Build debug APK using Gradle**
Run: `cd mobile && ./gradlew assembleDebug`
Expected: `app-debug.apk` generated.

- [ ] **Step 4: Commit and finalize**
```bash
git add mobile/
git commit -m "feat(mobile): finalize MainActivity, themes, and APK build targets"
```
