import QtQuick
import QtQuick.Layouts
import qs.Commons
import ".."

// Dedicated Approval Card for agent tool permissions.
Item {
  id: view

  property var island: null
  readonly property var bridge: island ? island.bridge : null

  Rectangle {
    anchors.fill: parent
    color: "transparent"

    ColumnLayout {
      anchors.fill: parent
      anchors.margins: island ? island.s(16) : 16
      spacing: island ? island.s(8) : 8

      // Warning header
      RowLayout {
        Layout.fillWidth: true
        spacing: island ? island.s(8) : 8

        Text {
          text: "󰀪"
          font.family: island ? island.fontFamily : "sans-serif"
          font.pixelSize: island ? island.f(18) : 18
          color: island ? island.orangeColor : "#f59e0b"
        }

        Text {
          text: (bridge ? bridge.agentName : "Agent") + " requests permission"
          textFormat: Text.PlainText
          renderType: Text.NativeRendering
          font.family: island ? island.textFamily : "sans-serif"
          font.pixelSize: island ? island.f(13) : 13
          font.weight: Font.Bold
          color: island ? island.fg : "#f8fafc"
        }

        Item { Layout.fillWidth: true }

        Text {
          text: "Action required"
          textFormat: Text.PlainText
          renderType: Text.NativeRendering
          font.family: island ? island.textFamily : "sans-serif"
          font.pixelSize: island ? island.f(11) : 11
          color: island ? island.orangeColor : "#f59e0b"
        }
      }

      // Command snippet
      Rectangle {
        Layout.fillWidth: true
        Layout.preferredHeight: island ? island.s(38) : 38
        radius: island ? island.s(6) : 6
        color: Util.alpha(island ? island.surface : "#000000", 0.7)
        border.color: Util.alpha(island ? island.orangeColor : "#f59e0b", 0.4)
        border.width: 1

        Row {
          anchors.fill: parent
          anchors.margins: island ? island.s(8) : 8
          spacing: island ? island.s(8) : 8

          Text {
            text: "󰅩"
            font.family: island ? island.fontFamily : "sans-serif"
            font.pixelSize: island ? island.f(13) : 13
            color: island ? island.fgDim : "#94a3b8"
            anchors.verticalCenter: parent.verticalCenter
          }

          Text {
            text: bridge && bridge.pendingToolTarget ? bridge.pendingToolTarget : "run_command: build and verify"
            textFormat: Text.PlainText
            renderType: Text.NativeRendering
            font.family: island ? island.fontFamily : "monospace"
            font.pixelSize: island ? island.f(11) : 11
            color: island ? island.fg : "#cbd5e1"
            elide: Text.ElideRight
            anchors.verticalCenter: parent.verticalCenter
          }
        }
      }

      // Allow / Deny buttons
      RowLayout {
        Layout.fillWidth: true
        spacing: island ? island.s(8) : 8

        Rectangle {
          Layout.fillWidth: true
          Layout.preferredHeight: island ? island.s(30) : 30
          radius: island ? island.s(6) : 6
          color: allowMouse.containsMouse ? "#10b981" : "#059669"

          Row {
            anchors.centerIn: parent
            spacing: 4
            Text { text: "󰄬"; font.pixelSize: 12; color: "#ffffff"; anchors.verticalCenter: parent.verticalCenter }
            Text { text: "Allow"; font.pixelSize: 11; font.weight: Font.Bold; color: "#ffffff"; anchors.verticalCenter: parent.verticalCenter }
          }

          MouseArea {
            id: allowMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
              if (bridge) bridge.allowPending()
              if (island) island.collapse()
            }
          }
        }

        Rectangle {
          Layout.fillWidth: true
          Layout.preferredHeight: island ? island.s(30) : 30
          radius: island ? island.s(6) : 6
          color: denyMouse.containsMouse ? "#ef4444" : "#dc2626"

          Row {
            anchors.centerIn: parent
            spacing: 4
            Text { text: "󰅖"; font.pixelSize: 12; color: "#ffffff"; anchors.verticalCenter: parent.verticalCenter }
            Text { text: "Deny"; font.pixelSize: 11; font.weight: Font.Bold; color: "#ffffff"; anchors.verticalCenter: parent.verticalCenter }
          }

          MouseArea {
            id: denyMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
              if (bridge) bridge.denyPending()
              if (island) island.collapse()
            }
          }
        }
      }
    }
  }
}
