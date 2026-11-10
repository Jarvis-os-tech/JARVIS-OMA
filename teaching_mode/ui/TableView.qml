import QtQuick
import QtQuick.Layouts

Item {
    id: root

    property string tableTitle: "Sorting Algorithm Performance Comparison"
    property string tableSubtitle: "Time & Space Complexities Across Data Distributions"
    property int activeRow: 0
    property int activeCol: 1

    // Reported pointer target for JARVIS cursor
    property real pointerX: 280
    property real pointerY: 160

    property var columnsList: [
        { key: "algo", label: "Algorithm", width: 180 },
        { key: "best", label: "Best Case", width: 120 },
        { key: "avg", label: "Average Case", width: 130 },
        { key: "worst", label: "Worst Case", width: 130 },
        { key: "space", label: "Space", width: 100 },
        { key: "stable", label: "Stable", width: 90 }
    ]

    property var rowsList: [
        {
            algo: "Quick Sort",
            best: "O(n log n)",
            avg: "O(n log n)",
            worst: "O(n²)",
            space: "O(log n)",
            stable: "No",
            tag: "Divide & Conquer"
        },
        {
            algo: "Merge Sort",
            best: "O(n log n)",
            avg: "O(n log n)",
            worst: "O(n log n)",
            space: "O(n)",
            stable: "Yes",
            tag: "Guaranteed O(n log n)"
        },
        {
            algo: "Heap Sort",
            best: "O(n log n)",
            avg: "O(n log n)",
            worst: "O(n log n)",
            space: "O(1)",
            stable: "No",
            tag: "In-Place"
        },
        {
            algo: "Bubble Sort",
            best: "O(n)",
            avg: "O(n²)",
            worst: "O(n²)",
            space: "O(1)",
            stable: "Yes",
            tag: "Educational"
        },
        {
            algo: "Insertion Sort",
            best: "O(n)",
            avg: "O(n²)",
            worst: "O(n²)",
            space: "O(1)",
            stable: "Yes",
            tag: "Fast for small N"
        }
    ]

    function setStep(payload) {
        if (!payload) return;
        if (payload.title) root.tableTitle = payload.title;
        if (payload.subtitle) root.tableSubtitle = payload.subtitle;
        if (payload.columns && Array.isArray(payload.columns)) root.columnsList = payload.columns;
        if (payload.rows && Array.isArray(payload.rows)) root.rowsList = payload.rows;

        if (payload.row !== undefined) root.activeRow = payload.row;
        if (payload.col !== undefined) root.activeCol = payload.col;

        // Position pointer over the active cell
        var startY = 130 + root.activeRow * 48;
        var startX = 60 + root.activeCol * 130;
        root.pointerX = startX + 40;
        root.pointerY = startY + 20;
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 12

        // Table Header
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Rectangle {
                width: 28; height: 28; radius: 6; color: "#0284c7"
                Text { anchors.centerIn: parent; text: "📋"; font.pixelSize: 14 }
            }

            Column {
                Layout.fillWidth: true
                Text { text: root.tableTitle; color: "#f8fafc"; font.pixelSize: 14; font.bold: true }
                Text { text: root.tableSubtitle; color: "#94a3b8"; font.pixelSize: 11 }
            }

            Rectangle {
                height: 24
                radius: 12
                color: "#1e293b"
                border.color: "#38bdf8"
                Layout.preferredWidth: rowCountText.implicitWidth + 16

                Text {
                    id: rowCountText
                    anchors.centerIn: parent
                    text: root.rowsList.length + " ROWS"
                    color: "#38bdf8"
                    font.pixelSize: 10
                    font.bold: true
                }
            }
        }

        // Table Column Headers
        Rectangle {
            Layout.fillWidth: true
            height: 36
            radius: 8
            color: Qt.rgba(0.08, 0.14, 0.26, 0.95)
            border.color: "#334155"

            Row {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 8

                Repeater {
                    model: root.columnsList
                    Item {
                        width: modelData.width || 120
                        height: parent.height

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.label.toUpperCase()
                            color: "#94a3b8"
                            font.pixelSize: 11
                            font.bold: true
                            font.letterSpacing: 0.8
                        }
                    }
                }
            }
        }

        // Table Rows List
        ListView {
            id: rowsView
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 6
            clip: true
            model: root.rowsList

            delegate: Rectangle {
                id: rowDelegate
                width: rowsView.width
                height: 44
                radius: 8

                property bool isRowActive: index === root.activeRow
                color: isRowActive ? Qt.rgba(0.12, 0.22, 0.38, 0.95) : (index % 2 === 0 ? Qt.rgba(0.06, 0.10, 0.18, 0.75) : Qt.rgba(0.04, 0.08, 0.14, 0.6))
                border.color: isRowActive ? "#facc15" : Qt.rgba(0.2, 0.3, 0.45, 0.4)
                border.width: isRowActive ? 1.8 : 1

                Behavior on color { ColorAnimation { duration: 150 } }
                Behavior on border.color { ColorAnimation { duration: 150 } }

                Row {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    spacing: 8

                    Repeater {
                        model: root.columnsList
                        Item {
                            width: modelData.width || 120
                            height: parent.height

                            property bool isCellActive: rowDelegate.isRowActive && index === root.activeCol

                            Rectangle {
                                anchors.fill: parent
                                anchors.margins: 2
                                radius: 4
                                color: parent.isCellActive ? Qt.rgba(0.98, 0.8, 0.08, 0.22) : "transparent"
                                border.color: parent.isCellActive ? "#facc15" : "transparent"
                                border.width: 1

                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.left: parent.left
                                    anchors.leftMargin: 6
                                    text: String(rowDelegate.modelData[modelData.key] || "")
                                    color: parent.parent.isCellActive ? "#facc15" : (index === 0 ? "#f8fafc" : "#cbd5e1")
                                    font.pixelSize: 13
                                    font.bold: index === 0 || parent.parent.isCellActive
                                    font.family: index > 0 && index < 5 ? "monospace" : "sans-serif"
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    root.activeRow = rowDelegate.index;
                                    root.activeCol = index;
                                    root.pointerX = mouseX + rowDelegate.x;
                                    root.pointerY = mouseY + rowDelegate.y;
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
