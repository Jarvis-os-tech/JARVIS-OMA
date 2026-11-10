import QtQuick

SciFiPanel {
    id: assistantPanel
    title: "J.A.R.V.I.S. INTELLIGENCE"
    titleColor: "#00e5ff"
    implicitWidth: 320
    implicitHeight: 88
    showHeaderAccent: false

    property string greetingText: {
        var h = new Date().getHours();
        var g = h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
        return g + ", Gopi. All tactical systems are operational.";
    }

    Row {
        anchors.fill: parent
        spacing: 12

        // Mini Glowing Arc Reactor Core Icon
        Item {
            width: 44
            height: 44
            anchors.verticalCenter: parent.verticalCenter

            Rectangle {
                anchors.centerIn: parent
                width: 40
                height: 40
                radius: 20
                color: "#03111f"
                border.color: "#00e5ff"
                border.width: 1.5

                Rectangle {
                    anchors.centerIn: parent
                    width: 24
                    height: 24
                    radius: 12
                    color: "transparent"
                    border.color: "#38bdf8"
                    border.width: 1.8
                }

                Rectangle {
                    anchors.centerIn: parent
                    width: 10
                    height: 10
                    radius: 5
                    color: "#00e5ff"
                }
            }
        }

        // Conversational Greeting
        Column {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - 56
            spacing: 2

            Text {
                text: "VOICE ASSISTANT ONLINE"
                color: "#4f7285"
                font.family: "JetBrainsMono Nerd Font, monospace"
                font.pixelSize: 8
                font.weight: Font.Bold
                font.letterSpacing: 0.8
            }

            Text {
                width: parent.width
                text: assistantPanel.greetingText
                color: "#d8f6ff"
                font.family: "Inter, sans-serif"
                font.pixelSize: 11
                font.weight: Font.DemiBold
                wrapMode: Text.WordWrap
            }
        }
    }
}
