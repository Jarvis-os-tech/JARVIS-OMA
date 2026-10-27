import QtQuick
import Quickshell
import Quickshell.Io
import "ReactiveModel.js" as Reactive

// Tracks live JARVIS Continuous Voice Daemon and AI Coding Agents.
// Bridges real-time speech states, mute controls, weather telemetry, and tool approvals.
Item {
  id: root

  // ── JARVIS Real-Time Daemon State ───────────────────────────────────────────
  property string voiceState: "offline" // idle, connecting, listening, thinking, speaking, processing, standby, error, offline
  property string jarvisActivity: "Connecting to JARVIS"
  property bool jarvisMuted: false
  property bool jarvisStandby: false
  property string jarvisModel: ""

  property real microphoneRms: 0
  property bool levelAvailable: false
  property int activeJobs: 0
  property string visionMode: "off"
  property string controlError: ""
  readonly property string displayState: Reactive.state(voiceState, jarvisMuted, jarvisStandby)
  readonly property string stateLabel: Reactive.label(displayState)
  readonly property color stateTone: Reactive.tone(displayState)
  readonly property bool connected: voiceState !== "offline" && voiceState !== "connecting"
  readonly property bool isJarvisActive: ["listening", "speaking", "thinking", "processing"].indexOf(displayState) !== -1
  readonly property real audioLevel: Reactive.audioLevel(microphoneRms, levelAvailable, jarvisMuted)
  readonly property bool controlPending: muteProc.running || interruptProc.running

  // Live subscription process to JARVIS daemon
  Process {
    id: jarvisSubProc
    command: ["/home/g0pi/Projects/JARVIS-OMA/.venv/bin/python",
              "/home/g0pi/Projects/JARVIS-OMA/scripts/island_status.py"]
    running: true
    onExited: {
      root.voiceState = "offline"
      root.jarvisActivity = "JARVIS is offline"
      root.microphoneRms = 0
      root.levelAvailable = false
      reconnectTimer.restart()
    }
    stdout: SplitParser {
      onRead: function(line) {
        try {
          var payload = JSON.parse(line || "{}");
          if (payload.state !== undefined) root.voiceState = String(payload.state).toLowerCase();
          if (payload.activity !== undefined) root.jarvisActivity = String(payload.activity);
          if (payload.muted !== undefined) root.jarvisMuted = Boolean(payload.muted);
          if (payload.standby !== undefined) root.jarvisStandby = Boolean(payload.standby);
          if (payload.model !== undefined) root.jarvisModel = String(payload.model);
          root.microphoneRms = Reactive.number(payload.microphone_rms, 0);
          root.levelAvailable = payload.level_available === true;
          root.activeJobs = Math.max(0, Reactive.number(payload.active_jobs, 0));
          root.visionMode = String(payload.vision_mode || "off");
        } catch(e) {}
      }
    }
  }

  Timer {
    id: reconnectTimer
    interval: 1500
    onTriggered: jarvisSubProc.running = true
  }

  // Mute control
  Process {
    id: muteProc
    command: ["/home/g0pi/Projects/JARVIS-OMA/.venv/bin/python",
              "/home/g0pi/Projects/JARVIS-OMA/scripts/jarvisctl.py", "toggle"]
    onExited: function(code) { root.controlError = code === 0 ? "" : "Could not change microphone state" }
  }

  function toggleMute() {
    if (!root.connected || root.controlPending) return;
    root.controlError = "";
    muteProc.running = true;
  }

  // Interrupt active speech
  Process {
    id: interruptProc
    command: ["/home/g0pi/Projects/JARVIS-OMA/.venv/bin/python",
              "/home/g0pi/Projects/JARVIS-OMA/scripts/jarvisctl.py", "interrupt"]
    onExited: function(code) { root.controlError = code === 0 ? "" : "Could not interrupt playback" }
  }

  function interruptSpeech() {
    if (!root.connected || root.controlPending) return;
    root.controlError = "";
    interruptProc.running = true;
  }

  // ── Live Weather Integration ────────────────────────────────────────────────
  property string tempC: "--°"
  property string weatherCondition: "Weather unavailable"
  property string weatherHumidity: "--"
  property string weatherWind: "--"
  property string weatherGlyph: "󰖑"

  function updateWeatherGlyph(desc) {
    var d = String(desc || "").toLowerCase();
    if (d.indexOf("sun") !== -1 || d.indexOf("clear") !== -1) return "󰖙";
    if (d.indexOf("haze") !== -1 || d.indexOf("smoke") !== -1 || d.indexOf("fog") !== -1 || d.indexOf("mist") !== -1) return "󰖑";
    if (d.indexOf("rain") !== -1 || d.indexOf("drizzle") !== -1 || d.indexOf("shower") !== -1) return "󰖗";
    if (d.indexOf("thunder") !== -1 || d.indexOf("storm") !== -1) return "󰖓";
    if (d.indexOf("snow") !== -1 || d.indexOf("ice") !== -1) return "󰖘";
    return "󰖐";
  }

  Process {
    id: weatherProc
    command: ["sh", "-c", "curl -fsS --max-time 4 'https://wttr.in/?format=j1' 2>/dev/null || true"]
    running: true
    stdout: StdioCollector {
      onStreamFinished: {
        try {
          var data = JSON.parse(text || "{}");
          var cond = data.current_condition && data.current_condition[0];
          if (cond) {
            if (cond.temp_C !== undefined) root.tempC = cond.temp_C + "°C";
            if (cond.weatherDesc && cond.weatherDesc[0]) {
              root.weatherCondition = cond.weatherDesc[0].value;
              root.weatherGlyph = root.updateWeatherGlyph(root.weatherCondition);
            }
            if (cond.humidity !== undefined) root.weatherHumidity = cond.humidity + "%";
            if (cond.windspeedKmph !== undefined) root.weatherWind = cond.windspeedKmph + " km/h";
          }
        } catch(e) {}
      }
    }
  }

  Timer {
    interval: 300000 // Refresh weather every 5 minutes
    running: true
    repeat: true
    onTriggered: {
      if (!weatherProc.running) weatherProc.running = true;
    }
  }

  function refreshWeather() {
    if (!weatherProc.running) weatherProc.running = true;
  }

  // ── Coding Agent Fleet & Tool Approvals ──────────────────────────────────────
  property string agentName: "Antigravity"
  property string stateName: voiceState !== "idle" ? voiceState : (hasPendingApproval ? "approval" : "idle")
  property string taskTitle: "JARVIS OS Integration"
  property string statusText: jarvisActivity
  property int addedLines: 120
  property int removedLines: 14

  property bool hasPendingApproval: false
  property string pendingToolName: ""
  property string pendingToolTarget: ""
  property string pendingRequestId: ""

  readonly property string home: Quickshell.env("HOME") || ""
  readonly property string hookFile: home + "/.local/state/jarvis/agent_hook.json"

  function allowPending() {
    hasPendingApproval = false;
    statusText = "Executing approved tool...";
  }

  function denyPending() {
    hasPendingApproval = false;
    statusText = "Tool execution rejected";
  }

  FileView {
    id: hookWatcher
    path: root.hookFile
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    Component.onCompleted: reload()
    onLoaded: {
      try {
        var data = JSON.parse(text());
        if (data.event === "approval_request") {
          root.hasPendingApproval = true;
          root.pendingToolName = data.tool || "Bash Command";
          root.pendingToolTarget = data.target || "";
        } else if (data.event === "idle") {
          root.hasPendingApproval = false;
        }
      } catch(e) {}
    }
  }

  // Local, measured telemetry. Unknown readings stay unknown.
  property real cpuUsage: -1
  property real ramUsage: -1
  property var previousCpu: null

  FileView {
    id: cpuFile
    path: "/proc/stat"
    printErrors: false
    onLoaded: {
      var current = Reactive.cpuSample(text())
      root.cpuUsage = Reactive.cpuUsage(root.previousCpu, current)
      root.previousCpu = current
    }
    onLoadFailed: { root.cpuUsage = -1; root.previousCpu = null }
  }
  FileView {
    id: ramFile
    path: "/proc/meminfo"
    printErrors: false
    onLoaded: root.ramUsage = Reactive.memoryUsage(text())
    onLoadFailed: root.ramUsage = -1
  }
  Timer {
    interval: 2000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: { cpuFile.reload(); ramFile.reload() }
  }
}
