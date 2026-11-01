import QtQuick
import qs.Commons

Rectangle {
  id: metric
  property string label: ""
  property real value: -1
  property color tone: "#73e0ed"
  property string fontFamily: "sans-serif"
  property bool reducedMotion: false
  property real scaleFactor: 1
  implicitWidth: 124 * scaleFactor
  implicitHeight: 38 * scaleFactor
  radius: 11 * scaleFactor
  color: Util.alpha(tone, 0.065)
  border.color: Util.alpha(tone, 0.12)
  Text {
    anchors.left: parent.left; anchors.leftMargin: 11 * metric.scaleFactor
    anchors.verticalCenter: parent.verticalCenter
    text: metric.label
    font.family: metric.fontFamily; font.pixelSize: 10 * metric.scaleFactor
    color: "#a4b2c5"
  }
  Text {
    anchors.right: parent.right; anchors.rightMargin: 11 * metric.scaleFactor
    anchors.verticalCenter: parent.verticalCenter
    text: metric.value < 0 ? "--" : Math.round(metric.value * 100) + "%"
    font.family: metric.fontFamily; font.pixelSize: 12 * metric.scaleFactor
    font.weight: Font.DemiBold; color: "#e6edf7"
  }
  Rectangle {
    x: 11 * metric.scaleFactor; y: parent.height - 5 * metric.scaleFactor
    width: (parent.width - 22 * metric.scaleFactor) * Math.max(0, Math.min(1, metric.value))
    height: metric.scaleFactor; radius: height / 2
    color: metric.tone; opacity: 0.65
    Behavior on width { NumberAnimation { duration: metric.reducedMotion ? 0 : 400; easing.type: Easing.OutCubic } }
  }
}
