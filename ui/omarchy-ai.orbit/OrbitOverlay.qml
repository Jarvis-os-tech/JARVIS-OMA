import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

Item {
    id: root
    property string voiceState: "connecting"
    property bool standby: false
    property bool muted: false
    property string activityLabel: "Ready"
    property real micLevel: 0.0
    property real cpuPercent: 0.0
    property real ramPercent: 0.0
    property real ramUsed: 0.0

    readonly property string displayState: standby ? "standby"
        : muted ? "disabled"
        : voiceState === "ducked" || voiceState === "barged_in" ? "listening"
        : voiceState

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
                        root.voiceState = String(payload.state || "offline").toLowerCase();
                    if (payload.activity !== undefined)
                        root.activityLabel = String(payload.activity || (root.voiceState === "idle" ? "Online" : root.voiceState));
                    if (payload.standby !== undefined)
                        root.standby = Boolean(payload.standby);
                    if (payload.muted !== undefined)
                        root.muted = Boolean(payload.muted);
                    if (payload.microphone_rms !== undefined) {
                        var rms = Number(payload.microphone_rms) || 0.0;
                        root.micLevel = Math.min(1.0, rms * 25.0);
                    }
                } catch (error) {
                    root.voiceState = "offline";
                }
            }
        }
    }

    Timer {
        interval: 200
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: {
            if (!stateProc.running)
                stateProc.running = true;
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
                    if (data.cpu !== undefined) root.cpuPercent = Number(data.cpu) || 0.0;
                    if (data.ram !== undefined) root.ramPercent = Number(data.ram) || 0.0;
                    if (data.ram_used !== undefined) root.ramUsed = Number(data.ram_used) || 0.0;
                } catch (err) {}
            }
        }
    }

    Timer {
        interval: 1500
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: {
            if (!telemetryProc.running)
                telemetryProc.running = true;
        }
    }

    // 3. Mute Toggle Process
    Process {
        id: muteProc
        command: ["/home/g0pi/.local/bin/jarvis-voice-toggle"]
    }

    function toggleMute() {
        if (!muteProc.running) {
            muteProc.running = true;
        }
    }

    // Top-level Floating Holographic Stark HUD Window
    Variants {
        model: Quickshell.screens
        PanelWindow {
            id: panel
            required property var modelData
            screen: modelData
            visible: true
            WlrLayershell.namespace: "jarvis-aura-orbit"
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
            exclusionMode: ExclusionMode.Ignore
            color: "transparent"

            anchors {
                top: true
                right: true
            }
            margins {
                top: 56
                right: 20
            }

            implicitWidth: 216
            implicitHeight: 112

            Rectangle {
                id: orbitCard
                anchors.fill: parent
                radius: 18
                color: Qt.rgba(0.027, 0.047, 0.082, 0.82)
                border.color: hover.hovered ? Qt.rgba(0.0, 0.898, 1.0, 0.8) : Qt.rgba(0.0, 0.898, 1.0, 0.35)
                border.width: 1.2

                // Left Wing: Real-Time CPU Telemetry
                Column {
                    anchors.left: parent.left
                    anchors.leftMargin: 12
                    anchors.top: parent.top
                    anchors.topMargin: 16
                    spacing: 3
                    width: 48

                    Text {
                        text: "CPU"
                        color: "#4f7285"
                        font.family: "JetBrainsMono Nerd Font, monospace"
                        font.pixelSize: 8
                        font.weight: Font.Bold
                        font.letterSpacing: 0.5
                    }

                    Text {
                        text: Math.round(root.cpuPercent) + "%"
                        color: root.cpuPercent > 80 ? "#ff3b5c" : "#00e5ff"
                        font.family: "JetBrainsMono Nerd Font, monospace"
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }

                    Rectangle {
                        width: 44
                        height: 3
                        radius: 1.5
                        color: "#132230"
                        Rectangle {
                            width: Math.min(parent.width, parent.width * (root.cpuPercent / 100.0))
                            height: parent.height
                            radius: 1.5
                            color: root.cpuPercent > 80 ? "#ff3b5c" : "#00e5ff"
                        }
                    }
                }

                // Center: Animated Glowing JARVIS Orbit
                Item {
                    id: orbitCenter
                    anchors.centerIn: parent
                    width: 76
                    height: 76

                    Rectangle {
                        anchors.centerIn: parent
                        width: 66
                        height: 66
                        radius: 33
                        color: Qt.rgba(0.0, 0.1, 0.18, 0.45)
                        border.color: Qt.rgba(0.0, 0.898, 1.0, hover.hovered ? 0.45 : 0.2)
                        border.width: 1
                    }

                    AuraFieldOrbit {
                        id: aura
                        anchors.centerIn: parent
                        width: 78
                        height: 78
                        orbitState: root.displayState
                        level: root.micLevel
                    }
                }

                // Right Wing: Real-Time RAM Telemetry
                Column {
                    anchors.right: parent.right
                    anchors.rightMargin: 12
                    anchors.top: parent.top
                    anchors.topMargin: 16
                    horizontalAlignment: Text.AlignRight
                    spacing: 3
                    width: 48

                    Text {
                        anchors.right: parent.right
                        text: "RAM"
                        color: "#4f7285"
                        font.family: "JetBrainsMono Nerd Font, monospace"
                        font.pixelSize: 8
                        font.weight: Font.Bold
                        font.letterSpacing: 0.5
                    }

                    Text {
                        anchors.right: parent.right
                        text: Math.round(root.ramPercent) + "%"
                        color: root.ramPercent > 85 ? "#ff3b5c" : "#00e5ff"
                        font.family: "JetBrainsMono Nerd Font, monospace"
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }

                    Rectangle {
                        anchors.right: parent.right
                        width: 44
                        height: 3
                        radius: 1.5
                        color: "#132230"
                        Rectangle {
                            anchors.right: parent.right
                            width: Math.min(parent.width, parent.width * (root.ramPercent / 100.0))
                            height: parent.height
                            radius: 1.5
                            color: root.ramPercent > 85 ? "#ff3b5c" : "#00e5ff"
                        }
                    }
                }

                // Bottom: High-Tech Status Pill
                Row {
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 8
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 5

                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 5
                        height: 5
                        radius: 2.5
                        color: root.muted ? "#ff3b5c"
                             : root.displayState === "standby" ? "#64748b"
                             : root.displayState === "speaking" ? "#ffb86b"
                             : root.displayState === "thinking" ? "#a855f7"
                             : root.displayState === "listening" ? "#00e5ff"
                             : "#00f0a8"
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: root.muted ? "MUTED"
                            : root.displayState === "standby" ? "STANDBY"
                            : root.displayState === "speaking" ? "SPEAKING"
                            : root.displayState === "thinking" ? "THINKING"
                            : root.displayState === "listening" ? "LISTENING"
                            : "JARVIS LIVE"
                        color: root.muted ? "#ff8da1"
                             : root.displayState === "standby" ? "#94a3b8"
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
                    onDoubleClicked: {
                        root.toggleMute();
                    }
                }
            }
        }
    }
}
