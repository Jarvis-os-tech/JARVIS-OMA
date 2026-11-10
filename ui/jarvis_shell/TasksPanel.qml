import QtQuick

SciFiPanel {
    id: tasksCard
    title: "TODAY'S TASKS"
    titleColor: "#00e5ff"
    implicitWidth: 320
    implicitHeight: 140

    property var taskList: [
        { title: "Complete LearnIQ Prototype", done: true },
        { title: "Finish Java Lab Programs", done: true },
        { title: "Study DBMS Concepts", done: false }
    ]

    Column {
        anchors.fill: parent
        spacing: 8

        Repeater {
            model: tasksCard.taskList

            Rectangle {
                width: parent.width
                height: 24
                color: "transparent"

                Row {
                    spacing: 8
                    anchors.verticalCenter: parent.verticalCenter

                    Rectangle {
                        width: 16
                        height: 16
                        radius: 8
                        color: modelData.done ? Qt.rgba(0, 0.94, 0.66, 0.2) : "transparent"
                        border.color: modelData.done ? "#00f0a8" : "#4f7285"
                        border.width: 1.5

                        Text {
                            visible: modelData.done
                            anchors.centerIn: parent
                            text: "✓"
                            color: "#00f0a8"
                            font.pixelSize: 10
                            font.bold: true
                        }
                    }

                    Text {
                        text: modelData.title
                        color: modelData.done ? "#d8f6ff" : "#8aa2b3"
                        font.family: "Inter, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Medium
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        var copy = [].concat(tasksCard.taskList);
                        copy[index].done = !copy[index].done;
                        tasksCard.taskList = copy;
                    }
                }
            }
        }
    }
}
