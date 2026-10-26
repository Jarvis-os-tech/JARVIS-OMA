
import QtQuick 2.15
import QtQuick.Controls 2.15

Rectangle {
    id: island
    width: 150
    height: 30
    radius: 15
    color: "black"
    clip: true
    
    // Positions it at the top center of the screen
    anchors.horizontalCenter: Parent.horizontalCenter 
    anchors.top: parent.top
    anchors.topMargin: 5

    // State machine: 0=Compact, 1=Expanded, 2=Full
    property int state: 0 

    Behavior on width { NumberAnimation { duration: 300; easing.type: Easing.OutExpo } }
    Behavior on height { NumberAnimation { duration: 300; easing.type: Easing.OutExpo } }

    // Actual dimensions based on state
    width: state === 0 ? 150 : (state === 1 ? 400 : 600)
    height: state === 0 ? 30 : (state === 1 ? 60 : 200)

    Loader {
        id: contentLoader
        anchors.fill: parent
        source: {
            if (island.state === 0) return "Compact.qml";
            if (island.state === 1) return "Expanded.qml";
            return "Full.qml";
        }
    }
}
