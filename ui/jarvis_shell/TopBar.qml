import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import Quickshell.Services.Pipewire
import Quickshell.Services.UPower
import Quickshell.Services.SystemTray

Rectangle {
    id: topBar
    property string voiceState: "idle"
    property bool muted: false
    property string currentTime: "12:00 PM"
    property string currentDate: "Monday, Nov 9, 2026"

    implicitWidth: 1240
    implicitHeight: 40
    color: "transparent"

    Timer {
        interval: 1000
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: {
            var d = new Date();
            var days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
            var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
            topBar.currentDate = days[d.getDay()] + ", " + months[d.getMonth()] + " " + d.getDate() + ", " + d.getFullYear();
            var hours = d.getHours();
            var ampm = hours >= 12 ? "PM" : "AM";
            hours = hours % 12; hours = hours ? hours : 12;
            var mins = d.getMinutes();
            topBar.currentTime = (hours < 10 ? "0" + hours : hours) + ":" + (mins < 10 ? "0" + mins : mins) + " " + ampm;
        }
    }

    // 1. Left Section: JARVIS Branding + Workspaces
    Row {
        id: leftSection
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        spacing: 12

        // Branding
        Row {
            spacing: 6
            anchors.verticalCenter: parent.verticalCenter

            Text {
                text: "JARVIS"
                color: "#00e5ff"
                font.family: "JetBrainsMono Nerd Font, monospace"
                font.pixelSize: 13
                font.weight: Font.Black
                font.letterSpacing: 1.5
            }

            Text {
                text: "AI OPERATING SYSTEM"
                color: "#4f7285"
                font.family: "JetBrainsMono Nerd Font, monospace"
                font.pixelSize: 8
                font.weight: Font.Bold
                font.letterSpacing: 0.8
                anchors.verticalCenter: parent.verticalCenter
            }

            Text {
                text: "//"
                color: "#ffb020"
                font.weight: Font.Bold
                font.pixelSize: 10
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        // Live Workspaces Switcher (1-5)
        Row {
            spacing: 4
            anchors.verticalCenter: parent.verticalCenter

            Repeater {
                model: 5
                Rectangle {
                    id: wsBox
                    property int wsNum: index + 1
                    property bool isCurrent: Hyprland.focusedMonitor && Hyprland.focusedMonitor.activeWorkspace && Hyprland.focusedMonitor.activeWorkspace.id === wsNum
                    width: 22
                    height: 22
                    radius: 4
                    color: isCurrent ? Qt.rgba(0.0, 0.898, 1.0, 0.22) : hWs.hovered ? Qt.rgba(0.0, 0.898, 1.0, 0.08) : "#051320"
                    border.color: isCurrent ? "#00e5ff" : hWs.hovered ? "#38bdf8" : "#143147"
                    border.width: isCurrent ? 1.4 : 1

                    Text {
                        anchors.centerIn: parent
                        text: String(wsBox.wsNum)
                        color: wsBox.isCurrent ? "#00e5ff" : "#8aa2b3"
                        font.family: "JetBrainsMono Nerd Font, monospace"
                        font.pixelSize: 10
                        font.weight: wsBox.isCurrent ? Font.Bold : Font.Normal
                    }

                    HoverHandler { id: hWs }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: Hyprland.dispatch("hl.dsp.focus({ workspace = '" + wsBox.wsNum + "' })")
                    }
                }
            }
        }
    }

    // 2. Center Section: Live Date, Time & Weather
    Row {
        id: centerDateTimeWeather
        anchors.centerIn: parent
        spacing: 10

        Text {
            text: topBar.currentDate
            color: "#8aa2b3"
            font.family: "Inter, sans-serif"
            font.pixelSize: 10
            font.weight: Font.Medium
            anchors.verticalCenter: parent.verticalCenter
        }

        Text { text: "|"; color: "#1e3040"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }

        Row {
            spacing: 4
            anchors.verticalCenter: parent.verticalCenter
            Text { text: "󰥔"; color: "#00e5ff"; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 10 }
            Text {
                text: topBar.currentTime
                color: "#d8f6ff"
                font.family: "JetBrainsMono Nerd Font, monospace"
                font.pixelSize: 10
                font.weight: Font.Bold
            }
        }

        Text { text: "|"; color: "#1e3040"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }

        Row {
            spacing: 4
            anchors.verticalCenter: parent.verticalCenter
            Text { text: "󰖐"; color: "#ffb020"; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 10 }
            Text {
                text: "24°C Clear"
                color: "#8aa2b3"
                font.family: "Inter, sans-serif"
                font.pixelSize: 10
            }
        }
    }

    // 3. Right Section: System Telemetry, Tray & Controls
    Row {
        id: rightControls
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        spacing: 10

        // PipeWire Audio Volume
        Row {
            spacing: 3
            anchors.verticalCenter: parent.verticalCenter
            Text {
                text: Pipewire.defaultAudioSink && Pipewire.defaultAudioSink.audio.muted ? "󰝟" : "󰕾"
                color: Pipewire.defaultAudioSink && Pipewire.defaultAudioSink.audio.muted ? "#ff3b5c" : "#00e5ff"
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 12
            }
            Text {
                text: Pipewire.defaultAudioSink ? Math.round(Pipewire.defaultAudioSink.audio.volume * 100) + "%" : "100%"
                color: "#d8f6ff"
                font.family: "JetBrainsMono Nerd Font, monospace"
                font.pixelSize: 10
                font.weight: Font.DemiBold
            }
        }

        Text { text: "|"; color: "#1e3040"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }

        // UPower Battery
        Row {
            spacing: 3
            anchors.verticalCenter: parent.verticalCenter
            Text {
                text: UPower.displayDevice && UPower.displayDevice.isCharging ? "󰂄" : "󰁹"
                color: UPower.displayDevice && UPower.displayDevice.percentage < 20 ? "#ff3b5c" : "#00f0a8"
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 12
            }
            Text {
                text: UPower.displayDevice ? Math.round(UPower.displayDevice.percentage) + "%" : "100%"
                color: "#d8f6ff"
                font.family: "JetBrainsMono Nerd Font, monospace"
                font.pixelSize: 10
                font.weight: Font.DemiBold
            }
        }

        Text { text: "|"; color: "#1e3040"; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter }

        // Online Status Badge
        Row {
            spacing: 4
            anchors.verticalCenter: parent.verticalCenter
            Rectangle {
                width: 6; height: 6; radius: 3
                color: topBar.muted ? "#ff3b5c" : "#00f0a8"
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: topBar.muted ? "Muted" : "Online"
                color: topBar.muted ? "#ff8da1" : "#00f0a8"
                font.family: "Inter, sans-serif"
                font.pixelSize: 9
                font.weight: Font.DemiBold
            }
        }

        // Voice Mic Button
        Rectangle {
            width: 26; height: 26; radius: 6
            color: hovMic.hovered ? "#0d2235" : "#061320"
            border.color: topBar.muted ? "#ff3b5c" : "#00e5ff"
            border.width: 1
            anchors.verticalCenter: parent.verticalCenter

            Text {
                anchors.centerIn: parent
                text: topBar.muted ? "󰍭" : "󰍬"
                color: topBar.muted ? "#ff3b5c" : "#00e5ff"
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 12
            }
            HoverHandler { id: hovMic }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: micProc.running = true
            }
            Process { id: micProc; command: ["/home/g0pi/.local/bin/jarvis-voice-toggle"] }
        }

        // Power Menu Button
        Rectangle {
            width: 26; height: 26; radius: 6
            color: hovPwr.hovered ? "#2b1805" : "#061320"
            border.color: hovPwr.hovered ? "#ffb020" : "#1a354c"
            border.width: 1
            anchors.verticalCenter: parent.verticalCenter

            Text {
                anchors.centerIn: parent
                text: "󰐥"
                color: hovPwr.hovered ? "#ffb020" : "#8aa2b3"
                font.family: "JetBrainsMono Nerd Font"
                font.pixelSize: 12
            }
            HoverHandler { id: hovPwr }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: pwrProc.running = true
            }
            Process { id: pwrProc; command: ["omarchy-menu", "toggle", "setup.power"] }
        }
    }
}
