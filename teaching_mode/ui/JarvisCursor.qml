import QtQuick
import QtQuick.Layouts

Item {
    id: root

    // Target coordinates (relative to root parent or screen)
    property real targetX: 300
    property real targetY: 200

    // Cursor style mode: "pointer" | "pen" | "laser" | "hand"
    property string cursorMode: "pointer"
    property bool isDrawing: false
    property string activeLabel: ""
    property color accentColor: "#facc15" // Amber / Gold

    width: 40
    height: 40
    x: targetX
    y: targetY
    z: 9999

    // Smooth physics-like spring interpolation
    Behavior on x {
        NumberAnimation {
            duration: 280
            easing.type: Easing.OutCubic
        }
    }
    Behavior on y {
        NumberAnimation {
            duration: 280
            easing.type: Easing.OutCubic
        }
    }

    // Trigger click / pulse ripple effect
    function pulse(label) {
        if (label) root.activeLabel = label;
        rippleAnim.restart();
    }

    // -------------------------------------------------------------
    // Ripple / Pulse Click Wave
    // -------------------------------------------------------------
    Rectangle {
        id: rippleRing
        anchors.centerIn: parent
        width: 12
        height: 12
        radius: width / 2
        color: "transparent"
        border.color: root.accentColor
        border.width: 2.5
        opacity: 0

        ParallelAnimation {
            id: rippleAnim
            NumberAnimation {
                target: rippleRing
                property: "width"
                from: 10
                to: 54
                duration: 500
                easing.type: Easing.OutQuad
            }
            NumberAnimation {
                target: rippleRing
                property: "height"
                from: 10
                to: 54
                duration: 500
                easing.type: Easing.OutQuad
            }
            NumberAnimation {
                target: rippleRing
                property: "opacity"
                from: 0.95
                to: 0.0
                duration: 500
                easing.type: Easing.OutQuad
            }
        }
    }

    // -------------------------------------------------------------
    // Luminous Aura / Glow around pointer
    // -------------------------------------------------------------
    Rectangle {
        anchors.centerIn: parent
        width: 32
        height: 32
        radius: 16
        color: Qt.rgba(0.98, 0.80, 0.08, 0.18)
        border.color: Qt.rgba(0.98, 0.80, 0.08, 0.35)
        border.width: 1
    }

    // -------------------------------------------------------------
    // Pointer Visual Rendering
    // -------------------------------------------------------------
    Canvas {
        id: cursorCanvas
        anchors.fill: parent

        onPaint: {
            var ctx = getContext("2d");
            ctx.reset();

            if (root.cursorMode === "pen") {
                // Tilted Stylus / Drawing Pen
                ctx.save();
                ctx.translate(6, 6);
                ctx.rotate(-15 * Math.PI / 180);

                // Pen Body
                ctx.fillStyle = "#facc15";
                ctx.strokeStyle = "#92400e";
                ctx.lineWidth = 1.8;

                ctx.beginPath();
                ctx.moveTo(0, 0);       // Pen nib tip
                ctx.lineTo(8, -4);
                ctx.lineTo(24, 18);
                ctx.lineTo(16, 26);
                ctx.lineTo(-4, 8);
                ctx.closePath();
                ctx.fill();
                ctx.stroke();

                // Nib accent
                ctx.fillStyle = "#1e293b";
                ctx.beginPath();
                ctx.moveTo(0, 0);
                ctx.lineTo(4, -2);
                ctx.lineTo(6, 4);
                ctx.closePath();
                ctx.fill();

                ctx.restore();
            } else if (root.cursorMode === "laser") {
                // Laser Point / Spotlight
                ctx.fillStyle = "#ef4444";
                ctx.strokeStyle = "#ffffff";
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.arc(20, 20, 7, 0, 2 * Math.PI);
                ctx.fill();
                ctx.stroke();
            } else {
                // Default Pointer: Sleek Gold Arrow with dark border
                ctx.fillStyle = "#facc15";
                ctx.strokeStyle = "#78350f";
                ctx.lineWidth = 1.8;
                ctx.lineJoin = "round";

                ctx.beginPath();
                ctx.moveTo(4, 4);       // Tip
                ctx.lineTo(30, 16);     // Right barb
                ctx.lineTo(19, 19);     // Inner notch
                ctx.lineTo(16, 30);     // Bottom barb
                ctx.closePath();
                ctx.fill();
                ctx.stroke();

                // Sleek specular highlight inside arrow
                ctx.fillStyle = "#fef08a";
                ctx.beginPath();
                ctx.moveTo(7, 7);
                ctx.lineTo(23, 15);
                ctx.lineTo(18, 17);
                ctx.closePath();
                ctx.fill();
            }
        }
    }

    // -------------------------------------------------------------
    // Floating Tooltip / Label beside the Cursor
    // -------------------------------------------------------------
    Rectangle {
        id: cursorTooltip
        visible: root.activeLabel.length > 0
        x: 32
        y: 12
        height: 24
        radius: 6
        color: Qt.rgba(0.08, 0.12, 0.22, 0.95)
        border.color: root.accentColor
        border.width: 1.2
        width: tooltipText.implicitWidth + 14

        Text {
            id: tooltipText
            anchors.centerIn: parent
            text: root.activeLabel
            color: "#f8fafc"
            font.pixelSize: 11
            font.bold: true
        }

        // Auto-fade tooltip after 2.5 seconds
        Timer {
            id: tooltipTimer
            interval: 2500
            running: root.activeLabel.length > 0
            onTriggered: root.activeLabel = ""
        }
    }
}
