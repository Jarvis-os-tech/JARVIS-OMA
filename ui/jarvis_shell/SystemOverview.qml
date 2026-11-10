import QtQuick

SciFiPanel {
    id: overview
    title: "SYSTEM OVERVIEW"
    titleColor: "#00e5ff"
    implicitWidth: 320
    implicitHeight: 200

    property real cpuPercent: 18.0
    property real ramPercent: 52.0
    property real gpuPercent: 32.0
    property real tempC: 67.0
    property real gpuTempC: 76.0

    Column {
        anchors.fill: parent
        spacing: 10

        // 3 Radial Gauges Row
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 24

            // 1. CPU Radial Gauge
            Item {
                width: 76
                height: 76

                Canvas {
                    id: cpuCanvas
                    anchors.fill: parent
                    onPaint: {
                        var ctx = getContext("2d");
                        ctx.reset();
                        var cx = width / 2, cy = height / 2, r = width / 2 - 6;

                        // Outer Segmented Track Ticks
                        ctx.strokeStyle = Qt.rgba(0.0, 0.898, 1.0, 0.18);
                        ctx.lineWidth = 1;
                        for (var i = 0; i < 24; i++) {
                            var th = i * (Math.PI * 2 / 24);
                            ctx.beginPath();
                            ctx.moveTo(cx + Math.cos(th) * (r - 2), cy + Math.sin(th) * (r - 2));
                            ctx.lineTo(cx + Math.cos(th) * (r + 2), cy + Math.sin(th) * (r + 2));
                            ctx.stroke();
                        }

                        // Background Arc
                        ctx.strokeStyle = Qt.rgba(0.0, 0.5, 0.9, 0.18);
                        ctx.lineWidth = 4;
                        ctx.beginPath();
                        ctx.arc(cx, cy, r - 3, 0, Math.PI * 2);
                        ctx.stroke();

                        // Glowing Active Arc
                        ctx.strokeStyle = "#00e5ff";
                        ctx.lineWidth = 4.5;
                        var endA = -Math.PI / 2 + (overview.cpuPercent / 100.0) * Math.PI * 2;
                        ctx.beginPath();
                        ctx.arc(cx, cy, r - 3, -Math.PI / 2, endA);
                        ctx.stroke();

                        // Needle Head Dot
                        ctx.fillStyle = "#ffffff";
                        ctx.beginPath();
                        ctx.arc(cx + Math.cos(endA) * (r - 3), cy + Math.sin(endA) * (r - 3), 3, 0, Math.PI * 2);
                        ctx.fill();
                    }
                    Connections {
                        target: overview
                        function onCpuPercentChanged() { cpuCanvas.requestPaint(); }
                    }
                }

                Column {
                    anchors.centerIn: parent
                    spacing: 1
                    Text { text: "CPU"; color: "#4f7285"; font.pixelSize: 8; font.weight: Font.Bold; anchors.horizontalCenter: parent.horizontalCenter }
                    Text { text: Math.round(overview.cpuPercent) + "%"; color: "#00e5ff"; font.pixelSize: 13; font.weight: Font.Bold; anchors.horizontalCenter: parent.horizontalCenter }
                }
            }

            // 2. RAM Radial Gauge
            Item {
                width: 76
                height: 76

                Canvas {
                    id: ramCanvas
                    anchors.fill: parent
                    onPaint: {
                        var ctx = getContext("2d");
                        ctx.reset();
                        var cx = width / 2, cy = height / 2, r = width / 2 - 6;

                        // Outer Track Ticks
                        ctx.strokeStyle = Qt.rgba(0.0, 0.898, 1.0, 0.18);
                        ctx.lineWidth = 1;
                        for (var i = 0; i < 24; i++) {
                            var th = i * (Math.PI * 2 / 24);
                            ctx.beginPath();
                            ctx.moveTo(cx + Math.cos(th) * (r - 2), cy + Math.sin(th) * (r - 2));
                            ctx.lineTo(cx + Math.cos(th) * (r + 2), cy + Math.sin(th) * (r + 2));
                            ctx.stroke();
                        }

                        // Background Arc
                        ctx.strokeStyle = Qt.rgba(0.0, 0.898, 1.0, 0.18);
                        ctx.lineWidth = 4;
                        ctx.beginPath();
                        ctx.arc(cx, cy, r - 3, 0, Math.PI * 2);
                        ctx.stroke();

                        // Glowing Active Arc
                        ctx.strokeStyle = "#38bdf8";
                        ctx.lineWidth = 4.5;
                        var endA = -Math.PI / 2 + (overview.ramPercent / 100.0) * Math.PI * 2;
                        ctx.beginPath();
                        ctx.arc(cx, cy, r - 3, -Math.PI / 2, endA);
                        ctx.stroke();

                        ctx.fillStyle = "#ffffff";
                        ctx.beginPath();
                        ctx.arc(cx + Math.cos(endA) * (r - 3), cy + Math.sin(endA) * (r - 3), 3, 0, Math.PI * 2);
                        ctx.fill();
                    }
                    Connections {
                        target: overview
                        function onRamPercentChanged() { ramCanvas.requestPaint(); }
                    }
                }

                Column {
                    anchors.centerIn: parent
                    spacing: 1
                    Text { text: "RAM"; color: "#4f7285"; font.pixelSize: 8; font.weight: Font.Bold; anchors.horizontalCenter: parent.horizontalCenter }
                    Text { text: Math.round(overview.ramPercent) + "%"; color: "#38bdf8"; font.pixelSize: 13; font.weight: Font.Bold; anchors.horizontalCenter: parent.horizontalCenter }
                }
            }

            // 3. GPU Radial Gauge
            Item {
                width: 76
                height: 76

                Canvas {
                    id: gpuCanvas
                    anchors.fill: parent
                    onPaint: {
                        var ctx = getContext("2d");
                        ctx.reset();
                        var cx = width / 2, cy = height / 2, r = width / 2 - 6;

                        ctx.strokeStyle = Qt.rgba(1.0, 0.7, 0.1, 0.18);
                        ctx.lineWidth = 1;
                        for (var i = 0; i < 24; i++) {
                            var th = i * (Math.PI * 2 / 24);
                            ctx.beginPath();
                            ctx.moveTo(cx + Math.cos(th) * (r - 2), cy + Math.sin(th) * (r - 2));
                            ctx.lineTo(cx + Math.cos(th) * (r + 2), cy + Math.sin(th) * (r + 2));
                            ctx.stroke();
                        }

                        ctx.strokeStyle = Qt.rgba(1.0, 0.7, 0.1, 0.18);
                        ctx.lineWidth = 4;
                        ctx.beginPath();
                        ctx.arc(cx, cy, r - 3, 0, Math.PI * 2);
                        ctx.stroke();

                        ctx.strokeStyle = "#ffb020";
                        ctx.lineWidth = 4.5;
                        var endA = -Math.PI / 2 + (overview.gpuPercent / 100.0) * Math.PI * 2;
                        ctx.beginPath();
                        ctx.arc(cx, cy, r - 3, -Math.PI / 2, endA);
                        ctx.stroke();

                        ctx.fillStyle = "#ffffff";
                        ctx.beginPath();
                        ctx.arc(cx + Math.cos(endA) * (r - 3), cy + Math.sin(endA) * (r - 3), 3, 0, Math.PI * 2);
                        ctx.fill();
                    }
                    Connections {
                        target: overview
                        function onGpuPercentChanged() { gpuCanvas.requestPaint(); }
                    }
                }

                Column {
                    anchors.centerIn: parent
                    spacing: 1
                    Text { text: "GPU"; color: "#4f7285"; font.pixelSize: 8; font.weight: Font.Bold; anchors.horizontalCenter: parent.horizontalCenter }
                    Text { text: Math.round(overview.gpuPercent) + "%"; color: "#ffb020"; font.pixelSize: 13; font.weight: Font.Bold; anchors.horizontalCenter: parent.horizontalCenter }
                }
            }
        }

        // Live Cyan Sparkline Waveform Graph
        Canvas {
            id: sparkCanvas
            width: parent.width
            height: 28
            property var points: [14, 20, 16, 24, 21, 30, 26, 38, 32, 35, 30, 42, 38, 45, 40, 34, 38, 46, 40, 32]

            onPaint: {
                var ctx = getContext("2d");
                ctx.reset();
                if (points.length < 2) return;
                var step = width / (points.length - 1);
                var grad = ctx.createLinearGradient(0, 0, 0, height);
                grad.addColorStop(0, "rgba(0, 229, 255, 0.4)");
                grad.addColorStop(1, "rgba(0, 229, 255, 0.0)");

                ctx.beginPath();
                ctx.moveTo(0, height);
                for (var i = 0; i < points.length; i++) {
                    var y = height - (points[i] / 50.0) * height;
                    ctx.lineTo(i * step, Math.max(2, y));
                }
                ctx.lineTo(width, height);
                ctx.closePath();
                ctx.fillStyle = grad;
                ctx.fill();

                ctx.beginPath();
                for (var j = 0; j < points.length; j++) {
                    var py = height - (points[j] / 50.0) * height;
                    if (j === 0) ctx.moveTo(0, Math.max(2, py));
                    else ctx.lineTo(j * step, Math.max(2, py));
                }
                ctx.strokeStyle = "#00e5ff";
                ctx.lineWidth = 1.6;
                ctx.stroke();
            }
        }

        // Vitals Footer
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 8
            Text { text: "Temp: " + Math.round(overview.tempC) + "°C"; color: "#4f7285"; font.pixelSize: 8; font.family: "JetBrainsMono Nerd Font, monospace" }
            Text { text: "|"; color: "#1e3040"; font.pixelSize: 8 }
            Text { text: "GPU: " + Math.round(overview.gpuTempC) + "°C"; color: "#4f7285"; font.pixelSize: 8; font.family: "JetBrainsMono Nerd Font, monospace" }
            Text { text: "|"; color: "#1e3040"; font.pixelSize: 8 }
            Text { text: "Power: Balanced 🍃"; color: "#00f0a8"; font.pixelSize: 8; font.family: "JetBrainsMono Nerd Font, monospace" }
        }
    }
}
