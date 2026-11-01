import QtQuick

// Vector companion: activity motion is distinct from measured microphone level.
Item {
  id: core
  property string voiceState: "idle"
  property string stateName: voiceState
  property bool isMuted: false
  property bool reducedMotion: false
  property real audioLevel: 0
  property real lookX: 0
  property real lookY: 0
  readonly property bool busy: voiceState === "thinking" || voiceState === "processing" || voiceState === "connecting"
  readonly property bool animated: visible && !reducedMotion && !isMuted && voiceState !== "offline" && voiceState !== "standby"
  property color primaryColor: isMuted ? "#f0ba73"
    : voiceState === "speaking" ? "#78e8ba"
    : busy ? "#b7a2ff" : voiceState === "error" ? "#fa8e9d"
    : voiceState === "offline" || voiceState === "standby" ? "#8b99ae" : "#73e0ed"
  property real breath: 1
  property real blink: 1
  implicitWidth: 32
  implicitHeight: 32
  Behavior on primaryColor { ColorAnimation { duration: core.reducedMotion ? 0 : 240 } }
  SequentialAnimation on breath {
    running: core.animated
    loops: Animation.Infinite
    NumberAnimation { to: 1.05; duration: core.voiceState === "speaking" ? 650 : 1700; easing.type: Easing.InOutSine }
    NumberAnimation { to: 0.96; duration: core.voiceState === "speaking" ? 650 : 1700; easing.type: Easing.InOutSine }
    onRunningChanged: if (!running) core.breath = 1
  }
  Timer {
    interval: 4300; repeat: true; running: core.animated && !core.busy
    onTriggered: eyeBlink.restart()
  }
  SequentialAnimation {
    id: eyeBlink
    NumberAnimation { target: core; property: "blink"; to: 0.12; duration: 80 }
    NumberAnimation { target: core; property: "blink"; to: 1; duration: 160; easing.type: Easing.OutCubic }
  }
  Rectangle {
    anchors.centerIn: parent
    width: parent.width * 0.94; height: width; radius: width / 2
    color: Qt.rgba(core.primaryColor.r, core.primaryColor.g, core.primaryColor.b, 0.07)
    border.width: 1
    border.color: Qt.rgba(core.primaryColor.r, core.primaryColor.g, core.primaryColor.b, 0.22)
    scale: core.breath + Math.min(1, Math.max(0, core.audioLevel)) * 0.09
    Behavior on scale { NumberAnimation { duration: core.reducedMotion ? 0 : 140 } }
  }
  Item {
    anchors.centerIn: parent
    width: parent.width * 0.88; height: width
    rotation: 0
    NumberAnimation on rotation {
      from: 0; to: 360; duration: 2000; loops: Animation.Infinite
      running: core.busy && core.animated
    }
    Rectangle {
      anchors.horizontalCenter: parent.horizontalCenter; y: -1
      width: Math.max(2, core.width * 0.08); height: width; radius: width / 2
      color: core.primaryColor
      visible: core.busy
    }
  }
  Rectangle {
    anchors.centerIn: parent
    width: parent.width * 0.72; height: width; radius: width / 2
    color: "#111d2c"
    border.width: 1
    border.color: Qt.rgba(core.primaryColor.r, core.primaryColor.g, core.primaryColor.b, 0.8)
    Row {
      anchors.centerIn: parent
      anchors.verticalCenterOffset: core.height * (core.busy ? -0.04 : 0) + core.lookY
      anchors.horizontalCenterOffset: core.lookX
      spacing: core.width * 0.13
      Repeater {
        model: 2
        Rectangle {
          width: Math.max(2, core.width * 0.09)
          height: Math.max(1.5, core.width * (core.isMuted || core.voiceState === "standby" ? 0.045 : 0.19) * core.blink)
          radius: width / 2
          rotation: core.busy ? -12 : 0
          color: core.primaryColor
          Behavior on height { NumberAnimation { duration: 100 } }
        }
      }
    }
  }
  Rectangle {
    visible: core.isMuted
    anchors.right: parent.right; anchors.bottom: parent.bottom
    width: Math.max(5, parent.width * 0.24); height: width; radius: width / 2
    color: "#f0ba73"; border.color: "#111d2c"; border.width: 1
  }
}
