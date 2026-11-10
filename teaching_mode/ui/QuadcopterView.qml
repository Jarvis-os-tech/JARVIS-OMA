import QtQuick
import QtQuick.Layouts

Item {
    id: root

    property string flightMode: "hover" // "hover" | "yaw_left" | "yaw_right" | "pitch_forward" | "roll_left"
    property real rotorSpeed1: 1.0
    property real rotorSpeed2: 1.0
    property real rotorSpeed3: 1.0
    property real rotorSpeed4: 1.0
    property string activeExplanation: "Hover: All four rotors produce equal thrust; clockwise and counter-clockwise reaction torques cancel out."

    property real pointerX: 0
    property real pointerY: 0

    implicitWidth: 760
    implicitHeight: 460

    function setStep(stepData) {
        if (!stepData) return;
        if (stepData.mode) flightMode = stepData.mode;
        if (stepData.say) activeExplanation = stepData.say;

        if (flightMode === "hover") {
            rotorSpeed1 = 1.0; rotorSpeed2 = 1.0; rotorSpeed3 = 1.0; rotorSpeed4 = 1.0;
            pointerX = droneFrame.x + 150;
            pointerY = droneFrame.y + 150;
        } else if (flightMode === "yaw_left") {
            rotorSpeed1 = 1.4; rotorSpeed2 = 0.6; rotorSpeed3 = 0.6; rotorSpeed4 = 1.4;
            pointerX = droneFrame.x + 50;
            pointerY = droneFrame.y + 50;
        } else if (flightMode === "yaw_right") {
            rotorSpeed1 = 0.6; rotorSpeed2 = 1.4; rotorSpeed3 = 1.4; rotorSpeed4 = 0.6;
            pointerX = droneFrame.x + 250;
            pointerY = droneFrame.y + 50;
        } else if (flightMode === "pitch_forward") {
            rotorSpeed1 = 0.7; rotorSpeed2 = 0.7; rotorSpeed3 = 1.3; rotorSpeed4 = 1.3;
            pointerX = droneFrame.x + 150;
            pointerY = droneFrame.y + 250;
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 24

        // Left Side: Interactive Drone Visual
        Item {
            id: droneFrame
            Layout.preferredWidth: 360
            Layout.fillHeight: true

            // "Front" Direction Indicator
            Row {
                anchors.top: parent.top
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 6
                Text { text: "▲"; color: "#38bdf8"; font.pixelSize: 14 }
                Text { text: "FRONT"; color: "#94a3b8"; font.pixelSize: 12; font.bold: true; font.letterSpacing: 2 }
            }

            // Diagonal Arm 1 (Top-Left to Bottom-Right)
            Rectangle {
                width: 250
                height: 10
                radius: 5
                color: "#334155"
                anchors.centerIn: parent
                rotation: 45
            }

            // Diagonal Arm 2 (Top-Right to Bottom-Left)
            Rectangle {
                width: 250
                height: 10
                radius: 5
                color: "#334155"
                anchors.centerIn: parent
                rotation: -45
            }

            // Central Flight Controller Body
            Rectangle {
                id: bodyBox
                width: 72
                height: 72
                radius: 16
                color: "#1e293b"
                border.color: "#475569"
                border.width: 2
                anchors.centerIn: parent

                // Status LED
                Rectangle {
                    width: 14
                    height: 14
                    radius: 7
                    color: "#10b981"
                    anchors.centerIn: parent
                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        NumberAnimation { from: 1.0; to: 0.4; duration: 600 }
                        NumberAnimation { from: 0.4; to: 1.0; duration: 600 }
                    }
                }
            }

            // --- Rotor 1 (Top Left): Clockwise (CW) ---
            Item {
                id: r1
                width: 90; height: 90
                x: droneFrame.width / 2 - 125 - width / 2
                y: droneFrame.height / 2 - 125 - height / 2

                Rectangle {
                    anchors.fill: parent
                    radius: width / 2
                    color: Qt.rgba(0.2, 0.5, 0.9, 0.15)
                    border.color: root.rotorSpeed1 > 1.1 ? "#60a5fa" : "#3b82f6"
                    border.width: root.rotorSpeed1 > 1.1 ? 3 : 2
                }

                Text {
                    anchors.centerIn: parent
                    text: "1"
                    color: "#60a5fa"
                    font.pixelSize: 18
                    font.bold: true
                }

                // Rotating blade marker (Clockwise)
                Item {
                    anchors.fill: parent
                    RotationAnimation on rotation {
                        from: 0; to: 360; duration: Math.max(100, 700 / root.rotorSpeed1)
                        loops: Animation.Infinite
                    }
                    Rectangle {
                        width: 8; height: 8; radius: 4
                        color: "#93c5fd"
                        anchors.top: parent.top; anchors.horizontalCenter: parent.horizontalCenter
                    }
                }

                Text {
                    anchors.bottom: parent.top; anchors.bottomMargin: 2
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "CW ↷"
                    color: "#93c5fd"
                    font.pixelSize: 11
                    font.bold: true
                }
            }

            // --- Rotor 2 (Top Right): Counter-Clockwise (CCW) ---
            Item {
                id: r2
                width: 90; height: 90
                x: droneFrame.width / 2 + 125 - width / 2
                y: droneFrame.height / 2 - 125 - height / 2

                Rectangle {
                    anchors.fill: parent
                    radius: width / 2
                    color: Qt.rgba(0.6, 0.3, 0.9, 0.15)
                    border.color: root.rotorSpeed2 > 1.1 ? "#c084fc" : "#a855f7"
                    border.width: root.rotorSpeed2 > 1.1 ? 3 : 2
                }

                Text {
                    anchors.centerIn: parent
                    text: "2"
                    color: "#c084fc"
                    font.pixelSize: 18
                    font.bold: true
                }

                // Rotating blade marker (Counter-Clockwise)
                Item {
                    anchors.fill: parent
                    RotationAnimation on rotation {
                        from: 360; to: 0; duration: Math.max(100, 700 / root.rotorSpeed2)
                        loops: Animation.Infinite
                    }
                    Rectangle {
                        width: 8; height: 8; radius: 4
                        color: "#e9d5ff"
                        anchors.top: parent.top; anchors.horizontalCenter: parent.horizontalCenter
                    }
                }

                Text {
                    anchors.bottom: parent.top; anchors.bottomMargin: 2
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "↶ CCW"
                    color: "#e9d5ff"
                    font.pixelSize: 11
                    font.bold: true
                }
            }

            // --- Rotor 3 (Bottom Left): Counter-Clockwise (CCW) ---
            Item {
                id: r3
                width: 90; height: 90
                x: droneFrame.width / 2 - 125 - width / 2
                y: droneFrame.height / 2 + 125 - height / 2

                Rectangle {
                    anchors.fill: parent
                    radius: width / 2
                    color: Qt.rgba(0.6, 0.3, 0.9, 0.15)
                    border.color: root.rotorSpeed3 > 1.1 ? "#c084fc" : "#a855f7"
                    border.width: root.rotorSpeed3 > 1.1 ? 3 : 2
                }

                Text {
                    anchors.centerIn: parent
                    text: "3"
                    color: "#c084fc"
                    font.pixelSize: 18
                    font.bold: true
                }

                Item {
                    anchors.fill: parent
                    RotationAnimation on rotation {
                        from: 360; to: 0; duration: Math.max(100, 700 / root.rotorSpeed3)
                        loops: Animation.Infinite
                    }
                    Rectangle {
                        width: 8; height: 8; radius: 4
                        color: "#e9d5ff"
                        anchors.top: parent.top; anchors.horizontalCenter: parent.horizontalCenter
                    }
                }

                Text {
                    anchors.top: parent.bottom; anchors.topMargin: 2
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "↶ CCW"
                    color: "#e9d5ff"
                    font.pixelSize: 11
                    font.bold: true
                }
            }

            // --- Rotor 4 (Bottom Right): Clockwise (CW) ---
            Item {
                id: r4
                width: 90; height: 90
                x: droneFrame.width / 2 + 125 - width / 2
                y: droneFrame.height / 2 + 125 - height / 2

                Rectangle {
                    anchors.fill: parent
                    radius: width / 2
                    color: Qt.rgba(0.2, 0.5, 0.9, 0.15)
                    border.color: root.rotorSpeed4 > 1.1 ? "#60a5fa" : "#3b82f6"
                    border.width: root.rotorSpeed4 > 1.1 ? 3 : 2
                }

                Text {
                    anchors.centerIn: parent
                    text: "4"
                    color: "#60a5fa"
                    font.pixelSize: 18
                    font.bold: true
                }

                Item {
                    anchors.fill: parent
                    RotationAnimation on rotation {
                        from: 0; to: 360; duration: Math.max(100, 700 / root.rotorSpeed4)
                        loops: Animation.Infinite
                    }
                    Rectangle {
                        width: 8; height: 8; radius: 4
                        color: "#93c5fd"
                        anchors.top: parent.top; anchors.horizontalCenter: parent.horizontalCenter
                    }
                }

                Text {
                    anchors.top: parent.bottom; anchors.topMargin: 2
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "CW ↷"
                    color: "#93c5fd"
                    font.pixelSize: 11
                    font.bold: true
                }
            }
        }

        // Right Side: Flight Control Principles & Status Table
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 14

            Rectangle {
                Layout.fillWidth: true
                height: 48
                radius: 10
                color: "#1e293b"
                border.color: "#38bdf8"
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    Text { text: "Active Mode:"; color: "#94a3b8"; font.pixelSize: 13 }
                    Text {
                        text: root.flightMode.toUpperCase().replace("_", " ")
                        color: "#38bdf8"
                        font.pixelSize: 15
                        font.bold: true
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 12
                color: Qt.rgba(0.08, 0.12, 0.22, 0.8)
                border.color: "#334155"

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 12

                    Text {
                        text: "FLIGHT DYNAMICS PRINCIPLE"
                        color: "#38bdf8"
                        font.pixelSize: 12
                        font.bold: true
                        font.letterSpacing: 1.5
                    }

                    Text {
                        Layout.fillWidth: true
                        text: root.activeExplanation
                        color: "#f8fafc"
                        font.pixelSize: 14
                        wrapMode: Text.WordWrap
                        lineHeight: 1.4
                    }

                    Rectangle { Layout.fillWidth: true; height: 1; color: "#334155" }

                    // Rotor Speed Comparison Grid
                    GridLayout {
                        columns: 2
                        columnSpacing: 16
                        rowSpacing: 10
                        Layout.fillWidth: true

                        Text { text: "Rotors 1 & 4 (CW):"; color: "#93c5fd"; font.pixelSize: 13; font.bold: true }
                        Text {
                            text: (root.rotorSpeed1 * 100).toFixed(0) + "% Speed"
                            color: root.rotorSpeed1 > 1.0 ? "#60a5fa" : "#cbd5e1"
                            font.pixelSize: 13
                            font.bold: true
                        }

                        Text { text: "Rotors 2 & 3 (CCW):"; color: "#e9d5ff"; font.pixelSize: 13; font.bold: true }
                        Text {
                            text: (root.rotorSpeed2 * 100).toFixed(0) + "% Speed"
                            color: root.rotorSpeed2 > 1.0 ? "#c084fc" : "#cbd5e1"
                            font.pixelSize: 13
                            font.bold: true
                        }

                        Text { text: "Net Reaction Torque:"; color: "#94a3b8"; font.pixelSize: 13 }
                        Text {
                            text: root.flightMode === "yaw_left" ? "Counter-Torque Turns Left" : root.flightMode === "yaw_right" ? "Counter-Torque Turns Right" : "0 (Balanced)"
                            color: root.flightMode !== "hover" ? "#facc15" : "#10b981"
                            font.pixelSize: 13
                            font.bold: true
                        }
                    }

                    Item { Layout.fillHeight: true }
                }
            }
        }
    }
}
