import QtQuick
import QtQuick.Layouts

Item {
    id: root

    property string chartTitle: "Algorithmic Time Complexity Growth"
    property string chartType: "line" // "bar" | "line" | "network"
    property int activeIndex: 2
    property string activeMetricNote: "Comparing O(n log n) vs O(n²)"

    // Reported pointer target for JARVIS cursor
    property real pointerX: 340
    property real pointerY: 220

    // Data series for bar chart
    property var barData: [
        { label: "O(1)", value: 5, color: "#22c55e", desc: "Constant Time" },
        { label: "O(log n)", value: 18, color: "#38bdf8", desc: "Logarithmic (Binary Search)" },
        { label: "O(n)", value: 35, color: "#a855f7", desc: "Linear (Single Pass)" },
        { label: "O(n log n)", value: 58, color: "#facc15", desc: "Log-Linear (Merge/Quick Sort)" },
        { label: "O(n²)", value: 92, color: "#f97316", desc: "Quadratic (Bubble/Insertion)" }
    ]

    // Data series for line function plot
    property var lineSeries: [
        { name: "O(n²)", color: "#ef4444", points: [[0,0], [1,1], [2,4], [3,9], [4,16], [5,25], [6,36], [7,49], [8,64]] },
        { name: "O(n log n)", color: "#facc15", points: [[0,0], [1,0], [2,2], [3,4.7], [4,8], [5,11.6], [6,15.5], [7,19.6], [8,24]] },
        { name: "O(n)", color: "#38bdf8", points: [[0,0], [1,1], [2,2], [3,3], [4,4], [5,5], [6,6], [7,7], [8,8]] }
    ]

    // Data for network node graph
    property var nodeData: [
        { id: "A", x: 120, y: 160, label: "Input Token", color: "#38bdf8" },
        { id: "B", x: 260, y: 100, label: "Query Matrix", color: "#a855f7" },
        { id: "C", x: 260, y: 220, label: "Key Matrix", color: "#a855f7" },
        { id: "D", x: 420, y: 160, label: "Softmax Attention", color: "#facc15" },
        { id: "E", x: 560, y: 160, label: "Output Context", color: "#22c55e" }
    ]

    function setStep(payload) {
        if (!payload) return;
        if (payload.title) root.chartTitle = payload.title;
        if (payload.chart_type) root.chartType = payload.chart_type;
        if (payload.bars && Array.isArray(payload.bars)) root.barData = payload.bars;
        if (payload.series && Array.isArray(payload.series)) root.lineSeries = payload.series;
        if (payload.nodes && Array.isArray(payload.nodes)) root.nodeData = payload.nodes;
        if (payload.note) root.activeMetricNote = payload.note;
        if (payload.index !== undefined) root.activeIndex = payload.index;

        if (root.chartType === "bar") {
            var barW = 80;
            var startX = 120 + root.activeIndex * 105;
            root.pointerX = startX + 40;
            root.pointerY = 180;
        } else if (root.chartType === "network") {
            var n = root.nodeData[root.activeIndex % root.nodeData.length];
            if (n) {
                root.pointerX = n.x + 30;
                root.pointerY = n.y + 20;
            }
        } else {
            root.pointerX = 360;
            root.pointerY = 200;
        }

        chartCanvas.requestPaint();
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 12

        // Chart Top Bar with Type Switcher
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Rectangle {
                width: 28; height: 28; radius: 6; color: "#0284c7"
                Text { anchors.centerIn: parent; text: "📊"; font.pixelSize: 14 }
            }

            Column {
                Layout.fillWidth: true
                Text { text: root.chartTitle; color: "#f8fafc"; font.pixelSize: 14; font.bold: true }
                Text { text: root.activeMetricNote; color: "#94a3b8"; font.pixelSize: 11 }
            }

            // Mode Selector Pills
            Row {
                spacing: 6

                Repeater {
                    model: [
                        { mode: "line", label: "📈 Curves" },
                        { mode: "bar", label: "📊 Bars" },
                        { mode: "network", label: "🕸 Graph" }
                    ]

                    Rectangle {
                        width: modeLabel.implicitWidth + 16
                        height: 26
                        radius: 13
                        color: root.chartType === modelData.mode ? "#38bdf8" : "#1e293b"
                        border.color: root.chartType === modelData.mode ? "#0284c7" : "#334155"

                        Text {
                            id: modeLabel
                            anchors.centerIn: parent
                            text: modelData.label
                            color: root.chartType === modelData.mode ? "#0f172a" : "#94a3b8"
                            font.pixelSize: 11
                            font.bold: true
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: {
                                root.chartType = modelData.mode;
                                chartCanvas.requestPaint();
                            }
                        }
                    }
                }
            }
        }

        // Divider
        Rectangle { Layout.fillWidth: true; height: 1; color: "#1e293b" }

        // Main Chart Canvas
        Canvas {
            id: chartCanvas
            Layout.fillWidth: true
            Layout.fillHeight: true

            onPaint: {
                var ctx = getContext("2d");
                ctx.reset();

                var w = width;
                var h = height;

                if (root.chartType === "bar") {
                    // ----------------------------------------
                    // Render Bar Chart
                    // ----------------------------------------
                    var padX = 70;
                    var padY = 40;
                    var availW = w - padX * 2;
                    var availH = h - padY * 2;
                    var count = root.barData.length;
                    var barW = Math.min(76, availW / count - 24);

                    // Draw baseline
                    ctx.strokeStyle = "#334155";
                    ctx.lineWidth = 1.5;
                    ctx.beginPath();
                    ctx.moveTo(padX - 10, h - padY);
                    ctx.lineTo(w - padX + 10, h - padY);
                    ctx.stroke();

                    for (var i = 0; i < count; i++) {
                        var b = root.barData[i];
                        var barX = padX + i * (availW / count) + 12;
                        var barH = (b.value / 100) * (availH - 30);
                        var barY = h - padY - barH;

                        var isAct = (i === root.activeIndex);

                        // Bar Rect
                        ctx.fillStyle = isAct ? "#facc15" : (b.color || "#38bdf8");
                        ctx.strokeStyle = isAct ? "#ca8a04" : "#1e293b";
                        ctx.lineWidth = isAct ? 2 : 1;

                        ctx.beginPath();
                        ctx.roundRect(barX, barY, barW, barH, [6, 6, 0, 0]);
                        ctx.fill();
                        ctx.stroke();

                        // Value on top of bar
                        ctx.fillStyle = "#f8fafc";
                        ctx.font = "bold 12px monospace";
                        ctx.textAlign = "center";
                        ctx.fillText(String(b.value), barX + barW / 2, barY - 8);

                        // Label below bar
                        ctx.fillStyle = isAct ? "#facc15" : "#94a3b8";
                        ctx.font = "bold 11px sans-serif";
                        ctx.fillText(b.label, barX + barW / 2, h - padY + 18);
                    }
                } else if (root.chartType === "network") {
                    // ----------------------------------------
                    // Render Network Graph
                    // ----------------------------------------
                    var nodes = root.nodeData;
                    // Draw edges
                    ctx.strokeStyle = "#475569";
                    ctx.lineWidth = 2;
                    for (var k = 0; k < nodes.length - 1; k++) {
                        var n1 = nodes[k];
                        var n2 = nodes[k + 1];
                        ctx.beginPath();
                        ctx.moveTo(n1.x, n1.y);
                        ctx.lineTo(n2.x, n2.y);
                        ctx.stroke();

                        // Arrow head
                        var angle = Math.atan2(n2.y - n1.y, n2.x - n1.x);
                        var ax = (n1.x + n2.x) / 2;
                        var ay = (n1.y + n2.y) / 2;
                        ctx.fillStyle = "#38bdf8";
                        ctx.beginPath();
                        ctx.moveTo(ax, ay);
                        ctx.lineTo(ax - 10 * Math.cos(angle - 0.5), ay - 10 * Math.sin(angle - 0.5));
                        ctx.lineTo(ax - 10 * Math.cos(angle + 0.5), ay - 10 * Math.sin(angle + 0.5));
                        ctx.closePath();
                        ctx.fill();
                    }

                    // Draw nodes
                    for (var m = 0; m < nodes.length; m++) {
                        var node = nodes[m];
                        var isNodeAct = (m === root.activeIndex);

                        ctx.fillStyle = isNodeAct ? "#facc15" : (node.color || "#38bdf8");
                        ctx.strokeStyle = "#0f172a";
                        ctx.lineWidth = 3;
                        ctx.beginPath();
                        ctx.arc(node.x, node.y, 22, 0, 2 * Math.PI);
                        ctx.fill();
                        ctx.stroke();

                        // Node ID
                        ctx.fillStyle = "#0f172a";
                        ctx.font = "bold 13px monospace";
                        ctx.textAlign = "center";
                        ctx.fillText(node.id, node.x, node.y + 5);

                        // Label under node
                        ctx.fillStyle = isNodeAct ? "#facc15" : "#cbd5e1";
                        ctx.font = "bold 11px sans-serif";
                        ctx.fillText(node.label, node.x, node.y + 36);
                    }
                } else {
                    // ----------------------------------------
                    // Render Line Chart / Mathematical Curves
                    // ----------------------------------------
                    var ox = 60;
                    var oy = h - 40;
                    var graphW = w - ox - 40;
                    var graphH = oy - 30;

                    // Grid lines
                    ctx.strokeStyle = "rgba(255,255,255,0.06)";
                    ctx.lineWidth = 1;
                    for (var gy = 0; gy <= 4; gy++) {
                        var gridY = oy - gy * (graphH / 4);
                        ctx.beginPath();
                        ctx.moveTo(ox, gridY);
                        ctx.lineTo(ox + graphW, gridY);
                        ctx.stroke();
                    }

                    // Axes
                    ctx.strokeStyle = "#475569";
                    ctx.lineWidth = 2;
                    ctx.beginPath();
                    ctx.moveTo(ox, oy - graphH);
                    ctx.lineTo(ox, oy);
                    ctx.lineTo(ox + graphW, oy);
                    ctx.stroke();

                    // Plot each line curve
                    for (var s = 0; s < root.lineSeries.length; s++) {
                        var ser = root.lineSeries[s];
                        var pts = ser.points;
                        if (!pts || pts.length === 0) continue;

                        ctx.strokeStyle = ser.color || "#38bdf8";
                        ctx.lineWidth = 2.8;
                        ctx.beginPath();

                        for (var p = 0; p < pts.length; p++) {
                            var px = ox + (pts[p][0] / 8) * graphW;
                            var py = oy - (pts[p][1] / 64) * graphH;
                            if (p === 0) ctx.moveTo(px, py);
                            else ctx.lineTo(px, py);
                        }
                        ctx.stroke();

                        // Legend label at the end of line
                        var lastPt = pts[pts.length - 1];
                        var lx = ox + (lastPt[0] / 8) * graphW + 6;
                        var ly = oy - (lastPt[1] / 64) * graphH;
                        ctx.fillStyle = ser.color;
                        ctx.font = "bold 11px monospace";
                        ctx.textAlign = "left";
                        ctx.fillText(ser.name, Math.min(lx, w - 80), ly);
                    }
                }
            }
        }
    }
}
