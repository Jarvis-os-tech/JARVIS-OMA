import QtQuick

Item {
    id: wave
    property real audioLevel: 0.1
    property string voiceState: "listening" // listening | thinking | speaking | idle
    property int barCount: 56
    property real barWidth: 4.5
    property real maxHeight: 84
    property real minHeight: 6

    implicitWidth: 500
    implicitHeight: maxHeight + 16

    property real phase: 0

    Timer {
        interval: 16
        repeat: true
        running: true
        onTriggered: {
            var speed = wave.voiceState === "speaking" ? 0.24
                      : wave.voiceState === "thinking" ? 0.14
                      : wave.voiceState === "listening" ? 0.18 : 0.06;
            wave.phase = (wave.phase + speed) % (Math.PI * 2);

            for (var i = 0; i < repeater.count; i++) {
                var item = repeater.itemAt(i);
                if (!item) continue;
                
                var normDist = Math.abs(i - (wave.barCount - 1) / 2) / ((wave.barCount - 1) / 2);
                var bell = Math.exp(-Math.pow(normDist * 2.2, 2));

                var waveOsc = 0.5 + 0.5 * Math.sin(wave.phase + i * 0.32);
                var activeEnergy = Math.max(0.12, wave.audioLevel * 1.8);
                
                if (wave.voiceState === "thinking") {
                    var pulse = (Math.sin(wave.phase - Math.abs(i - wave.barCount/2) * 0.45) + 1.0) / 2.0;
                    item.level = Math.max(0.14, bell * (0.25 + 0.6 * pulse));
                } else if (wave.voiceState === "speaking") {
                    var randJitter = (Math.sin(wave.phase * 3.5 + i * 1.9) + 1.0) * 0.22;
                    item.level = Math.max(0.18, Math.min(1.0, bell * (0.35 + 0.65 * waveOsc + randJitter)));
                } else if (wave.voiceState === "listening") {
                    item.level = Math.max(0.12, Math.min(1.0, bell * (0.2 + activeEnergy * waveOsc * 1.6)));
                } else {
                    item.level = Math.max(0.08, bell * 0.22 * waveOsc);
                }
            }
        }
    }

    // Glowing Base Line
    Rectangle {
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 4
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width * 0.88
        height: 1.5
        color: Qt.rgba(0.0, 0.898, 1.0, 0.3)
    }

    Row {
        anchors.centerIn: parent
        spacing: 4

        Repeater {
            id: repeater
            model: wave.barCount

            Rectangle {
                id: bar
                property real level: 0.1
                width: wave.barWidth
                radius: width / 2
                anchors.verticalCenter: parent.verticalCenter
                height: Math.max(wave.minHeight, wave.maxHeight * level)

                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#ffffff" }
                    GradientStop { position: 0.25; color: "#55ddea" }
                    GradientStop { position: 0.6; color: "#00e5ff" }
                    GradientStop { position: 1.0; color: "#005588" }
                }

                Behavior on height {
                    NumberAnimation { duration: 50; easing.type: Easing.OutQuad }
                }
            }
        }
    }
}
