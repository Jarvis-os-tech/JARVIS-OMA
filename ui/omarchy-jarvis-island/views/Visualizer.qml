import QtQuick

// level >= 0 displays measured input; -1 is an activity animation, not a meter.
Row {
  id: viz
  property bool playing: false
  property bool reducedMotion: false
  property real level: -1
  property color color: "white"
  property int bars: 5
  property real barWidth: 3
  property real maxHeight: 18
  property real phase: 0
  spacing: Math.max(1, barWidth * 0.85)
  height: maxHeight
  NumberAnimation on phase {
    from: 0; to: Math.PI * 2; duration: 1100; loops: Animation.Infinite
    running: viz.playing && viz.visible && !viz.reducedMotion && viz.level < 0
  }
  Repeater {
    model: viz.bars
    Rectangle {
      required property int index
      readonly property real envelope: viz.level >= 0
        ? Math.min(1, Math.max(0, viz.level)) * (0.48 + 0.52 * Math.sin((index + 1) * Math.PI / (viz.bars + 1)))
        : viz.reducedMotion ? 0.38 : 0.28 + 0.68 * Math.pow(Math.sin(viz.phase + index * 0.8), 2)
      anchors.verticalCenter: parent.verticalCenter
      width: viz.barWidth
      height: Math.max(viz.barWidth, viz.maxHeight * (viz.playing ? envelope : 0.14))
      radius: width / 2
      opacity: viz.playing ? 0.65 + 0.35 * envelope : 0.3
      gradient: Gradient {
        GradientStop { position: 0; color: Qt.lighter(viz.color, 1.18) }
        GradientStop { position: 1; color: viz.color }
      }
      Behavior on height { NumberAnimation { duration: viz.reducedMotion ? 0 : 130; easing.type: Easing.OutCubic } }
      Behavior on opacity { NumberAnimation { duration: 180 } }
    }
  }
}
