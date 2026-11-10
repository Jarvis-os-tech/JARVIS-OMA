import QtQuick

Item {
    id: core
    property real energy: 0.3
    property string voiceState: "idle"
    property bool muted: false

    implicitWidth: 260
    implicitHeight: 260

    Canvas {
        id: canvas
        anchors.fill: parent
        property real angle1: 0
        property real angle2: 0
        property real pulse: 0

        Timer {
            interval: 16
            repeat: true
            running: true
            onTriggered: {
                var speed = core.voiceState === "speaking" ? 0.035
                          : core.voiceState === "thinking" ? 0.025
                          : core.voiceState === "listening" ? 0.018 : 0.008;
                canvas.angle1 = (canvas.angle1 + speed) % (Math.PI * 2);
                canvas.angle2 = (canvas.angle2 - speed * 1.3) % (Math.PI * 2);
                canvas.pulse = (canvas.pulse + 0.04) % (Math.PI * 2);
                canvas.requestPaint();
            }
        }

        onPaint: {
            var ctx = getContext("2d");
            ctx.reset();
            var cx = width / 2;
            var cy = height / 2;
            var maxR = Math.min(width, height) / 2 - 8;

            var primaryColor = core.muted ? "#ff3b5c"
                             : core.voiceState === "speaking" ? "#ffb86b"
                             : core.voiceState === "thinking" ? "#a855f7"
                             : "#00e5ff";
            var accentGold = "#ffb020";

            // 1. Outer Dark Halo Glow
            var outerGlow = ctx.createRadialGradient(cx, cy, maxR * 0.5, cx, cy, maxR);
            outerGlow.addColorStop(0, "rgba(0, 229, 255, 0.0)");
            outerGlow.addColorStop(0.8, "rgba(0, 229, 255, 0.08)");
            outerGlow.addColorStop(1, "rgba(0, 0, 0, 0)");
            ctx.fillStyle = outerGlow;
            ctx.beginPath();
            ctx.arc(cx, cy, maxR, 0, Math.PI * 2);
            ctx.fill();

            // 2. Outer Segmented Cyan Ring
            ctx.save();
            ctx.strokeStyle = Qt.rgba(0.0, 0.898, 1.0, 0.25);
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.arc(cx, cy, maxR - 4, 0, Math.PI * 2);
            ctx.stroke();

            // Rotating Cyan Arcs
            ctx.strokeStyle = primaryColor;
            ctx.lineWidth = 2.5;
            for (var i = 0; i < 4; i++) {
                var aStart = canvas.angle1 + i * (Math.PI / 2);
                ctx.beginPath();
                ctx.arc(cx, cy, maxR - 4, aStart, aStart + 0.55);
                ctx.stroke();
            }

            // 3. Middle Counter-Rotating Amber / Gold Ring
            ctx.strokeStyle = accentGold;
            ctx.lineWidth = 1.8;
            for (var j = 0; j < 3; j++) {
                var bStart = canvas.angle2 + j * (Math.PI * 2 / 3);
                ctx.beginPath();
                ctx.arc(cx, cy, maxR - 16, bStart, bStart + 0.75);
                ctx.stroke();
            }

            // 4. Tick Marks Ring
            ctx.strokeStyle = Qt.rgba(0.0, 0.898, 1.0, 0.5);
            ctx.lineWidth = 1;
            var numTicks = 36;
            for (var t = 0; t < numTicks; t++) {
                var theta = t * (Math.PI * 2 / numTicks);
                var rIn = maxR - 26;
                var rOut = (t % 3 === 0) ? maxR - 20 : maxR - 23;
                ctx.beginPath();
                ctx.moveTo(cx + Math.cos(theta) * rIn, cy + Math.sin(theta) * rIn);
                ctx.lineTo(cx + Math.cos(theta) * rOut, cy + Math.sin(theta) * rOut);
                ctx.stroke();
            }

            // 5. Inner Concentric Glowing Circle
            var innerR = maxR - 34;
            ctx.strokeStyle = primaryColor;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(cx, cy, innerR, 0, Math.PI * 2);
            ctx.stroke();

            // 6. Deep Dark Core Background
            var coreGrad = ctx.createRadialGradient(cx, cy, 2, cx, cy, innerR);
            coreGrad.addColorStop(0, "rgba(5, 18, 32, 0.95)");
            coreGrad.addColorStop(0.7, "rgba(2, 8, 16, 0.98)");
            coreGrad.addColorStop(1, Qt.rgba(0.0, 0.898, 1.0, 0.3));
            ctx.fillStyle = coreGrad;
            ctx.beginPath();
            ctx.arc(cx, cy, innerR - 2, 0, Math.PI * 2);
            ctx.fill();

            // 7. Ambient Pulsing Core Waves
            var pRad = (innerR - 10) * (0.8 + 0.2 * Math.sin(canvas.pulse));
            var pGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, pRad);
            pGlow.addColorStop(0, Qt.rgba(0.0, 0.898, 1.0, 0.3 + core.energy * 0.3));
            pGlow.addColorStop(0.6, Qt.rgba(0.0, 0.5, 0.9, 0.15));
            pGlow.addColorStop(1, "rgba(0,0,0,0)");
            ctx.fillStyle = pGlow;
            ctx.beginPath();
            ctx.arc(cx, cy, pRad, 0, Math.PI * 2);
            ctx.fill();

            ctx.restore();
        }
    }

    // Centered Holographic Typography
    Column {
        anchors.centerIn: parent
        spacing: 4

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "J . A . R . V . I . S ."
            color: "#00e5ff"
            font.family: "JetBrainsMono Nerd Font, monospace"
            font.pixelSize: 18
            font.weight: Font.Black
            font.letterSpacing: 2.0
            style: Text.Outline
            styleColor: Qt.rgba(0, 0.898, 1.0, 0.4)
        }

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 5

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 6
                height: 6
                radius: 3
                color: core.muted ? "#ff3b5c" : "#00f0a8"
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: core.muted ? "MUTED"
                    : core.voiceState === "speaking" ? "SPEAKING"
                    : core.voiceState === "thinking" ? "THINKING"
                    : core.voiceState === "listening" ? "LISTENING"
                    : "ONLINE"
                color: core.muted ? "#ff8da1" : "#00f0a8"
                font.family: "JetBrainsMono Nerd Font, monospace"
                font.pixelSize: 10
                font.weight: Font.Bold
                font.letterSpacing: 1.5
            }
        }
    }
}
