import QtQuick

Canvas {
    id: canvas

    property var ops: []
    property real pointerX: 200
    property real pointerY: 150

    implicitWidth: 760
    implicitHeight: 420

    onOpsChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()

    function setOps(newOps) {
        if (!newOps) return;
        ops = newOps;
        if (ops.length > 0) {
            var last = ops[ops.length - 1];
            if (last.x !== undefined && last.y !== undefined) {
                pointerX = last.x;
                pointerY = last.y;
            }
        }
    }

    onPaint: {
        var ctx = getContext("2d");
        ctx.reset();
        ctx.clearRect(0, 0, width, height);

        // Draw light grid
        ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
        ctx.lineWidth = 1;
        var step = 30;
        for (var x = 0; x < width; x += step) {
            ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, height); ctx.stroke();
        }
        for (var y = 0; y < height; y += step) {
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke();
        }

        for (var i = 0; i < ops.length; i++) {
            var op = ops[i];
            ctx.save();
            var col = op.color || "#38bdf8";
            ctx.fillStyle = col;
            ctx.strokeStyle = col;
            ctx.lineWidth = op.width || 2.5;

            if (op.op === "box") {
                var bx = op.x || 40, by = op.y || 40, bw = op.w || 160, bh = op.h || 60;
                ctx.fillStyle = "rgba(30, 41, 59, 0.85)";
                ctx.beginPath();
                ctx.roundRect(bx, by, bw, bh, 8);
                ctx.fill();
                ctx.strokeStyle = col;
                ctx.stroke();
                if (op.text) {
                    ctx.fillStyle = "#f8fafc";
                    ctx.font = "bold " + (op.size || 16) + "px sans-serif";
                    ctx.textAlign = "center";
                    ctx.textBaseline = "middle";
                    ctx.fillText(op.text, bx + bw / 2, by + bh / 2);
                }
            } else if (op.op === "circle" || op.op === "dot") {
                var cx = op.x || 100, cy = op.y || 100, cr = op.r || 24;
                ctx.beginPath();
                ctx.arc(cx, cy, cr, 0, Math.PI * 2);
                ctx.fillStyle = Qt.rgba(0.12, 0.16, 0.24, 0.9);
                ctx.fill();
                ctx.strokeStyle = col;
                ctx.stroke();
                if (op.text) {
                    ctx.fillStyle = "#f8fafc";
                    ctx.font = "bold " + (op.size || 14) + "px sans-serif";
                    ctx.textAlign = "center";
                    ctx.textBaseline = "middle";
                    ctx.fillText(op.text, cx, cy);
                }
            } else if (op.op === "line") {
                var pts = op.points || [[op.x1 || 0, op.y1 || 0], [op.x2 || 100, op.y2 || 100]];
                if (pts.length >= 2) {
                    ctx.beginPath();
                    ctx.moveTo(pts[0][0], pts[0][1]);
                    for (var p = 1; p < pts.length; p++) ctx.lineTo(pts[p][0], pts[p][1]);
                    ctx.stroke();
                }
            } else if (op.op === "arrow") {
                var fromX = op.from ? op.from[0] : (op.x1 || 50);
                var fromY = op.from ? op.from[1] : (op.y1 || 50);
                var toX = op.to ? op.to[0] : (op.x2 || 200);
                var toY = op.to ? op.to[1] : (op.y2 || 50);

                ctx.beginPath();
                ctx.moveTo(fromX, fromY);
                ctx.lineTo(toX, toY);
                ctx.stroke();

                // Arrow head
                var angle = Math.atan2(toY - fromY, toX - fromX);
                var headLen = 12;
                ctx.beginPath();
                ctx.moveTo(toX, toY);
                ctx.lineTo(toX - headLen * Math.cos(angle - Math.PI / 6), toY - headLen * Math.sin(angle - Math.PI / 6));
                ctx.lineTo(toX - headLen * Math.cos(angle + Math.PI / 6), toY - headLen * Math.sin(angle + Math.PI / 6));
                ctx.closePath();
                ctx.fillStyle = col;
                ctx.fill();

                if (op.label) {
                    ctx.fillStyle = "#94a3b8";
                    ctx.font = "13px sans-serif";
                    ctx.textAlign = "center";
                    ctx.fillText(op.label, (fromX + toX) / 2, (fromY + toY) / 2 - 8);
                }
            } else if (op.op === "text") {
                ctx.fillStyle = col || "#f8fafc";
                ctx.font = (op.bold ? "bold " : "") + (op.size || 18) + "px sans-serif";
                ctx.textAlign = op.align || "left";
                ctx.fillText(op.text || "", op.x || 40, op.y || 40);
            } else if (op.op === "check") {
                var chkX = op.x || 100, chkY = op.y || 100;
                ctx.beginPath();
                ctx.moveTo(chkX - 10, chkY);
                ctx.lineTo(chkX - 2, chkY + 9);
                ctx.lineTo(chkX + 13, chkY - 12);
                ctx.strokeStyle = col || "#22c55e";
                ctx.lineWidth = 3;
                ctx.lineCap = "round";
                ctx.lineJoin = "round";
                ctx.stroke();
            } else if (op.op === "number") {
                var numX = op.x || 50, numY = op.y || 50, numN = op.n || 1;
                ctx.beginPath();
                ctx.arc(numX, numY, 14, 0, Math.PI * 2);
                ctx.fillStyle = Qt.rgba(0.98, 0.8, 0.08, 0.2);
                ctx.fill();
                ctx.strokeStyle = "#facc15";
                ctx.lineWidth = 2;
                ctx.stroke();

                ctx.fillStyle = "#facc15";
                ctx.font = "bold 13px sans-serif";
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText(String(numN), numX, numY);
            } else if (op.op === "mark") {
                var mx = op.x || 100, my = op.y || 100, mw = op.w || 120, mh = op.h || 30;
                if (op.style === "underline") {
                    ctx.beginPath();
                    ctx.moveTo(mx, my + mh);
                    ctx.quadraticCurveTo(mx + mw / 2, my + mh + 4, mx + mw, my + mh);
                    ctx.strokeStyle = "#facc15";
                    ctx.lineWidth = 2.5;
                    ctx.stroke();
                } else {
                    ctx.beginPath();
                    ctx.ellipse(mx + mw / 2, my + mh / 2, mw / 2 + 10, mh / 2 + 8, 0, 0, Math.PI * 2);
                    ctx.strokeStyle = "#facc15";
                    ctx.lineWidth = 2.5;
                    ctx.stroke();
                }
            } else if (op.op === "clear") {
                ctx.clearRect(0, 0, width, height);
            }
            ctx.restore();
        }
    }
}
