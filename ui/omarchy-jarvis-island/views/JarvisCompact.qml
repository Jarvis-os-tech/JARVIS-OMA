import QtQuick
import QtQuick.Layouts
import qs.Commons
import ".."

Item {
  id: view
  property var island: null
  readonly property var bridge: island ? island.bridge : null
  readonly property color tone: bridge ? bridge.stateTone : "#8b99ae"
  RowLayout {
    anchors.fill: parent
    anchors.leftMargin: island ? island.s(10) : 10
    anchors.rightMargin: island ? island.s(9) : 9
    spacing: island ? island.s(9) : 9
    Companion {
      Layout.preferredWidth: island ? island.s(25) : 25
      Layout.preferredHeight: Layout.preferredWidth
      voiceState: bridge ? bridge.displayState : "offline"
      isMuted: bridge ? bridge.jarvisMuted : false
      audioLevel: bridge ? bridge.audioLevel : 0
      reducedMotion: island ? island.reducedMotion : false
    }
    ColumnLayout {
      Layout.fillWidth: true; spacing: 0
      Text {
        text: bridge ? bridge.stateLabel : "Offline"
        font.family: island ? island.textFamily : "sans-serif"
        font.pixelSize: island ? island.f(10) : 10
        font.weight: Font.DemiBold; color: view.tone
        textFormat: Text.PlainText
      }
      Text {
        Layout.fillWidth: true
        text: bridge ? bridge.jarvisActivity : "JARVIS is offline"
        font.family: island ? island.textFamily : "sans-serif"
        font.pixelSize: island ? island.f(9) : 9
        color: island ? island.fgDim : "#94a3b8"
        elide: Text.ElideRight; textFormat: Text.PlainText
      }
    }
    Visualizer {
      playing: bridge ? bridge.isJarvisActive : false
      level: bridge && bridge.displayState === "listening" ? bridge.audioLevel : -1
      color: view.tone
      reducedMotion: island ? island.reducedMotion : false
      barWidth: island ? island.s(2) : 2
      maxHeight: island ? island.s(17) : 17
      Layout.alignment: Qt.AlignVCenter
    }
    BatteryStatus {
      island: view.island
      Layout.alignment: Qt.AlignVCenter
    }
  }
}
