import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: bar
    property string draft: ""
    property bool busy: false
    property string error: ""
    signal edited(string value)
    signal submitted(string value)
    signal closeRequested()
    implicitHeight: 64 + (error ? 32 : 0)
    radius: 22
    color: "#F0162433"
    border.color: input.activeFocus ? "#55DDEA" : "#506277"
    border.width: input.activeFocus ? 2 : 1

    function takeFocus() { input.forceActiveFocus(); }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 9
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            TextField {
                id: input
                objectName: "requestInput"
                Layout.fillWidth: true
                Layout.preferredHeight: 44
                text: bar.draft
                onTextEdited: bar.edited(text)
                enabled: !bar.busy
                placeholderText: "Ask JARVIS…"
                color: "#F2F5FA"; placeholderTextColor: "#A8B6C8"
                font.pixelSize: 15
                selectByMouse: true
                background: Item {}
                Accessible.name: "Request to JARVIS"
                onAccepted: if (text.trim()) bar.submitted(text)
            }
            ActionButton {
                text: bar.busy ? "Sending…" : "Send"
                primary: true
                enabled: !bar.busy && input.text.trim().length > 0
                onClicked: bar.submitted(input.text)
            }
        }
        Text {
            Layout.fillWidth: true
            visible: bar.error.length > 0
            text: bar.error; textFormat: Text.PlainText
            color: "#F193A0"; font.pixelSize: 12
            elide: Text.ElideRight
        }
    }
}
