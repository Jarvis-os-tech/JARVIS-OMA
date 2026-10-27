import QtQuick
import QtQuick.Layouts
import qs.Commons

Rectangle {
  id: control
  property string icon: ""
  property string label: ""
  property real value: 0
  property color tone: "#73e0ed"
  property string fontFamily: "sans-serif"
  property bool reducedMotion: false
  property real scaleFactor: 1
  signal valueRequested(real next)

  implicitHeight: 38 * scaleFactor
  radius: 12 * scaleFactor
  color: Util.alpha(tone, hovered ? 0.095 : 0.055)
  border.color: activeFocus ? tone : Util.alpha(tone, hovered ? 0.24 : 0.12)
  border.width: activeFocus ? 2 : 1
  focus: false
  activeFocusOnTab: true
  Accessible.name: label
  Accessible.role: Accessible.Slider
  Accessible.description: Math.round(value * 100) + " percent"
  readonly property bool hovered: hover.hovered
  readonly property real safeValue: Math.max(0, Math.min(1, value))

  Behavior on color { ColorAnimation { duration: control.reducedMotion ? 0 : 150 } }

  RowLayout {
    anchors.fill: parent
    anchors.leftMargin: 10 * control.scaleFactor
    anchors.rightMargin: 10 * control.scaleFactor
    spacing: 7 * control.scaleFactor

    Text {
      text: control.icon
      font.family: control.fontFamily
      font.pixelSize: 13 * control.scaleFactor
      color: control.tone
    }
    Text {
      text: control.label
      font.family: control.fontFamily
      font.pixelSize: 9 * control.scaleFactor
      font.weight: Font.DemiBold
      color: "#a4b2c5"
    }
    Item {
      id: track
      Layout.fillWidth: true
      Layout.preferredHeight: 16 * control.scaleFactor

      Rectangle {
        anchors.left: parent.left; anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        height: 4 * control.scaleFactor; radius: height / 2
        color: "#273345"
      }
      Rectangle {
        anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
        width: parent.width * control.safeValue
        height: 4 * control.scaleFactor; radius: height / 2
        color: control.tone
        Behavior on width {
          enabled: !drag.pressed && !control.reducedMotion
          NumberAnimation { duration: 170; easing.type: Easing.OutCubic }
        }
      }
      Rectangle {
        x: Math.max(0, Math.min(parent.width - width, parent.width * control.safeValue - width / 2))
        anchors.verticalCenter: parent.verticalCenter
        width: (drag.pressed || control.hovered ? 11 : 8) * control.scaleFactor
        height: width; radius: width / 2
        color: "#f3f7fb"
        border.color: Util.alpha(control.tone, 0.45)
        Behavior on width { NumberAnimation { duration: control.reducedMotion ? 0 : 120 } }
      }
      MouseArea {
        id: drag
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        function commit(px) {
          control.valueRequested(Math.max(0, Math.min(1, px / Math.max(1, width))))
        }
        onPressed: function(mouse) { control.forceActiveFocus(); commit(mouse.x) }
        onPositionChanged: function(mouse) { if (pressed) commit(mouse.x) }
      }
    }
    Text {
      Layout.preferredWidth: 28 * control.scaleFactor
      horizontalAlignment: Text.AlignRight
      text: Math.round(control.safeValue * 100) + "%"
      font.family: control.fontFamily
      font.pixelSize: 9 * control.scaleFactor
      font.weight: Font.DemiBold
      color: "#e6edf7"
    }
  }

  HoverHandler { id: hover }
  Keys.onLeftPressed: valueRequested(Math.max(0, safeValue - 0.05))
  Keys.onRightPressed: valueRequested(Math.min(1, safeValue + 0.05))
  Keys.onDownPressed: valueRequested(Math.max(0, safeValue - 0.05))
  Keys.onUpPressed: valueRequested(Math.min(1, safeValue + 0.05))
}
