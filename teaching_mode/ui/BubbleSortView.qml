import QtQuick
import QtQuick.Layouts

Item {
    id: root

    property var arrayData: [5, 1, 4, 2, 8]
    property int comparingA: -1
    property int comparingB: -1
    property int swappingA: -1
    property int swappingB: -1
    property var sortedIndices: []
    property int comparisonCount: 0
    property int swapCount: 0
    property string explanationText: "Ready to trace Bubble Sort"
    property real pointerX: 0
    property real pointerY: 0

    implicitWidth: 760
    implicitHeight: 420

    function setStep(stepData) {
        if (!stepData) return;
        if (stepData.data && Array.isArray(stepData.data)) {
            arrayData = stepData.data;
        }
        if (stepData.action === "compare") {
            comparingA = stepData.indices ? stepData.indices[0] : -1;
            comparingB = stepData.indices ? stepData.indices[1] : -1;
            swappingA = -1;
            swappingB = -1;
            comparisonCount++;
            explanationText = "Comparing elements at index " + comparingA + " (" + arrayData[comparingA] + ") and " + comparingB + " (" + arrayData[comparingB] + ")";
            updatePointer();
        } else if (stepData.action === "swap") {
            swappingA = stepData.indices ? stepData.indices[0] : -1;
            swappingB = stepData.indices ? stepData.indices[1] : -1;
            swapCount++;
            explanationText = "Swap: " + arrayData[swappingA] + " > " + arrayData[swappingB] + " → Swapping positions";
            // Perform visual swap in array
            var arr = arrayData.slice();
            var tmp = arr[swappingA];
            arr[swappingA] = arr[swappingB];
            arr[swappingB] = tmp;
            arrayData = arr;
            updatePointer();
        } else if (stepData.action === "sorted_mark") {
            if (stepData.indices) {
                var s = sortedIndices.slice();
                for (var i = 0; i < stepData.indices.length; i++) {
                    if (s.indexOf(stepData.indices[i]) === -1) s.push(stepData.indices[i]);
                }
                sortedIndices = s;
            }
            comparingA = -1;
            comparingB = -1;
            explanationText = "Element settled in final sorted position";
        } else if (stepData.action === "complete") {
            comparingA = -1;
            comparingB = -1;
            swappingA = -1;
            swappingB = -1;
            var all = [];
            for (var j = 0; j < arrayData.length; j++) all.push(j);
            sortedIndices = all;
            explanationText = "Bubble sort complete! Array is fully sorted.";
        }
        if (stepData.say) {
            explanationText = stepData.say;
        }
    }

    function updatePointer() {
        var targetIdx = (swappingA >= 0) ? swappingA : (comparingA >= 0) ? comparingA : 0;
        var barW = 76;
        var gap = 24;
        var totalW = arrayData.length * (barW + gap) - gap;
        var startX = (barsContainer.width - totalW) / 2;
        root.pointerX = barsContainer.x + startX + targetIdx * (barW + gap) + barW / 2;
        root.pointerY = barsContainer.y + 60;
    }

    Column {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 18

        // Top Status & Complexity Badges
        RowLayout {
            width: parent.width
            spacing: 12

            Rectangle {
                height: 32
                radius: 8
                color: "#1e293b"
                border.color: "#334155"
                Layout.preferredWidth: compLabel.implicitWidth + 24

                Text {
                    id: compLabel
                    anchors.centerIn: parent
                    text: "Comparisons: " + root.comparisonCount
                    color: "#facc15"
                    font.pixelSize: 13
                    font.bold: true
                }
            }

            Rectangle {
                height: 32
                radius: 8
                color: "#1e293b"
                border.color: "#334155"
                Layout.preferredWidth: swapLabel.implicitWidth + 24

                Text {
                    id: swapLabel
                    anchors.centerIn: parent
                    text: "Swaps: " + root.swapCount
                    color: "#f97316"
                    font.pixelSize: 13
                    font.bold: true
                }
            }

            Rectangle {
                height: 32
                radius: 8
                color: "#1e293b"
                border.color: "#334155"
                Layout.preferredWidth: oLabel.implicitWidth + 24

                Text {
                    id: oLabel
                    anchors.centerIn: parent
                    text: "Time: O(n²) | Space: O(1)"
                    color: "#38bdf8"
                    font.pixelSize: 13
                    font.bold: true
                }
            }

            Item { Layout.fillWidth: true }

            Rectangle {
                height: 32
                radius: 8
                color: "#0f766e"
                Layout.preferredWidth: stableLabel.implicitWidth + 20

                Text {
                    id: stableLabel
                    anchors.centerIn: parent
                    text: "Stable Algorithm"
                    color: "#5eead4"
                    font.pixelSize: 12
                    font.bold: true
                }
            }
        }

        // Live Action Banner
        Rectangle {
            width: parent.width
            height: 44
            radius: 10
            color: Qt.rgba(0.08, 0.15, 0.28, 0.7)
            border.color: root.swappingA >= 0 ? "#f97316" : root.comparingA >= 0 ? "#facc15" : "#38bdf8"
            border.width: 1.5

            RowLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 10

                Text {
                    text: root.swappingA >= 0 ? "🔄" : root.comparingA >= 0 ? "🔍" : "ℹ️"
                    font.pixelSize: 16
                }

                Text {
                    Layout.fillWidth: true
                    text: root.explanationText
                    color: "#f8fafc"
                    font.pixelSize: 14
                    font.bold: true
                    elide: Text.ElideRight
                }
            }
        }

        // Main Visualization Canvas (Bars Area)
        Item {
            id: barsContainer
            width: parent.width
            height: 250

            Row {
                anchors.centerIn: parent
                spacing: 24

                Repeater {
                    model: root.arrayData.length

                    Item {
                        id: barItem
                        property int val: root.arrayData[index]
                        property bool isComparing: (index === root.comparingA || index === root.comparingB)
                        property bool isSwapping: (index === root.swappingA || index === root.swappingB)
                        property bool isSorted: root.sortedIndices.indexOf(index) !== -1

                        width: 76
                        height: 240

                        Column {
                            anchors.bottom: parent.bottom
                            anchors.horizontalCenter: parent.horizontalCenter
                            spacing: 8

                            // Pointer Arrow above active bar
                            Item {
                                width: 24
                                height: 24
                                anchors.horizontalCenter: parent.horizontalCenter
                                opacity: barItem.isComparing || barItem.isSwapping ? 1.0 : 0.0

                                Behavior on opacity { NumberAnimation { duration: 200 } }

                                Text {
                                    anchors.centerIn: parent
                                    text: "▼"
                                    color: barItem.isSwapping ? "#f97316" : "#facc15"
                                    font.pixelSize: 18
                                }
                            }

                            // The Bar
                            Rectangle {
                                id: barRect
                                width: 76
                                height: Math.max(48, barItem.val * 24)
                                radius: 10
                                color: {
                                    if (barItem.isSwapping) return "#f97316";
                                    if (barItem.isComparing) return "#facc15";
                                    if (barItem.isSorted) return "#10b981";
                                    return "#38bdf8";
                                }

                                border.color: Qt.lighter(color, 1.3)
                                border.width: barItem.isComparing || barItem.isSwapping ? 2.5 : 1.0

                                Behavior on color { ColorAnimation { duration: 250 } }
                                Behavior on height { NumberAnimation { duration: 300; easing.type: Easing.OutBack } }

                                // Value label inside bar
                                Text {
                                    anchors.centerIn: parent
                                    text: String(barItem.val)
                                    color: (barItem.isComparing) ? "#0f172a" : "#ffffff"
                                    font.pixelSize: 22
                                    font.bold: true
                                }
                            }

                            // Index label under bar
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: "[" + index + "]"
                                color: "#94a3b8"
                                font.pixelSize: 12
                                font.family: "monospace"
                            }
                        }
                    }
                }
            }
        }
    }
}
