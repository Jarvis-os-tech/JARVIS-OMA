import QtQuick
import QtQuick.Layouts
import qs.Commons
import ".."

// Full Weather telemetry card for the JARVIS Dynamic Island.
Item {
  id: view

  property var island: null
  readonly property var bridge: island ? island.bridge : null

  RowLayout {
    anchors.fill: parent
    anchors.margins: island ? island.s(16) : 16
    spacing: island ? island.s(14) : 14

    // Left pane: Large Weather Icon & Current Temp
    Rectangle {
      Layout.preferredWidth: island ? island.s(200) : 200
      Layout.fillHeight: true
      radius: island ? island.s(10) : 10
      color: Util.alpha(island ? island.surface : "#000000", 0.6)
      border.color: Util.alpha(island ? island.accentColor : "#00f0ff", 0.25)

      ColumnLayout {
        anchors.fill: parent
        anchors.margins: island ? island.s(12) : 12
        spacing: island ? island.s(6) : 6

        RowLayout {
          Layout.fillWidth: true
          Text {
            text: bridge ? bridge.weatherGlyph : "󰖑"
            font.family: island ? island.fontFamily : "sans-serif"
            font.pixelSize: island ? island.f(36) : 36
            color: "#00f0ff"
          }
          Item { Layout.fillWidth: true }
          Column {
            Text {
              text: bridge ? bridge.tempC : "23°C"
              textFormat: Text.PlainText
              renderType: Text.NativeRendering
              font.family: island ? island.fontFamily : "sans-serif"
              font.pixelSize: island ? island.f(26) : 26
              font.weight: Font.Bold
              color: island ? island.fg : "#f8fafc"
            }
            Text {
              text: "Local Telemetry"
              textFormat: Text.PlainText
              renderType: Text.NativeRendering
              font.family: island ? island.textFamily : "sans-serif"
              font.pixelSize: island ? island.f(10) : 10
              color: island ? island.fgDim : "#64748b"
            }
          }
        }

        Text {
          text: bridge ? bridge.weatherCondition : "Smoky haze"
          textFormat: Text.PlainText
          renderType: Text.NativeRendering
          font.family: island ? island.textFamily : "sans-serif"
          font.pixelSize: island ? island.f(12) : 12
          font.weight: Font.Medium
          color: island ? island.fg : "#cbd5e1"
        }

        Item { Layout.fillHeight: true }

        // Refresh button
        Rectangle {
          Layout.fillWidth: true
          Layout.preferredHeight: island ? island.s(26) : 26
          radius: height / 2
          color: refMouse.containsMouse ? Util.alpha("#00f0ff", 0.25) : Util.alpha(island ? island.fg : "#ffffff", 0.08)
          border.color: Util.alpha("#00f0ff", 0.35)
          border.width: 1

          Row {
            anchors.centerIn: parent
            spacing: 6
            Text { text: "󰑐"; font.pixelSize: 11; color: "#00f0ff"; anchors.verticalCenter: parent.verticalCenter }
            Text { text: "Refresh Weather"; font.pixelSize: 10; font.weight: Font.DemiBold; color: "#00f0ff"; anchors.verticalCenter: parent.verticalCenter }
          }

          MouseArea {
            id: refMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
              if (bridge) bridge.refreshWeather()
            }
          }
        }
      }
    }

    // Right pane: Metrics grid (Humidity, Wind, Air)
    ColumnLayout {
      Layout.fillWidth: true
      Layout.fillHeight: true
      spacing: island ? island.s(8) : 8

      Text {
        text: "Atmospheric Telemetry"
        textFormat: Text.PlainText
        renderType: Text.NativeRendering
        font.family: island ? island.textFamily : "sans-serif"
        font.pixelSize: island ? island.f(12) : 12
        font.weight: Font.Bold
        color: island ? island.fg : "#f8fafc"
      }

      GridLayout {
        Layout.fillWidth: true
        columns: 2
        rowSpacing: island ? island.s(8) : 8
        columnSpacing: island ? island.s(8) : 8

        // Humidity
        Rectangle {
          Layout.fillWidth: true
          Layout.preferredHeight: island ? island.s(44) : 44
          radius: island ? island.s(6) : 6
          color: Util.alpha(island ? island.surface : "#000000", 0.5)
          border.color: Util.alpha(island ? island.fg : "#ffffff", 0.08)

          RowLayout {
            anchors.fill: parent
            anchors.margins: 8
            spacing: 6
            Text { text: "󰖌"; font.pixelSize: 16; color: "#38bdf8" }
            Column {
              Text { text: "Humidity"; font.pixelSize: 9; color: island ? island.fgDim : "#64748b" }
              Text { text: bridge ? bridge.weatherHumidity : "94%"; font.pixelSize: 12; font.weight: Font.DemiBold; color: island ? island.fg : "#e2e8f0" }
            }
          }
        }

        // Wind speed
        Rectangle {
          Layout.fillWidth: true
          Layout.preferredHeight: island ? island.s(44) : 44
          radius: island ? island.s(6) : 6
          color: Util.alpha(island ? island.surface : "#000000", 0.5)
          border.color: Util.alpha(island ? island.fg : "#ffffff", 0.08)

          RowLayout {
            anchors.fill: parent
            anchors.margins: 8
            spacing: 6
            Text { text: "󰈐"; font.pixelSize: 16; color: "#00f0ff" }
            Column {
              Text { text: "Wind Speed"; font.pixelSize: 9; color: island ? island.fgDim : "#64748b" }
              Text { text: bridge ? bridge.weatherWind : "5 km/h"; font.pixelSize: 12; font.weight: Font.DemiBold; color: island ? island.fg : "#e2e8f0" }
            }
          }
        }
      }

      Item { Layout.fillHeight: true }

      // Back to JARVIS HUD button
      Rectangle {
        Layout.preferredWidth: island ? island.s(100) : 100
        Layout.preferredHeight: island ? island.s(26) : 26
        radius: height / 2
        color: backMouse.containsMouse ? Util.alpha(island ? island.fg : "#ffffff", 0.15) : Util.alpha(island ? island.fg : "#ffffff", 0.08)

        Row {
          anchors.centerIn: parent
          spacing: 4
          Text { text: "󰌑"; font.pixelSize: 10; color: island ? island.fgDim : "#94a3b8" }
          Text { text: "Back to HUD"; font.pixelSize: 10; color: island ? island.fg : "#e2e8f0" }
        }

        MouseArea {
          id: backMouse
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: {
            if (island) island.openJarvis()
          }
        }
      }
    }
  }
}
