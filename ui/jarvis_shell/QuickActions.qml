import QtQuick
import Quickshell.Io

SciFiPanel {
    id: actionsCard
    title: "⚡ QUICK ACTIONS"
    titleColor: "#ffb020"
    implicitWidth: 320
    implicitHeight: 140

    Process { id: launcherProc }

    function launch(cmd) {
        launcherProc.command = ["bash", "-c", cmd];
        launcherProc.running = true;
    }

    Grid {
        anchors.fill: parent
        columns: 2
        spacing: 8

        // 1. Open VS Code
        Rectangle {
            width: (parent.width - 8) / 2
            height: 38
            radius: 6
            color: btn1.hovered ? "#0d263d" : "#051320"
            border.color: btn1.hovered ? "#38bdf8" : "#143147"
            border.width: 1

            Row {
                anchors.centerIn: parent
                spacing: 8
                Text { text: "󰨞"; color: "#38bdf8"; font.pixelSize: 14; font.family: "JetBrainsMono Nerd Font" }
                Text { text: "Open VS Code"; color: "#d8f6ff"; font.pixelSize: 10; font.weight: Font.DemiBold }
            }
            HoverHandler { id: btn1 }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: actionsCard.launch("omarchy launch code 2>/dev/null || code || t3code &")
            }
        }

        // 2. Search Web
        Rectangle {
            width: (parent.width - 8) / 2
            height: 38
            radius: 6
            color: btn2.hovered ? "#0d263d" : "#051320"
            border.color: btn2.hovered ? "#00e5ff" : "#143147"
            border.width: 1

            Row {
                anchors.centerIn: parent
                spacing: 8
                Text { text: "󰖟"; color: "#00e5ff"; font.pixelSize: 14; font.family: "JetBrainsMono Nerd Font" }
                Text { text: "Search Web"; color: "#d8f6ff"; font.pixelSize: 10; font.weight: Font.DemiBold }
            }
            HoverHandler { id: btn2 }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: actionsCard.launch("omarchy launch browser 'https://google.com' &")
            }
        }

        // 3. Play Music
        Rectangle {
            width: (parent.width - 8) / 2
            height: 38
            radius: 6
            color: btn3.hovered ? "#0d263d" : "#051320"
            border.color: btn3.hovered ? "#ffb020" : "#143147"
            border.width: 1

            Row {
                anchors.centerIn: parent
                spacing: 8
                Text { text: "󰝚"; color: "#ffb020"; font.pixelSize: 14; font.family: "JetBrainsMono Nerd Font" }
                Text { text: "Play Music"; color: "#d8f6ff"; font.pixelSize: 10; font.weight: Font.DemiBold }
            }
            HoverHandler { id: btn3 }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: actionsCard.launch("playerctl play-pause 2>/dev/null || omarchy launch browser 'https://music.youtube.com' &")
            }
        }

        // 4. Take Screenshot
        Rectangle {
            width: (parent.width - 8) / 2
            height: 38
            radius: 6
            color: btn4.hovered ? "#0d263d" : "#051320"
            border.color: btn4.hovered ? "#00f0a8" : "#143147"
            border.width: 1

            Row {
                anchors.centerIn: parent
                spacing: 8
                Text { text: "󰄀"; color: "#00f0a8"; font.pixelSize: 14; font.family: "JetBrainsMono Nerd Font" }
                Text { text: "Take Screenshot"; color: "#d8f6ff"; font.pixelSize: 10; font.weight: Font.DemiBold }
            }
            HoverHandler { id: btn4 }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: actionsCard.launch("omarchy capture screenshot &")
            }
        }

        // 5. Open YouTube
        Rectangle {
            width: (parent.width - 8) / 2
            height: 38
            radius: 6
            color: btn5.hovered ? "#0d263d" : "#051320"
            border.color: btn5.hovered ? "#ff3b5c" : "#143147"
            border.width: 1

            Row {
                anchors.centerIn: parent
                spacing: 8
                Text { text: "󰗃"; color: "#ff3b5c"; font.pixelSize: 14; font.family: "JetBrainsMono Nerd Font" }
                Text { text: "Open YouTube"; color: "#d8f6ff"; font.pixelSize: 10; font.weight: Font.DemiBold }
            }
            HoverHandler { id: btn5 }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: actionsCard.launch("omarchy launch browser 'https://youtube.com' &")
            }
        }

        // 6. Shut Down
        Rectangle {
            width: (parent.width - 8) / 2
            height: 38
            radius: 6
            color: btn6.hovered ? "#0d263d" : "#051320"
            border.color: btn6.hovered ? "#ff9100" : "#143147"
            border.width: 1

            Row {
                anchors.centerIn: parent
                spacing: 8
                Text { text: "󰐥"; color: "#ff9100"; font.pixelSize: 14; font.family: "JetBrainsMono Nerd Font" }
                Text { text: "Shut Down"; color: "#d8f6ff"; font.pixelSize: 10; font.weight: Font.DemiBold }
            }
            HoverHandler { id: btn6 }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: actionsCard.launch("omarchy-menu toggle setup.power &")
            }
        }
    }
}
