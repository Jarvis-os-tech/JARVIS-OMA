# Design Spec: JARVIS Mobile UI/UX Redesign

**Date**: 2026-11-01  
**Project**: JARVIS Mobile Android Client (`com.jarvis.os`)  
**Status**: Approved (Transitioning to Implementation Plan)  

---

## 1. Executive Summary & Background
JARVIS Mobile is a native Android application serving as the handheld companion to the JARVIS OS ecosystem. It provides continuous low-power "Hey Jarvis" wake-word detection, real-time Gemini Live / Gemini Voice bidirectional interaction, desktop pairing, cloud memory synchronization, accessibility-based voice automation, and over-the-air updates.

While previous updates (v1.2.2 and v1.2.3) stabilized the low-power audio pipeline (zero-allocation VAD, gated Vosk neural inference, hardware-backed AEC), the app interface (`MainActivity.kt`) remained an unstyled, single vertical column of text buttons and raw status rows.

This document specifies a complete redesign of the user interface and user experience, introducing a **Cybernetic Obsidian** aesthetic, an interactive **Bottom Navigation Architecture**, a living **Arc Reactor Voice Core**, a **Device Matrix Hub**, and a clean **Settings & Intelligence Vault**.

---

## 2. Visual Design System: *Cybernetic Obsidian*

### 2.1 Color Palette & Tokens
* **Background Deep Obsidian**: `Color(0xFF080A0F)`
* **Surface Container / Glass Panels**: `Color(0xFF111520)` with 60% opacity for frosted glass effects
* **Border Lines**: `Color(0xFF1F283C)` with accent highlights `Color(0x3300F2FE)`
* **Primary Neon Accent (Electric Cyan)**: `Color(0xFF00F2FE)`
* **Secondary Gradient (Arc Reactor Blue)**: `Color(0xFF0077FE)`
* **Intelligence Accent (Neural Violet)**: `Color(0xFF9B51E0)`
* **Status Ready / Online (Matrix Green)**: `Color(0xFF00E676)`
* **Status Warning / Paused (Standby Amber)**: `Color(0xFFFFB300)`
* **Error / Disconnected**: `Color(0xFFFF5252)`
* **Text Primary**: `Color(0xFFFFFFFF)`
* **Text Secondary**: `Color(0xFF8E9BAE)`
* **Text Accent**: `Color(0xFF7EE7F8)`

### 2.2 Styling & Surfaces
* **Corner Radius**:
  * Large Panels: `RoundedCornerShape(20.dp)`
  * Interactive Buttons / Cards: `RoundedCornerShape(14.dp)`
  * Badges & Indicators: `RoundedCornerShape(32.dp)` (Pill)
* **Glassmorphism**: Border strokes (`1.dp` solid or gradient) combined with deep translucent dark card fills, creating elevation without material shadow artifacts.

---

## 3. Information Architecture & Navigation

The application replaces the single-scroll layout with a 3-tab Bottom Navigation architecture:

```
┌────────────────────────────────────────────────────────┐
│  [JARVIS OS] ⚡ v1.2.3                [● STANDBY ACTIVE]│ Top Telemetry Bar
├────────────────────────────────────────────────────────┤
│                                                        │
│                                                        │
│                 TAB CONTENT CONTAINER                  │
│                                                        │
│   Tab 0: ASSISTANT   |  Tab 1: DEVICES  |  Tab 2: SETTINGS
│   (Voice Core)       |  (PC Link & Perms)│ (Keys & Update)  │
│                                                        │
├────────────────────────────────────────────────────────┤
│    [ 🎙️ Assistant ]     [ 💻 Devices ]     [ ⚙️ Settings ] │ Bottom Glass Dock
└────────────────────────────────────────────────────────┘
```

### 3.1 Persistent Top Telemetry Bar
Visible across all tabs:
* Left: JARVIS OS wordmark with cyber glow accent and version pill (`v1.2.3`).
* Right: Dynamic Standby Status Chip:
  * Green pulsing dot: `STANDBY ACTIVE` (when `JarvisVoiceService` is running).
  * Amber static dot: `PAUSED` (when service is off or microphone is paused).

---

## 4. Screen Specifications

### 4.1 Tab 1: Assistant Screen (`AssistantScreen.kt`)
The primary voice interaction hub designed to feel like an active AI core.

1. **Central Arc Reactor Visualizer (`ArcReactorVisualizer.kt`)**:
   * Multi-ring cybernetic core rendering via Jetpack Compose `Canvas`.
   * **Idle/Standby**: Subtle cyan/blue breathing pulse (scale 0.95 to 1.05) with outer orbital tick marks.
   * **Listening**: Dynamic reactive dilation driven by mic RMS amplitude; bright electric cyan bloom.
   * **Thinking**: Concentric rotating rings with shimmering neural violet gradient.
   * **Speaking**: Audio soundwave oscillations mapped to speech output energy.
2. **Status & Execution Target Header**:
   * Text readouts for voice status (`voice_status`) and execution target (`device_execution_status`).
   * Chip indicators: `Phone Execution` vs `PC Execution`.
3. **Live Transcript / Activity Feed Card**:
   * Displays the most recent command and assistant response in a sleek frosted panel:
     * User prompt quote icon and text.
     * JARVIS response quote and execution status.
     * Empty state prompt: *"Tap mic or say 'Hey Jarvis' to ask anything..."*
4. **Voice Action Dock (Bottom)**:
   * **Central Mic Button**: Prominent circular button with cyan glow. Tap to trigger immediate listening turn without requiring the wake word.
   * **Standby Toggle Switch**: Toggle "Hey Jarvis" background listening on/off.
   * **Execution Toggle**: Quick switch between `Auto`, `Force Phone`, `Force PC`.

---

### 4.2 Tab 2: Devices & Actions Screen (`DevicesScreen.kt`)
Hardware integration, desktop bridging, and Android system permissions.

1. **Desktop PC Connection Matrix**:
   * **Status Banner**:
     * If Paired: Shows desktop name/ID, IP address, connection status, and last synced memory timestamp.
     * If Not Paired: Explanatory card highlighting PC capabilities (shared execution, clipboard, cloud sync).
   * **Actions**:
     * `Scan QR Code`: Opens camera scanner modal for instant pairing.
     * `Manual Payload`: Dialog for pasting JSON payload.
     * `Unpair / Reset PC Link`: Clean disconnect option.
2. **System Permissions & Integrations Hub**:
   Each permission is rendered as an interactive status row with clear visual feedback:
   * **Audio / Microphone**: Wake-word & speech input (Granted / Denied).
   * **Floating Siri HUD**: Overlay window permission (`Settings.ACTION_MANAGE_OVERLAY_PERMISSION`).
   * **Voice App Navigation**: Accessibility Service (`Settings.ACTION_ACCESSIBILITY_SETTINGS`) to allow JARVIS to navigate apps and tap elements.
   * **System Settings**: Write Settings permission (`Settings.ACTION_MANAGE_WRITE_SETTINGS`) for brightness and volume control.
   * **Battery Whitelist**: Request ignoring battery optimization to prevent OEM task killers.
3. **Quick Action Triggers**:
   * `Sync Cloud Memory Now`: Manually dispatches `CloudMemorySyncWorker`.
   * `Restart Voice Engine`: Soft-restart for audio capture and wake-word daemon.

---

### 4.3 Tab 3: Settings & Intelligence Screen (`SettingsScreen.kt`)
Configuration, API credentials, sensitivity calibration, and maintenance.

1. **AI Credentials & Vault**:
   * Display of current Gemini API key state (Obfuscated `••••••••AIzaSy...`).
   * Source badge: `PC Linked` or `Personal API Key`.
   * `Configure Keys` button opening the secure setup dialog.
2. **Voice Tuning & Standby Preferences**:
   * Wake-word detection sensitivity preset: `Normal` / `High Sensitivity (Quiet)` / `Low Sensitivity (Noisy)`.
   * Silence auto-sleep timeout indicator (15s default).
3. **OTA Mobile Updates (`MobileUpdater`)**:
   * Current app version: `v1.2.3` (Release channel: `main`).
   * One-tap `Check for Updates` button.
   * Animated download/verification progress indicator and status banner.
4. **System Diagnostics**:
   * Audio configuration telemetry: Sample rate (`16,000 Hz`), Channels (`Mono`), Echo Cancellation (`AEC Active`).
   * Vosk Model status: Offline Kaldi model loaded in memory.

---

## 5. Architectural Implementation Plan

### 5.1 File & Package Structure
```
mobile/app/src/main/java/com/jarvis/os/ui/
├── MainActivity.kt                # Refactored Activity host & Tab controller
├── theme/
│   ├── Color.kt                   # Cybernetic Obsidian color palette
│   └── Theme.kt                   # JARVIS dark theme provider
├── components/
│   ├── CyberBottomNav.kt          # Frosted glass bottom navigation bar
│   ├── TopTelemetryBar.kt         # Persistent top header with status chip
│   ├── ArcReactorVisualizer.kt    # Responsive Compose Canvas arc reactor
│   └── GlassCard.kt               # Reusable frosted container composable
├── screens/
│   ├── AssistantScreen.kt         # Tab 0: Voice core & live response
│   ├── DevicesScreen.kt           # Tab 1: PC pairing & permissions hub
│   └── SettingsScreen.kt          # Tab 2: Keys vault, update, tuning
├── QrScannerDialog.kt             # Existing Camera QR scanner (preserved)
└── ApiKeySetupDialog.kt           # Existing API Key setup modal (preserved)
```

### 5.2 State Management & Service Linkage
* `MainActivity` observes `SharedPreferences` ("jarvis_prefs") for:
  * `voice_status`: Live assistant status string.
  * `device_execution_status`: Phone / PC target routing.
  * `service_running` / `is_standby`: Background daemon state.
* Shared state passed down cleanly to composable screens.
* Preserves all intent-based triggers:
  * `com.jarvis.os.action.START`
  * `com.jarvis.os.action.STOP`
  * `com.jarvis.os.action.SYNC_MEMORY`

---

## 6. Non-Breaking Guarantees & Verification Plan

1. **Zero Impact on Audio Pipeline**:
   * The low-power standby gating, AEC capture, and `JarvisVoiceService` service lifecycle remain completely intact.
2. **Pairing & Credentials Compatibility**:
   * `QrPairingScanner` and `ApiCredentials` functions and schemas are untouched.
3. **Verification Steps**:
   * Unit tests: `./gradlew testDebugUnitTest` must pass with 100% success.
   * Build verification: `./gradlew assembleDebug` must compile cleanly without errors.
   * Runtime verification on connected device (`10.167.177.68:5555`):
     * Verify bottom navigation switching between Assistant, Devices, and Settings tabs.
     * Verify Arc Reactor rendering and animation.
     * Verify permission deep links open target Android settings screens.
     * Verify Tap-to-Talk and Standby toggle control the service as expected.
