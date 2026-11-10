import QtQuick

SciFiPanel {
    id: netStorage
    title: "NETWORK & STORAGE"
    titleColor: "#00e5ff"
    implicitWidth: 320
    implicitHeight: 96
    showHeaderAccent: false

    Row {
        anchors.fill: parent
        spacing: 16
        anchors.verticalCenter: parent.verticalCenter

        // Network Info
        Column {
            width: 130
            spacing: 2
            Row {
                spacing: 4
                Text { text: "󰤨"; color: "#00f0a8"; font.pixelSize: 10; font.family: "JetBrainsMono Nerd Font" }
                Text { text: "Wi-Fi Connected"; color: "#d8f6ff"; font.pixelSize: 9; font.weight: Font.DemiBold }
            }
            Text { text: "Download: 12.4 MB/s"; color: "#4f7285"; font.pixelSize: 8 }
            Text { text: "Upload: 8.7 MB/s"; color: "#4f7285"; font.pixelSize: 8 }
        }

        // Storage Info
        Column {
            width: 140
            spacing: 4
            Row {
                spacing: 6
                Text { text: "󰋊"; color: "#38bdf8"; font.pixelSize: 10; font.family: "JetBrainsMono Nerd Font" }
                Text { text: "Root: 55.1 GB Free"; color: "#d8f6ff"; font.pixelSize: 8; font.weight: Font.Medium }
            }
            Rectangle {
                width: 130; height: 3; radius: 1.5; color: "#132230"
                Rectangle { width: 130 * 0.76; height: 3; radius: 1.5; color: "#00e5ff" }
            }

            Row {
                spacing: 6
                Text { text: "󰋊"; color: "#00f0a8"; font.pixelSize: 10; font.family: "JetBrainsMono Nerd Font" }
                Text { text: "Home: 194.5 GB Free"; color: "#d8f6ff"; font.pixelSize: 8; font.weight: Font.Medium }
            }
            Rectangle {
                width: 130; height: 3; radius: 1.5; color: "#132230"
                Rectangle { width: 130 * 0.45; height: 3; radius: 1.5; color: "#00f0a8" }
            }
        }
    }
}
