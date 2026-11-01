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
    property bool demoMode: false
    property real posX: -1
    property real posY: 64

    readonly property string displayState: standby ? "standby"
        : muted ? "disabled"
        : voiceState === "ducked" || voiceState === "barged_in" ? "listening"
        : voiceState

    Process {
        id: stateProc
        command: ["/home/g0pi/Projects/JARVIS-OMA/.venv/bin/python",
                  "/home/g0pi/Projects/JARVIS-OMA/scripts/orbit_status.py", "--subscribe"]
        running: true
        stdout: SplitParser {
            onRead: function(line) {
                try {
                    var payload = JSON.parse(line || "{}")
                    root.voiceState = String(payload.state || "offline").toLowerCase()
                    root.activityLabel = String(payload.activity ||
                        (root.voiceState === "idle" ? "Ready" : root.voiceState))
                    root.standby = Boolean(payload.standby)
                    root.demoMode = Boolean(payload.demo)
                    if (!root.demoMode)
                        root.muted = Boolean(payload.muted)
                } catch (error) {
                    root.voiceState = "offline"
                }
            }
        }
    }

    Process { id: savePosition }
    Process {
        id: muteProc
        property bool previousMuted: false
        command: ["/home/g0pi/Projects/JARVIS-OMA/.venv/bin/python",
                  "/home/g0pi/Projects/JARVIS-OMA/scripts/jarvisctl.py", "toggle"]
        onExited: function(exitCode) {
            if (exitCode !== 0)
                root.muted = previousMuted
        }
    }
    function toggleMute() {
        if (muteProc.running)
            return
        var previous = root.muted
        root.muted = !root.muted
        if (!root.demoMode) {
            muteProc.previousMuted = previous
            muteProc.running = true
        }
    }

    function persistPosition(x, y) {
        savePosition.command = ["/usr/bin/bash", "-c",
            "mkdir -p ~/.local/state/jarvis && printf '{\\\"x\\\":%d,\\\"y\\\":%d}' "
            + Math.round(x) + " " + Math.round(y) + " > ~/.local/state/jarvis/orbit-position.json"]
        savePosition.running = true
    }

    Process {
        command: ["/usr/bin/bash", "-c", "cat ~/.local/state/jarvis/orbit-position.json 2>/dev/null || true"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var p = JSON.parse(text || "{}")
                    if (p.x !== undefined) root.posX = p.x
                    if (p.y !== undefined) root.posY = p.y
                } catch (error) {}
            }
        }
    }

    Variants {
        model: Quickshell.screens
        PanelWindow {
            id: panel
            required property var modelData
            screen: modelData
            anchors { top: true; bottom: true; left: true; right: true }
            color: "transparent"
            WlrLayershell.namespace: "jarvis-aura-orbit"
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
            exclusionMode: ExclusionMode.Ignore
            mask: Region { item: orbitWidget }

            Item {
                id: orbitWidget
                width: 108
                height: 116
                x: root.posX >= 0 ? Math.min(root.posX, panel.width - width - 12)
                                  : panel.width - width - 24
                y: Math.max(12, Math.min(root.posY, panel.height - height - 12))

                Rectangle {
                    anchors.centerIn: aura
                    width: 82
                    height: 82
                    radius: 41
                    color: Qt.rgba(0.025, 0.045, 0.09, 0.52)
                    border.color: Qt.rgba(1, 1, 1, hover.hovered ? 0.16 : 0.07)
                    border.width: 1
                }

                AuraFieldOrbit {
                    id: aura
                    anchors.top: parent.top
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 96
                    height: 96
                    orbitState: root.displayState
                }

                Text {
                    anchors.top: aura.bottom
                    anchors.topMargin: -2
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: root.muted ? "MUTED · DOUBLE TAP"
                        : root.displayState === "standby" ? "STANDBY · SAY HEY JARVIS"
                        : root.activityLabel.toUpperCase()
                    color: root.muted || root.displayState === "standby" ? "#94a3b8" : "#cbd5e1"
                    font.family: "Inter, sans-serif"
                    font.pixelSize: root.displayState === "standby" ? 8 : 9
                    font.weight: Font.DemiBold
                    font.letterSpacing: 0.8
                }

                HoverHandler { id: hover }
                MouseArea {
                    property double lastTapAt: 0
                    anchors.fill: parent
                    cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                    drag.target: orbitWidget
                    drag.minimumX: 8
                    drag.maximumX: panel.width - orbitWidget.width - 8
                    drag.minimumY: 8
                    drag.maximumY: panel.height - orbitWidget.height - 8
                    onPositionChanged: if (drag.active) {
                        root.posX = orbitWidget.x
                        root.posY = orbitWidget.y
                    }
                    drag.onActiveChanged: if (!drag.active)
                        root.persistPosition(orbitWidget.x, orbitWidget.y)
                    onPressed: function(mouse) {
                        var now = Date.now()
                        if (now - lastTapAt <= 500) {
                            lastTapAt = 0
                            root.toggleMute()
                        } else {
                            lastTapAt = now
                        }
                    }
                }
            }
        }
    }
}
