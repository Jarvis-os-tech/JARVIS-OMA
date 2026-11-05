import QtQuick
import QtQuick.Controls
import QtTest
import "../../ui/jarvis_widgets"
import "../../ui/jarvis_widgets/WidgetModel.js" as Model
import "../../ui/jarvis_widgets/ViewSchema.js" as Schema
import "../../ui/jarvis_widgets/TaskEvents.js" as Tasks

TestCase {
    id: test
    name: "ExistingShellWidgets"
    width: 650; height: 520; visible: true
    when: windowShown

    Component { id: cardComponent; WidgetCard { width: 600; height: 450 } }
    InputBar { id: input; width: 600; draft: "Keep my draft" }
    SignalSpy { id: closed; target: input; signalName: "closeRequested" }
    Component { id: viewComponent; GeneratedView { width: 600 } }
    property var activeView: null
    SignalSpy { id: submitted; target: test.activeView; signalName: "submitted" }

    function test_input_has_no_escape_navigation() {
        closed.clear();
        input.takeFocus(); keyClick(Qt.Key_Escape);
        compare(closed.count, 0); compare(input.draft, "Keep my draft");
    }
    function viewSpec() {
        return {state: {hours: 4, rate: 25}, computed: {cost: {op: "multiply", args: [{ref: "hours"}, {ref: "rate"}]}},
            layout: {type: "column", children: [
                {type: "slider", id: "hours", label: "Hours", bind: "hours", min: 1, max: 12},
                {type: "metric", label: "Cost", value: {ref: "cost"}},
                {type: "button", id: "apply", label: "Use estimate", prompt: "Use {{hours}} hours, total {{cost}}"}
            ]}};
    }
    function test_generated_controls_recalculate_and_submit_selected_values() {
        activeView = createTemporaryObject(viewComponent, test, {specification: Schema.validate(viewSpec())});
        verify(activeView); wait(30);
        compare(activeView.value({ref: "cost"}), 100);
        const slider = findChild(activeView, "control-hours"); verify(slider);
        slider.forceActiveFocus(); keyClick(Qt.Key_Right);
        compare(activeView.formState.hours, 5);
        compare(activeView.value({ref: "cost"}), 125);
        const action = findChild(activeView, "control-apply"); verify(action);
        submitted.clear(); action.forceActiveFocus(); keyClick(Qt.Key_Space);
        compare(submitted.count, 1);
        compare(submitted.signalArguments[0][0], "Use 5 hours, total 125");
        compare(submitted.signalArguments[0][1].hours, 5);
        activeView = null;
    }
    function test_generated_layouts_reject_code_cycles_and_unknown_bindings() {
        let failures = 0;
        for (const spec of [
            {layout: {type: "html", code: "alert(1)"}},
            {computed: {a: {ref: "a"}}, layout: {type: "text", text: "A"}},
            {state: {}, layout: {type: "input", label: "Bad", bind: "unknown"}}
        ]) { try { Schema.validate(spec); } catch (error) { failures++; } }
        compare(failures, 3);
        compare(Schema.resolve({op: "divide", args: [1, 0]}, {}, {}), "Unavailable");
    }
    function test_generated_canvas_and_nested_layout_render() {
        const spec = {state: {x: 200}, layout: {type: "row", children: [
            {type: "canvas", height: 180, shapes: [{type: "circle", x: {ref: "x"}, y: 500, r: 50}]},
            {type: "column", children: [{type: "heading", text: "Diagram"}, {type: "text", text: "Position {{x}}"}]}
        ]}};
        const view = createTemporaryObject(viewComponent, test, {specification: Schema.validate(spec)});
        verify(view); wait(30); verify(view.implicitHeight >= 180);
    }

    function fixture(id, kind, data) {
        return Model.validate({id: id, kind: kind, title: "Example", data: data, expires_seconds: 60});
    }
    function taskEvent(state, revision) {
        return {schema_version: 1, stream_id: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", sequence: revision,
            task_id: "file_task:example", widget_id: "jtask_aaaaaaaaaaaaaaaaaaaaaaaa", source: "file_task",
            revision: revision, generation: 1, state: state, terminal: state === "completed",
            title: "Save notes", message: "Observed task state", updated_at: "2026-11-03T00:00:00Z",
            evidence: {verified: state === "completed", scope: state === "completed" ? "file_step_checks" : "none"},
            progress: {completed: state === "completed" ? 3 : 1, total: 3}};
    }
    function taskBatch(event) { return {schema_version: 1, stream_id: event.stream_id, cursor: event.sequence, events: [event]}; }
    function test_task_card_renders_measured_progress_and_verified_state() {
        const event = taskEvent("completed", 2);
        const result = Tasks.apply([], Tasks.initial(), taskBatch(event), 100);
        const card = createTemporaryObject(cardComponent, test, {widget: result.items[0]});
        verify(card); wait(30);
        const label = findChild(card, "task-state"); verify(label); compare(label.text, "Completed");
        compare(card.widgetData.progress.completed, 3);
        compare(result.items[0].task.task_id, event.task_id);
    }
    function test_task_replay_cannot_overwrite_or_resurrect_a_completed_card() {
        const first = taskEvent("running", 1), last = taskEvent("completed", 2);
        let result = Tasks.apply([], Tasks.initial(), taskBatch(first), 0);
        result = Tasks.apply(result.items, result.state, taskBatch(last), 10);
        result = Tasks.apply(result.items, result.state, taskBatch(first), 20);
        compare(result.items.length, 1); compare(result.items[0].data.label, "Completed");
        const hidden = Tasks.hide(result.state, last.widget_id);
        compare(Tasks.apply([], hidden, taskBatch(last), 30).items.length, 0);
        const resumed = taskEvent("running", 3); resumed.generation = 2;
        compare(Tasks.apply([], hidden, taskBatch(resumed), 40).items.length, 1);
        let rejected = false;
        last.evidence.verified = false;
        try { Tasks.validate(last); } catch (error) { rejected = true; }
        verify(rejected);
    }
    function test_update_preserves_pin_and_identity() {
        let items = Model.upsert([], fixture("one", "text", {text: "First"}));
        items = Model.manage(items, "one", "pin");
        items = Model.upsert(items, fixture("one", "text", {text: "Updated"}));
        compare(items.length, 1); verify(items[0].pinned); compare(items[0].data.text, "Updated");
    }
    function test_expiration_respects_pins_and_interaction() {
        let a = fixture("a", "text", {text: "A"}); a.expiresAt = 1;
        let b = fixture("b", "text", {text: "B"}); b.expiresAt = 1; b.pinned = true;
        let c = fixture("c", "text", {text: "C"}); c.expiresAt = 1;
        let items = Model.prune([a, b, c], 100, ["c"]);
        compare(items.length, 2); compare(items[0].id, "b"); compare(items[1].id, "c");
    }
    function test_remote_media_and_code_rejected() {
        let failed = 0;
        try { fixture("one", "qml", {code: "exit"}); } catch (e) { failed++; }
        try { fixture("two", "image", {source: "https://example.org/a.png"}); } catch (e) { failed++; }
        compare(failed, 2);
    }
    function test_supported_card_renderers_data() {
        return [
            {tag: "text", kind: "text", value: {text: "Real retrieved text"}},
            {tag: "table", kind: "table", value: {columns: ["Release", "Memory"], rows: [["A", "418 MiB"]]}},
            {tag: "chart", kind: "chart", value: {labels: ["A", "B"], values: [418, 462], unit: "MiB"}},
            {tag: "progress", kind: "progress", value: {text: "Reading sources", value: 1, maximum: 3}},
            {tag: "view", kind: "view", value: viewSpec()}
        ];
    }
    function test_supported_card_renderers(row) {
        const card = createTemporaryObject(cardComponent, test, {widget: fixture("example", row.kind, row.value)});
        verify(card); wait(1); verify(card.width > 0); verify(card.visible);
    }
}
