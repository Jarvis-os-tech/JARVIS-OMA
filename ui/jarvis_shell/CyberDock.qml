import QtQuick
import QtQuick.Shapes
import Quickshell.Io

Item {
    id: dock
    implicitWidth: 440
    implicitHeight: 52

    Process { id: proc }
    function run(cmd) {
        proc.command = ["bash", "-c", cmd];
        proc.running = true;
    }

    // Angled Chamfered Cyber Dock Frame
    Shape {
        anchors.fill: parent
        ShapePath {
            strokeColor: Qt.rgba(0.0, 0.898, 1.0, 0.5)
            strokeWidth: 1.4
            fillGradient: LinearGradient {
                x1: 0; y1: 0; x2: dock.width; y2: dock.height
                GradientStop { position: 0.0; color: "#d9051424" }
                GradientStop { position: 1.0; color: "#f2010408" }
            }
            startX: 16; startY: 0
            PathLine { x: dock.width - 16; y: 0 }
            PathLine { x: dock.width; y: 16 }
            PathLine { x: dock.width - 12; y: dock.height }
            PathLine { x: 12; y: dock.height }
            PathLine { x: 0; y: 16 }
            PathLine { x: 16; y: 0 }
        }
    }

    // Glowing Cyan Underline
    Rectangle {
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 2
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width * 0.7
        height: 1.5
        color: "#00e5ff"
    }

    Row {
        anchors.centerIn: parent
        spacing: 12

        // 1. Omarchy / App Menu
        Rectangle {
            width: 34; height: 34; radius: 6
            color: h1.hovered ? "#0f2b3e" : "#051320"
            border.color: h1.hovered ? "#00e5ff" : "#143147"
            border.width: 1
            Text { anchors.centerIn: parent; text: "󰣇"; color: "#00e5ff"; font.pixelSize: 18; font.family: "JetBrainsMono Nerd Font" }
            HoverHandler { id: h1 }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: dock.run("omarchy-menu toggle root &") }
        }

        // 2. Search
        Rectangle {
            width: 34; height: 34; radius: 6
            color: h2.hovered ? "#0f2b3e" : "#051320"
            border.color: h2.hovered ? "#38bdf8" : "#143147"
            border.width: 1
            Text { anchors.centerIn: parent; text: "󰍉"; color: "#38bdf8"; font.pixelSize: 16; font.family: "JetBrainsMono Nerd Font" }
            HoverHandler { id: h2 }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: dock.run("omarchy-menu toggle search &") }
        }

        // 3. Files
        Rectangle {
            width: 34; height: 34; radius: 6
            color: h3.hovered ? "#0f2b3e" : "#051320"
            border.color: h3.hovered ? "#ffb020" : "#143147"
            border.width: 1
            Text { anchors.centerIn: parent; text: "󰉋"; color: "#ffb020"; font.pixelSize: 18; font.family: "JetBrainsMono Nerd Font" }
            HoverHandler { id: h3 }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: dock.run("nautilus &") }
        }

        // 4. VS Code
        Rectangle {
            width: 34; height: 34; radius: 6
            color: h4.hovered ? "#0f2b3e" : "#051320"
            border.color: h4.hovered ? "#38bdf8" : "#143147"
            border.width: 1
            Text { anchors.centerIn: parent; text: "󰨞"; color: "#38bdf8"; font.pixelSize: 18; font.family: "JetBrainsMono Nerd Font" }
            HoverHandler { id: h4 }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: dock.run("code || t3code &") }
        }

        // 5. Browser
        Rectangle {
            width: 34; height: 34; radius: 6
            color: h5.hovered ? "#0f2b3e" : "#051320"
            border.color: h5.hovered ? "#ff5722" : "#143147"
            border.width: 1
            Text { anchors.centerIn: parent; text: "󰖟"; color: "#ff5722"; font.pixelSize: 18; font.family: "JetBrainsMono Nerd Font" }
            HoverHandler { id: h5 }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: dock.run("omarchy launch browser &") }
        }

        // 6. YouTube
        Rectangle {
            width: 34; height: 34; radius: 6
            color: h6.hovered ? "#0f2b3e" : "#051320"
            border.color: h6.hovered ? "#ff3b5c" : "#143147"
            border.width: 1
            Text { anchors.centerIn: parent; text: "󰗃"; color: "#ff3b5c"; font.pixelSize: 18; font.family: "JetBrainsMono Nerd Font" }
            HoverHandler { id: h6 }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: dock.run("omarchy launch browser 'https://youtube.com' &") }
        }

        // 7. Discord
        Rectangle {
            width: 34; height: 34; radius: 6
            color: h7.hovered ? "#0f2b3e" : "#051320"
            border.color: h7.hovered ? "#818cf8" : "#143147"
            border.width: 1
            Text { anchors.centerIn: parent; text: "󰙯"; color: "#818cf8"; font.pixelSize: 18; font.family: "JetBrainsMono Nerd Font" }
            HoverHandler { id: h7 }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: dock.run("omarchy launch browser 'https://discord.com/app' &") }
        }

        // 8. Spotify
        Rectangle {
            width: 34; height: 34; radius: 6
            color: h8.hovered ? "#0f2b3e" : "#051320"
            border.color: h8.hovered ? "#1ed760" : "#143147"
            border.width: 1
            Text { anchors.centerIn: parent; text: "󰓇"; color: "#1ed760"; font.pixelSize: 18; font.family: "JetBrainsMono Nerd Font" }
            HoverHandler { id: h8 }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: dock.run("spotify || omarchy launch browser 'https://open.spotify.com' &") }
        }

        // 9. Terminal
        Rectangle {
            width: 34; height: 34; radius: 6
            color: h9.hovered ? "#0f2b3e" : "#051320"
            border.color: h9.hovered ? "#00e5ff" : "#143147"
            border.width: 1
            Text { anchors.centerIn: parent; text: "󰞷"; color: "#00e5ff"; font.pixelSize: 16; font.family: "JetBrainsMono Nerd Font" }
            HoverHandler { id: h9 }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: dock.run("foot &") }
        }
    }
}
