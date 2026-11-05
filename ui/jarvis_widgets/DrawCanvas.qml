import QtQuick

Canvas {
    id: drawing
    property var node
    property var viewContext
    implicitHeight: node.height || 240
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onNodeChanged: requestPaint()
    Connections { target: drawing.viewContext; function onFormStateChanged() { drawing.requestPaint(); } }
    onPaint: {
        const ctx = getContext("2d");
        ctx.reset(); ctx.clearRect(0, 0, width, height);
        const scale = Math.min(width, height) / 1000;
        function n(s, key, fallback) {
            const value = drawing.viewContext.value(s[key] ?? fallback);
            return typeof value === "number" && isFinite(value) ? Math.max(-2000, Math.min(2000, value)) : 0;
        }
        for (const s of drawing.node.shapes) {
            ctx.save();
            ctx.fillStyle = s.fill || "#76DDD2"; ctx.strokeStyle = s.stroke || "#76DDD2";
            ctx.lineWidth = Math.max(1, Math.min(10, n(s, "width", 2)));
            const x = n(s, "x", 0) * width / 1000, y = n(s, "y", 0) * height / 1000;
            if (s.type === "rect") {
                ctx.fillRect(x, y, n(s, "w", 100) * width / 1000, n(s, "h", 100) * height / 1000);
            } else if (s.type === "circle") {
                ctx.beginPath(); ctx.arc(x, y, Math.abs(n(s, "r", 30)) * scale, 0, 2 * Math.PI); ctx.fill();
            } else if (s.type === "line") {
                ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(n(s, "x2", 100) * width / 1000, n(s, "y2", 100) * height / 1000); ctx.stroke();
            } else {
                ctx.font = "14px sans-serif"; ctx.fillText(drawing.viewContext.format(s.text), x, y);
            }
            ctx.restore();
        }
    }
}
