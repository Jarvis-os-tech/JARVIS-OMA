import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

PanelWindow {
    id: rootWin
    property string currentTheme: "jarvis"
    readonly property bool isJarvisTheme: currentTheme.trim().toLowerCase() === "jarvis"
    visible: isJarvisTheme
    WlrLayershell.namespace: "jarvis-os-shell"
    WlrLayershell.layer: WlrLayer.Bottom // Sits directly on desktop beneath application windows
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    exclusionMode: ExclusionMode.Ignore
    color: "#040810"

    anchors {
        top: true
        bottom: true
        left: true
        right: true
    }

    property string voiceState: "idle"
    property bool standby: false
    property bool muted: false
    property string activityLabel: "Ready"
    property real micLevel: 0.0
    property real cpuPercent: 18.0
    property real ramPercent: 52.0
    property real gpuPercent: 32.0
    // Watch Active System Theme
    FileView {
        id: themeWatcher
        path: Quickshell.env("HOME") + "/.local/state/omarchy/current/theme.name"
        watchChanges: true
        onFileChanged: themeWatcher.reload()
        onLoaded: {
            rootWin.currentTheme = String(text() || "").trim().toLowerCase();
        }
    }

    // 1. Live Voice State Polling (every 200ms)
    Process {
        id: stateProc
        command: ["sh", "-c", "cat ${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/jarvis/state.json 2>/dev/null || echo '{}'"]
        running: false
        stdout: SplitParser {
            onRead: function(line) {
                try {
                    var payload = JSON.parse(line || "{}");
                    if (payload.state !== undefined)
                        rootWin.voiceState = String(payload.state || "offline").toLowerCase();
                    if (payload.activity !== undefined)
                        rootWin.activityLabel = String(payload.activity || (rootWin.voiceState === "idle" ? "Online" : rootWin.voiceState));
                    if (payload.standby !== undefined)
                        rootWin.standby = Boolean(payload.standby);
                    if (payload.muted !== undefined)
                        rootWin.muted = Boolean(payload.muted);
                    if (payload.microphone_rms !== undefined) {
                        var rms = Number(payload.microphone_rms) || 0.0;
                        rootWin.micLevel = Math.min(1.0, rms * 25.0);
                    }
                } catch (e) {}
            }
        }
    }

    Timer {
        interval: 200
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: {
            if (!stateProc.running) stateProc.running = true;
        }
    }

    // 2. Real-time Telemetry Polling (every 1.5s)
    Process {
        id: telemetryProc
        command: ["/home/g0pi/.local/bin/jarvis-sysinfo"]
        running: false
        stdout: SplitParser {
            onRead: function(line) {
                try {
                    var data = JSON.parse(line || "{}");
                    if (data.cpu !== undefined) rootWin.cpuPercent = Number(data.cpu) || 0.0;
                    if (data.ram !== undefined) rootWin.ramPercent = Number(data.ram) || 0.0;
                } catch (e) {}
            }
        }
    }

    Timer {
        interval: 1500
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: {
            if (!telemetryProc.running) telemetryProc.running = true;
        }
    }

    // Procedural Cybernetic Atmosphere (No static wallpaper)
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#02050b" }
            GradientStop { position: 0.5; color: "#040914" }
            GradientStop { position: 1.0; color: "#010307" }
        }
    }

    // Holographic Core Ambient Radial Glow
    Canvas {
        anchors.fill: parent
        onPaint: {
            var ctx = getContext("2d");
            ctx.reset();
            var cx = width / 2;
            var cy = height * 0.32;
            var grad = ctx.createRadialGradient(cx, cy, 20, cx, cy, 420);
            grad.addColorStop(0, "rgba(0, 229, 255, 0.12)");
            grad.addColorStop(0.5, "rgba(0, 140, 255, 0.06)");
            grad.addColorStop(1, "rgba(0, 0, 0, 0)");
            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.arc(cx, cy, 420, 0, Math.PI * 2);
            ctx.fill();

            // Perspective Cyber Floor Pedestal (Bottom Center)
            var floorY = height - 52;
            ctx.strokeStyle = "rgba(0, 229, 255, 0.3)";
            ctx.lineWidth = 1.2;
            for (var r = 1; r <= 3; r++) {
                ctx.beginPath();
                ctx.ellipse(cx - r * 90, floorY - r * 10, r * 180, r * 20);
                ctx.stroke();
            }

            // Perspective grid rays
            ctx.strokeStyle = "rgba(0, 229, 255, 0.08)";
            ctx.lineWidth = 0.8;
            for (var a = -4; a <= 4; a++) {
                ctx.beginPath();
                ctx.moveTo(cx + a * 50, floorY - 30);
                ctx.lineTo(cx + a * 140, height);
                ctx.stroke();
            }
        }
    }

    // -------------------------------------------------------------
    // Main UI HUD Layout
    // -------------------------------------------------------------
    Item {
        id: mainContainer
        anchors.fill: parent
        anchors.margins: 16

        // 1. Top Status Bar
        TopBar {
            id: topBar
            anchors.top: parent.top
            anchors.topMargin: 4
            anchors.left: parent.left
            anchors.right: parent.right
            voiceState: rootWin.voiceState
            muted: rootWin.muted
        }

        // 2. Far Left Navigation Rail
        LeftNav {
            id: leftNav
            anchors.left: parent.left
            anchors.top: topBar.bottom
            anchors.topMargin: 12
            anchors.bottom: bottomRow.top
            anchors.bottomMargin: 12
            width: 124
        }

        // 3. Left Widgets Column
        Column {
            id: leftCol
            anchors.left: leftNav.right
            anchors.leftMargin: 12
            anchors.top: topBar.bottom
            anchors.topMargin: 12
            spacing: 10
            width: 310

            SystemOverview {
                width: parent.width
                cpuPercent: rootWin.cpuPercent
                ramPercent: rootWin.ramPercent
                gpuPercent: rootWin.gpuPercent
            }

            AssistantCard {
                width: parent.width
            }

            QuickActions {
                width: parent.width
            }
        }

        // 4. Center Stage (Arc Reactor Core + Acoustic Waveform + Pedestal)
        Item {
            id: centerCol
            anchors.left: leftCol.right
            anchors.right: rightCol.left
            anchors.top: topBar.bottom
            anchors.bottom: bottomRow.top
            anchors.margins: 12

            // Arc Reactor Core (Top Center)
            ArcReactorCore {
                id: arcCore
                anchors.top: parent.top
                anchors.topMargin: 8
                anchors.horizontalCenter: parent.horizontalCenter
                voiceState: rootWin.voiceState
                muted: rootWin.muted
                energy: rootWin.micLevel
                width: 250
                height: 250
            }

            // Listening Status Pill (Middle)
            Rectangle {
                id: listenPill
                anchors.top: arcCore.bottom
                anchors.topMargin: 10
                anchors.horizontalCenter: parent.horizontalCenter
                width: 160
                height: 32
                radius: 16
                color: Qt.rgba(0.02, 0.05, 0.1, 0.8)
                border.color: rootWin.muted ? "#ff3b5c" : "#00e5ff"
                border.width: 1.2

                Row {
                    anchors.centerIn: parent
                    spacing: 6
                    Text {
                        text: rootWin.muted ? "󰍭" : "🎙️"
                        font.pixelSize: 13
                    }
                    Text {
                        text: rootWin.muted ? "Muted"
                            : rootWin.voiceState === "speaking" ? "Speaking..."
                            : rootWin.voiceState === "thinking" ? "Thinking..."
                            : rootWin.voiceState === "listening" ? "Listening..."
                            : "Online..."
                        color: rootWin.muted ? "#ff8da1" : "#00e5ff"
                        font.family: "JetBrainsMono Nerd Font, monospace"
                        font.pixelSize: 11
                        font.weight: Font.Bold
                    }
                }
            }

            // Subtitle hint
            Text {
                anchors.top: listenPill.bottom
                anchors.topMargin: 4
                anchors.horizontalCenter: parent.horizontalCenter
                text: rootWin.muted ? "Double-click to activate voice" : "\"Listening for your commands...\""
                color: "#4f7285"
                font.family: "Inter, sans-serif"
                font.pixelSize: 9
                font.italic: true
            }

            // Live Cyan Acoustic Waveform Visualizer
            AcousticWaveform {
                id: liveWave
                anchors.top: listenPill.bottom
                anchors.topMargin: 20
                anchors.horizontalCenter: parent.horizontalCenter
                voiceState: rootWin.voiceState
                audioLevel: rootWin.micLevel
                width: Math.min(460, parent.width - 20)
            }
        }

        // 5. Right Widgets Column
        Column {
            id: rightCol
            anchors.right: parent.right
            anchors.top: topBar.bottom
            anchors.topMargin: 12
            spacing: 10
            width: 310

            TasksPanel {
                width: parent.width
            }

            AgentsStatusPanel {
                width: parent.width
            }

            MemoryPanel {
                width: parent.width
            }
        }

        // 6. Bottom Tray Row (Network/Storage | Cyber Dock | Launching Progress & Avengers)
        Item {
            id: bottomRow
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            height: 80

            // Left: Network & Storage
            NetworkStoragePanel {
                anchors.left: parent.left
                anchors.bottom: parent.bottom
                width: 310
            }

            // Center: Cyber Dock
            CyberDock {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 8
            }

            // Right: Launching Progress & Avengers Emblem
            ProgressAvengers {
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                width: 310
            }
        }
    }
}
