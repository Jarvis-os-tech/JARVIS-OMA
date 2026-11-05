.pragma library

var fields = {
    column: ["children"], row: ["children"], text: ["text", "tone"], heading: ["text"],
    metric: ["label", "value"], input: ["label", "bind"], slider: ["label", "bind", "min", "max", "step"],
    toggle: ["label", "bind"], select: ["label", "bind", "options"], button: ["label", "prompt"],
    canvas: ["height", "shapes"], divider: []
};
var operations = ["add", "subtract", "multiply", "divide", "min", "max", "round"];

function validate(spec) {
    if (!spec || !spec.layout || Object.keys(spec).some(k => !["state", "computed", "layout", "width"].includes(k))) throw Error("Invalid generated view");
    const state = spec.state || {}, computed = spec.computed || {};
    const keys = Object.keys(state).concat(Object.keys(computed));
    if (Object.keys(state).length > 32 || Object.keys(computed).length > 32 || new Set(keys).size !== keys.length || keys.some(k => !/^[A-Za-z][A-Za-z0-9_]{0,47}$/.test(k))) throw Error("Invalid view state");
    Object.values(state).forEach(v => {
        if (!["string", "number", "boolean"].includes(typeof v) || (typeof v === "number" && (!isFinite(v) || Math.abs(v) > 1e12)) || (typeof v === "string" && v.length > 2000)) throw Error("Invalid state value");
    });
    function expression(e, depth, seen) {
        if (depth > 8) throw Error("Expression too deep");
        if (typeof e === "number" && isFinite(e) && Math.abs(e) <= 1e12) return;
        if (typeof e === "string" && e.length <= 2000 || typeof e === "boolean") return;
        if (!e || Array.isArray(e) || typeof e !== "object") throw Error("Invalid expression");
        if (Object.keys(e).length === 1 && keys.includes(e.ref)) {
            if (computed[e.ref] !== undefined) {
                if (seen.includes(e.ref)) throw Error("Computed cycle");
                expression(computed[e.ref], depth + 1, seen.concat([e.ref]));
            }
        } else if (Object.keys(e).length === 2 && operations.includes(e.op) && Array.isArray(e.args) && e.args.length >= 1 && e.args.length <= 8) {
            if ((e.op === "round" && e.args.length !== 1) || (["divide", "subtract"].includes(e.op) && e.args.length !== 2)) throw Error("Invalid arithmetic arity");
            e.args.forEach(a => expression(a, depth + 1, seen));
        } else throw Error("Unsupported expression");
    }
    Object.keys(computed).forEach(k => expression(computed[k], 0, [k]));
    let count = 0; const ids = [];
    function node(n, depth) {
        if (++count > 160 || depth > 8 || !n || !fields[n.type]) throw Error("Unsupported layout");
        if (Object.keys(n).some(k => !["type", "id"].concat(fields[n.type]).includes(k))) throw Error("Unknown component property");
        if (n.id !== undefined) {
            if (!/^[A-Za-z][A-Za-z0-9_]{0,47}$/.test(n.id) || ids.includes(n.id)) throw Error("Invalid component ID");
            ids.push(n.id);
        }
        ["text", "label", "prompt"].forEach(k => { if (n[k] !== undefined && (typeof n[k] !== "string" || n[k].length > 2000)) throw Error("Invalid text"); });
        if (["text", "heading"].includes(n.type) && typeof n.text !== "string") throw Error("Text required");
        if (["input", "slider", "toggle", "select", "button", "metric"].includes(n.type) && typeof n.label !== "string") throw Error("Label required");
        if (["row", "column"].includes(n.type)) {
            if (!Array.isArray(n.children) || !n.children.length || n.children.length > 32) throw Error("Invalid children");
            n.children.forEach(c => node(c, depth + 1));
        }
        if (["input", "slider", "toggle", "select"].includes(n.type) && !Object.prototype.hasOwnProperty.call(state, n.bind)) throw Error("Unknown control binding");
        if (["input", "select"].includes(n.type) && typeof state[n.bind] !== "string") throw Error("Text state required");
        if (n.type === "toggle" && typeof state[n.bind] !== "boolean") throw Error("Boolean state required");
        if (n.type === "slider" && (typeof state[n.bind] !== "number" || !isFinite(n.min ?? 0) || !isFinite(n.max ?? 100) || (n.min ?? 0) >= (n.max ?? 100) || (n.step ?? 1) <= 0 || state[n.bind] < (n.min ?? 0) || state[n.bind] > (n.max ?? 100))) throw Error("Invalid slider");
        if (n.type === "select" && (!Array.isArray(n.options) || n.options.length > 30 || !n.options.includes(state[n.bind]) || n.options.some(x => typeof x !== "string" || x.length > 160))) throw Error("Invalid options");
        if (n.type === "button" && typeof n.prompt !== "string") throw Error("Button prompt required");
        if (n.type === "metric") expression(n.value, 0, []);
        if (n.type === "canvas") {
            if ((n.height ?? 240) < 80 || (n.height ?? 240) > 600 || !Array.isArray(n.shapes) || n.shapes.length > 200) throw Error("Invalid canvas");
            n.shapes.forEach(s => {
                if (!s || !["rect", "circle", "line", "text"].includes(s.type)) throw Error("Invalid shape");
                Object.keys(s).forEach(k => {
                    if (["type", "text"].includes(k)) { if (typeof s[k] !== "string" || s[k].length > 2000) throw Error("Invalid shape text"); }
                    else if (["fill", "stroke"].includes(k)) { if (!/^#[a-fA-F0-9]{6}$/.test(s[k])) throw Error("Invalid color"); }
                    else if (["x", "y", "w", "h", "x2", "y2", "r", "width"].includes(k)) expression(s[k], 0, []);
                    else throw Error("Unknown shape field");
                });
            });
        }
    }
    node(spec.layout, 0);
    if (typeof (spec.width ?? 480) !== "number" || (spec.width ?? 480) < 300 || (spec.width ?? 480) > 960) throw Error("Invalid view width");
    return spec;
}

function resolve(e, state, computed, depth) {
    depth = depth || 0;
    if (depth > 16) return "Unavailable";
    if (!e || typeof e !== "object") return e;
    if (e.ref !== undefined) return Object.prototype.hasOwnProperty.call(state, e.ref) ? state[e.ref] : resolve(computed[e.ref], state, computed, depth + 1);
    const a = e.args.map(x => resolve(x, state, computed, depth + 1));
    if (a.some(n => typeof n !== "number" || !isFinite(n))) return "Unavailable";
    let result;
    if (e.op === "add") result = a.reduce((x, y) => x + y, 0);
    else if (e.op === "subtract") result = a[0] - a[1];
    else if (e.op === "multiply") result = a.reduce((x, y) => x * y, 1);
    else if (e.op === "divide") result = a[1] === 0 ? NaN : a[0] / a[1];
    else if (e.op === "min") result = Math.min(...a);
    else if (e.op === "max") result = Math.max(...a);
    else if (e.op === "round") result = Math.round(a[0]);
    return isFinite(result) && Math.abs(result) <= 1e12 ? Math.round(result * 10000) / 10000 : "Unavailable";
}

function format(text, state, computed) {
    return String(text || "").replace(/\{\{([A-Za-z][A-Za-z0-9_]*)\}\}/g, (_, key) => {
        const value = resolve({ref: key}, state, computed);
        return value === undefined ? "" : String(value);
    });
}
