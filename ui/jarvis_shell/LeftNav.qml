import QtQuick
import Quickshell.Io

SciFiPanel {
    id: leftNav
    title: "NAV"
    titleColor: "#00e5ff"
    implicitWidth: 140
    implicitHeight: 480
    showHeaderAccent: false

    property int activeIndex: 0
    property var navItems: [
        { label: "Home", icon: "󰋜", cmd: "hyprctl dispatch 'hl.dsp.focus({ workspace = \"1\" })' &" },
        { label: "Mission Control", icon: "󰆍", cmd: "foot --hold jarvis status &" },
        { label: "AI Agents", icon: "󰚩", cmd: "omarchy launch hermes 2>/dev/null || foot -e hermes &" },
        { label: "Apps", icon: "󰀻", cmd: "omarchy-menu toggle root &" },
        { label: "Files", icon: "󰉋", cmd: "nautilus &" },
        { label: "Browser", icon: "󰖟", cmd: "omarchy launch browser &" },
        { label: "Workspace", icon: "󰨇", cmd: "hyprctl dispatch 'hl.dsp.focus({ workspace = \"m+1\" })' &" },
        { label: "Settings", icon: "󰒓", cmd: "omarchy-menu toggle setup &" }
    ]

    Process { id: navProc }
    function run(cmd) {
        if (!cmd) return;
        navProc.command = ["bash", "-c", cmd];
        navProc.running = true;
    }

    // Nav Items Column
    Column {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        spacing: 5

        Repeater {
            model: leftNav.navItems

            Rectangle {
                width: parent.width
                height: 34
                radius: 6
                color: leftNav.activeIndex === index ? Qt.rgba(1.0, 0.7, 0.1, 0.22)
                     : hov.hovered ? Qt.rgba(0.0, 0.898, 1.0, 0.14)
                     : "transparent"
                border.color: leftNav.activeIndex === index ? "#ffb020" : "transparent"
                border.width: 1

                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.left: parent.left
                    anchors.leftMargin: 8
                    spacing: 8

                    Text {
                        text: modelData.icon
                        color: leftNav.activeIndex === index ? "#ffb020"
                             : hov.hovered ? "#00e5ff" : "#8aa2b3"
                        font.family: "JetBrainsMono Nerd Font"
                        font.pixelSize: 13
                    }

                    Text {
                        text: modelData.label
                        color: leftNav.activeIndex === index ? "#ffb020"
                             : hov.hovered ? "#ffffff" : "#d8f6ff"
                        font.family: "Inter, sans-serif"
                        font.pixelSize: 10
                        font.weight: leftNav.activeIndex === index ? Font.Bold : Font.Medium
                    }
                }

                HoverHandler { id: hov }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        leftNav.activeIndex = index;
                        leftNav.run(modelData.cmd);
                    }
                }
            }
        }
    }

    // Bottom Badge: JARVIS v1.0 Powered by Gemini
    Rectangle {
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        height: 38
        radius: 6
        color: "#04111d"
        border.color: Qt.rgba(0.0, 0.898, 1.0, 0.25)
        border.width: 1

        Row {
            anchors.centerIn: parent
            spacing: 6

            Text { text: "G"; color: "#4285f4"; font.weight: Font.Black; font.pixelSize: 13 }
            Column {
                spacing: 1
                Text { text: "JARVIS v1.0"; color: "#d8f6ff"; font.pixelSize: 8; font.weight: Font.Bold }
                Text { text: "Powered by Gemini"; color: "#4f7285"; font.pixelSize: 7 }
            }
        }
    }
}
