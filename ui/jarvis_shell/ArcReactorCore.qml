import QtQuick

Item {
    id: core
    property real energy: 0.3
    property string voiceState: "idle"
    property bool muted: false

    implicitWidth: 320
    implicitHeight: 320

    Canvas {
        id: canvas
        anchors.fill: parent
        property real angleOuter: 0
        property real angleInner: 0
        property real angleGear: 0
        property real pulse: 0

        Timer {
            interval: 16
            repeat: true
            running: true
            onTriggered: {
                var speed = core.voiceState === "speaking" ? 0.04
                          : core.voiceState === "thinking" ? 0.03
                          : core.voiceState === "listening" ? 0.02 : 0.009;
                canvas.angleOuter = (canvas.angleOuter + speed) % (Math.PI * 2);
                canvas.angleInner = (canvas.angleInner - speed * 1.4) % (Math.PI * 2);
                canvas.angleGear = (canvas.angleGear + speed * 0.8) % (Math.PI * 2);
                canvas.pulse = (canvas.pulse + 0.05) % (Math.PI * 2);
                canvas.requestPaint();
            }
        }

        onPaint: {
            var ctx = getContext("2d");
            ctx.reset();
            var cx = width / 2;
            var cy = height / 2;
            var maxR = Math.min(width, height) / 2 - 10;

            var primaryCyan = core.muted ? "#ff3b5c"
                            : core.voiceState === "speaking" ? "#ffb86b"
                            : core.voiceState === "thinking" ? "#a855f7"
                            : "#00e5ff";
            var goldAmber = "#ffb020";

            // 1. Deep Core Ambient Volumetric Glow
            var ambientGrad = ctx.createRadialGradient(cx, cy, 10, cx, cy, maxR);
            ambientGrad.addColorStop(0, "rgba(0, 229, 255, 0.22)");
            ambientGrad.addColorStop(0.5, "rgba(0, 100, 200, 0.08)");
            ambientGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
            ctx.fillStyle = ambientGrad;
            ctx.beginPath();
            ctx.arc(cx, cy, maxR, 0, Math.PI * 2);
            ctx.fill();

            ctx.save();

            // 2. Outermost Segmented Cyan Shield Ring
            ctx.strokeStyle = Qt.rgba(0.0, 0.898, 1.0, 0.22);
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.arc(cx, cy, maxR - 2, 0, Math.PI * 2);
            ctx.stroke();

            // Rotating Shield Segments
            ctx.strokeStyle = primaryCyan;
            ctx.lineWidth = 3.5;
            for (var s = 0; s < 4; s++) {
                var sStart = canvas.angleOuter + s * (Math.PI / 2);
                ctx.beginPath();
                ctx.arc(cx, cy, maxR - 2, sStart, sStart + 0.65);
                ctx.stroke();
            }

            // 3. Rotating Mechanical Gear Ring (24 teeth)
            var gearR = maxR - 14;
            ctx.strokeStyle = goldAmber;
            ctx.lineWidth = 2.0;
            var teeth = 24;
            for (var g = 0; g < teeth; g++) {
                var theta = canvas.angleGear + g * (Math.PI * 2 / teeth);
                var r0 = gearR - 4;
                var r1 = gearR + 4;
                ctx.beginPath();
                ctx.moveTo(cx + Math.cos(theta) * r0, cy + Math.sin(theta) * r0);
                ctx.lineTo(cx + Math.cos(theta) * r1, cy + Math.sin(theta) * r1);
                ctx.stroke();
            }

            // 4. Dense Radial Tick Marks (72 precision marks)
            var tickR = maxR - 28;
            var numTicks = 72;
            for (var t = 0; t < numTicks; t++) {
                var tTheta = t * (Math.PI * 2 / numTicks);
                var isMajor = (t % 6 === 0);
                var len = isMajor ? 8 : 4;
                ctx.strokeStyle = isMajor ? primaryCyan : Qt.rgba(0.0, 0.898, 1.0, 0.35);
                ctx.lineWidth = isMajor ? 1.8 : 1.0;
                ctx.beginPath();
                ctx.moveTo(cx + Math.cos(tTheta) * (tickR - len), cy + Math.sin(tTheta) * (tickR - len));
                ctx.lineTo(cx + Math.cos(tTheta) * tickR, cy + Math.sin(tTheta) * tickR);
                ctx.stroke();
            }

            // 5. Counter-Rotating Middle Heavy Arc Ring (3 segments)
            var midR = maxR - 38;
            ctx.strokeStyle = goldAmber;
            ctx.lineWidth = 2.5;
            for (var m = 0; m < 3; m++) {
                var mStart = canvas.angleInner + m * (Math.PI * 2 / 3);
                ctx.beginPath();
                ctx.arc(cx, cy, midR, mStart, mStart + 1.1);
                ctx.stroke();
            }

            // 6. Inner Transformer Ring with 8 Solenoid Coils
            var coilR = maxR - 54;
            ctx.strokeStyle = primaryCyan;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(cx, cy, coilR, 0, Math.PI * 2);
            ctx.stroke();

            var coils = 8;
            for (var c = 0; c < coils; c++) {
                var cTheta = c * (Math.PI * 2 / coils);
                var padX = cx + Math.cos(cTheta) * coilR;
                var padY = cy + Math.sin(cTheta) * coilR;
                ctx.fillStyle = primaryCyan;
                ctx.beginPath();
                ctx.arc(padX, padY, 3.5, 0, Math.PI * 2);
                ctx.fill();
            }

            // 7. Dark Glass Core Well
            var innerR = maxR - 64;
            var coreGrad = ctx.createRadialGradient(cx, cy, 4, cx, cy, innerR);
            coreGrad.addColorStop(0, "rgba(4, 18, 32, 0.96)");
            coreGrad.addColorStop(0.75, "rgba(1, 8, 18, 0.99)");
            coreGrad.addColorStop(1, Qt.rgba(0.0, 0.898, 1.0, 0.5));
            ctx.fillStyle = coreGrad;
            ctx.beginPath();
            ctx.arc(cx, cy, innerR, 0, Math.PI * 2);
            ctx.fill();

            // 8. Dynamic Energy Pulse Corona
            var pulseR = (innerR - 12) * (0.8 + 0.2 * Math.sin(canvas.pulse));
            var pGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, pulseR);
            pGlow.addColorStop(0, Qt.rgba(0.0, 0.898, 1.0, 0.45 + core.energy * 0.4));
            pGlow.addColorStop(0.6, Qt.rgba(0.0, 0.55, 0.9, 0.2));
            pGlow.addColorStop(1, "rgba(0,0,0,0)");
            ctx.fillStyle = pGlow;
            ctx.beginPath();
            ctx.arc(cx, cy, pulseR, 0, Math.PI * 2);
            ctx.fill();

            ctx.restore();
        }
    }

    // Centered Holographic Stark Typography
    Column {
        anchors.centerIn: parent
        spacing: 5

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "J . A . R . V . I . S ."
            color: "#00e5ff"
            font.family: "JetBrainsMono Nerd Font, monospace"
            font.pixelSize: 22
            font.weight: Font.Black
            font.letterSpacing: 2.8
            style: Text.Outline
            styleColor: Qt.rgba(0, 0.898, 1.0, 0.6)
        }

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 6

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 7
                height: 7
                radius: 3.5
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
                font.pixelSize: 11
                font.weight: Font.Black
                font.letterSpacing: 2.0
            }
        }
    }
}
