import QtQuick
import QtQuick.Layouts
import Quickshell
import qs.Commons
import ".."

// What the resting island shows (the "idleFace" setting):
//   jarvis - Companion, Date/Day/Time, Battery, and Music Visualizer
//   ticker - a glance that flips through the time, date, battery, next meeting, today's festival
//   clock  - just the time
//   lens   - a camera lens, like the hardware island
//   none   - the plain pill
Item {
  id: face

  property var island: null
  readonly property var bridge: island ? island.bridge : null
  readonly property string mode: island ? island.idleFace : "jarvis"
  readonly property var item: island ? island.idleItem : null

  SystemClock {
    id: clock
    precision: SystemClock.Minutes
  }

  // ── JARVIS FACE (Default: Companion, Date/Day/Time, Battery) ───────────────
  RowLayout {
    anchors.fill: parent
    anchors.leftMargin: island ? island.s(8) : 8
    anchors.rightMargin: island ? island.s(10) : 10
    spacing: island ? island.s(8) : 8
    visible: face.mode === "jarvis"

    // 1. Animated Companion
    Item {
      Layout.preferredWidth: island ? island.s(22) : 22
      Layout.preferredHeight: island ? island.s(22) : 22

      Companion {
        anchors.fill: parent
        voiceState: bridge ? bridge.displayState : "offline"
        audioLevel: bridge ? bridge.audioLevel : 0
        reducedMotion: island ? island.reducedMotion : false
        isMuted: bridge ? bridge.jarvisMuted : false
      }

      MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: if (island) island.openJarvis()
      }
    }

    // 2. Date / Day / Time (Click opens calendar)
    Item {
      Layout.fillWidth: true
      Layout.fillHeight: true

      RowLayout {
        anchors.fill: parent
        spacing: island ? island.s(4) : 4

        Text {
          Layout.fillWidth: true
          text: bridge && bridge.isJarvisActive
                ? bridge.jarvisActivity
                : Qt.formatDateTime(clock.date, "ddd d MMM · h:mm AP")
          textFormat: Text.PlainText
          renderType: Text.NativeRendering
          font.family: island ? island.textFamily : "sans-serif"
          font.pixelSize: island ? island.f(11) : 11
          font.weight: Font.DemiBold
          color: bridge && bridge.isJarvisActive ? "#00f0ff" : (island ? island.fg : "#e2e8f0")
          elide: Text.ElideRight
          Layout.alignment: Qt.AlignVCenter
        }

        // Mini music visualizer if media is playing
        Visualizer {
          visible: island && island.mediaPlaying
          playing: island ? island.mediaPlaying : false
          reducedMotion: island ? island.reducedMotion : false
          color: island ? island.mediaTint : (bridge ? bridge.stateTone : "#73e0ed")
          barWidth: island ? island.s(2) : 2
          maxHeight: island ? island.s(12) : 12
          Layout.alignment: Qt.AlignVCenter
        }
      }

      MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: if (island) island.openCalendar()
      }
    }

    // 3. Battery status
    BatteryStatus {
      island: face.island
      Layout.alignment: Qt.AlignVCenter
    }
  }

  // ── TICKER & CLOCK MODES (From reference repo) ──────────────────────────────
  Flip {
    anchors.fill: parent
    visible: face.mode === "ticker" || face.mode === "clock"
    text: face.item ? face.item.text : ""
    color: face.item && face.item.color ? face.item.color : Util.alpha(island ? island.fg : "#ffffff", 0.9)
    fontFamily: island ? island.fontFamily : "sans-serif"
    pixelSize: island ? island.f(12) : 12
  }

  // ── LENS MODE ───────────────────────────────────────────────────────────────
  Item {
    visible: face.mode === "lens"
    anchors.right: parent.right
    anchors.rightMargin: island ? island.s(11) : 11
    anchors.verticalCenter: parent.verticalCenter
    width: island ? island.s(12) : 12
    height: width

    Rectangle {
      anchors.fill: parent
      radius: width / 2
      color: Qt.darker(island ? island.surface : "#000000", 1.6)
      border.width: Math.max(1, island ? island.s(1) : 1)
      border.color: Util.alpha(island ? island.accentColor : (bridge ? bridge.stateTone : "#73e0ed"), 0.28)
    }

    Rectangle {
      anchors.centerIn: parent
      width: parent.width * 0.42
      height: width
      radius: width / 2
      color: Util.alpha(island ? island.accentColor : (bridge ? bridge.stateTone : "#73e0ed"), 0.35)
    }

    Rectangle {
      x: parent.width * 0.26
      y: parent.height * 0.22
      width: parent.width * 0.2
      height: width
      radius: width / 2
      color: Util.alpha("#ffffff", 0.55)
    }
  }
}
