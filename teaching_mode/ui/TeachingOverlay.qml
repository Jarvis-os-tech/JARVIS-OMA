import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

Item {
    id: root

    property bool active: false
    property string topic: "Bubble Sort Algorithm"
    // Modes: "math" | "graph" | "table" | "bubble_sort" | "quadcopter" | "whiteboard"
    property string viewMode: "bubble_sort"
    property int currentStep: 0
    property int totalSteps: 5
    property string activeNarration: "Welcome to Teaching Mode. I'll explain visually while speaking."

    property real posX: -1
    property real posY: 80

    // Master pen/cursor target coordinates (relative to stageCard or screen)
    property real targetPenX: 280
    property real targetPenY: 180
    property string cursorStyle: "pointer" // "pointer" | "pen" | "laser"
    property string cursorLabel: ""

    // IPC Handler to control from JARVIS Python backend or CLI
    IpcHandler {
        target: "teaching"

        function start(payloadJson: string): string {
            try {
                var p = JSON.parse(payloadJson || "{}");
                if (p.topic) root.topic = p.topic;

                var t = root.topic.toLowerCase();
                if (p.mode) {
                    root.viewMode = p.mode;
                } else if (t.indexOf("math") !== -1 || t.indexOf("formula") !== -1 || t.indexOf("calc") !== -1 || t.indexOf("equation") !== -1) {
                    root.viewMode = "math";
                } else if (t.indexOf("graph") !== -1 || t.indexOf("chart") !== -1 || t.indexOf("plot") !== -1 || t.indexOf("curve") !== -1 || t.indexOf("network") !== -1) {
                    root.viewMode = "graph";
                } else if (t.indexOf("table") !== -1 || t.indexOf("matrix") !== -1 || t.indexOf("benchmark") !== -1 || t.indexOf("comparison") !== -1) {
                    root.viewMode = "table";
                } else if (t.indexOf("bubble") !== -1 || t.indexOf("sort") !== -1) {
                    root.viewMode = "bubble_sort";
                } else if (t.indexOf("quad") !== -1 || t.indexOf("drone") !== -1 || t.indexOf("flight") !== -1 || t.indexOf("rotor") !== -1) {
                    root.viewMode = "quadcopter";
                } else {
                    root.viewMode = "whiteboard";
                }

                root.currentStep = 0;
                root.totalSteps = p.total_steps || 5;
                root.activeNarration = p.say || ("Teaching: " + root.topic);
                root.active = true;

                // Initialize view
                if (root.viewMode === "bubble_sort" && bubbleLoader.item) {
                    bubbleLoader.item.setStep({action: "reset", data: p.data || [5, 1, 4, 2, 8], say: root.activeNarration});
                } else if (root.viewMode === "quadcopter" && quadLoader.item) {
                    quadLoader.item.setStep({mode: "hover", say: root.activeNarration});
                } else if (root.viewMode === "math" && mathLoader.item) {
                    mathLoader.item.setStep(p);
                } else if (root.viewMode === "graph" && graphLoader.item) {
                    graphLoader.item.setStep(p);
                } else if (root.viewMode === "table" && tableLoader.item) {
                    tableLoader.item.setStep(p);
                } else if (whiteboardLoader.item && p.ops) {
                    whiteboardLoader.item.setOps(p.ops);
                }

                if (jarvisCursor) jarvisCursor.pulse("Mode: " + root.viewMode);

                return JSON.stringify({ok: true, status: "started", topic: root.topic, mode: root.viewMode});
            } catch (err) {
                return JSON.stringify({ok: false, error: String(err)});
            }
        }

        function step(payloadJson: string): string {
            try {
                var p = JSON.parse(payloadJson || "{}");
                if (p.step !== undefined) root.currentStep = p.step;
                if (p.total_steps !== undefined) root.totalSteps = p.total_steps;
                if (p.say) root.activeNarration = p.say;
                if (p.cursor_style) root.cursorStyle = p.cursor_style;
                if (p.cursor_label) root.cursorLabel = p.cursor_label;

                if (root.viewMode === "bubble_sort" && bubbleLoader.item) {
                    bubbleLoader.item.setStep(p);
                    root.targetPenX = bubbleLoader.item.pointerX;
                    root.targetPenY = bubbleLoader.item.pointerY;
                } else if (root.viewMode === "quadcopter" && quadLoader.item) {
                    quadLoader.item.setStep(p);
                    root.targetPenX = quadLoader.item.pointerX;
                    root.targetPenY = quadLoader.item.pointerY;
                } else if (root.viewMode === "math" && mathLoader.item) {
                    mathLoader.item.setStep(p);
                    root.targetPenX = mathLoader.item.pointerX;
                    root.targetPenY = mathLoader.item.pointerY;
                } else if (root.viewMode === "graph" && graphLoader.item) {
                    graphLoader.item.setStep(p);
                    root.targetPenX = graphLoader.item.pointerX;
                    root.targetPenY = graphLoader.item.pointerY;
                } else if (root.viewMode === "table" && tableLoader.item) {
                    tableLoader.item.setStep(p);
                    root.targetPenX = tableLoader.item.pointerX;
                    root.targetPenY = tableLoader.item.pointerY;
                } else if (root.viewMode === "whiteboard" && whiteboardLoader.item) {
                    if (p.ops) whiteboardLoader.item.setOps(p.ops);
                    root.targetPenX = whiteboardLoader.item.pointerX;
                    root.targetPenY = whiteboardLoader.item.pointerY;
                }

                if (p.cursor_x !== undefined) root.targetPenX = p.cursor_x;
                if (p.cursor_y !== undefined) root.targetPenY = p.cursor_y;

                if (jarvisCursor) jarvisCursor.pulse(root.cursorLabel);

                return JSON.stringify({ok: true, status: "step_updated", step: root.currentStep});
            } catch (err) {
                return JSON.stringify({ok: false, error: String(err)});
            }
        }

        function cursor(payloadJson: string): string {
            try {
                var p = JSON.parse(payloadJson || "{}");
                if (p.x !== undefined) root.targetPenX = p.x;
                if (p.y !== undefined) root.targetPenY = p.y;
                if (p.mode) root.cursorStyle = p.mode;
                if (p.label) root.cursorLabel = p.label;
                if (p.click && jarvisCursor) jarvisCursor.pulse(p.label || "");
                return JSON.stringify({ok: true, status: "cursor_moved", x: root.targetPenX, y: root.targetPenY});
            } catch (err) {
                return JSON.stringify({ok: false, error: String(err)});
            }
        }

        function draw(payloadJson: string): string {
            try {
                var p = JSON.parse(payloadJson || "{}");
                root.viewMode = "whiteboard";
                if (whiteboardLoader.item && p.ops) {
                    whiteboardLoader.item.setOps(p.ops);
                    root.targetPenX = whiteboardLoader.item.pointerX;
                    root.targetPenY = whiteboardLoader.item.pointerY;
                }
                if (jarvisCursor) jarvisCursor.pulse("Drawing");
                return JSON.stringify({ok: true, status: "drawn"});
            } catch (err) {
                return JSON.stringify({ok: false, error: String(err)});
            }
        }

        function close(): string {
            root.active = false;
            return JSON.stringify({ok: true, status: "closed"});
        }

        function status(): string {
            return JSON.stringify({
                ok: true,
                active: root.active,
                topic: root.topic,
                mode: root.viewMode,
                step: root.currentStep,
                total_steps: root.totalSteps,
                narration: root.activeNarration,
                cursor: { x: root.targetPenX, y: root.targetPenY, mode: root.cursorStyle }
            });
        }
    }

    PanelWindow {
        id: panel
        screen: Quickshell.screens.length > 0 ? Quickshell.screens[0] : null
        visible: root.active

        anchors {
            top: true
            bottom: true
            left: true
            right: true
        }
        color: "transparent"

        WlrLayershell.namespace: "omarchy-ai-teaching"
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
        exclusionMode: ExclusionMode.Ignore

        // Make clicks pass through everywhere EXCEPT the stage card and the bottom ribbon
        mask: Region {
            item: stageCard
        }

        // ==========================================
        // Floating Teaching Stage Card (Whiteboard)
        // ==========================================
        Rectangle {
            id: stageCard
            width: 860
            height: 560
            x: root.posX >= 0 ? root.posX : (panel.width - width) / 2
            y: root.posY >= 0 ? root.posY : 70
            radius: 18

            color: Qt.rgba(0.04, 0.07, 0.15, 0.95)
            border.color: "#38bdf8"
            border.width: 1.6

            // Specular Inner Border
            Rectangle {
                anchors.fill: parent
                anchors.margins: 1
                radius: parent.radius - 1
                color: "transparent"
                border.color: Qt.rgba(1.0, 1.0, 1.0, 0.08)
                border.width: 1
            }

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                // Header / Title Bar
                Rectangle {
                    Layout.fillWidth: true
                    height: 56
                    radius: 18
                    color: Qt.rgba(0.07, 0.11, 0.22, 0.96)

                    // Drag Handler
                    DragHandler {
                        target: stageCard
                        onActiveChanged: {
                            if (!active) {
                                root.posX = stageCard.x;
                                root.posY = stageCard.y;
                            }
                        }
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 16
                        anchors.rightMargin: 14
                        spacing: 10

                        // Topic Icon & Badge
                        Rectangle {
                            width: 30; height: 30; radius: 6; color: "#0284c7"
                            Text { anchors.centerIn: parent; text: "🎓"; font.pixelSize: 15 }
                        }

                        Text {
                            text: root.topic.toUpperCase()
                            color: "#f8fafc"
                            font.pixelSize: 13
                            font.bold: true
                            font.letterSpacing: 1.1
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }

                        // Mode Selector Pills
                        Row {
                            spacing: 4

                            Repeater {
                                model: [
                                    { mode: "math", icon: "📐", label: "Math" },
                                    { mode: "graph", icon: "📊", label: "Graph" },
                                    { mode: "table", icon: "📋", label: "Table" },
                                    { mode: "bubble_sort", icon: "💡", label: "Sort" },
                                    { mode: "quadcopter", icon: "🚁", label: "Physics" },
                                    { mode: "whiteboard", icon: "✏️", label: "Board" }
                                ]

                                Rectangle {
                                    height: 24
                                    radius: 12
                                    width: pillText.implicitWidth + 14
                                    color: root.viewMode === modelData.mode ? "#0284c7" : "#1e293b"
                                    border.color: root.viewMode === modelData.mode ? "#38bdf8" : "#334155"

                                    Text {
                                        id: pillText
                                        anchors.centerIn: parent
                                        text: modelData.icon + " " + modelData.label
                                        color: root.viewMode === modelData.mode ? "#ffffff" : "#94a3b8"
                                        font.pixelSize: 10
                                        font.bold: true
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: {
                                            root.viewMode = modelData.mode;
                                            if (jarvisCursor) jarvisCursor.pulse(modelData.label);
                                        }
                                    }
                                }
                            }
                        }

                        // Step Counter Pill
                        Rectangle {
                            height: 26
                            radius: 13
                            color: "#0f172a"
                            border.color: "#38bdf8"
                            Layout.preferredWidth: stepText.implicitWidth + 16

                            Text {
                                id: stepText
                                anchors.centerIn: parent
                                text: "STEP " + (root.currentStep + 1) + " / " + root.totalSteps
                                color: "#38bdf8"
                                font.pixelSize: 11
                                font.bold: true
                            }
                        }

                        // Close Button
                        Rectangle {
                            width: 28; height: 28; radius: 14
                            color: closeHover.hovered ? "#ef4444" : "#1e293b"
                            border.color: "#475569"

                            Behavior on color { ColorAnimation { duration: 150 } }

                            Text {
                                anchors.centerIn: parent
                                text: "×"
                                color: "#ffffff"
                                font.pixelSize: 17
                                font.bold: true
                            }

                            HoverHandler { id: closeHover }
                            TapHandler {
                                onTapped: root.active = false
                            }
                        }
                    }
                }

                // Divider line
                Rectangle { Layout.fillWidth: true; height: 1; color: "#1e293b" }

                // Main Content Viewport
                Item {
                    id: viewportArea
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true

                    // View 1: Bubble Sort Algorithm
                    Loader {
                        id: bubbleLoader
                        anchors.fill: parent
                        active: root.viewMode === "bubble_sort"
                        visible: active
                        source: "BubbleSortView.qml"
                    }

                    // View 2: Quadcopter Physics
                    Loader {
                        id: quadLoader
                        anchors.fill: parent
                        active: root.viewMode === "quadcopter"
                        visible: active
                        source: "QuadcopterView.qml"
                    }

                    // View 3: Math & Calculation Derivations
                    Loader {
                        id: mathLoader
                        anchors.fill: parent
                        active: root.viewMode === "math"
                        visible: active
                        source: "MathCalculationView.qml"
                    }

                    // View 4: Graphs, Functions, Curves & Node Networks
                    Loader {
                        id: graphLoader
                        anchors.fill: parent
                        active: root.viewMode === "graph"
                        visible: active
                        source: "GraphChartView.qml"
                    }

                    // View 5: Structured Data & Comparison Tables
                    Loader {
                        id: tableLoader
                        anchors.fill: parent
                        active: root.viewMode === "table"
                        visible: active
                        source: "TableView.qml"
                    }

                    // View 6: Free-form Whiteboard Canvas
                    Loader {
                        id: whiteboardLoader
                        anchors.fill: parent
                        active: root.viewMode === "whiteboard"
                        visible: active
                        source: "WhiteboardCanvas.qml"
                    }

                    // ==========================================
                    // Isolated JARVIS Virtual Mouse Pointer
                    // ==========================================
                    JarvisCursor {
                        id: jarvisCursor
                        targetX: root.targetPenX
                        targetY: root.targetPenY
                        cursorMode: root.cursorStyle
                        activeLabel: root.cursorLabel
                    }
                }
            }
        }

        // ========================================================
        // Bottom Status & Narration Ribbon (Matches user screenshot)
        // ========================================================
        Rectangle {
            id: bottomRibbon
            width: Math.min(880, panel.width - 40)
            height: 74
            radius: 16
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 24
            anchors.horizontalCenter: parent.horizontalCenter

            color: Qt.rgba(0.04, 0.07, 0.14, 0.96)
            border.color: "#1e293b"
            border.width: 1.5

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 4

                // Top workflow bar (Identical to Poinky bottom banner!)
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 16

                    // Step 1: Voice Asking
                    Row {
                        spacing: 8
                        Rectangle { width: 20; height: 20; radius: 10; color: "#1e293b"; border.color: "#38bdf8"; Text { anchors.centerIn: parent; text: "1"; color: "#38bdf8"; font.pixelSize: 11; font.bold: true } }
                        Text { text: "Hold / Speak to Ask"; color: "#94a3b8"; font.pixelSize: 12; font.bold: true }
                    }

                    Text { text: "›"; color: "#475569"; font.pixelSize: 14 }

                    // Step 2: Answering out loud
                    Row {
                        spacing: 8
                        Rectangle { width: 20; height: 20; radius: 10; color: "#1e293b"; border.color: "#38bdf8"; Text { anchors.centerIn: parent; text: "2"; color: "#38bdf8"; font.pixelSize: 11; font.bold: true } }
                        Text { text: "JARVIS answers out loud"; color: "#94a3b8"; font.pixelSize: 12; font.bold: true }
                    }

                    Text { text: "›"; color: "#475569"; font.pixelSize: 14 }

                    // Step 3: Drawing explanation
                    Row {
                        spacing: 8
                        Rectangle { width: 20; height: 20; radius: 10; color: "#0284c7"; Text { anchors.centerIn: parent; text: "3"; color: "#ffffff"; font.pixelSize: 11; font.bold: true } }
                        Text { text: "...and draws the explanation"; color: "#38bdf8"; font.pixelSize: 12; font.bold: true }
                    }
                }

                // Active Narration Text line
                Text {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignHCenter
                    horizontalAlignment: Text.AlignHCenter
                    text: root.activeNarration
                    color: "#f8fafc"
                    font.pixelSize: 13
                    font.weight: Font.Medium
                    elide: Text.ElideRight
                }
            }
        }
    }
}
