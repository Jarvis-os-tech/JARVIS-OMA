import QtQuick
import QtQuick.Layouts
import qs.Commons
import "../IslandModel.js" as Model

RowLayout {
  id: status
  property var island: null
  readonly property real unit: island ? island.s(100) / 100 : 1
  readonly property real level: island ? island.batteryLevel : 0
  readonly property bool charging: island ? island.charging : false
  readonly property color tone: charging ? (island ? island.greenColor : "#78e8ba")
    : level <= 0.2 ? (island ? island.urgentColor : "#fa8e9d")
    : (island ? island.fgDim : "#94a3b8")
  visible: island ? island.hasBattery : false
  spacing: 4 * unit
  Accessible.role: Accessible.StaticText
  Accessible.name: (charging ? "Charging, " : "Battery, ") + Model.percentText(level)

  Text {
    objectName: "batteryIcon"
    text: Model.batteryIcon(status.level, status.charging)
    textFormat: Text.PlainText
    renderType: Text.NativeRendering
    font.family: status.island ? status.island.fontFamily : "sans-serif"
    font.pixelSize: status.island ? status.island.f(12) : 12
    color: status.tone
  }
  Text {
    objectName: "batteryPercentage"
    text: Model.percentText(status.level)
    textFormat: Text.PlainText
    renderType: Text.NativeRendering
    font.family: status.island ? status.island.textFamily : "sans-serif"
    font.pixelSize: status.island ? status.island.f(10) : 10
    font.weight: Font.Medium
    color: status.island ? status.island.fgDim : "#94a3b8"
  }
}
