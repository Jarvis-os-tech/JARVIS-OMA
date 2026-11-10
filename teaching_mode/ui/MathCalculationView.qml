import QtQuick
import QtQuick.Layouts

Item {
    id: root

    property string equationTitle: "Quadratic Formula & Root Derivation"
    property string mainFormula: "a·x² + b·x + c = 0"
    property int activeStepIndex: 0
    property string activeRule: "Discriminant Evaluation"

    // Reported pointer target for JARVIS isolated cursor
    property real pointerX: 250
    property real pointerY: 180

    // Math derivation steps model
    property var stepsList: [
        {
            num: 1,
            title: "Standard Form Equation",
            math: "2x² - 8x + 6 = 0",
            rule: "Identify coefficients: a = 2, b = -8, c = 6",
            highlight: "coefficients"
        },
        {
            num: 2,
            title: "Compute Discriminant (Δ)",
            math: "Δ = b² - 4ac = (-8)² - 4(2)(6)",
            rule: "Δ = 64 - 48 = 16  (Δ > 0 → 2 Real Roots)",
            highlight: "discriminant"
        },
        {
            num: 3,
            title: "Apply Quadratic Solution",
            math: "x = (-b ± √Δ) / 2a",
            rule: "Substitute: x = (8 ± √16) / 4",
            highlight: "quadratic_root"
        },
        {
            num: 4,
            title: "Calculate Distinct Roots",
            math: "x₁ = (8 + 4)/4 = 3,   x₂ = (8 - 4)/4 = 1",
            rule: "Roots found: x ∈ { 1, 3 }",
            highlight: "final_roots"
        }
    ]

    // Variables & values inspector
    property var variablesList: [
        { name: "a", value: "2", role: "Leading coeff" },
        { name: "b", value: "-8", role: "Linear coeff" },
        { name: "c", value: "6", role: "Constant term" },
        { name: "Δ", value: "16", role: "Positive (> 0)" },
        { name: "x₁", value: "3", role: "First solution" },
        { name: "x₂", value: "1", role: "Second solution" }
    ]

    function setStep(payload) {
        if (!payload) return;
        if (payload.title) root.equationTitle = payload.title;
        if (payload.formula) root.mainFormula = payload.formula;
        if (payload.steps && Array.isArray(payload.steps)) root.stepsList = payload.steps;
        if (payload.variables && Array.isArray(payload.variables)) root.variablesList = payload.variables;

        if (payload.step !== undefined) {
            root.activeStepIndex = Math.min(Math.max(0, payload.step - 1), root.stepsList.length - 1);
        }

        // Update pointer to point at the active step card
        var targetCardY = 120 + root.activeStepIndex * 70;
        root.pointerX = 280;
        root.pointerY = targetCardY;
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 16

        // Left Column: Step-by-Step Derivation Cards
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 10

            // Main Formula Display Card
            Rectangle {
                Layout.fillWidth: true
                height: 64
                radius: 12
                color: Qt.rgba(0.08, 0.14, 0.26, 0.9)
                border.color: "#38bdf8"
                border.width: 1.5

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 14

                    Rectangle {
                        width: 32; height: 32; radius: 8; color: "#0284c7"
                        Text { anchors.centerIn: parent; text: "∑"; color: "#ffffff"; font.pixelSize: 18; font.bold: true }
                    }

                    Column {
                        Layout.fillWidth: true
                        Text { text: root.equationTitle; color: "#94a3b8"; font.pixelSize: 11; font.bold: true }
                        Text { text: root.mainFormula; color: "#38bdf8"; font.pixelSize: 17; font.bold: true; font.family: "monospace" }
                    }
                }
            }

            // Steps List
            ListView {
                id: stepsView
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 8
                clip: true
                model: root.stepsList

                delegate: Rectangle {
                    id: stepDelegate
                    width: stepsView.width
                    height: 64
                    radius: 10

                    property bool isActive: index === root.activeStepIndex
                    color: isActive ? Qt.rgba(0.12, 0.22, 0.38, 0.95) : Qt.rgba(0.06, 0.10, 0.18, 0.75)
                    border.color: isActive ? "#facc15" : Qt.rgba(0.2, 0.3, 0.45, 0.5)
                    border.width: isActive ? 2 : 1

                    Behavior on color { ColorAnimation { duration: 200 } }
                    Behavior on border.color { ColorAnimation { duration: 200 } }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        spacing: 12

                        // Step Number Badge
                        Rectangle {
                            width: 26; height: 26; radius: 13
                            color: stepDelegate.isActive ? "#facc15" : "#1e293b"
                            border.color: stepDelegate.isActive ? "#ca8a04" : "#475569"

                            Text {
                                anchors.centerIn: parent
                                text: String(modelData.num || (index + 1))
                                color: stepDelegate.isActive ? "#1e293b" : "#94a3b8"
                                font.pixelSize: 12
                                font.bold: true
                            }
                        }

                        // Formula & Rule
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2

                            Text {
                                text: modelData.math || ""
                                color: stepDelegate.isActive ? "#ffffff" : "#cbd5e1"
                                font.pixelSize: 14
                                font.bold: true
                                font.family: "monospace"
                            }
                            Text {
                                text: modelData.rule || ""
                                color: stepDelegate.isActive ? "#38bdf8" : "#64748b"
                                font.pixelSize: 11
                            }
                        }

                        // Active Indicator Tag
                        Rectangle {
                            visible: stepDelegate.isActive
                            height: 22
                            radius: 11
                            color: Qt.rgba(0.98, 0.8, 0.08, 0.2)
                            border.color: "#facc15"
                            Layout.preferredWidth: activeTagText.implicitWidth + 14

                            Text {
                                id: activeTagText
                                anchors.centerIn: parent
                                text: "CALCULATING"
                                color: "#facc15"
                                font.pixelSize: 9
                                font.bold: true
                            }
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            root.activeStepIndex = index;
                            root.pointerX = stepDelegate.x + 180;
                            root.pointerY = stepDelegate.y + 110;
                        }
                    }
                }
            }
        }

        // Right Column: State & Variables Inspector
        Rectangle {
            Layout.preferredWidth: 240
            Layout.fillHeight: true
            radius: 14
            color: Qt.rgba(0.06, 0.10, 0.20, 0.95)
            border.color: "#1e293b"
            border.width: 1.5

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 10

                RowLayout {
                    spacing: 8
                    Text { text: "📐"; font.pixelSize: 14 }
                    Text { text: "VARIABLES & STATE"; color: "#94a3b8"; font.pixelSize: 11; font.bold: true; font.letterSpacing: 1 }
                }

                Rectangle { Layout.fillWidth: true; height: 1; color: "#1e293b" }

                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 8
                    clip: true
                    model: root.variablesList

                    delegate: Rectangle {
                        width: parent.width
                        height: 38
                        radius: 8
                        color: Qt.rgba(0.1, 0.15, 0.26, 0.8)
                        border.color: "#334155"

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 8
                            spacing: 8

                            Text {
                                text: modelData.name + " ="
                                color: "#facc15"
                                font.pixelSize: 13
                                font.bold: true
                                font.family: "monospace"
                            }

                            Text {
                                text: modelData.value
                                color: "#38bdf8"
                                font.pixelSize: 13
                                font.bold: true
                                font.family: "monospace"
                                Layout.fillWidth: true
                            }

                            Text {
                                text: modelData.role || ""
                                color: "#64748b"
                                font.pixelSize: 10
                            }
                        }
                    }
                }
            }
        }
    }
}
