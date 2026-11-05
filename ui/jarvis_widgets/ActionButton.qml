import QtQuick
import QtQuick.Controls

Button {
    id: button
    property bool primary: false
    implicitHeight: 44
    implicitWidth: Math.max(44, label.implicitWidth + 24)
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    Accessible.name: text
    contentItem: Text {
        id: label
        text: button.text
        font.pixelSize: 13
        font.family: "sans-serif"
        color: !button.enabled ? "#8E9BAD" : button.primary ? "#09222A" : "#F2F5FA"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: 14
        color: button.primary ? "#55DDEA" : button.down ? "#34465A" : button.hovered ? "#26384A" : "#1B2938"
        border.width: button.visualFocus ? 2 : 1
        border.color: button.visualFocus ? "#55DDEA" : "#47596B"
        opacity: button.enabled ? 1 : 0.6
    }
}
