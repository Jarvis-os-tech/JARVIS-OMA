pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    property var node: ({type: "text", text: ""})
    property var context
    implicitHeight: renderer.item ? renderer.item.implicitHeight : 0
    objectName: node.id || ""
    Loader {
        id: renderer
        width: parent.width
        sourceComponent: root.node.type === "row" ? rowLayout : root.node.type === "column" ? columnLayout
            : root.node.type === "heading" || root.node.type === "text" ? textNode
            : root.node.type === "metric" ? metricNode : root.node.type === "input" ? inputNode
            : root.node.type === "slider" ? sliderNode : root.node.type === "toggle" ? toggleNode
            : root.node.type === "select" ? selectNode : root.node.type === "button" ? buttonNode
            : root.node.type === "canvas" ? canvasNode : dividerNode
    }
    Component {
        id: columnLayout
        Column {
            spacing: 14
            Repeater {
                model: root.node.children
                Loader {
                    required property var modelData
                    width: parent.width
                    Component.onCompleted: setSource(Qt.resolvedUrl("ViewNode.qml"), {node: modelData, context: root.context})
                }
            }
        }
    }
    Component {
        id: rowLayout
        RowLayout {
            spacing: 16
            Repeater {
                model: root.node.children
                Loader {
                    required property var modelData
                    Layout.fillWidth: true; Layout.preferredWidth: 1
                    Layout.alignment: Qt.AlignTop
                    Component.onCompleted: setSource(Qt.resolvedUrl("ViewNode.qml"), {node: modelData, context: root.context})
                }
            }
        }
    }
    Component {
        id: textNode
        Text {
            text: root.context.format(root.node.text)
            textFormat: Text.PlainText; wrapMode: Text.WordWrap
            lineHeight: 1.4
            font.pixelSize: root.node.type === "heading" ? 21 : 14
            font.weight: root.node.type === "heading" ? Font.DemiBold : Font.Normal
            color: root.node.tone === "muted" ? "#A7B1BE" : root.node.tone === "accent" ? "#76DDD2" : "#E7ECF1"
        }
    }
    Component {
        id: metricNode
        Column {
            spacing: 4
            Text { text: root.context.format(root.node.label); textFormat: Text.PlainText; color: "#A7B1BE"; font.pixelSize: 13 }
            Text { text: String(root.context.value(root.node.value)); textFormat: Text.PlainText; color: "#E7ECF1"; font.pixelSize: 28; font.weight: Font.DemiBold }
        }
    }
    Component {
        id: inputNode
        Column {
            spacing: 6
            Text { text: root.context.format(root.node.label); textFormat: Text.PlainText; color: "#A7B1BE"; font.pixelSize: 13 }
            TextField {
                width: parent.width; implicitHeight: 44
                objectName: "control-" + (root.node.id || root.node.bind)
                text: String(root.context.formState[root.node.bind] ?? "")
                maximumLength: 2000; selectByMouse: true
                color: "#E7ECF1"; font.pixelSize: 15
                Accessible.name: root.node.label
                background: Rectangle { radius: 10; color: "#19222D"; border.color: parent.activeFocus ? "#76DDD2" : "#39434F" }
                onTextEdited: root.context.edit(root.node.bind, text)
            }
        }
    }
    Component {
        id: sliderNode
        Column {
            spacing: 4
            Text { text: root.context.format(root.node.label) + " · " + root.context.formState[root.node.bind]; textFormat: Text.PlainText; color: "#C7CFD9"; font.pixelSize: 14 }
            Slider {
                width: parent.width; implicitHeight: 44
                objectName: "control-" + (root.node.id || root.node.bind)
                from: root.node.min ?? 0; to: root.node.max ?? 100; stepSize: root.node.step ?? 1
                value: Number(root.context.formState[root.node.bind])
                Accessible.name: root.node.label
                onMoved: root.context.edit(root.node.bind, value)
                background: Rectangle { x: 8; y: parent.height / 2 - 2; width: parent.width - 16; height: 4; radius: 2; color: "#39434F" }
                handle: Rectangle { x: 8 + parent.visualPosition * (parent.width - width - 16); y: parent.height / 2 - 9; width: 18; height: 18; radius: 9; color: "#76DDD2" }
            }
        }
    }
    Component {
        id: toggleNode
        Switch {
            objectName: "control-" + (root.node.id || root.node.bind)
            text: root.context.format(root.node.label); checked: root.context.formState[root.node.bind] === true
            palette.windowText: "#E7ECF1"; palette.highlight: "#76DDD2"
            implicitHeight: 44
            onToggled: root.context.edit(root.node.bind, checked)
        }
    }
    Component {
        id: selectNode
        Column {
            spacing: 6
            Text { text: root.context.format(root.node.label); textFormat: Text.PlainText; color: "#A7B1BE"; font.pixelSize: 13 }
            ComboBox {
                width: parent.width; implicitHeight: 44
                objectName: "control-" + (root.node.id || root.node.bind)
                model: root.node.options
                currentIndex: root.node.options.indexOf(root.context.formState[root.node.bind])
                palette.button: "#19222D"; palette.buttonText: "#E7ECF1"; palette.highlight: "#76DDD2"
                Accessible.name: root.node.label
                onActivated: root.context.edit(root.node.bind, currentText)
            }
        }
    }
    Component {
        id: buttonNode
        ActionButton {
            objectName: "control-" + (root.node.id || "action")
            text: root.context.format(root.node.label); primary: true
            enabled: !root.context.busy
            onClicked: root.context.submitted(root.context.format(root.node.prompt), root.context.formState)
        }
    }
    Component { id: canvasNode; DrawCanvas { node: root.node; viewContext: root.context } }
    Component { id: dividerNode; Rectangle { implicitHeight: 1; color: "#34404B" } }
}
