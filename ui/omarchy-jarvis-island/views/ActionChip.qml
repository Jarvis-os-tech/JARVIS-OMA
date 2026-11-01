import QtQuick
import QtQuick.Controls
import qs.Commons

Button {
  id: chip
  property color tone: "#73e0ed"
  property bool emphasized: false
  property bool reducedMotion: false
  property string family: "sans-serif"
  property int pixelSize: 11
  implicitHeight: 34
  implicitWidth: contentItem.implicitWidth + 28
  hoverEnabled: true
  scale: down ? 0.96 : hovered ? 1.025 : 1
  Accessible.name: text
  Behavior on scale { NumberAnimation { duration: chip.reducedMotion ? 0 : 150; easing.type: Easing.OutCubic } }
  contentItem: Text {
    text: chip.text; color: chip.enabled ? (chip.emphasized ? "#10232a" : chip.tone) : "#667185"
    font.family: chip.family; font.pixelSize: chip.pixelSize; font.weight: Font.DemiBold
    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
    textFormat: Text.PlainText
  }
  background: Rectangle {
    radius: height / 2
    color: chip.emphasized && chip.enabled ? chip.tone : Util.alpha(chip.tone, chip.hovered ? 0.16 : 0.07)
    border.color: chip.activeFocus ? chip.tone : Util.alpha(chip.tone, chip.enabled ? 0.26 : 0.08)
    border.width: chip.activeFocus ? 2 : 1
    Behavior on color { ColorAnimation { duration: chip.reducedMotion ? 0 : 160 } }
  }
}
