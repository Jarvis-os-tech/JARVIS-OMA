import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

PanelWindow {
    id: win
    visible: true
    WlrLayershell.namespace: "jarvis-orbit-hud"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    color: "transparent"

    property real posX: -1
    property real posY: 70
    property string voiceState: "idle"
    property bool standby: false
    property bool muted: false
    property string activityLabel: "Ready"
    property real micLevel: 0.0
    property real cpuPercent: 0.0
    property real ramPercent: 0.0
    property real ramUsed: 0.0
    property real ramTotal: 7.4
    property real batteryPercent: 88.0
    property bool isCharging: false

    readonly property string displayState: standby ? "standby"
        : muted ? "disabled"
        : voiceState === "ducked" || voiceState === "barged_in" ? "listening"
        : voiceState

    anchors {
        top: true
        right: true
    }
    margins {
        top: Math.max(16, win.posY)
        right: win.posX >= 0 ? Math.max(16, win.posX) : 24
    }

    implicitWidth: 260
    implicitHeight: 130

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
                        win.voiceState = String(payload.state || "offline").toLowerCase();
                    if (payload.activity !== undefined)
                        win.activityLabel = String(payload.activity || (win.voiceState === "idle" ? "Online" : win.voiceState));
                    if (payload.standby !== undefined)
                        win.standby = Boolean(payload.standby);
                    if (payload.muted !== undefined)
                        win.muted = Boolean(payload.muted);
                    if (payload.microphone_rms !== undefined) {
                        var rms = Number(payload.microphone_rms) || 0.0;
                        win.micLevel = Math.min(1.0, rms * 25.0);
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
                    if (data.cpu !== undefined) win.cpuPercent = Number(data.cpu) || 0.0;
                    if (data.ram !== undefined) win.ramPercent = Number(data.ram) || 0.0;
                    if (data.ram_used !== undefined) win.ramUsed = Number(data.ram_used) || 0.0;
                    if (data.ram_total !== undefined) win.ramTotal = Number(data.ram_total) || 7.4;
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

    // 3. Mute Toggle Process
    Process {
        id: muteProc
        command: ["/home/g0pi/.local/bin/jarvis-voice-toggle"]
    }

    function toggleMute() {
        if (!muteProc.running) muteProc.running = true;
    }

    // HUD Chassis Container
    Rectangle {
        id: hudCard
        anchors.fill: parent
        radius: 20
        color: Qt.rgba(0.027, 0.047, 0.082, 0.88)
        border.color: hover.hovered ? Qt.rgba(0.0, 0.898, 1.0, 0.85) : Qt.rgba(0.0, 0.898, 1.0, 0.35)
        border.width: 1.4

        // Top Telemetry Header
        Row {
            anchors.top: parent.top
            anchors.topMargin: 8
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 12

            Text {
                text: "JARVIS HUD v2.5"
                color: Qt.rgba(0.0, 0.898, 1.0, 0.7)
                font.family: "JetBrainsMono Nerd Font, monospace"
                font.pixelSize: 8
                font.weight: Font.Bold
                font.letterSpacing: 1.0
            }

            Text {
                text: "SYSTEM NORMAL"
                color: win.cpuPercent > 80 || win.ramPercent > 85 ? "#ff3b5c" : "#4f7285"
                font.family: "JetBrainsMono Nerd Font, monospace"
                font.pixelSize: 8
                font.weight: Font.Bold
                font.letterSpacing: 0.5
            }
        }

        // Left Wing: CPU Live Telemetry
        Column {
            anchors.left: parent.left
            anchors.leftMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            spacing: 3
            width: 54

            Text {
                text: " CPU"
                color: "#4f7285"
                font.family: "JetBrainsMono Nerd Font, monospace"
                font.pixelSize: 9
                font.weight: Font.Bold
            }

            Text {
                text: Math.round(win.cpuPercent) + "%"
                color: win.cpuPercent > 80 ? "#ff3b5c" : "#00e5ff"
                font.family: "JetBrainsMono Nerd Font, monospace"
                font.pixelSize: 15
                font.weight: Font.Bold
            }

            Rectangle {
                width: 48
                height: 3
                radius: 1.5
                color: "#132230"
                Rectangle {
                    width: Math.min(parent.width, parent.width * (win.cpuPercent / 100.0))
                    height: parent.height
                    radius: 1.5
                    color: win.cpuPercent > 80 ? "#ff3b5c" : "#00e5ff"
                }
            }
        }

        // Center: High-Tech Animated Stark Arc Reactor / Orbit Canvas
        Item {
            id: reactorContainer
            anchors.centerIn: parent
            width: 84
            height: 84

            Canvas {
                id: reactorCanvas
                anchors.fill: parent
                property real angle: 0
                property real energy: 0.2

                Timer {
                    interval: 16
                    repeat: true
                    running: true
                    onTriggered: {
                        var stateSpeed = win.displayState === "speaking" ? 0.05
                                       : win.displayState === "thinking" ? 0.035
                                       : win.displayState === "listening" ? 0.025
                                       : 0.012;
                        reactorCanvas.angle = (reactorCanvas.angle + stateSpeed) % (Math.PI * 2);
                        
                        var targetEnergy = win.displayState === "speaking" ? 0.5 + win.micLevel * 0.5
                                         : win.displayState === "listening" ? 0.4 + win.micLevel * 0.6
                                         : win.displayState === "thinking" ? 0.45
                                         : 0.2;
                        reactorCanvas.energy += (targetEnergy - reactorCanvas.energy) * 0.15;
                        reactorCanvas.requestPaint();
                    }
                }

                onPaint: {
                    var ctx = getContext("2d");
                    ctx.reset();
                    var cx = width / 2;
                    var cy = height / 2;
                    var r = width / 2 - 4;

                    // Color Palette based on State
                    var mainColor = win.displayState === "speaking" ? "#ffb86b"
                                  : win.displayState === "thinking" ? "#a855f7"
                                  : win.displayState === "listening" ? "#00e5ff"
                                  : win.muted ? "#ff3b5c"
                                  : win.displayState === "standby" ? "#64748b"
                                  : "#00f0a8";

                    var glowColor = win.displayState === "speaking" ? Qt.rgba(1.0, 0.72, 0.42, 0.35)
                                  : win.displayState === "thinking" ? Qt.rgba(0.66, 0.33, 0.97, 0.35)
                                  : Qt.rgba(0.0, 0.898, 1.0, 0.4);

                    // 1. Outer Concentric Arc
                    ctx.save();
                    ctx.strokeStyle = Qt.rgba(0.0, 0.898, 1.0, 0.18);
                    ctx.lineWidth = 1.5;
                    ctx.beginPath();
                    ctx.arc(cx, cy, r - 2, 0, Math.PI * 2);
                    ctx.stroke();

                    // 2. Rotating Segmented Energy Arcs
                    ctx.strokeStyle = mainColor;
                    ctx.lineWidth = 2.0;
                    ctx.beginPath();
                    ctx.arc(cx, cy, r - 2, reactorCanvas.angle, reactorCanvas.angle + 1.2);
                    ctx.stroke();

                    ctx.beginPath();
                    ctx.arc(cx, cy, r - 2, reactorCanvas.angle + Math.PI, reactorCanvas.angle + Math.PI + 1.2);
                    ctx.stroke();

                    // 3. Counter-Rotating Inner Ticks
                    ctx.strokeStyle = Qt.rgba(0.0, 0.898, 1.0, 0.35);
                    ctx.lineWidth = 1.2;
                    ctx.beginPath();
                    ctx.arc(cx, cy, r - 8, -reactorCanvas.angle * 1.5, -reactorCanvas.angle * 1.5 + 2.0);
                    ctx.stroke();

                    // 4. Glowing Center Core
                    var coreR = (r - 16) * (0.8 + reactorCanvas.energy * 0.4);
                    var grad = ctx.createRadialGradient(cx, cy, 2, cx, cy, coreR);
                    grad.addColorStop(0, mainColor);
                    grad.addColorStop(0.5, glowColor);
                    grad.addColorStop(1, "rgba(0,0,0,0)");
                    ctx.fillStyle = grad;
                    ctx.beginPath();
                    ctx.arc(cx, cy, coreR, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.restore();
                }
            }
        }

        // Right Wing: RAM Live Telemetry
        Column {
            anchors.right: parent.right
            anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            spacing: 3
            width: 54

            Text {
                anchors.right: parent.right
                text: " RAM"
                color: "#4f7285"
                font.family: "JetBrainsMono Nerd Font, monospace"
                font.pixelSize: 9
                font.weight: Font.Bold
            }

            Text {
                anchors.right: parent.right
                text: Math.round(win.ramPercent) + "%"
                color: win.ramPercent > 85 ? "#ff3b5c" : "#00e5ff"
                font.family: "JetBrainsMono Nerd Font, monospace"
                font.pixelSize: 15
                font.weight: Font.Bold
            }

            Rectangle {
                anchors.right: parent.right
                width: 48
                height: 3
                radius: 1.5
                color: "#132230"
                Rectangle {
                    anchors.right: parent.right
                    width: Math.min(parent.width, parent.width * (win.ramPercent / 100.0))
                    height: parent.height
                    radius: 1.5
                    color: win.ramPercent > 85 ? "#ff3b5c" : "#00e5ff"
                }
            }
        }

        // Bottom State Pill
        Row {
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 8
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 6

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 6
                height: 6
                radius: 3
                color: win.muted ? "#ff3b5c"
                     : win.displayState === "standby" ? "#64748b"
                     : win.displayState === "speaking" ? "#ffb86b"
                     : win.displayState === "thinking" ? "#a855f7"
                     : win.displayState === "listening" ? "#00e5ff"
                     : "#00f0a8"
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: win.muted ? "MUTED (CLICK TO UNMUTE)"
                    : win.displayState === "standby" ? "STANDBY (SAY HEY JARVIS)"
                    : win.displayState === "speaking" ? "SPEAKING..."
                    : win.displayState === "thinking" ? "THINKING..."
                    : win.displayState === "listening" ? "LISTENING..."
                    : "JARVIS ACTIVE"
                color: win.muted ? "#ff8da1"
                     : win.displayState === "standby" ? "#94a3b8"
                     : "#d8f6ff"
                font.family: "JetBrainsMono Nerd Font, monospace"
                font.pixelSize: 8
                font.weight: Font.Bold
                font.letterSpacing: 0.8
            }
        }

        HoverHandler { id: hover }

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                win.toggleMute();
            }
        }
    }
}
