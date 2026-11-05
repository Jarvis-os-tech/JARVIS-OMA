"""Bounded, composable UI descriptions. No generated program is executed."""
import math
import re

KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,47}$")
OPS = {"add", "subtract", "multiply", "divide", "min", "max", "round"}
NODE_FIELDS = {
    "column": {"children"}, "row": {"children"},
    "text": {"text", "tone"}, "heading": {"text"}, "metric": {"label", "value"},
    "input": {"label", "bind"}, "slider": {"label", "bind", "min", "max", "step"},
    "toggle": {"label", "bind"}, "select": {"label", "bind", "options"},
    "button": {"label", "prompt"}, "canvas": {"height", "shapes"},
    "divider": set(),
}


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 1e12:
        raise ValueError("Expected a bounded finite number")
    return value


def string(value, limit=2000):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError("Invalid view text")
    return value


def validate_view(spec):
    if not isinstance(spec, dict) or set(spec) - {"state", "computed", "layout", "width"}:
        raise ValueError("Expected state, computed, layout and optional width")
    state, computed = spec.get("state", {}), spec.get("computed", {})
    for values in (state, computed):
        if not isinstance(values, dict) or len(values) > 32 or any(not KEY.fullmatch(key) for key in values):
            raise ValueError("View state/computed keys must be short identifiers; at most 32 each")
    if set(state) & set(computed):
        raise ValueError("Computed names must differ from state names")
    for value in state.values():
        if isinstance(value, str): string(value)
        elif type(value) is not bool: number(value)
    refs = set(state) | set(computed)

    def expr(value, depth=0, visiting=()):
        if depth > 8: raise ValueError("Expression too deep")
        if isinstance(value, (str, bool)): return
        if type(value) in (int, float): number(value); return
        if not isinstance(value, dict): raise ValueError("Invalid expression")
        if set(value) == {"ref"}:
            key = value["ref"]
            if not isinstance(key, str) or key not in refs: raise ValueError("Unknown state reference")
            if key in computed:
                if key in visiting: raise ValueError("Cyclic computed values")
                expr(computed[key], depth + 1, visiting + (key,))
        elif set(value) == {"op", "args"} and value["op"] in OPS:
            args = value["args"]
            if not isinstance(args, list) or not 1 <= len(args) <= 8: raise ValueError("Invalid operation arguments")
            if value["op"] == "round" and len(args) != 1: raise ValueError("Round takes one argument")
            if value["op"] in {"subtract", "divide"} and len(args) != 2: raise ValueError("Operation takes two arguments")
            for arg in args: expr(arg, depth + 1, visiting)
        else: raise ValueError("Only references and arithmetic operations are supported")

    for key, value in computed.items(): expr(value, visiting=(key,))
    count = 0
    ids = set()

    def node(item, depth=0):
        nonlocal count
        count += 1
        if depth > 8 or count > 160: raise ValueError("View exceeds layout limits")
        if not isinstance(item, dict) or item.get("type") not in NODE_FIELDS: raise ValueError("Unsupported view component")
        kind = item["type"]
        if set(item) - ({"type", "id"} | NODE_FIELDS[kind]): raise ValueError("Unexpected component properties")
        if "id" in item:
            if not isinstance(item["id"], str) or not KEY.fullmatch(item["id"]) or item["id"] in ids: raise ValueError("Invalid/duplicate component ID")
            ids.add(item["id"])
        for field in ("text", "label", "prompt"):
            if field in item: string(item[field])
        if kind in {"text", "heading"}: string(item.get("text"))
        if kind in {"metric", "button", "input", "slider", "select", "toggle"}: string(item.get("label"), 160)
        if kind == "button": string(item.get("prompt"))
        if kind == "metric": expr(item.get("value"))
        if kind == "text" and item.get("tone", "normal") not in {"normal", "muted", "accent"}: raise ValueError("Invalid text tone")
        if kind in {"row", "column"}:
            children = item.get("children")
            if not isinstance(children, list) or not 1 <= len(children) <= 32: raise ValueError("Layout needs 1–32 children")
            for child in children: node(child, depth + 1)
        if kind in {"input", "slider", "select", "toggle"}:
            key = item.get("bind")
            if not isinstance(key, str) or key not in state: raise ValueError("Controls must bind an existing state field")
            value = state[key]
            if kind in {"input", "select"} and not isinstance(value, str): raise ValueError("Text controls need string state")
            if kind == "toggle" and type(value) is not bool: raise ValueError("Toggle needs boolean state")
            if kind == "slider":
                lo, hi, step = number(item.get("min", 0)), number(item.get("max", 100)), number(item.get("step", 1))
                if lo >= hi or step <= 0 or not lo <= number(value) <= hi: raise ValueError("Invalid slider range/state")
            if kind == "select":
                options = item.get("options")
                if not isinstance(options, list) or not 1 <= len(options) <= 30: raise ValueError("Invalid select options")
                for option in options: string(option, 160)
                if value not in options: raise ValueError("Select state must match an option")
        if kind == "canvas":
            height = number(item.get("height", 240))
            if not 80 <= height <= 600: raise ValueError("Canvas height must be 80–600")
            shapes = item.get("shapes")
            if not isinstance(shapes, list) or len(shapes) > 200: raise ValueError("Too many canvas shapes")
            for shape in shapes:
                if not isinstance(shape, dict) or shape.get("type") not in {"rect", "circle", "line", "text"}: raise ValueError("Unsupported shape")
                if set(shape) - {"type", "x", "y", "w", "h", "x2", "y2", "r", "text", "fill", "stroke", "width"}: raise ValueError("Unexpected shape properties")
                for key, value in shape.items():
                    if key in {"type", "text"}: string(value)
                    elif key in {"fill", "stroke"}:
                        if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value): raise ValueError("Use six-digit hex colors")
                    else: expr(value)

    node(spec.get("layout"))
    width = number(spec.get("width", 480))
    if not 300 <= width <= 960: raise ValueError("View width must be 300–960")
    return {"state": state, "computed": computed, "layout": spec["layout"], "width": width}


EXAMPLE = {
    "state": {"hours": 4, "rate": 25},
    "computed": {"cost": {"op": "multiply", "args": [{"ref": "hours"}, {"ref": "rate"}]}},
    "layout": {"type": "column", "children": [
        {"type": "text", "text": "Estimate before scheduling", "tone": "muted"},
        {"type": "slider", "label": "Hours", "bind": "hours", "min": 1, "max": 12},
        {"type": "metric", "label": "Estimated cost", "value": {"ref": "cost"}},
        {"type": "button", "label": "Use this estimate", "prompt": "Use the estimate for {{hours}} hours at {{rate}} per hour, total {{cost}}."},
    ]},
}


def describe():
    return {"kind": "view", "purpose": "Generate a custom interactive layout for this task, not a fixed dashboard.",
            "components": {key: sorted(value) for key, value in NODE_FIELDS.items()},
            "data": "{state:{key:scalar},computed:{key:expression},layout:node,width?:300..960}",
            "expressions": "Scalar, {ref:key}, or {op:operation,args:[expressions]}. Operations: add,subtract,multiply,divide,min,max,round. No code strings.",
            "text_bindings": "Text/labels/prompts support {{state_or_computed_key}}. Controls update local state immediately. Button prompt is sent to JARVIS with widget ID and current state.",
            "canvas": "Shapes: rect,circle,line,text; x,y,w,h,x2,y2,r,width are expressions in a 0..1000 coordinate space; fill/stroke are #RRGGBB. Text supports bindings.",
            "lifecycle": "Default floating; same widget_id updates layout. manage_widget handles latest or explicit ID, pin, move (x,y integer percentages 0..100), dismiss, state. clear_all removes all widgets. No Esc/desktop-return controls. Never invent source data or claim button effects before tool receipts.",
            "example": EXAMPLE}
