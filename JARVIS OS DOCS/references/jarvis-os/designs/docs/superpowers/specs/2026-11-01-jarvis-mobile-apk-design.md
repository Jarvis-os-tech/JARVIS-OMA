# Architectural Specification: JARVIS Mobile Android Client & Cloud Sync

**Date:** 2026-11-01  
**Status:** Approved  
**Author:** Antigravity & Pair Developer  
**Scope:** Android APK, Foreground Voice Service, Siri-Style Dynamic Overlay, Multi-Device Memory Sync

---

## 1. Executive Summary

This specification defines the architecture, protocols, and implementation plan for **JARVIS Mobile**, a voice-first native Android companion app (APK) for JARVIS OS.

JARVIS Mobile mirrors the desktop JARVIS OS experience:
1. **Background Ambient Engine:** Runs persistently via an Android `ForegroundService` with full-duplex speech-to-speech Gemini Live streaming.
2. **Siri-Style Halo Orb & Dynamic Island Overlay:** An ambient, non-intrusive floating visualizer rendered via `WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY`. It remains **100% invisible with zero touch-interception when idle**, fading in only while the user speaks or JARVIS is replying.
3. **Cognitive Local Filler Execution:** Implements the zero-latency local filler reflex ("humm", "let's see...") with a 50ms Raised-Cosine ducking cross-fader to eliminate audio pops and dead-air latency.
4. **QR Code Pairing & Sovereign Cloud Memory Sync:** Quick one-touch QR pairing with desktop JARVIS, and asynchronous event-sourced cloud ledger synchronization via Google Cloud (`jarvis-os-508612` Firestore / GCS) ensuring memories, facts, and tasks captured while away from home synchronize seamlessly when the laptop wakes up.

---

## 2. System Architecture

```
+-----------------------------------------------------------------------------------+
|                                  JARVIS Mobile (APK)                              |
|                                                                                   |
|  +---------------------------+   +---------------------------------------------+  |
|  |     MainActivity (UI)     |   |          JarvisVoiceService                 |  |
|  |  - Setup & Permissions    |   |  - FOREGROUND_SERVICE_TYPE_MICROPHONE       |  |
|  |  - QR Code Scanner        |   |  - Persistent lifecycle & wake triggers     |  |
|  |  - Diagnostics & Logs     |   +----------------------+----------------------+  |
|  +---------------------------+                          |                         |
|                                                         v                         |
|  +-----------------------------------------------------------------------------+  |
|  |                              Audio Engine                                   |  |
|  |  - AudioRecord: 16 kHz Mono PCM16 mic capture                               |  |
|  |  - Silero VAD (ONNX): Local speech endpointing & turn segmentation          |  |
|  |  - AudioTrack: 24 kHz Mono PCM16 playback                                   |  |
|  |  - LocalFillerMixer: 50ms Raised-Cosine crossfade & precharged RAM cache    |  |
|  +----------------------+-------------------------------+----------------------+  |
|                         |                               |                         |
|                         v                               v                         |
|  +-------------------------------+   +-----------------------------------------+  |
|  |       Overlay WindowManager   |   |           Network & Transport           |  |
|  |  - Siri-Style Halo Orb        |   |  - Gemini Live Client (OkHttp WSS)      |  |
|  |  - Dynamic Island Pill (HUD)  |   |  - Multi-Device Memory Sync Engine      |  |
|  |  - FLAG_NOT_TOUCHABLE (Idle)  |   |    (Firestore / Cloud Storage Delta)    |  |
|  +-------------------------------+   +--------------------+--------------------+  |
|                                                           |                       |
+-----------------------------------------------------------|-----------------------+
                                                            |
                       +------------------------------------+--------------------+
                       |                                                         |
                       v                                                         v
    +------------------------------------+             +------------------------------------+
    |    Gemini Live API (Cloud WSS)     |             | Google Cloud Sync (jarvis-os-508612)|
    |    Bidirectional Audio Stream      |             | Firestore / GCS Event Mailbox      |
    +------------------------------------+             +------------------+-----------------+
                                                                          |
                                                                          v
                                                       +------------------------------------+
                                                       |     JARVIS Desktop (Laptop at Home)|
                                                       |     - SQLite WAL Knowledge Ledger  |
                                                       |     - Obsidian Vault Continuous Sync|
                                                       +------------------------------------+
```

---

## 3. Detailed Component Design

### 3.1 Background Voice Service (`JarvisVoiceService`)
- Declared as an Android Foreground Service with `foregroundServiceType="microphone"`.
- Displays a low-priority, ongoing notification ("JARVIS Standby").
- Lifecycle management:
  - Auto-start on boot (`RECEIVE_BOOT_COMPLETED`).
  - Battery optimization whitelist guidance (`REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`).
  - Graceful reconnection on network shifts (Wi-Fi <-> Cellular).

### 3.2 Audio & Cognitive Reflex Pipeline
- **Input Stream (`AudioCaptureEngine`):**
  - Captures 16 kHz, 16-bit mono PCM frames (640 bytes = 20 ms).
  - Integrates Silero VAD (ONNX Runtime Mobile) to evaluate speech probability every 20ms frame.
- **Output Stream (`AudioPlaybackEngine`):**
  - Plays 24 kHz, 16-bit mono PCM audio (960 bytes = 20 ms) directly through `AudioTrack` in low-latency stream mode.
- **Local Filler Ducking Mixer (`LocalFillerMixer`):**
  - Matches desktop implementation in `audio/downstream.py`.
  - When Gemini Live emits `play_local_filler(context_type)`:
    - Pre-cached PCM snippet ("humm", "let's see...") flashes immediately to `AudioTrack`.
  - When Gemini's first response packets arrive:
    - Applies a 50 ms Raised-Cosine crossfade over $N = 1,200$ samples:
      $$\alpha(i) = \frac{1}{2}\left(1 + \cos\left(\frac{\pi (i + 1)}{N}\right)\right), \quad \beta(i) = 1 - \alpha(i)$$
      $$\text{sample}_{\text{out}} = \text{clip}\left(\text{round}(s_{\text{filler}} \cdot \alpha + s_{\text{gemini}} \cdot \beta), -32768, 32767\right)$$
    - Eliminates audio pops, phase clicks, and DC jumps.

### 3.3 Siri-Style Overlay System (`OverlayWindowManager`)
- **Permissions:** Requires `android.permission.SYSTEM_ALERT_WINDOW`.
- **States & Transitions:**
  - `STATE_IDLE`:
    - Layout: `View.GONE` / 0% alpha.
    - Flags: `FLAG_NOT_FOCUSABLE | FLAG_NOT_TOUCHABLE | FLAG_LAYOUT_NO_LIMITS`.
    - Touch behavior: 100% click-through. The user can interact with any foreground app unimpeded.
  - `STATE_LISTENING` (Triggered by voice or tap):
    - View: Iridescent circular **Halo Orb** floating near the bottom or top of the screen.
    - Animation: Dynamic glow responding to mic RMS amplitude.
  - `STATE_THINKING`:
    - View: The Orb smoothly morphs into a compact **Dynamic Island pill** docked at the screen top.
    - Animation: Subtle breathing pulse while local filler plays.
  - `STATE_SPEAKING`:
    - View: Dynamic Island expands slightly to show an animated 3-bar equalizer and 1-line real-time transcript preview.
  - `STATE_GRACE_WINDOW`:
    - After Gemini turn completes, overlay remains for 1.5 seconds to permit conversational follow-ups.
    - If no speech occurs within 1.5s, it smoothly fades out (250ms alpha transition) back to `STATE_IDLE`.

### 3.4 Multi-Device Pairing & Sovereign Cloud Sync

#### A. Initial QR Pairing
1. On Desktop: Run `jarvis pair` (or open the Orbit QuickShell UI).
2. Desktop generates a signed JSON pairing payload containing:
   ```json
   {
     "project_id": "jarvis-os-508612",
     "channel_id": "user_primary_ledger",
     "encryption_key": "<device_shared_secret>",
     "lan_endpoint": "192.168.1.50:8765"
   }
   ```
3. On Mobile: The user scans the QR code via `MainActivity` camera scanner.
4. Mobile validates the signature and stores the encrypted keys in Android EncryptedSharedPreferences.

#### B. Asynchronous Remote Sync (Out-of-Town Protocol)
- **When user is away from home:**
  - The phone creates memories, facts, and conversation transcripts locally in Room SQLite.
  - Pushes atomic sync delta events to Google Cloud (`jarvis-os-508612` Firestore / GCS):
    ```json
    {
      "turn_id": "urn:uuid:7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "timestamp": "2026-11-01T10:45:00Z",
      "device": "mobile",
      "user_text": "Remember that our project review is Friday at 3 PM",
      "assistant_text": "Understood, noted project review for Friday at 3 PM.",
      "extracted_facts": ["Project review is Friday at 3 PM"],
      "hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    }
    ```
- **When laptop wakes up at home:**
  - The desktop `jarvis_memory` bridge detects the new remote turns via Firestore stream or GCS poll.
  - Appends them to the continuous history file (`Conversations/YYYY-MM-DD.md`).
  - Ingests facts into `knowledge.db` and triggers embedding generation.
  - Deduplicates via entry hash to ensure no collisions.

---

## 4. Security & Privacy Boundary

1. **Local Audio:** Microphone audio is never stored to cloud disks unencrypted; it is streamed strictly ephemeral to Gemini Live and discarded.
2. **End-to-End Encryption:** Remote memory events synced via GCS/Firestore use AES-256-GCM encrypted payloads using the device secret exchanged during QR pairing.
3. **Overlay Isolation:** The overlay window uses `FLAG_SECURE` where needed and never captures or records touch events outside of its own HUD bounding box.

---

## 5. Implementation Roadmap

- **Phase 1 (Android Project Scaffold & Build):** Setup Gradle Kotlin project, AndroidManifest, dependencies (OkHttp, Compose, ONNX runtime, CameraX for QR).
- **Phase 2 (Audio & Gemini Live Streaming):** Implement `AudioCaptureEngine`, `AudioPlaybackEngine`, `SileroVadDetector`, and `LocalFillerMixer`.
- **Phase 3 (Siri-Style Overlay & Dynamic Island):** Implement `OverlayWindowManager`, Compose Canvas shaders, state machine transitions, and touch filtering.
- **Phase 4 (QR Pairing & Cloud Sync):** Implement `jarvis pair` desktop generator, mobile camera QR reader, and Firestore/GCS async delta sync worker.
- **Phase 5 (Verification & APK Build):** Compile debug/release APK, run end-to-end latency benchmarks and memory sync tests.
