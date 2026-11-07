pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import QtMultimedia

Rectangle {
    id: card
    property var widget: ({id: "", title: "", kind: "text", data: {text: ""}})
    property bool inCanvas: true
    property bool activeMedia: true
    property bool requestBusy: false
    property string requestError: ""
    readonly property var widgetData: widget.data || {}
    readonly property bool interacting: hover.hovered || containsFocus(Window.window ? Window.window.activeFocusItem : null)
    function containsFocus(item) {
        while (item) { if (item === card) return true; item = item.parent; }
        return false;
    }
    signal requested(string action)
    signal dragStarted()
    signal dragged(real x, real y)
    signal stateEdited(var values)
    signal submitted(string prompt, var values)
    signal dismissRequested()

    readonly property bool hasActions: Array.isArray(widgetData.actions) && widgetData.actions.length > 0
    readonly property int textLength: String(widgetData.text || "").length
    implicitWidth: widget.kind === "view" ? Math.min(520, Math.max(340, widgetData.width || 380))
        : ["chart", "table", "image", "pip", "3d"].includes(widget.kind) ? 460
        : widget.kind === "text" && textLength > 250 ? 420
        : 340
    implicitHeight: (widget.kind === "view" ? Math.min(660, (widgetData.layout ? generatedHeight : 280) + 72)
        : ["image", "pip", "3d"].includes(widget.kind) ? 340
        : widget.kind === "qr" ? 340
        : ["chart", "table"].includes(widget.kind) ? 320
        : widget.kind === "progress" ? 115
        : widget.kind === "task" ? 135
        : widget.kind === "text" ? (textLength > 300 ? 360 : textLength > 100 ? 200 : 110)
        : 140) + (hasActions ? 44 : 0)
    property real generatedHeight: 300
    radius: 20
    color: "#EF14202D"
    border.color: (card.widget && card.widget.pinned) ? "#55DDEA" : "#4A6075"
    HoverHandler { id: hover }
    clip: true

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 30
                Text {
                    anchors.fill: parent
                    text: (card.widget && card.widget.title) ? card.widget.title : ""
                    textFormat: Text.PlainText
                    color: "#F2F5FA"
                    font.pixelSize: 16
                    font.weight: Font.DemiBold
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
                DragHandler {
                    target: null
                    enabled: !card.inCanvas
                    onActiveChanged: if (active) card.dragStarted()
                    onTranslationChanged: card.dragged(translation.x, translation.y)
                }
            }
            ActionButton {
                text: "✕"
                implicitHeight: 28
                implicitWidth: 28
                Layout.preferredHeight: 28
                Layout.preferredWidth: 28
                onClicked: card.dismissRequested()
            }
        }

        Loader {
            Layout.fillWidth: true
            Layout.fillHeight: true
            sourceComponent: card.widget.kind === "3d" ? threeDBlock
                : card.widget.kind === "task" ? taskBlock
                : card.widget.kind === "view" ? generatedBlock
                : card.widget.kind === "text" ? textBlock
                : card.widget.kind === "table" ? tableBlock
                : card.widget.kind === "chart" ? chartBlock
                : card.widget.kind === "progress" ? progressBlock
                : card.widget.kind === "pip" && card.widgetData.video ? videoBlock : imageBlock
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 2
            visible: card.hasActions
            spacing: 8
            Item { Layout.fillWidth: true }
            Repeater {
                model: card.hasActions ? card.widgetData.actions : []
                ActionButton {
                    required property var modelData
                    text: modelData.label || "Action"
                    primary: modelData.primary === true
                    implicitHeight: 32
                    Layout.preferredHeight: 32
                    enabled: !card.requestBusy
                    onClicked: {
                        if (modelData.action === "dismiss") {
                            card.dismissRequested();
                        } else {
                            card.submitted(modelData.prompt || modelData.action, {action: modelData.action, widget_id: card.widget.id});
                        }
                    }
                }
            }
        }
        Text {
            Layout.fillWidth: true
            text: card.requestError
            visible: text.length > 0
            textFormat: Text.PlainText; wrapMode: Text.WordWrap
            color: "#F193A0"; font.pixelSize: 12
        }
    }

    Component {
        id: taskBlock
        ColumnLayout {
            spacing: 8
            Text {
                objectName: "task-state"
                text: card.widgetData.label || "Needs review"
                textFormat: Text.PlainText
                color: card.widgetData.state === "failed" ? "#F193A0" : "#55DDEA"
                font.pixelSize: 18; font.weight: Font.DemiBold
            }
            Text {
                Layout.fillWidth: true
                text: card.widgetData.text || ""
                textFormat: Text.PlainText; wrapMode: Text.WordWrap
                maximumLineCount: 3; elide: Text.ElideRight
                color: "#F2F5FA"; font.pixelSize: 14
            }
            ProgressBar {
                Layout.fillWidth: true
                visible: !!card.widgetData.progress || ["queued", "running", "cancelling"].indexOf(card.widgetData.state) !== -1
                indeterminate: !card.widgetData.progress
                from: 0; to: card.widgetData.progress ? card.widgetData.progress.total : 1
                value: card.widgetData.progress ? card.widgetData.progress.completed : 0
            }
            Text {
                Layout.fillWidth: true
                text: card.widgetData.evidence || ""
                textFormat: Text.PlainText; wrapMode: Text.WordWrap
                color: "#B7C5D6"; font.pixelSize: 12
            }
        }
    }

    Component {
        id: generatedBlock
        ScrollView {
            id: generatedScroll
            clip: true
            contentWidth: availableWidth
            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
                width: 6
                background: Rectangle { color: "transparent" }
                contentItem: Rectangle { implicitWidth: 6; radius: 3; color: "#4A6075"; opacity: 0.85 }
            }
            GeneratedView {
                width: generatedScroll.availableWidth
                specification: card.widgetData
                busy: card.requestBusy
                onImplicitHeightChanged: card.generatedHeight = implicitHeight
                Component.onCompleted: card.generatedHeight = implicitHeight
                onStateEdited: values => card.stateEdited(values)
                onSubmitted: (prompt, values) => card.submitted(prompt, values)
            }
        }
    }

    Component {
        id: textBlock
        ScrollView {
            id: textScroll
            clip: true
            contentWidth: availableWidth
            ScrollBar.vertical: ScrollBar {
                id: vbar
                policy: textScroll.contentHeight > textScroll.availableHeight ? ScrollBar.AlwaysOn : ScrollBar.AsNeeded
                active: true
                width: 6
                background: Rectangle { color: "transparent" }
                contentItem: Rectangle {
                    implicitWidth: 6
                    radius: 3
                    color: vbar.pressed ? "#55DDEA" : vbar.hovered ? "#7BE7F1" : "#4A6075"
                    opacity: 0.85
                }
            }
            TextArea {
                id: textArea
                width: textScroll.availableWidth
                text: String(card.widgetData.text || "")
                textFormat: TextEdit.MarkdownText
                color: "#F2F5FA"
                font.pixelSize: 14
                wrapMode: TextEdit.Wrap
                readOnly: true
                selectByMouse: true
                hoverEnabled: true
                background: Item {}
                padding: 4
            }
        }
    }

    Component {
        id: threeDBlock
        ColumnLayout {
            spacing: 8
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "#101923"
                radius: 12
                clip: true

                AnimatedImage {
                    id: turntableAnim
                    anchors.fill: parent
                    source: String(card.widgetData.source || "")
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                    playing: card.activeMedia
                }

                Rectangle {
                    anchors.top: parent.top
                    anchors.right: parent.right
                    anchors.margins: 8
                    radius: 6
                    color: "#A014202D"
                    border.color: "#354A5E"
                    implicitHeight: 22
                    implicitWidth: badgeText.implicitWidth + 12

                    Text {
                        id: badgeText
                        anchors.centerIn: parent
                        text: "3D LIVE"
                        color: "#55DDEA"
                        font.pixelSize: 10
                        font.weight: Font.Bold
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                visible: card.widgetData.dimensions !== undefined

                Text {
                    Layout.fillWidth: true
                    text: {
                        var d = card.widgetData.dimensions || {width: 0, height: 0, depth: 0, unit: "m"}
                        return d.width + " × " + d.height + " × " + d.depth + " " + (d.unit || "m") + "  •  " + (card.widgetData.triangles || 0) + " tris"
                    }
                    color: "#8DA0B5"
                    font.pixelSize: 11
                    elide: Text.ElideRight
                }
            }

            Text {
                Layout.fillWidth: true
                visible: text.length > 0
                text: String(card.widgetData.caption || "")
                textFormat: Text.PlainText
                color: "#B4BFCE"
                wrapMode: Text.WordWrap
                font.pixelSize: 13
            }
        }
    }

    Component {
        id: imageBlock
        ColumnLayout {
            spacing: 8
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: card.widget.kind === "qr" ? "white" : "#101923"
                radius: 12
                clip: true
                Image {
                    id: image
                    anchors.fill: parent
                    anchors.margins: card.widget.kind === "qr" ? 12 : 0
                    source: String(card.widgetData.source || "")
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                    mipmap: card.widget.kind !== "qr"
                    Accessible.name: (card.widget && card.widget.title) ? card.widget.title : ""
                }
                Text {
                    anchors.centerIn: parent
                    visible: image.status === Image.Error
                    text: "This image is unavailable"
                    color: "#F193A0"
                }
            }
            Text {
                Layout.fillWidth: true
                visible: text.length > 0
                text: String(card.widgetData.caption || "")
                textFormat: Text.PlainText
                color: "#B4BFCE"
                wrapMode: Text.WordWrap
                font.pixelSize: 13
            }
        }
    }

    Component {
        id: videoBlock
        ColumnLayout {
            MediaPlayer {
                id: player
                property bool resumeOnShow: false
                source: String(card.widgetData.source || "")
                videoOutput: output
                // Intentionally silent; do not compete with the voice service.
                Component.onCompleted: if (card.activeMedia) play()
                onErrorOccurred: mediaError.text = "Playback unavailable: " + errorString
            }
            Connections {
                target: card
                function onActiveMediaChanged() {
                    if (!card.activeMedia) {
                        player.resumeOnShow = player.playbackState === MediaPlayer.PlayingState;
                        player.pause();
                    } else if (player.resumeOnShow) player.play();
                }
            }
            VideoOutput {
                id: output
                Layout.fillWidth: true
                Layout.fillHeight: true
                fillMode: VideoOutput.PreserveAspectFit
            }
            Text {
                id: mediaError
                Layout.fillWidth: true
                color: "#F193A0"
                wrapMode: Text.WordWrap
                textFormat: Text.PlainText
                visible: text.length > 0
            }
            ActionButton {
                text: player.playbackState === MediaPlayer.PlayingState ? "Pause" : "Play"
                onClicked: player.playbackState === MediaPlayer.PlayingState ? player.pause() : player.play()
            }
        }
    }

    Component {
        id: tableBlock
        ScrollView {
            id: tableScroll
            clip: true
            contentWidth: Math.max(320, card.widgetData.columns.length * 140)
            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
                width: 6
                background: Rectangle { color: "transparent" }
                contentItem: Rectangle { implicitWidth: 6; radius: 3; color: "#4A6075"; opacity: 0.85 }
            }
            ScrollBar.horizontal: ScrollBar {
                policy: ScrollBar.AsNeeded
                height: 6
                background: Rectangle { color: "transparent" }
                contentItem: Rectangle { implicitHeight: 6; radius: 3; color: "#4A6075"; opacity: 0.85 }
            }
            Column {
                width: Math.max(320, card.widgetData.columns.length * 140)
                spacing: 1
                Row {
                    Repeater {
                        model: card.widgetData.columns
                        Rectangle {
                            id: columnHeader
                            required property var modelData
                            width: 140; height: 42; color: "#293D50"
                            Text {
                                anchors.fill: parent; anchors.margins: 8
                                text: String(columnHeader.modelData); textFormat: Text.PlainText
                                color: "#F2F5FA"; font.pixelSize: 14; font.bold: true
                                verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
                            }
                        }
                    }
                }
                Repeater {
                    model: card.widgetData.rows
                    Row {
                        id: tableRow
                        required property var modelData
                        required property int index
                        Repeater {
                            model: tableRow.modelData
                            Rectangle {
                                id: tableCell
                                required property var modelData
                                width: 140; height: 42
                                color: tableRow.index % 2 ? "#182635" : "#203040"
                                Text {
                                    anchors.fill: parent; anchors.margins: 8
                                    text: String(tableCell.modelData); textFormat: Text.PlainText
                                    color: "#F2F5FA"; font.pixelSize: 14
                                    verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: chartBlock
        ScrollView {
            id: chartScroll
            clip: true
            contentWidth: availableWidth
            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
                width: 6
                background: Rectangle { color: "transparent" }
                contentItem: Rectangle { implicitWidth: 6; radius: 3; color: "#4A6075"; opacity: 0.85 }
            }
            Column {
                width: parent.width
                spacing: 12
                Repeater {
                    model: card.widgetData.labels
                    Column {
                        id: chartRow
                        required property var modelData
                        required property int index
                        width: parent.width
                        spacing: 5
                        Text {
                            text: String(chartRow.modelData) + "   " + card.widgetData.values[chartRow.index] + " " + String(card.widgetData.unit || "")
                            textFormat: Text.PlainText
                            color: "#F2F5FA"; font.pixelSize: 14
                        }
                        Rectangle {
                            width: Math.max(3, chartRow.width * card.widgetData.values[chartRow.index] / Math.max(1, ...card.widgetData.values))
                            height: 12; radius: 6; color: "#55DDEA"
                        }
                    }
                }
            }
        }
    }

    Component {
        id: progressBlock
        ColumnLayout {
            Text {
                Layout.fillWidth: true
                text: String(card.widgetData.text || "Working…")
                textFormat: Text.PlainText; wrapMode: Text.WordWrap
                color: "#F2F5FA"; font.pixelSize: 16
            }
            ProgressBar {
                Layout.fillWidth: true
                indeterminate: card.widgetData.value === undefined
                from: 0
                to: Number(card.widgetData.maximum || 100)
                value: Number(card.widgetData.value || 0)
            }
            Text {
                visible: card.widgetData.value !== undefined
                text: String(card.widgetData.value || 0) + " / " + String(card.widgetData.maximum || 100)
                color: "#B4BFCE"; font.pixelSize: 14
            }
            Item { Layout.fillHeight: true }
        }
    }
}
