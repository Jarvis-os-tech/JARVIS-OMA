pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "WidgetModel.js" as Model
import "TaskEvents.js" as TaskEvents

Item {
    id: root
    property var shell: null
    property var manifest: null
    property var widgets: []
    property var taskState: TaskEvents.initial()
    property int omittedTasks: 0
    property int taskProjectionErrors: 0
    property var widgetStates: ({})
    property var positions: ({})
    property string lastActive: ""
    property string mode: "hidden"
    property string draft: ""
    property string inputError: ""
    property string pendingDraft: ""
    property string pendingWidget: ""
    property bool sending: false
    property var interactingIds: []
    readonly property bool opened: mode !== "hidden"
    readonly property string helper: decodeURIComponent(Qt.resolvedUrl("backend.py").toString().replace(/^file:\/\//, ""))
    readonly property var canvasWidgets: widgets.filter(item => !item.floating)

    function receipt(extra) { return JSON.stringify(Object.assign({ok: true}, extra || {})); }
    function open(payloadJson) { mode = "canvas"; return receipt({mode: mode}); }
    function close() { return closeAll(); }
    function toggle() { mode = mode === "canvas" ? "hidden" : "canvas"; }
    function closeAll() {
        mode = "hidden";
        widgets = widgets.map(item => Object.assign({}, item, {floating: false}));
        return receipt({mode: mode});
    }
    function trimState() {
        const state = {}, position = {};
        widgets.forEach(item => { state[item.id] = widgetStates[item.id] || {}; position[item.id] = positions[item.id] || {}; });
        widgetStates = state; positions = position;
    }
    function present(payloadJson) {
        try {
            const widget = Model.validate(JSON.parse(payloadJson));
            widgets = Model.upsert(widgets, widget);
            widgetStates = Object.assign({}, widgetStates, {[widget.id]: widget.data.state || {}});
            lastActive = widget.id;
            if (!widget.floating) mode = "canvas";
            return receipt({status: "accepted", id: widget.id, title: widget.title, kind: widget.kind});
        } catch (error) { return JSON.stringify({ok: false, error: String(error)}); }
    }
    function manage(payloadJson) {
        try {
            const request = JSON.parse(payloadJson);
            const id = request.id || (widgets.some(w => w.id === lastActive) ? lastActive : widgets.length ? widgets[widgets.length - 1].id : "");
            if (!widgets.some(w => w.id === id)) throw Error("Widget not found");
            if (request.action === "dismiss" && widgets.some(w => w.id === id && w.task)) taskState = TaskEvents.hide(taskState, id);
            if (request.action === "move") {
                if (typeof request.x !== "number" || typeof request.y !== "number" || !isFinite(request.x) || !isFinite(request.y) || request.x < 0 || request.x > 1 || request.y < 0 || request.y > 1) throw Error("Position must be normalized 0–1");
                widgets = Model.manage(widgets, id, "float");
                positions = Object.assign({}, positions, {[id]: {x: request.x, y: request.y}});
            } else if (request.action !== "state") widgets = Model.manage(widgets, id, request.action);
            if (request.action === "canvas") mode = "canvas";
            trimState();
            return receipt({id: id, action: request.action, state: widgetStates[id] || {}});
        } catch (error) { return JSON.stringify({ok: false, error: String(error)}); }
    }
    function interact(id, active) {
        interactingIds = interactingIds.filter(value => value !== id);
        if (active) { interactingIds = interactingIds.concat([id]); lastActive = id; }
    }
    function taskEvents(payloadJson) {
        try {
            const batch = JSON.parse(payloadJson);
            const result = TaskEvents.apply(widgets, taskState, batch, Date.now());
            widgets = result.items; taskState = result.state;
            omittedTasks = batch.omitted || 0;
            taskProjectionErrors = (batch.projection_errors || []).length;
            trimState();
            return receipt({accepted: result.accepted, cursor: taskState.cursor});
        } catch (error) { return JSON.stringify({ok: false, error: String(error)}); }
    }
    function saveState(id, values) {
        lastActive = id;
        widgetStates = Object.assign({}, widgetStates, {[id]: values});
    }
    function send(message, widgetId) {
        if (sending || !message.trim()) return;
        if (message.length > 16000) { inputError = "This request is too large. Shorten the input and try again."; return; }
        pendingWidget = widgetId || "";
        pendingDraft = message; sending = true; inputError = "";
        sendProcess.command = ["python3", "-u", helper, "send", message];
        sendProcess.running = true;
    }
    function submitWidget(id, prompt, values) {
        saveState(id, values);
        send(prompt + "\nWidget context: " + JSON.stringify({id: id, state: values}), id);
    }

    IpcHandler {
        target: "jarvis-canvas"
        function open(): string { return root.open("{}"); }
        function close(): string { return root.closeAll(); }
        function input(): string { root.mode = "input"; return root.receipt({mode: root.mode}); }
        function closeInput(): string {
            if (root.mode === "input") root.mode = "hidden";
            return root.receipt({mode: root.mode});
        }
        function clear(): string {
            root.widgets.filter(item => item.task && !item.pinned).forEach(item => { root.taskState = TaskEvents.hide(root.taskState, item.id); });
            root.widgets = root.widgets.filter(item => item.pinned); root.trimState();
            return root.receipt({retained: root.widgets.length});
        }
        function clearAll(): string {
            root.widgets.filter(item => item.task).forEach(item => { root.taskState = TaskEvents.hide(root.taskState, item.id); });
            root.widgets = []; root.trimState(); root.mode = "hidden";
            return root.receipt({retained: 0});
        }
        function present(payload: string): string { return root.present(payload); }
        function taskEvents(payload: string): string { return root.taskEvents(payload); }
        function manage(payload: string): string { return root.manage(payload); }
        function status(): string {
            return root.receipt({engine: "composed-v1", mode: root.mode, canvasVisible: canvas.backingWindowVisible,
                taskEventStream: root.taskState.stream_id, taskCursor: root.taskState.cursor,
                omittedTasks: root.omittedTasks, taskProjectionErrors: root.taskProjectionErrors,
                inputVisible: inputPanel.backingWindowVisible, active_widget_id: root.lastActive,
                widgets: root.widgets.map(item => ({id: item.id, title: item.title, kind: item.kind,
                    floating: item.floating, pinned: item.pinned, task: item.task || null,
                    state: root.widgetStates[item.id] || {}}))});
        }
    }
    Timer {
        interval: 2000; running: root.widgets.length > 0; repeat: true
        onTriggered: {
            const keep = Model.prune(root.widgets, Date.now(), root.interactingIds);
            if (keep.length !== root.widgets.length) { root.widgets = keep; root.trimState(); }
        }
    }
    Process {
        id: sendProcess
        stdout: StdioCollector { id: sendOutput }
        stderr: StdioCollector {}
        onExited: code => {
            root.sending = false;
            try {
                const result = JSON.parse(sendOutput.text);
                if (code === 0 && result.ok) {
                    if (root.draft === root.pendingDraft) root.draft = "";
                    if (root.mode === "input" && !root.pendingWidget) root.mode = "hidden";
                } else root.inputError = result.error || "Request was not accepted";
            } catch (error) { root.inputError = "JARVIS Voice is unavailable. Your inputs are kept."; }
        }
    }

    // A nonmodal group of widgets, without workspace chrome or a desktop backdrop.
    PanelWindow {
        id: canvas
        visible: root.mode === "canvas" && root.canvasWidgets.length > 0
        anchors { top: true; right: true }
        margins { top: 90; right: 24 }
        implicitWidth: Math.min(1020, screen.width - 48)
        implicitHeight: Math.min(screen.height - 130, grid.implicitHeight + 8)
        color: "transparent"; exclusionMode: ExclusionMode.Ignore
        WlrLayershell.namespace: "jarvis-task-canvas"
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand
        ScrollView {
            id: canvasScroll
            anchors.fill: parent; clip: true; contentWidth: availableWidth
            GridLayout {
                id: grid
                width: canvasScroll.availableWidth
                columns: width >= 900 ? 2 : 1
                rowSpacing: 16; columnSpacing: 16
                Repeater {
                    model: root.canvasWidgets
                    WidgetCard {
                        required property var modelData
                        Layout.fillWidth: true; Layout.preferredWidth: 440; Layout.preferredHeight: implicitHeight
                        widget: modelData; activeMedia: canvas.visible
                        requestBusy: root.sending
                        requestError: root.pendingWidget === modelData.id ? root.inputError : ""
                        onStateEdited: values => root.saveState(modelData.id, values)
                        onSubmitted: (prompt, values) => root.submitWidget(modelData.id, prompt, values)
                        onDismissRequested: root.manage(JSON.stringify({id: modelData.id, action: "dismiss"}))
                        onInteractingChanged: root.interact(modelData.id, interacting)
                        Component.onDestruction: root.interact(modelData.id, false)
                    }
                }
            }
        }
    }
    PanelWindow {
        id: inputPanel
        anchors { bottom: true; left: true; right: true }
        margins.bottom: 44
        margins.left: Math.max(24, (screen.width - 820) / 2)
        margins.right: Math.max(24, (screen.width - 820) / 2)
        implicitHeight: floatingInput.implicitHeight
        visible: root.mode === "input"
        color: "transparent"; exclusionMode: ExclusionMode.Ignore
        WlrLayershell.namespace: "jarvis-context-input"
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand
        InputBar {
            id: floatingInput
            anchors.fill: parent
            draft: root.draft; busy: root.sending; error: root.inputError
            onEdited: value => root.draft = value
            onSubmitted: value => root.send(value, "")
        }
    }
    Variants {
        model: root.widgets.filter(item => item.floating).map(item => item.id)
        PanelWindow {
            id: floating
            required property string modelData
            readonly property var widgetValue: root.widgets.find(w => w.id === modelData) || ({data: {}})
            readonly property int slot: root.widgets.findIndex(w => w.id === modelData)
            readonly property var position: root.positions[modelData] || ({})
            property real startX: 0
            property real startY: 0
            anchors { top: true; left: true }
            margins.top: position.y !== undefined ? Math.max(0, screen.height - height) * position.y : Math.max(0, Math.min(screen.height - height, 100 + slot * 36))
            margins.left: position.x !== undefined ? Math.max(0, screen.width - width) * position.x : Math.max(0, screen.width - width - 28 - slot * 36)
            implicitWidth: Math.min(widgetValue.data.width || floatingCard.implicitWidth, screen.width - 32)
            implicitHeight: Math.min(floatingCard.implicitHeight, screen.height - 120)
            color: "transparent"; visible: true; exclusionMode: ExclusionMode.Ignore
            WlrLayershell.namespace: "jarvis-context-widget"
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand
            WidgetCard {
                id: floatingCard
                anchors.fill: parent
                widget: floating.widgetValue; inCanvas: false
                requestBusy: root.sending
                requestError: root.pendingWidget === floating.modelData ? root.inputError : ""
                onStateEdited: values => root.saveState(floating.modelData, values)
                onSubmitted: (prompt, values) => root.submitWidget(floating.modelData, prompt, values)
                onDismissRequested: root.manage(JSON.stringify({id: floating.modelData, action: "dismiss"}))
                onDragStarted: { floating.startX = floating.margins.left; floating.startY = floating.margins.top; }
                onDragged: (x, y) => {
                    const px = Math.max(0, Math.min(1, (floating.startX + x) / Math.max(1, floating.screen.width - floating.width)));
                    const py = Math.max(0, Math.min(1, (floating.startY + y) / Math.max(1, floating.screen.height - floating.height)));
                    root.positions = Object.assign({}, root.positions, {[floating.modelData]: {x: px, y: py}});
                }
                onInteractingChanged: root.interact(floating.modelData, interacting)
                Component.onDestruction: root.interact(floating.modelData, false)
            }
        }
    }
}
