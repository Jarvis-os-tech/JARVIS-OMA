import QtQuick
import QtQuick.Shapes
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import qs.components
import qs.panels

PanelWindow {
    id: window

    readonly property int contentPadding: 14
    readonly property int collapsedHeight: 32
    readonly property int cornerWing: 16
    readonly property int canvasWidth: 552
    readonly property int canvasHeight: 600
    readonly property int requestedTopPadding: ShellState.panel === "launcher" ? 10 : contentPadding
    readonly property int requestedBottomPadding: ShellState.panel === "launcher" ? 4 : contentPadding
    readonly property int displayedTopPadding: displayedPanel === "launcher" ? 10 : contentPadding
    readonly property int displayedBottomPadding: displayedPanel === "launcher" ? 4 : contentPadding
    readonly property real targetVisualWidth: ShellState.targetWidth + cornerWing * 2
    readonly property real targetVisualHeight: ShellState.expanded ? panelContentHeight + requestedTopPadding + requestedBottomPadding : collapsedHeight
    readonly property real panelContentHeight: ShellState.expanded ? Math.max(ShellState.panelHeights[ShellState.panel] || 0, requestedPanel ? requestedPanel.implicitHeight : 0) : 0
    property bool contentRevealed: false
    property bool clockRevealed: true
    property string displayedPanel: "control"

    property string jarvisState: "unavailable"

    FileView {
        id: jarvisStateFile
        path: (Quickshell.env("XDG_RUNTIME_DIR") || Quickshell.env("XDG_STATE_HOME")
               || (Quickshell.env("HOME") + "/.local/state")) + "/jarvis/state.json"
        watchChanges: true
        onFileChanged: reload()
        onLoadFailed: window.jarvisState = "unavailable"
        onLoaded: {
            try {
                var d = JSON.parse(text());
                if (!d || typeof d.state !== "string" ||
                    (typeof d.status_written_at === "number" && Date.now() - d.status_written_at * 1000 >= voiceStatusExpiry.interval)) {
                    window.jarvisState = "unavailable";
                    return;
                }
                var st = d.state;
                if (d.connection_state === "listening" && st !== "speaking" && st !== "thinking") {
                    st = "listening";
                }
                window.jarvisState = st;
                voiceStatusExpiry.restart();
            } catch (e) {
                window.jarvisState = "unavailable";
            }
        }
    }

    Timer {
        id: voiceStatusExpiry
        interval: 2500
        onTriggered: window.jarvisState = "unavailable"
    }
    readonly property Item activePanel: {
        const panels = {
            "control": controlPanel,
            "launcher": launcherPanel,
            "clipboard": clipboardPanel,
            "todo": todoPanel,
            "notes": quickNotesPanel,
            "theme": themePanel,
            "wallpaper": wallpaperPanel,
            "capture": capturePanel,
            "power": powerPanel
        };
        return panels[displayedPanel] || null;
    }
    readonly property Item requestedPanel: {
        const panels = {
            "control": controlPanel,
            "launcher": launcherPanel,
            "clipboard": clipboardPanel,
            "todo": todoPanel,
            "notes": quickNotesPanel,
            "theme": themePanel,
            "wallpaper": wallpaperPanel,
            "capture": capturePanel,
            "power": powerPanel
        };
        return panels[ShellState.panel] || null;
    }

    function focusInitialControl() {
        if (!ShellState.expanded || !activePanel)
            return ;

        if (typeof activePanel.takeInitialFocus === "function") {
            activePanel.takeInitialFocus();
            return ;
        }
        activePanel.forceActiveFocus(Qt.TabFocusReason);
        const firstControl = activePanel.nextItemInFocusChain(true);
        if (firstControl && firstControl !== activePanel)
            firstControl.forceActiveFocus(Qt.TabFocusReason);

    }

    function moveFocus(forward) {
        const current = window.activeFocusItem;
        if (!current) {
            focusInitialControl();
            return ;
        }
        const target = current.nextItemInFocusChain(forward);
        if (target)
            target.forceActiveFocus(forward ? Qt.TabFocusReason : Qt.BacktabFocusReason);

    }

    margins.left: Math.round((screen.width - canvasWidth) / 2)
    implicitWidth: canvasWidth
    implicitHeight: canvasHeight
    color: "transparent"
    aboveWindows: true
    focusable: ShellState.expanded
    exclusionMode: ExclusionMode.Ignore

    anchors {
        top: true
        left: true
    }

    Connections {
        function onPanelChanged() {
            window.contentRevealed = ShellState.expanded;
            if (ShellState.expanded) {
                clockRevealTimer.stop();
                window.clockRevealed = false;
                window.displayedPanel = ShellState.panel;
                focusTimer.restart();
            } else {
                clockRevealTimer.restart();
            }
        }

        target: ShellState
    }

    FocusScope {
        id: notchSurface

        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        width: window.targetVisualWidth
        height: window.targetVisualHeight
        focus: true

        Rectangle {
            id: notchBody

            x: window.cornerWing
            y: -15
            width: parent.width - window.cornerWing * 2
            height: parent.height + 15
            radius: Theme.radius
            color: Theme.shellBackground
        }

        Shape {
            x: 0
            width: window.cornerWing
            height: window.cornerWing
            preferredRendererType: Shape.CurveRenderer

            ShapePath {
                id: leftShoulderPath

                readonly property real size: window.cornerWing

                strokeWidth: 0
                fillColor: Theme.shellBackground
                startX: 0
                startY: 0

                PathLine {
                    x: leftShoulderPath.size
                    y: 0
                }

                PathLine {
                    x: leftShoulderPath.size
                    y: leftShoulderPath.size
                }

                PathCubic {
                    control1X: leftShoulderPath.size
                    control1Y: leftShoulderPath.size * 0.448
                    control2X: leftShoulderPath.size * 0.552
                    control2Y: 0
                    x: 0
                    y: 0
                }

            }

        }

        Shape {
            x: parent.width - width
            width: window.cornerWing
            height: window.cornerWing
            preferredRendererType: Shape.CurveRenderer

            ShapePath {
                id: rightShoulderPath

                readonly property real size: window.cornerWing

                strokeWidth: 0
                fillColor: Theme.shellBackground
                startX: rightShoulderPath.size
                startY: 0

                PathLine {
                    x: 0
                    y: 0
                }

                PathLine {
                    x: 0
                    y: rightShoulderPath.size
                }

                PathCubic {
                    control1X: 0
                    control1Y: rightShoulderPath.size * 0.448
                    control2X: rightShoulderPath.size * 0.448
                    control2Y: 0
                    x: rightShoulderPath.size
                    y: 0
                }

            }

        }

        Row {
            anchors.left: notchBody.left
            anchors.right: notchBody.right
            anchors.top: parent.top
            height: window.collapsedHeight
            anchors.leftMargin: 6
            anchors.rightMargin: 6
            visible: opacity > 0
            opacity: window.clockRevealed ? 1 : 0

            ShellText {
                width: (parent.width - 24) / 2
                height: parent.height
                horizontalAlignment: Text.AlignRight
                verticalAlignment: Text.AlignVCenter
                rightPadding: 4
                text: Qt.formatDateTime(clock.date, "HH:mm")
                color: Theme.shellForeground
                font.pixelSize: 12
                font.weight: Font.DemiBold
            }

            // JARVIS Dynamic Core Indicator
            Item {
                width: 24
                height: parent.height
                anchors.verticalCenter: parent.verticalCenter

                Rectangle {
                    id: jarvisCore
                    anchors.centerIn: parent
                    width: window.jarvisState === "listening" || window.jarvisState === "speaking" ? 14 : 7
                    height: 7
                    radius: 3.5
                    color: window.jarvisState === "unavailable" ? "#7f849c"
                         : window.jarvisState === "thinking" ? "#f9e2af"
                         : window.jarvisState === "speaking" ? "#94e2d5"
                         : "#89dceb"

                    SequentialAnimation on opacity {
                        running: !ShellState.expanded
                        loops: Animation.Infinite
                        NumberAnimation { from: 0.35; to: 1.0; duration: window.jarvisState === "thinking" ? 400 : 1200; easing.type: Easing.InOutQuad }
                        NumberAnimation { from: 1.0; to: 0.35; duration: window.jarvisState === "thinking" ? 400 : 1200; easing.type: Easing.InOutQuad }
                    }

                    Behavior on width {
                        NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
                    }
                    Behavior on color {
                        ColorAnimation { duration: 200 }
                    }
                }
            }

            ShellText {
                width: (parent.width - 24) / 2
                height: parent.height
                horizontalAlignment: Text.AlignLeft
                verticalAlignment: Text.AlignVCenter
                leftPadding: 4
                text: ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"][clock.date.getDay()] + " " + Qt.formatDateTime(clock.date, "d/M")
                color: Theme.shellForeground
                font.pixelSize: 12
                font.weight: Font.DemiBold
            }

            Behavior on opacity {
                NumberAnimation {
                    duration: 90
                    easing.type: Easing.OutCubic
                }

            }

        }

        MouseArea {
            anchors.fill: parent
            enabled: !ShellState.expanded
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: ShellState.show("control")
        }

        Item {
            id: panelHost

            anchors.left: notchBody.left
            anchors.right: notchBody.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.leftMargin: window.contentPadding
            anchors.rightMargin: window.contentPadding
            anchors.topMargin: window.displayedTopPadding
            anchors.bottomMargin: window.displayedBottomPadding
            visible: opacity > 0
            opacity: window.contentRevealed ? 1 : 0
            clip: true

            ControlPanel {
                id: controlPanel

                width: parent.width
                height: parent.height
                visible: window.displayedPanel === "control"
            }

            LauncherPanel {
                id: launcherPanel

                width: parent.width
                visible: window.displayedPanel === "launcher"
            }

            ClipboardPanel {
                id: clipboardPanel

                width: parent.width
                visible: window.displayedPanel === "clipboard"
            }

            TodoPanel {
                id: todoPanel

                width: parent.width
                visible: window.displayedPanel === "todo"
            }

            QuickNotesPanel {
                id: quickNotesPanel

                width: parent.width
                height: parent.height
                visible: window.displayedPanel === "notes"
            }

            ThemePanel {
                id: themePanel

                width: parent.width
                height: parent.height
                visible: window.displayedPanel === "theme"
            }

            WallpaperPanel {
                id: wallpaperPanel

                width: parent.width
                height: parent.height
                visible: window.displayedPanel === "wallpaper"
            }

            CapturePanel {
                id: capturePanel

                width: parent.width
                visible: window.displayedPanel === "capture"
            }

            PowerPanel {
                id: powerPanel

                width: parent.width
                visible: window.displayedPanel === "power"
            }

            Behavior on opacity {
                NumberAnimation {
                    duration: Theme.animationNormal
                    easing.type: Easing.OutCubic
                }

            }

        }

        Behavior on width {
            NumberAnimation {
                duration: Theme.animationNormal
                easing.type: Easing.OutCubic
            }

        }

        Behavior on height {
            enabled: !clipboardPanel.previewTransitionActive

            NumberAnimation {
                duration: Theme.animationNormal
                easing.type: Easing.OutCubic
            }

        }

    }

    SystemClock {
        id: clock

        precision: SystemClock.Minutes
    }

    HyprlandFocusGrab {
        windows: [window]
        active: ShellState.expanded && Backend.captureSelectionMode !== "region"
        onCleared: {
            if (ShellState.expanded && Backend.captureSelectionMode !== "region")
                ShellState.close();

        }
    }

    Timer {
        id: focusTimer

        interval: 35
        onTriggered: window.focusInitialControl()
    }

    Timer {
        id: clockRevealTimer

        interval: 150
        onTriggered: {
            if (!ShellState.expanded)
                window.clockRevealed = true;

        }
    }

    mask: Region {
        item: notchBody
        topLeftRadius: 0
        topRightRadius: 0
        bottomLeftRadius: Theme.radius
        bottomRightRadius: Theme.radius
    }

}
