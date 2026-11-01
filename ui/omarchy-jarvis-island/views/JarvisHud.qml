import QtQuick
import QtQuick.Layouts
import Quickshell
import qs.Commons
import ".."

Item {
  id: view
  property var island: null
  readonly property var bridge: island ? island.bridge : null
  readonly property color tone: bridge ? bridge.stateTone : "#8b99ae"
  readonly property bool calm: island ? island.reducedMotion : false
  readonly property real unit: island ? island.s(100) / 100 : 1
  function px(value) { return island ? island.s(value) : value }
  function font(value) { return island ? island.f(value) : value }
  readonly property string family: island ? island.textFamily : "sans-serif"

  SystemClock { id: clock; precision: SystemClock.Minutes }

  ColumnLayout {
    anchors.fill: parent
    anchors.margins: view.px(17)
    spacing: view.px(9)

    RowLayout {
      Layout.fillWidth: true
      Layout.preferredHeight: view.px(30)
      spacing: view.px(9)
      Rectangle {
        width: view.px(6); height: width; radius: width / 2
        color: view.tone
        Behavior on color { ColorAnimation { duration: view.calm ? 0 : 250 } }
      }
      Text {
        text: "J A R V I S"
        font.family: view.family; font.pixelSize: view.font(12); font.weight: Font.Bold
        color: island ? island.fg : "#e6edf7"
      }
      Text {
        text: bridge && bridge.activeJobs > 0 ? bridge.activeJobs + " active task" + (bridge.activeJobs === 1 ? "" : "s") : "Your desktop, in sync"
        font.family: view.family; font.pixelSize: view.font(10)
        color: island ? island.fgDim : "#8b99ae"
      }
      Item { Layout.fillWidth: true }
      Text {
        text: Qt.formatDateTime(clock.date, "h:mm AP")
        font.family: view.family; font.pixelSize: view.font(11)
        color: island ? island.fgDim : "#8b99ae"
      }
      IconButton {
        glyph: "󰅖"; glyphSize: view.font(13)
        fontFamily: island ? island.fontFamily : "sans-serif"
        color: island ? island.fgDim : "#8b99ae"
        onClicked: if (island) island.collapse()
      }
    }

    Rectangle {
      Layout.fillWidth: true
      Layout.fillHeight: true
      Layout.minimumHeight: view.px(85)
      radius: view.px(19)
      gradient: Gradient {
        orientation: Gradient.Horizontal
        GradientStop { position: 0; color: Qt.tint("#111c2b", Util.alpha(view.tone, 0.09)) }
        GradientStop { position: 1; color: "#101723" }
      }
      border.color: Util.alpha(view.tone, 0.25)
      border.width: 1
      RowLayout {
        anchors.fill: parent; anchors.margins: view.px(15)
        spacing: view.px(13)
        Companion {
          Layout.preferredWidth: view.px(47); Layout.preferredHeight: view.px(47)
          voiceState: bridge ? bridge.displayState : "offline"
          isMuted: bridge ? bridge.jarvisMuted : false
          audioLevel: bridge ? bridge.audioLevel : 0
          reducedMotion: view.calm
        }
        ColumnLayout {
          Layout.fillWidth: true; spacing: view.px(3)
          RowLayout {
            spacing: view.px(8)
            Text {
              text: bridge ? bridge.stateLabel : "Offline"
              color: "#e6edf7"; font.family: view.family
              font.pixelSize: view.font(20); font.weight: Font.DemiBold
            }
            Rectangle {
              implicitWidth: connectionLabel.implicitWidth + view.px(13)
              implicitHeight: view.px(17); radius: height / 2
              color: Util.alpha(view.tone, 0.12)
              Text {
                id: connectionLabel; anchors.centerIn: parent
                text: bridge && bridge.connected ? (bridge.jarvisStandby ? "LOCAL WAKE" : "CONNECTED") : "DISCONNECTED"
                color: view.tone; font.family: view.family; font.pixelSize: view.font(8); font.weight: Font.Bold
              }
            }
          }
          Text {
            Layout.fillWidth: true
            text: bridge ? bridge.jarvisActivity : "Waiting for JARVIS"
            textFormat: Text.PlainText; elide: Text.ElideRight
            color: "#a4b2c5"; font.family: view.family; font.pixelSize: view.font(11)
          }
          Text {
            Layout.fillWidth: true
            text: bridge && bridge.jarvisModel ? bridge.jarvisModel : "Voice service unavailable"
            textFormat: Text.PlainText; elide: Text.ElideRight
            color: "#73849c"; font.family: view.family; font.pixelSize: view.font(9)
          }
        }
        Column {
          spacing: view.px(5)
          Visualizer {
            anchors.horizontalCenter: parent.horizontalCenter
            bars: 7; barWidth: view.px(3); maxHeight: view.px(26)
            playing: bridge ? bridge.isJarvisActive : false
            level: bridge && bridge.displayState === "listening" ? bridge.audioLevel : -1
            color: view.tone; reducedMotion: view.calm
          }
          Text {
            text: bridge && bridge.displayState === "listening" ? (bridge.levelAvailable ? "MIC INPUT" : "NO LEVEL") : "ACTIVITY"
            color: "#73849c"; font.family: view.family; font.pixelSize: view.font(7)
          }
        }
      }
    }

    RowLayout {
      Layout.fillWidth: true
      spacing: view.px(7)
      ActionChip {
        text: bridge && bridge.controlPending ? "Please wait" : bridge && bridge.jarvisMuted ? "Unmute mic" : "Mute mic"
        tone: view.tone; emphasized: bridge ? bridge.jarvisMuted : false
        enabled: bridge ? bridge.connected && !bridge.controlPending : false
        family: view.family; pixelSize: view.font(10); reducedMotion: view.calm
        Layout.preferredHeight: view.px(30)
        onClicked: if (bridge) bridge.toggleMute()
      }
      ActionChip {
        text: "Stop speaking"; tone: "#fa8e9d"
        enabled: bridge ? bridge.connected && !bridge.controlPending && bridge.displayState === "speaking" : false
        family: view.family; pixelSize: view.font(10); reducedMotion: view.calm
        Layout.preferredHeight: view.px(30)
        onClicked: if (bridge) bridge.interruptSpeech()
      }
      Item { Layout.fillWidth: true }
      Text {
        Layout.maximumWidth: view.px(180)
        text: bridge && bridge.controlError ? bridge.controlError
          : bridge && bridge.visionMode !== "off" ? "Sharing: " + bridge.visionMode
          : bridge && bridge.connected ? "JARVIS vision off" : "Voice disconnected"
        textFormat: Text.PlainText; elide: Text.ElideRight
        color: bridge && bridge.controlError ? "#fa8e9d" : (island ? island.fgDim : "#8b99ae")
        font.family: view.family; font.pixelSize: view.font(9)
      }
    }


    RowLayout {
      Layout.fillWidth: true
      spacing: view.px(7)
      MetricPill {
        Layout.fillWidth: true
        label: "CPU"; value: bridge ? bridge.cpuUsage : -1; tone: "#73e0ed"
        fontFamily: view.family; scaleFactor: view.unit; reducedMotion: view.calm
      }
      MetricPill {
        Layout.fillWidth: true
        label: "Memory"; value: bridge ? bridge.ramUsage : -1
        tone: value > 0.85 ? "#f0ba73" : "#b7a2ff"
        fontFamily: view.family; scaleFactor: view.unit; reducedMotion: view.calm
      }
      MetricPill {
        Layout.fillWidth: true
        label: island && island.charging ? "Charging" : "Battery"
        value: island && island.hasBattery ? island.batteryLevel : -1
        tone: value >= 0 && value < 0.2 ? "#fa8e9d" : "#78e8ba"
        fontFamily: view.family; scaleFactor: view.unit; reducedMotion: view.calm
      }
    }

    RowLayout {
      Layout.fillWidth: true
      spacing: view.px(6)
      ActionChip {
        text: "Calendar"; tone: "#9aacbf"; family: view.family; pixelSize: view.font(10)
        reducedMotion: view.calm; Layout.preferredHeight: view.px(26)
        onClicked: if (island) island.openCalendar()
      }
      ActionChip {
        text: bridge ? bridge.tempC + "  Weather" : "Weather"
        tone: "#9aacbf"; family: view.family; pixelSize: view.font(10)
        reducedMotion: view.calm; Layout.preferredHeight: view.px(26)
        onClicked: if (island) island.openWeather()
      }
      ActionChip {
        text: "Timers"; tone: "#9aacbf"; family: view.family; pixelSize: view.font(10)
        reducedMotion: view.calm; Layout.preferredHeight: view.px(26)
        onClicked: if (island) { island.openFocus = "timer"; island.expand() }
      }
      Item { Layout.fillWidth: true }
      Text {
        text: Qt.formatDateTime(clock.date, "ddd, d MMM")
        color: island ? island.fgDim : "#8b99ae"
        font.family: view.family; font.pixelSize: view.font(9)
      }
    }
  }
}
