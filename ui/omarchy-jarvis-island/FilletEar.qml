import QtQuick

// Coucou signature notch ear fillet.
// Concave arc blending the top screen bezel into the vertical edge of the island.
Canvas {
  id: root

  property bool isRight: false
  property color earColor: "#050608"
  property real earRadius: 14

  width: earRadius
  height: earRadius

  onEarColorChanged: requestPaint()
  onEarRadiusChanged: requestPaint()

  onPaint: {
    var ctx = getContext("2d");
    ctx.reset();
    ctx.fillStyle = root.earColor;

    if (!root.isRight) {
      // Left ear: fills top-right quadrant outside circle at (0, r)
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(width, 0);
      ctx.lineTo(width, height);
      ctx.arcTo(width, 0, 0, 0, root.earRadius);
      ctx.closePath();
      ctx.fill();
    } else {
      // Right ear: fills top-left quadrant outside circle at (r, r)
      ctx.beginPath();
      ctx.moveTo(width, 0);
      ctx.lineTo(0, 0);
      ctx.lineTo(0, height);
      ctx.arcTo(0, 0, width, 0, root.earRadius);
      ctx.closePath();
      ctx.fill();
    }
  }
}
