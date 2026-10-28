# JARVIS OS — Practical Build Roadmap

**[VERIFIED] Audit date:** 27 October 2026. Planning-only update; no runtime or desktop configuration changes made in this audit.

**Labels:** VERIFIED = directly inspected or tested, within the stated scope; DOCUMENTED = a source claims it; UNVERIFIED = not established; PLANNED = future work; NEW = proposed estimate, metric or design choice.

## 1. Audit: what the evidence actually proves

| Label | Area | Evidence and limit |
|---|---|---|
| VERIFIED | Hardware | i5-1235U, 12 logical CPUs, 7.4 GiB usable RAM, Intel Iris Xe integrated graphics. Snapshot: 2.7 GiB available, 5.9 GiB swap used; swap usage alone does not prove current thrashing. |
| UNVERIFIED | Developer capacity | Hours/week is still [X]. No personalized calendar commitment is possible yet. |
| VERIFIED | Startup | ./run.sh --check passed without opening audio/network. ./run.sh --list-skills succeeded and listed dependency availability. |
| VERIFIED | Tools | Both manifest trees contain 23 JSON files and 188 unique skill entries; trees are byte-identical. Default DesktopSkills exposes 190 declarations, including the two domain tools. This is discovery, not successful execution of 190 features. |
| VERIFIED | Focused tests | Fresh run: **93 passed, 3 failed**, across eight selected modules; not a full-suite result. |
| VERIFIED | Voice foundation | Startup/recovery/connection tests in that run passed; all seven protected audio files passed integrity verification. |
| UNVERIFIED | Natural real-time conversation | No fresh acoustic test, end-to-end latency measurement, interruption benchmark or uptime trial in this audit. |
| VERIFIED | OS-control defect | Two integration tests expect unverified_effect but receive success for typing. See skills/action_verification.py and the failing test names below. |
| VERIFIED | Memory foundation | Selected memory integration tests passed: persistence, context/trust and related fixture behavior. |
| UNVERIFIED | Personal memory quality | Long-term relevance, recall accuracy on your projects, and all deletion paths need a realistic evaluation dataset. |
| VERIFIED | Background foundation | Selected event-store and runtime-worker tests passed. Existing SQLite events/ledger should be reused. |
| UNVERIFIED | Agent reliability | Agent credentials, actual delegated task completion, process-crash recovery and durable team recovery were not tested here. |
| VERIFIED | Vision inconsistency | test_stream_vision_timeout_resilience fails: code raises RenewConnection while the test expects its task to stay alive; an unhandled-task diagnostic is emitted. |
| UNVERIFIED | Screen/camera use | Actual screen delivery, camera consent boundaries and visual understanding need live verification. |
| VERIFIED | Model-routing code | Gemini candidate models and a Groq tool router exist. Groq code rotates keys on HTTP 429. |
| UNVERIFIED | General model fallback | Code presence/key rotation does not prove cross-provider conversation fallback, equivalent tool schemas, or local offline speech. |
| VERIFIED | HUD wiring | Orbit QML uses orbit_status.py --subscribe; a state connection already exists. |
| UNVERIFIED | HUD quality | No fresh visual, accessibility, focus, multi-monitor or crash-recovery test. |

**[VERIFIED] Reproduction commands used** (from the project root; the test set mocks audio/cloud and needs temporary Unix sockets permitted):

~~~sh
git status --short
./run.sh --check
./run.sh --list-skills
python3 scripts/verify_voice_lock.py
timeout 45s .venv/bin/pytest -q --tb=short \
  tests/test_core/test_startup.py tests/test_core/test_connection.py \
  tests/test_audio/test_voice_lock.py tests/test_skills/test_system_control.py \
  tests/test_memory/test_memory_integration.py \
  tests/test_proactive/test_proactive_events.py \
  tests/test_proactive/test_runtime_workers.py tests/test_core/test_vision_stream.py
~~~

**[VERIFIED] Failing tests:**

- DesktopSkillsSystemControlIntegrationTests.test_skills_execute_type_text_targeting_app
- DesktopSkillsSystemControlIntegrationTests.test_skills_manifest_and_execution
- VisionStreamTests.test_stream_vision_timeout_resilience

**[PLANNED] Full baseline:** after classifying live tests and making them safe to exclude, run the complete offline suite using the project interpreter. Do not treat existing marker names as proof every test is correctly marked.

## 2. Inconsistencies and cleanup decisions

| Label | Finding | Consequence |
|---|---|---|
| VERIFIED | CODEBASE_REFERENCE says 188 tools; its generator also contains an older hardcoded “110 tools” description | Repair the generator's definitions. Manifest entries, runtime declarations, and provider-exposed tools are different counts. |
| DOCUMENTED | Older reports contain 922 passed/29 failed; the reverted experiment recorded 142 passed | Historical snapshots, not the current result. Current selected run is 93/3. |
| VERIFIED | Dirty checkout: runtime/config/test edits, many documentation deletions and untracked project-docs | Record ownership and reconcile intended archival moves before a clean release baseline. Do not reset others' work. |
| VERIFIED | README still links docs/system-control-and-information.md after its archive move | Fix affected documentation links and indexes before promotion. |
| VERIFIED | Native PipeWire companion plus legacy engine | Alternative backends, not proof of simultaneous duplicate capture; retain rollback until live parity is measured. |
| VERIFIED | Two manifest folders with identical content | Choose an authoritative source and drift check; avoid independent hand edits. |
| VERIFIED | jarvis_memory imports redirect into memory/codes-dev/jarvis_memory; universal-memory-mcp also exists | Map actual imports and storage ownership before deduplicating folders. A compatibility shim is not an unused duplicate. |
| VERIFIED | Native audio is a child process | Attachment's “single-process daemon” conflicts with current architecture. Keep one supervisor with isolated audio timing. |
| VERIFIED | CLI set_mute requests lack a matching IPC branch in the restored baseline | Carry explicit mute and error-reporting fixes into the planned work; do not assume the reverted fix remains installed. |
| VERIFIED | Mode switcher shares production .venv and copies config/credentials; promotion checks can be skipped when executables/files are absent | Separate test environments/data and make release gates fail closed. |
| DOCUMENTED | Attachment promises zero-latency interruption and implies dock removal first | Replace with measurements; retain current interaction until replacement parity. |
| UNVERIFIED | Bloom/Sentient code, proposed panel dimensions, phone integration and specific installed plugin claims | Treat as design references pending inspection, not implementation facts. |

## 3. Scope and effort

**[NEW] MVP scope:** one user's current computer; 20 common spoken actions; one primary voice provider plus one deliberately tested fallback path; explicit screen sharing; camera off by default; project memory; one bounded background agent task; existing HUD improved after reliability.

**[NEW] Capacity assumption:** 10 focused engineering hours/week including review, testing and debugging, even when AI writes code. Effort below totals **128–208 hours**, plus **25% contingency = 160–260 hours**. At 10 h/week: **16–26 weeks**; at 5 h/week: **32–52 weeks**; at 20 h/week: **8–13 weeks**. Use ceil(160/X)–ceil(260/X) weeks for your actual X. These are planning ranges, not delivery promises; a redistributable OS image is outside this MVP.

**[PLANNED] Sequence:** phases below are dependency ordered. Keep existing implementations and use their public extensions; no new framework, message broker or always-on service is required for the initial plan.

| Phase / label | Build and reuse/change | Effort; weeks at 10h | Tests and measurable done check |
|---|---|---|---|
| P0 PLANNED — trustworthy baseline | Reconcile edits and archive links; inspect generator, manifests and pyproject.toml; define the two disputed result contracts | NEW: 8–12h; 0.8–1.2w | Fresh scoped baseline recorded; every failure classified; no skipped release gate; protected files intact |
| P1 PLANNED — dependable voice | core/agent.py, core/ipc.py, core/connection.py, core/audio_scheduler.py, audio/extension.py, existing native adapter and jarvisctl.py | NEW: 24–40h; 2.4–4w | Explicit mute idempotence, local stop, reconnect/short-turn tests; 30 measured turns and 20 interruption trials; Super+H dictation preserved |
| P2 PLANNED — verified OS control | skills/system_control.py, system_extensions.py, action_verification.py, ground_truth.py, manifests and existing filesystem/browser adapters | NEW: 28–44h; 2.8–4.4w | 20 intents × 3 trials, at least 57/60 correct verified outcomes, zero wrong-target writes; failure/ambiguity cases report honestly |
| P3 PLANNED — memory and durable work | Existing MemoryBridge/store, proactive/events.py, ledger.py, runtime.py and orchestration/agent_orchestrator.py | NEW: 24–40h; 2.4–4w | 30 project-memory questions; proposed ≥24 correct sourced answers, unknowns abstain; restart/reconcile 10 task trials; no duplicate effects; progress/cancel demonstrated |
| P4 PLANNED — screen and fallback | core/vision_stream.py, agent.py, groq_tool_router.py and current credential/config adapters | NEW: 16–28h; 1.6–2.8w | Reconcile vision timeout test with supervisor; screen on/off and camera opt-in tests; inject 429/timeout/auth failures without duplicate actions or silent data-policy changes |
| P5 PLANNED — reliable minimal HUD | Reuse orbit_status.py, OrbitOverlay.qml and current event stream | NEW: 16–24h; 1.6–2.4w | HUD represents mute/offline/tool failure truthfully; restart shell without losing work; no typing-focus theft; keyboard/reduced-motion/scaling checks |
| P6 PLANNED — stable personal release | Existing systemd template, installers, run.sh and jarvis_mode.py; release/config records | NEW: 12–20h; 1.2–2w | One JARVIS audio owner; test data/dependencies isolated; missing tests block promotion; failed switch restores known-good runtime; 8h then 24h soak |

**[PLANNED] Cross-cutting security:** keep camera off unless enabled; separate JARVIS mute from physical mic mute; preserve Super+H dictation; use typed arguments and exact targets; retain credential filtering; treat screen/web/agent content as untrusted; require explicit authority for destructive actions. Test these in each phase rather than postponing them to a final security sweep.

## 4. Performance and privacy targets

**[NEW] Initial acceptance targets, to revise after a baseline. None is an achieved result.**

| Metric | Proposed target | Measurement |
|---|---|---|
| Local stop-speaking | p95 ≤200 ms | Timestamp stop input and acoustic output cessation across 20 trials; no automatic unmute |
| Natural conversational response | p95 ≤2.0 s on the selected provider/network | End of actual user speech to first audible reply across 30 turns; separate provider PCM timing from speaker timing |
| Local action dispatch | p95 ≤300 ms for simple controls | Accepted structured intent to adapter dispatch; measure application completion separately |
| Audio integrity | No stale response resurrection or repeatable self-triggering in the test set | Short/long replies, double-talk and interrupted/reconnected trials with audio evidence |
| Incremental resource use | Initial budget: ≤1 GiB RAM and ≤10% of one CPU core at idle | Compare baseline and 30-minute idle samples; report workload, sampling method and excluded external agents |
| Privacy controls | Zero camera captures while disabled; zero user-audio payload after explicit mute | Mock boundary tests plus instrumented capture/send audit; define silence keepalive policy separately |
| Background work | No duplicate external effects in tested restart cases | Crash before/after dispatch; ambiguous outcomes reconcile rather than blind retry |
| Stability | 8h then 24h without uncontrolled restart loops or sustained memory growth | Service restarts, RSS, task recovery, audio errors and provider usage logged |

**[VERIFIED] Existing response timing labels exclude speaker buffering.** They cannot alone establish acoustic latency.

**[NEW] Hardware policy:** start with the current provider-backed voice path and bounded local processing. Benchmark one small local fallback candidate later; do not plan multiple resident models on this RAM budget. The iGPU alone establishes no model-compatibility or performance guarantee.

## 5. Postpone, avoid, and five risks

**[PLANNED] Postpone:** full Dynamic Island makeover, dock removal, custom OS image/branding, IoT, phone UI, broad self-healing, many simultaneous agents, and always-on camera.

**[PLANNED] Avoid:** rewriting locked/working audio; merging everything into one process; deleting compatibility folders by name; another framework/event broker without measured need; treating a tool exit as success; toggles for explicit pause/mute; model failover that repeats an external action; changing live configuration during planning.

| Risk / label | Why it matters | Planned mitigation |
|---|---|---|
| 1 VERIFIED finding / UNVERIFIED impact | Desktop “success” can exceed actual evidence | Resolve verifier contract and exact-target readback before expanding commands |
| 2 UNVERIFIED | Real-time audio under CPU/memory/network load | Acoustic baseline, bounded work, interrupt/reconnect tests, preserve native callback isolation |
| 3 VERIFIED structural limit | In-process action cache does not establish crash-safe replay prevention | Persist action identity; reconcile unknown effects before retry |
| 4 VERIFIED finding | Development shares environment/state assumptions with production | Separate dependencies/state, validate revision, fail-closed promotion and reversible switching |
| 5 UNVERIFIED | Screen/memory content can leak or influence execution | Explicit capture states, source trust, secret filtering, retention/deletion checks, provider-routing policy |

## 6. Week 1 — 10-hour example

**[PLANNED] Scale to actual availability; no implementation is performed by this plan.**

| Day | Time (NEW) | Work and output (PLANNED) |
|---|---:|---|
| 1 | 1h | Record baseline commit, dirty-file ownership, protected shortcuts and test outputs |
| 2 | 2h | Define verified vs delivered semantics; investigate and resolve the two desktop-verification failures in isolation |
| 3 | 2h | Reconcile vision timeout/reconnect behavior and collect task exceptions cleanly |
| 4 | 1.5h | Reproduce CLI/IPC mute mismatch; specify idempotence and error tests |
| 5 | 1.5h | Inspect test-mode isolation and promotion gates; write concrete change list |
| 6 | 1h | Prepare the voice latency/interrupt measurement procedure; camera remains off |
| 7 | 1h | Rerun focused tests; review baseline delta; set the next package from evidence |

**[PLANNED] ONE next action:** resolve the two desktop success-verification failures in an isolated worktree, preserving Super+H and the running desktop.

