import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

// VisionPip.qml
// Floating, draggable Picture-in-Picture (PiP) HUD for JARVIS Vision Sharing.
// Displays live desktop screen sharing and webcam feeds with real-time HUD controls.
Item {
    id: root

    // Active vision mode: "screen" | "camera" | "off"
    property string activeMode: "off"

    // Size mode: compact (300x195) vs expanded (480x305)
    property bool isExpanded: false

    // Window position
    property real posX: -1
    property real posY: 64

    // Frame update tick for cache-busting
    property int frameTick: 0
    property bool showingA: true
    property bool hasLoadedFrame: false
    property string sourceA: ""
    property string sourceB: ""

    // Frame paths
    readonly property string screenFramePath: "/run/user/1000/jarvis_screen/live_stream.jpg"
    readonly property string cameraFramePath: "/run/user/1000/jarvis_webcam/live_stream.jpg"
    readonly property string socketPath: "/run/user/1000/jarvis/control.sock"

    readonly property string targetFramePath: {
        if (activeMode === "screen") return screenFramePath
        if (activeMode === "camera") return cameraFramePath
        return ""
    }

    onActiveModeChanged: {
        hasLoadedFrame = false
        sourceA = ""
        sourceB = ""
        showingA = true
        if (targetFramePath.length > 0) {
            frameTick = (frameTick + 1) % 1000000
            sourceA = "file://" + targetFramePath + "?t=" + frameTick
        }
    }

    // Startup directory initialization
    Process {
        id: initDirsProc
        command: ["mkdir", "-p", "/run/user/1000/jarvis_webcam", "/run/user/1000/jarvis_screen"]
        running: true
    }

    // Save window coordinates
    Process {
        id: savePosProc
    }

    function savePosition(x, y) {
        savePosProc.command = [
            "/usr/bin/bash", "-c",
            "mkdir -p ~/.local/state/omarchy-ai && echo '{\"x\":" + Math.round(x) + ",\"y\":" + Math.round(y) + "}' > ~/.local/state/omarchy-ai/vision_pip_position.json"
        ]
        savePosProc.running = true
    }

    // Load saved coordinates on startup
    Process {
        id: loadPosProc
        command: ["/usr/bin/bash", "-c", "cat ~/.local/state/omarchy-ai/vision_pip_position.json 2>/dev/null || echo ''"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var data = JSON.parse(text || "{}")
                    if (data.x !== undefined && data.y !== undefined) {
                        root.posX = data.x
                        root.posY = data.y
                    }
                } catch (e) {}
            }
        }
    }

    // Send set_vision_mode command to JARVIS daemon IPC socket
    Process {
        id: sendModeProc
    }

    function sendSetVisionMode(mode) {
        var clean = String(mode).trim().toLowerCase()
        root.activeMode = clean
        sendModeProc.command = [
            "/usr/bin/python3", "-c",
            "import socket, os, json; " +
            "cands = ['/run/user/1000/jarvis/control.sock', '/run/user/1000/jarvis.sock']; " +
            "target = next((p for p in cands if os.path.exists(p)), cands[0]); " +
            "s = socket.socket(socket.AF_UNIX); " +
            "s.settimeout(1.0); " +
            "s.connect(target); " +
            "s.sendall(json.dumps({'command': 'set_vision_mode', 'mode': '" + clean + "'}).encode() + b'\\n'); " +
            "print(s.recv(1024).decode())"
        ]
        sendModeProc.running = true
    }

    // Periodic state poller to sync with JARVIS daemon
    Process {
        id: syncModeProc
        command: [
            "/usr/bin/python3", "-c",
            "import socket, os, json; " +
            "cands = ['/run/user/1000/jarvis/control.sock', '/run/user/1000/jarvis.sock']; " +
            "target = next((p for p in cands if os.path.exists(p)), cands[0]); " +
            "s = socket.socket(socket.AF_UNIX); " +
            "s.settimeout(0.6); " +
            "s.connect(target); " +
            "s.sendall(json.dumps({'command': 'get_vision_mode'}).encode() + b'\\n'); " +
            "print(s.recv(1024).decode())"
        ]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var res = JSON.parse(text || "{}")
                    if (res && res.status === "ok" && res.vision_mode !== undefined) {
                        var m = String(res.vision_mode).trim().toLowerCase()
                        if (root.activeMode !== m) {
                            root.activeMode = m
                        }
                    }
                } catch (e) {
                    // Daemon socket might be offline, check if frame files are still active
                }
            }
        }
    }

    Timer {
        id: daemonSyncTimer
        interval: 1200
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: {
            if (!syncModeProc.running) {
                syncModeProc.running = true
            }
        }
    }

    // Frame refresh timer: fast (80ms / ~12.5 FPS) in camera mode for fluid video, 500ms in screen mode
    Timer {
        id: frameRefreshTimer
        interval: (root.activeMode === "camera") ? 80 : 500
        repeat: true
        running: root.activeMode !== "off"
        onTriggered: {
            if (root.targetFramePath.length === 0) return
            root.frameTick = (root.frameTick + 1) % 1000000
            var nextUrl = "file://" + root.targetFramePath + "?t=" + root.frameTick

            if (root.showingA) {
                root.sourceB = nextUrl
            } else {
                root.sourceA = nextUrl
            }
        }
    }

    // Quickshell IPC Handler so JARVIS daemon or CLI can notify immediately
    IpcHandler {
        target: "vision-pip"

        function setState(payloadJson: string): string {
            try {
                var p = JSON.parse(payloadJson || "{}")
                if (p.mode !== undefined) {
                    root.activeMode = String(p.mode).trim().toLowerCase()
                }
            } catch (err) {
                console.warn("vision-pip: could not parse payload:", err)
            }
            return "ok"
        }

        function setMode(mode: string): string {
            root.sendSetVisionMode(mode)
            return "ok"
        }

        function toggle(): string {
            if (root.activeMode === "off") {
                root.sendSetVisionMode("screen")
            } else {
                root.sendSetVisionMode("off")
            }
            return root.activeMode
        }

        function toggleExpand(): string {
            root.isExpanded = !root.isExpanded
            return root.isExpanded ? "expanded" : "compact"
        }

        function ping(): string {
            return "pong"
        }
    }

    PanelWindow {
        id: panel
        screen: Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
        visible: root.activeMode !== "off"

            anchors {
                top: true
                bottom: true
                left: true
                right: true
            }
            color: "transparent"

            WlrLayershell.namespace: "omarchy-ai-vision-pip"
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
            exclusionMode: ExclusionMode.Ignore

            // 100% click-through for desktop except the PiP frame itself
            mask: Region { item: pipWidget }

            Item {
                id: pipWidget
                x: root.posX >= 0 ? Math.min(root.posX, panel.width - width - 12) : (panel.width - width - 28)
                y: Math.max(12, Math.min(root.posY, panel.height - height - 12))

                width: root.isExpanded ? 480 : 310
                height: root.isExpanded ? 305 : 198

                Behavior on width {
                    NumberAnimation {
                        duration: 220
                        easing.type: Easing.OutCubic
                    }
                }

                Behavior on height {
                    NumberAnimation {
                        duration: 220
                        easing.type: Easing.OutCubic
                    }
                }

                opacity: (root.activeMode !== "off") ? 1.0 : 0.0

                Behavior on opacity {
                    NumberAnimation {
                        duration: 180
                        easing.type: Easing.InOutQuad
                    }
                }

                // Glassmorphic Backdrop Card
                Rectangle {
                    id: cardBg
                    anchors.fill: parent
                    radius: 12
                    color: Qt.rgba(0.03, 0.05, 0.10, 0.95)

                    border.color: {
                        if (headerHover.hovered) return Qt.rgba(0.22, 0.85, 0.98, 0.85)
                        if (root.activeMode === "screen") return Qt.rgba(0.06, 0.75, 0.88, 0.70)
                        if (root.activeMode === "camera") return Qt.rgba(0.22, 0.78, 0.65, 0.70)
                        return Qt.rgba(0.18, 0.24, 0.35, 0.60)
                    }
                    border.width: headerHover.hovered ? 1.6 : 1.2

                    // Specular inner border
                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 1
                        radius: parent.radius - 1
                        color: "transparent"
                        border.color: Qt.rgba(1.0, 1.0, 1.0, 0.08)
                        border.width: 1
                    }
                }

                // Main Column Layout (Header + Video Viewport)
                Column {
                    anchors.fill: parent
                    anchors.margins: 2
                    spacing: 0

                    // Header Bar
                    Item {
                        id: headerBar
                        width: parent.width
                        height: 32

                        // Header background
                        Rectangle {
                            anchors.fill: parent
                            color: Qt.rgba(0.07, 0.11, 0.18, 0.85)
                            topLeftRadius: 10
                            topRightRadius: 10
                        }

                        // Drag & Double-Click Mouse Area
                        MouseArea {
                            id: dragArea
                            anchors.fill: parent
                            cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                            drag.target: pipWidget
                            drag.axis: Drag.XAndYAxis
                            drag.minimumX: 8
                            drag.maximumX: panel.width - pipWidget.width - 8
                            drag.minimumY: 8
                            drag.maximumY: panel.height - pipWidget.height - 8

                            property bool wasDragged: false

                            onPressed: (mouse) => {
                                wasDragged = false
                            }

                            onPositionChanged: (mouse) => {
                                if (drag.active) {
                                    wasDragged = true
                                    root.posX = pipWidget.x
                                    root.posY = pipWidget.y
                                }
                            }

                            drag.onActiveChanged: {
                                if (!drag.active) {
                                    root.savePosition(pipWidget.x, pipWidget.y)
                                }
                            }

                            onDoubleClicked: (mouse) => {
                                root.isExpanded = !root.isExpanded
                            }
                        }

                        HoverHandler {
                            id: headerHover
                        }

                        // Header Content Row
                        Row {
                            anchors.left: parent.left
                            anchors.leftMargin: 10
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 7

                            // Pulsing Live Indicator LED
                            Rectangle {
                                width: 7
                                height: 7
                                radius: 3.5
                                anchors.verticalCenter: parent.verticalCenter
                                color: root.activeMode === "screen" ? "#38bdf8" : "#34d399"

                                SequentialAnimation on opacity {
                                    running: root.activeMode !== "off"
                                    loops: Animation.Infinite
                                    NumberAnimation { from: 1.0; to: 0.35; duration: 500; easing.type: Easing.InOutQuad }
                                    NumberAnimation { from: 0.35; to: 1.0; duration: 500; easing.type: Easing.InOutQuad }
                                }
                            }

                            // Mode Label
                            Text {
                                text: {
                                    if (root.activeMode === "screen") return "LIVE SCREEN SHARE"
                                    if (root.activeMode === "camera") return "LIVE WEBCAM FEED"
                                    return "VISION STREAM"
                                }
                                color: root.activeMode === "screen" ? "#7dd3fc" : "#6ee7b7"
                                font.pixelSize: 10
                                font.bold: true
                                font.family: "Monospace, Inter, sans-serif"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        // Right Action Controls
                        Row {
                            anchors.right: parent.right
                            anchors.rightMargin: 6
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 4

                            // Switch Source Button
                            Rectangle {
                                id: switchBtn
                                width: switchLabel.implicitWidth + 12
                                height: 20
                                radius: 4
                                anchors.verticalCenter: parent.verticalCenter
                                color: switchHover.hovered ? Qt.rgba(0.20, 0.28, 0.42, 0.90) : Qt.rgba(0.12, 0.16, 0.25, 0.80)
                                border.color: switchHover.hovered ? "#38bdf8" : Qt.rgba(1.0, 1.0, 1.0, 0.12)
                                border.width: 1

                                Text {
                                    id: switchLabel
                                    anchors.centerIn: parent
                                    text: root.activeMode === "camera" ? "🖥 Screen" : "📷 Camera"
                                    color: switchHover.hovered ? "#e0f2fe" : "#94a3b8"
                                    font.pixelSize: 9
                                    font.bold: true
                                    font.family: "Inter, sans-serif"
                                }

                                MouseArea {
                                    id: switchMouse
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        var target = (root.activeMode === "camera") ? "screen" : "camera"
                                        root.sendSetVisionMode(target)
                                    }
                                }

                                HoverHandler {
                                    id: switchHover
                                }
                            }

                            // Expand / Minimize Button
                            Rectangle {
                                id: expandBtn
                                width: 20
                                height: 20
                                radius: 4
                                anchors.verticalCenter: parent.verticalCenter
                                color: expandHover.hovered ? Qt.rgba(0.20, 0.28, 0.42, 0.90) : Qt.rgba(0.12, 0.16, 0.25, 0.80)
                                border.color: expandHover.hovered ? "#38bdf8" : Qt.rgba(1.0, 1.0, 1.0, 0.12)
                                border.width: 1

                                Text {
                                    anchors.centerIn: parent
                                    text: root.isExpanded ? "🗗" : "🗖"
                                    color: expandHover.hovered ? "#e0f2fe" : "#94a3b8"
                                    font.pixelSize: 10
                                    font.bold: true
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        root.isExpanded = !root.isExpanded
                                    }
                                }

                                HoverHandler {
                                    id: expandHover
                                }
                            }

                            // Close Button (Turn vision off)
                            Rectangle {
                                id: closeBtn
                                width: 20
                                height: 20
                                radius: 4
                                anchors.verticalCenter: parent.verticalCenter
                                color: closeHover.hovered ? Qt.rgba(0.85, 0.20, 0.25, 0.85) : Qt.rgba(0.12, 0.16, 0.25, 0.80)
                                border.color: closeHover.hovered ? "#f87171" : Qt.rgba(1.0, 1.0, 1.0, 0.12)
                                border.width: 1

                                Text {
                                    anchors.centerIn: parent
                                    text: "✕"
                                    color: closeHover.hovered ? "#ffffff" : "#94a3b8"
                                    font.pixelSize: 10
                                    font.bold: true
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        root.sendSetVisionMode("off")
                                    }
                                }

                                HoverHandler {
                                    id: closeHover
                                }
                            }
                        }
                    }

                    // Divider Line
                    Rectangle {
                        width: parent.width
                        height: 1
                        color: Qt.rgba(0.15, 0.22, 0.35, 0.70)
                    }

                    // Video Stream Viewport
                    Item {
                        id: viewportArea
                        width: parent.width
                        height: parent.height - headerBar.height - 1
                        clip: true

                        // Viewport black background
                        Rectangle {
                            anchors.fill: parent
                            color: "#020408"
                            bottomLeftRadius: 10
                            bottomRightRadius: 10
                        }

                        // Double-Buffered Live Video Frames (Zero Blinking / Zero Torn Frames)
                        Image {
                            id: imgA
                            anchors.fill: parent
                            cache: false
                            asynchronous: true
                            fillMode: root.activeMode === "screen" ? Image.PreserveAspectFit : Image.PreserveAspectCrop
                            source: root.sourceA
                            opacity: (root.activeMode !== "off" && root.showingA) ? 1.0 : 0.0
                            visible: opacity > 0.001
                            z: root.showingA ? 2 : 1

                            onStatusChanged: {
                                if (status === Image.Ready) {
                                    root.hasLoadedFrame = true
                                    if (!root.showingA) {
                                        root.showingA = true
                                        root.sourceB = ""
                                    }
                                }
                            }
                        }

                        Image {
                            id: imgB
                            anchors.fill: parent
                            cache: false
                            asynchronous: true
                            fillMode: root.activeMode === "screen" ? Image.PreserveAspectFit : Image.PreserveAspectCrop
                            source: root.sourceB
                            opacity: (root.activeMode !== "off" && !root.showingA) ? 1.0 : 0.0
                            visible: opacity > 0.001
                            z: !root.showingA ? 2 : 1

                            onStatusChanged: {
                                if (status === Image.Ready) {
                                    root.hasLoadedFrame = true
                                    if (root.showingA) {
                                        root.showingA = false
                                        root.sourceA = ""
                                    }
                                }
                            }
                        }

                        // Fallback Placeholder ONLY shown on initial startup before any frame is decoded
                        Item {
                            anchors.fill: parent
                            visible: (root.activeMode !== "off" && !root.hasLoadedFrame)

                            Column {
                                anchors.centerIn: parent
                                spacing: 8

                                Rectangle {
                                    width: 12
                                    height: 12
                                    radius: 6
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    color: "#06b6d4"

                                    SequentialAnimation on scale {
                                        running: (root.activeMode === "screen" && !root.hasLoadedFrame)
                                        loops: Animation.Infinite
                                        NumberAnimation { from: 0.8; to: 1.3; duration: 400; easing.type: Easing.InOutQuad }
                                        NumberAnimation { from: 1.3; to: 0.8; duration: 400; easing.type: Easing.InOutQuad }
                                    }
                                }

                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: "STREAMING TO GEMINI LIVE..."
                                    color: "#67e8f9"
                                    font.pixelSize: 10
                                    font.bold: true
                                    font.family: "Monospace, Inter, sans-serif"
                                }
                            }
                        }

                        // Subtle scanline overlay animation
                        Rectangle {
                            width: parent.width
                            height: 2
                            color: Qt.rgba(0.22, 0.74, 0.97, 0.12)
                            SequentialAnimation on y {
                                running: root.activeMode !== "off"
                                loops: Animation.Infinite
                                NumberAnimation { from: 0; to: viewportArea.height; duration: 2800; easing.type: Easing.Linear }
                                PauseAnimation { duration: 400 }
                            }
                        }

                        // Bottom-Left Status Pill
                        Rectangle {
                            anchors.left: parent.left
                            anchors.leftMargin: 8
                            anchors.bottom: parent.bottom
                            anchors.bottomMargin: 8
                            height: 18
                            width: statusRow.implicitWidth + 14
                            radius: 9
                            color: Qt.rgba(0.02, 0.04, 0.08, 0.75)
                            border.color: Qt.rgba(1.0, 1.0, 1.0, 0.12)
                            border.width: 1

                            Row {
                                id: statusRow
                                anchors.centerIn: parent
                                spacing: 5

                                Rectangle {
                                    width: 5
                                    height: 5
                                    radius: 2.5
                                    color: root.activeMode === "camera" ? "#34d399" : "#22d3ee"
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                Text {
                                    text: root.activeMode === "camera" ? "REALTIME CAM 30 FPS" : "REALTIME SCREEN"
                                    color: "#e2e8f0"
                                    font.pixelSize: 8
                                    font.bold: true
                                    font.family: "Monospace, Inter, sans-serif"
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                        }
                    }
                }
            }
        }
    }
