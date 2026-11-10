# Universal Visual Learning & Interactive Diagram Engine (Teaching Mode)

* **Author:** Gopi
* **Date:** 2026-11-06

## Overview

Teaching Mode is an interactive, voice-toggled pedagogical operating mode in JARVIS OS that transforms the assistant into a universal visual tutor. Designed around the cognitive principle that complex technical concepts are best understood when spoken explanations are synchronized with live visual artifacts, Teaching Mode observes what the student is doing on screen via Wayland capture (`grim`), speaks conversationally over PipeWire audio, and dynamically generates multi-modal visual explanations—including algorithmic animations, architectural diagrams, call graphs, and syntax walkthroughs—inside the desktop Quickshell HUD (`ui/jarvis_widgets`).

Whether the user asks to understand an algorithm (e.g. Bubble Sort, Dijkstra), a systems concept (e.g. Linux IPC, PipeWire audio graphs), a code error, or a math formulation, the engine automatically selects the optimal visual rendering pipeline, moves an animated pointer to spotlight key elements as it explains them, and restricts mutating desktop actuation to preserve student agency.

---

## Analysis

### 1. The 4-Tier Visual Diagramming & Rendering Engine
To enable learning "anything" visually without bloated external dependencies, JARVIS OS leverages four distinct visual pipelines already supported by the Linux host:

```
                                  ┌───────────────────────────────┐
                                  │   Student Speech / Question   │
                                  └───────────────┬───────────────┘
                                                  │
                                                  ▼
                                ┌───────────────────────────────────┐
                                │   Teaching Domain Intent Router   │
                                └─────────────────┬─────────────────┘
                                                  │
                ┌──────────────────┬──────────────┴─────┬──────────────────┐
                ▼                  ▼                    ▼                  ▼
     ┌─────────────────────┐┌──────────────┐   ┌─────────────────┐┌──────────────────┐
     │ 1. Vector Canvas    ││ 2. Graphviz  │   │ 3. Code/Syntax  ││ 4. Tabular &     │
     │    (DrawCanvas.qml) ││    (dot CLI) │   │    (Markdown)   ││    Bar Charts    │
     │ • Dynamic Arrays    ││ • System DAGs│   │ • Line Diffs    ││ • Complexity     │
     │ • Sorting Bars      ││ • State Mach.│   │ • Error Spans   ││ • Memory Layouts │
     │ • Pointers/Nodes    ││ • UML / Flow │   │ • Call Stacks   ││ • Value Traces   │
     └──────────┬──────────┘└──────┬───────┘   └────────┬────────┘└────────┬─────────┘
                │                  │                    │                  │
                └──────────────────┴──────────────┬─────┴──────────────────┘
                                                  │
                                                  ▼
                                ┌───────────────────────────────────┐
                                │   Quickshell Teaching HUD Card   │
                                │   (ui/jarvis_widgets - Floating)  │
                                │   • Synchronized Animated Pointer │
                                │   • Progressive Step Breadcrumb   │
                                └───────────────────────────────────┘
```

#### Pipeline 1: Native Vector Canvas (`DrawCanvas.qml` & `view_schema.py`)
* **Mechanism**: Declarative normalized 0..1000 coordinate space rendering `rect`, `circle`, `line`, and `text` with hex colors and arithmetic expression bindings.
* **Best Suited For**: Dynamic data structures, sorting array comparisons, pointer traversals, binary search trees, and heap trees.
* **Animated Pointer**: Renders an animated glowing spotlight (`#55DDEA`) that glides across cells/nodes as the voice explanation highlights each comparison.

#### Pipeline 2: Graphviz Structural Engine (`/usr/bin/dot`)
* **Mechanism**: Instant compilation of Graphviz DOT syntax into vector SVG or high-resolution PNG images written to `$XDG_RUNTIME_DIR/jarvis_diagrams/` and presented via `show_widget(kind="image", path=...)`.
* **Best Suited For**: System architecture diagrams, network topologies, database ERDs, Git commit graphs, compiler ASTs, and finite state machines.
* **Zero New Dependencies**: `dot` is already installed and verified at `/usr/bin/dot`.

#### Pipeline 3: Syntax & Diagnostic Walkthrough (`MarkdownBlocks.js`)
* **Mechanism**: Bounded Markdown cards supporting syntax-highlighted code blocks, line numbers, error badges, and collapsible hint accordions.
* **Best Suited For**: Debugging stack traces, code refactoring explanations, language idioms, and terminal command recipes.

#### Pipeline 4: Comparative Cards & Charts (`WidgetCard.qml`)
* **Mechanism**: Built-in multi-column tables, progress indicators, and native bar charts.
* **Best Suited For**: Time/space complexity comparisons ($O(n^2)$ vs $O(n \log n)$), memory register tables, and benchmarking traces.

---

### 2. Concrete Multi-Domain Walkthroughs

#### Scenario A: Algorithms & Data Structures (e.g., Bubble Sort, QuickSort, Trees)
1. **Student**: *"Teach me how Bubble Sort works on an array of 5 numbers."*
2. **Visual**: The widget opens displaying 5 array boxes `[5, 1, 4, 2, 8]` using Pipeline 1 (`canvas`).
3. **Audio + Pointer Motion**: As JARVIS speaks (*"First, we compare index 0 with index 1"*), the visual spotlight moves from box 0 (`5`) to box 1 (`1`), turns amber to indicate comparison, animates their position swap, and marks sorted elements in green.

#### Scenario B: System Architecture & Networking (e.g., How PipeWire audio works)
1. **Student**: *"Show me how PipeWire routes audio in Linux."*
2. **Visual**: JARVIS compiles a clean Graphviz DOT diagram (`Hardware Mic -> PipeWire Daemon -> VAD Filter -> Client App`) to a PNG and displays it instantly in the HUD.
3. **Audio + Pointer**: Spoken explanation walks through buffer passing and latency fences while highlighting each node sequentially.

#### Scenario C: Code Debugging & Screen Perception
1. **Student**: *"Why is my Python script throwing this TypeError?"*
2. **Perception**: `grim -g` snaps the active editor window, OCR extracts the error message and line number 42.
3. **Visual**: HUD renders a focused 2-line code diff showing the fix, with an explanation of why mutable default arguments caused the bug.

---

### 3. Actuation Boundary & Physical Safety

* **Mutating Actuation Prohibition**: In Teaching Mode, all autonomous modifying tools (`gui_click_*`, `type_text`, `press_key`, `filesystem.write`, `system.run`) are intercepted by `PedagogicalGuard` in `DesktopSkills.execute`. The assistant never alters code or executes terminal commands on the user's behalf.
* **Demonstrative Pointing Allowed**: Visual pointers, animated canvas cursors, and coordinate spotlights are permitted because they provide directional guidance without modifying system state.
* **Fail-Safe Break-Glass**: The session can be terminated at any millisecond via:
  1. Voice: *"exit teaching mode"*
  2. Physical Hotkey: Hyprland binding (`$mainMod+SHIFT+Escape`)
  3. UI Close Button: Clickable dismiss icon on the top-right of the Quickshell HUD
  4. Heartbeat Inactivity Watchdog: Auto-exits after 15 minutes of silence.

---

### 4. Zero-Touch Voice Subsystem Compliance

* **Integrity Guardrail**: `audio/.voice_lock.json` protects all files in `voice_layer/`, `jarvis_voice/`, and `audio/`.
* **Execution Boundary**: Teaching Mode is strictly confined to:
  - Skill Domain: `skills/domains/teaching.py`
  - Tool Manifest: `skill_manifests/teaching.json`
  - Tool Registration: `orchestration/tool_tiers.py` (`CORE_TOOLS`)
  - UI Presentation: `ui/jarvis_widgets/` (Quickshell layer)
* **Verification**: Running `python scripts/verify_voice_lock.py` passes 100% with zero modified files in protected roots.

---

## Goals vs. Non-Goals

### In-Scope Goals
* **Universal Domain Coverage**: Teach algorithms, systems architecture, code debugging, networking, and mathematical concepts using dynamically selected visual representations.
* **4-Tier Diagramming Engine**: Vector canvas (`DrawCanvas.qml`), Graphviz (`dot`), syntax cards, and metric tables.
* **Synchronized Demonstrative Pointer**: Animated in-widget spotlight moving smoothly across elements in sync with spoken voice.
* **Targeted Delta Perception**: Grabs active window frames with `grim -g` on demand to conserve Gemini Live token budgets.
* **Pedagogical Actuation Fence**: Deterministic blocking of mutating tools with instructional fallbacks.
* **Triple-Vector Break Glass**: Fail-safe exit via voice, physical keybind, or UI dismiss button.

### Out-of-Scope Non-Goals
* **Physical Hardware Mouse Hijacking**: No moving the OS mouse cursor across external windows; pointer motion is contained within the visual HUD overlay.
* **Modifying Locked Voice Code**: Zero changes to `voice_layer/`, `jarvis_voice/`, or `audio/`.
* **Standalone GUI Frameworks**: No Electron, Qt-Python wrappers, or webview daemons; 100% native Quickshell integration.
* **Curriculum / Courseware Database**: No persistent grading, student tracking, or classroom quizzes.

---

## Alternatives Weighed

1. **Client-Side Mermaid.js vs Native Graphviz (`dot`)**:
   * *Rejected*: Mermaid requires running a headless browser (Puppeteer) or NodeJS rendering pipeline, which adds 300MB+ in dependencies and 2–4s compilation latency.
   * *Adopted*: Native Graphviz (`/usr/bin/dot`), already installed on the system, compiling diagrams to SVG/PNG in under 80 milliseconds.

2. **OS Pointer Hijacking vs In-Widget Canvas Pointer**:
   * *Rejected*: Moving the operating system's hardware mouse pointer fights the student's physical hand and risks accidental clicks.
   * *Adopted*: In-widget animated spotlight/pointer that smoothly guides eye focus across diagram elements without cursor contention.

3. **Continuous 1-FPS Video Stream vs Event-Driven Delta Capture**:
   * *Rejected*: Continuous 1-FPS video burns 920,000 tokens per hour and degrades voice duplex latency.
   * *Adopted*: Event-driven active-window capture triggered on student speech turns or major screen focus shifts.

---

## Key Decisions & Implementation Staging

1. **File Manifest**:
   * `skills/domains/teaching.py`: Core domain mixin, FSM state machine, diagram generator bridge (`dot` + `view_schema`), and `PedagogicalGuard`.
   * `skill_manifests/teaching.json`: Declarations for `activate_teaching_mode`, `update_teaching_lesson`, `exit_teaching_mode`.
   * `tests/test_teaching_mode.py`: Automated tests for state transitions, diagram generation, actuation interception, and clean deactivation.
2. **Next Milestone**:
   * Execute `/egm-draft` to generate the formal specification document at `docs/designs/universal_visual_learning_teaching_mode.md`.
