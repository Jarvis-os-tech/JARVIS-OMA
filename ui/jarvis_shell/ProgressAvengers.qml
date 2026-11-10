import QtQuick

SciFiPanel {
    id: avengersCard
    title: "MISSION PROGRESS"
    titleColor: "#ffb020"
    implicitWidth: 320
    implicitHeight: 96
    showHeaderAccent: true
    glowColor: "#ffb020"
    borderColor: Qt.rgba(1.0, 0.7, 0.1, 0.35)

    Row {
        anchors.fill: parent
        spacing: 14
        anchors.verticalCenter: parent.verticalCenter

        // Progress Bar Column
        Column {
            width: parent.width - 56
            anchors.verticalCenter: parent.verticalCenter
            spacing: 5

            Item {
                width: parent.width
                height: 14
                Text {
                    anchors.left: parent.left
                    text: "LAUNCHING..."
                    color: "#ffb020"
                    font.family: "JetBrainsMono Nerd Font, monospace"
                    font.pixelSize: 9
                    font.weight: Font.Bold
                    font.letterSpacing: 0.8
                }
                Text {
                    anchors.right: parent.right
                    text: "87%"
                    color: "#ffb020"
                    font.family: "JetBrainsMono Nerd Font, monospace"
                    font.pixelSize: 9
                    font.weight: Font.Bold
                }
            }

            Rectangle {
                width: parent.width
                height: 4
                radius: 2
                color: "#132230"
                Rectangle {
                    width: parent.width * 0.87
                    height: parent.height
                    radius: 2
                    color: "#ffb020"
                }
            }

            Text {
                text: "Preparing your AI workspace..."
                color: "#4f7285"
                font.pixelSize: 8
                font.family: "Inter, sans-serif"
            }
        }

        // Glowing Golden Avengers Emblem
        Item {
            width: 42
            height: 42
            anchors.verticalCenter: parent.verticalCenter

            Canvas {
                id: avengersCanvas
                anchors.fill: parent
                onPaint: {
                    var ctx = getContext("2d");
                    ctx.reset();
                    var cx = width / 2;
                    var cy = height / 2;
                    var r = width / 2 - 2;

                    // Golden Outer Circle with Glow
                    ctx.shadowColor = "#ffb020";
                    ctx.shadowBlur = 8;
                    ctx.strokeStyle = "#ffb020";
                    ctx.lineWidth = 2.0;
                    ctx.beginPath();
                    ctx.arc(cx, cy, r, 0, Math.PI * 2);
                    ctx.stroke();

                    // Inner circle
                    ctx.shadowBlur = 0;
                    ctx.strokeStyle = Qt.rgba(1.0, 0.7, 0.1, 0.4);
                    ctx.lineWidth = 1.0;
                    ctx.beginPath();
                    ctx.arc(cx, cy, r - 3, 0, Math.PI * 2);
                    ctx.stroke();

                    // Avengers 'A' Arrow
                    ctx.fillStyle = "#ffb020";
                    ctx.font = "bold 22px sans-serif";
                    ctx.textAlign = "center";
                    ctx.textBaseline = "middle";
                    ctx.fillText("A", cx, cy + 1);
                }
            }
        }
    }
}
