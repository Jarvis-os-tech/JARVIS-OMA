import QtQuick
import QtQuick.Shapes

Item {
    id: panel
    property string title: ""
    property string titleColor: "#00e5ff"
    property real cutSize: 14
    property bool showBrackets: true
    property bool showHeaderAccent: true
    property color borderColor: Qt.rgba(0.0, 0.898, 1.0, 0.4)
    property color glowColor: "#00e5ff"
    default property alias content: bodyContainer.data

    implicitWidth: 320
    implicitHeight: 200

    // 1. Chamfered Sci-Fi Panel Frame (45° cut corners)
    Shape {
        id: bgShape
        anchors.fill: parent
        layer.enabled: true

        ShapePath {
            strokeColor: panel.borderColor
            strokeWidth: 1.2
            fillGradient: LinearGradient {
                x1: 0; y1: 0; x2: panel.width; y2: panel.height
                GradientStop { position: 0.0; color: "#d9051424" }
                GradientStop { position: 0.5; color: "#e6030a14" }
                GradientStop { position: 1.0; color: "#f2010408" }
            }

            startX: panel.cutSize; startY: 0
            PathLine { x: panel.width - panel.cutSize * 1.5; y: 0 }
            PathLine { x: panel.width; y: panel.cutSize * 1.5 }
            PathLine { x: panel.width; y: panel.height - panel.cutSize }
            PathLine { x: panel.width - panel.cutSize; y: panel.height }
            PathLine { x: panel.cutSize * 1.5; y: panel.height }
            PathLine { x: 0; y: panel.height - panel.cutSize * 1.5 }
            PathLine { x: 0; y: panel.cutSize }
            PathLine { x: panel.cutSize; y: 0 }
        }
    }

    // 2. Corner Cybernetic Brackets
    Canvas {
        id: bracketsCanvas
        anchors.fill: parent
        visible: panel.showBrackets
        onPaint: {
            var ctx = getContext("2d");
            ctx.reset();
            ctx.strokeStyle = panel.glowColor;
            ctx.lineWidth = 1.8;

            // Top-Left Cyber Bracket
            ctx.beginPath();
            ctx.moveTo(2, 24); ctx.lineTo(2, 6); ctx.lineTo(24, 6);
            ctx.stroke();

            // Bottom-Right Cyber Bracket
            ctx.beginPath();
            ctx.moveTo(width - 24, height - 6); ctx.lineTo(width - 2, height - 6); ctx.lineTo(width - 2, height - 24);
            ctx.stroke();

            // Accent Ticks
            ctx.fillStyle = panel.glowColor;
            ctx.fillRect(4, 4, 3, 3);
            ctx.fillRect(width - 7, height - 7, 3, 3);
        }
    }

    // 3. Header Bar with Title & Hazard Stripes
    Item {
        id: header
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 12
        height: 22

        Row {
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8

            Text {
                text: panel.title
                color: panel.titleColor
                font.family: "JetBrainsMono Nerd Font, monospace"
                font.pixelSize: 11
                font.weight: Font.Black
                font.letterSpacing: 1.5
            }
        }

        // Amber Hazard Striping on Top-Right of Panel
        Row {
            anchors.right: parent.right
            anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            spacing: 3
            visible: panel.showHeaderAccent

            Repeater {
                model: 4
                Rectangle {
                    width: 3; height: 10
                    color: "#ffb020"
                    rotation: 25
                }
            }
        }
    }

    // 4. Panel Content Area
    Item {
        id: bodyContainer
        anchors.top: header.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 12
        anchors.topMargin: 4
    }
}
