import QtQuick

SciFiPanel {
    id: memoryPanel
    title: "MEMORY & CONTEXT"
    titleColor: "#00e5ff"
    implicitWidth: 320
    implicitHeight: 96
    showHeaderAccent: false

    Row {
        anchors.fill: parent
        spacing: 12

        Column {
            width: parent.width - 80
            spacing: 3
            anchors.verticalCenter: parent.verticalCenter

            Text {
                text: "Active Memory: JARVIS.BRAIN"
                color: "#d8f6ff"
                font.pixelSize: 9
                font.weight: Font.DemiBold
            }

            Text {
                text: "Last Activity: 2m ago"
                color: "#4f7285"
                font.pixelSize: 8
            }

            Text {
                text: "\"Building the future... one conversation at a time.\""
                color: "#7dd3fc"
                font.pixelSize: 8
                font.italic: true
            }
        }

        // Mini Spectrum Sparkline
        Canvas {
            id: memCanvas
            width: 68
            height: 44
            anchors.verticalCenter: parent.verticalCenter
            property real tick: 0

            Timer {
                interval: 40
                repeat: true
                running: true
                onTriggered: {
                    memCanvas.tick = (memCanvas.tick + 0.12) % (Math.PI * 2);
                    memCanvas.requestPaint();
                }
            }

            onPaint: {
                var ctx = getContext("2d");
                ctx.reset();
                var count = 12;
                var barW = width / count - 2;
                for (var i = 0; i < count; i++) {
                    var h = height * (0.25 + 0.7 * (0.5 + 0.5 * Math.sin(memCanvas.tick + i * 0.7)));
                    var grad = ctx.createLinearGradient(0, height - h, 0, height);
                    grad.addColorStop(0, "#00ffff");
                    grad.addColorStop(1, "#005588");
                    ctx.fillStyle = grad;
                    ctx.fillRect(i * (barW + 2), height - h, barW, h);
                }
            }
        }
    }
}
