.pragma library
.import "TaskEventContract.js" as Contract

function check(value, schema) {
    if (schema.anyOf) {
        for (const option of schema.anyOf) { try { check(value, option); return; } catch (e) {} }
        throw Error("Task value does not match the contract");
    }
    const type = schema.type;
    if ((type === "object" && (!value || typeof value !== "object" || Array.isArray(value))) ||
        (type === "string" && typeof value !== "string") ||
        (type === "integer" && !Number.isSafeInteger(value)) ||
        (type === "boolean" && typeof value !== "boolean") ||
        (type === "null" && value !== null)) throw Error("Invalid task field type");
    if (schema.const !== undefined && value !== schema.const) throw Error("Unsupported task schema");
    if (schema.enum && schema.enum.indexOf(value) === -1) throw Error("Unsupported task field value");
    if (type === "string") {
        const length = Array.from(value).length;
        if ((schema.minLength !== undefined && length < schema.minLength) ||
            (schema.maxLength !== undefined && length > schema.maxLength) ||
            (schema.pattern && !new RegExp(schema.pattern).test(value))) throw Error("Invalid task text");
    }
    if (type === "integer" && ((schema.minimum !== undefined && value < schema.minimum) ||
                              (schema.maximum !== undefined && value > schema.maximum))) throw Error("Invalid task counter");
    if (type === "object") {
        (schema.required || []).forEach(key => { if (!Object.prototype.hasOwnProperty.call(value, key)) throw Error("Missing task field"); });
        Object.keys(value).forEach(key => {
            if (!schema.properties[key]) { if (schema.additionalProperties === false) throw Error("Unexpected task field"); }
            else check(value[key], schema.properties[key]);
        });
    }
}

function validate(event) {
    check(event, Contract.contract);
    if (event.terminal !== (Contract.contract["x-terminal-states"].indexOf(event.state) !== -1)) throw Error("Invalid task terminal flag");
    if (event.progress && event.progress.completed > event.progress.total) throw Error("Invalid task progress");
    if (event.evidence.verified !== (event.state === Contract.contract["x-verified-state"])) throw Error("Task success requires evidence");
    if (event.evidence.verified && Contract.contract["x-verified-scopes"].indexOf(event.evidence.scope) === -1) throw Error("Invalid verification scope");
    return event;
}

function initial() { return {stream_id: "", cursor: 0, hidden: {}, revisions: {}, pending: {}}; }

function hide(state, id) {
    const key = Object.keys(state.revisions).find(key => state.revisions[key].widget_id === id);
    const generation = key ? state.revisions[key].generation : 1;
    return Object.assign({}, state, {hidden: Object.assign({}, state.hidden, {[id]: generation})});
}

function apply(items, state, batch, now) {
    if (!batch || batch.schema_version !== 1 || !/^[a-f0-9]{32}$/.test(batch.stream_id || "") ||
        !Number.isSafeInteger(batch.cursor) || batch.cursor < 0 || !Array.isArray(batch.events) || batch.events.length > 24)
        throw Error("Invalid task snapshot");
    if (state.stream_id && state.stream_id !== batch.stream_id) throw Error("Task stream changed; reconnect the view");
    batch.events.forEach(event => {
        validate(event);
        if (event.stream_id !== batch.stream_id || event.sequence > batch.cursor) throw Error("Task snapshot identity mismatch");
    });
    if (batch.cursor < state.cursor) return {items: items, state: state, accepted: 0};
    const next = Object.assign({}, state, {stream_id: batch.stream_id,
        cursor: batch.cursor, revisions: Object.assign({}, state.revisions), hidden: Object.assign({}, state.hidden), pending: {}});
    let copy = items.slice(), accepted = 0;
    batch.events.slice().sort((a, b) => a.sequence - b.sequence).forEach(event => {
        const old = next.revisions[event.task_id];
        if (!old && event.sequence <= state.cursor && !state.pending[event.task_id]) return;
        if (old && (event.revision <= old.revision || event.generation < old.generation ||
                    (old.terminal && event.generation === old.generation))) return;
        const existing = copy.find(item => item.id === event.widget_id);
        if (existing && (!existing.task || existing.task.task_id !== event.task_id)) throw Error("Task card identity collision");
        const hidden = next.hidden[event.widget_id] !== undefined && event.generation <= next.hidden[event.widget_id];
        if (!hidden && !existing && copy.length >= 24) { next.pending[event.task_id] = event.sequence; return; }
        next.revisions[event.task_id] = {revision: event.revision, generation: event.generation, terminal: event.terminal, sequence: event.sequence, widget_id: event.widget_id};
        if (hidden) return;
        delete next.hidden[event.widget_id];
        const widget = {id: event.widget_id, kind: "task", title: event.title,
            data: {text: event.message, state: event.state,
                   label: Contract.contract["x-state-labels"][event.state],
                   evidence: Contract.contract["x-evidence-labels"][event.evidence.scope],
                   progress: event.progress}, task: event,
            floating: existing ? existing.floating : true, pinned: existing ? existing.pinned : false,
            expiresAt: event.terminal ? now + 120000 : 0};
        if (existing) copy = copy.map(item => item.id === widget.id ? widget : item);
        else copy.push(widget);
        accepted++;
    });
    // A global cursor fences forgotten older events, so retained view metadata
    // remains bounded without resurrecting expired or dismissed cards.
    const keys = Object.keys(next.revisions).sort((a, b) => next.revisions[b].sequence - next.revisions[a].sequence);
    keys.slice(256).forEach(key => { delete next.revisions[key]; });
    const hidden = Object.keys(next.hidden);
    hidden.slice(0, Math.max(0, hidden.length - 256)).forEach(key => { delete next.hidden[key]; });
    return {items: copy, state: next, accepted: accepted};
}
