.pragma library
.import "ViewSchema.js" as Views

var kinds = ["view", "text", "qr", "image", "pip", "table", "chart", "progress"];

function validate(value) {
    if (!value || typeof value !== "object" || Array.isArray(value))
        throw new Error("Expected a widget object");
    if (!/^[A-Za-z0-9_-]{1,80}$/.test(value.id || "") || kinds.indexOf(value.kind) === -1)
        throw new Error("Unsupported widget identity or kind");
    if (value.id.indexOf("jtask_") === 0) throw new Error("Task card IDs are reserved for task events");
    if (typeof value.title !== "string" || value.title.length > 160 || !value.data || typeof value.data !== "object")
        throw new Error("Invalid widget title/data");
    if (JSON.stringify(value).length > 65536)
        throw new Error("Widget payload too large");
    var d = value.data;
    if (value.kind === "view") Views.validate(d);
    if (["qr", "image", "pip"].indexOf(value.kind) !== -1 &&
        (typeof d.source !== "string" || !/^file:\/\//.test(d.source)))
        throw new Error("Only prepared local media is supported");
    if (value.kind === "text" && (typeof d.text !== "string" || d.text.length > 8000))
        throw new Error("Invalid text card");
    if (value.kind === "table" && (!Array.isArray(d.columns) || !d.columns.length || d.columns.length > 8 || !Array.isArray(d.rows) || d.rows.length > 100))
        throw new Error("Invalid table");
    if (value.kind === "chart" && (!Array.isArray(d.labels) || !Array.isArray(d.values) || !d.labels.length || d.labels.length > 20 || d.labels.length !== d.values.length || !d.values.every(n => typeof n === "number" && isFinite(n) && n >= 0)))
        throw new Error("Invalid chart");
    if (value.kind === "progress" && d.value !== undefined &&
        (typeof d.value !== "number" || !isFinite(d.value) || typeof d.maximum !== "number" || !isFinite(d.maximum) || d.maximum <= 0 || d.value < 0 || d.value > d.maximum))
        throw new Error("Invalid progress");
    var ttl = value.expires_seconds === undefined ? 120 : value.expires_seconds;
    if (typeof ttl !== "number" || !isFinite(ttl) || ttl < 0 || ttl > 86400)
        throw new Error("Invalid widget lifetime");
    return {id: value.id, kind: value.kind, title: value.title, data: d,
            floating: value.floating !== false, pinned: false,
            expiresAt: ttl ? Date.now() + ttl * 1000 : 0};
}

function upsert(items, widget) {
    var copy = items.slice();
    var index = copy.findIndex(item => item.id === widget.id);
    if (index === -1) {
        if (copy.length >= 24) throw new Error("Close a card before adding more");
        copy.push(widget);
    } else {
        if (copy[index].task) throw new Error("Task cards can only be updated by task events");
        widget.pinned = copy[index].pinned;
        copy[index] = widget;
    }
    return copy;
}

function manage(items, id, action) {
    var index = items.findIndex(item => item.id === id);
    if (index === -1) throw new Error("Widget not found");
    if (action === "dismiss") return items.filter(item => item.id !== id);
    var item = Object.assign({}, items[index]);
    if (action === "pin") item.pinned = true;
    else if (action === "unpin") { item.pinned = false; item.expiresAt = Date.now() + 120000; }
    else if (action === "float") item.floating = true;
    else if (action === "canvas") item.floating = false;
    else throw new Error("Unknown widget action");
    var copy = items.slice(); copy[index] = item; return copy;
}

function prune(items, now, interactingIds) {
    return items.filter(item => item.pinned || !item.expiresAt || item.expiresAt > now || interactingIds.indexOf(item.id) !== -1);
}
