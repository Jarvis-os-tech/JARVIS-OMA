# Desktop autonomy: evidence and adversarial review

Research checked 14 October 2026. This is a design memo, not a claim that Jarvis has achieved these capabilities. No runtime changes or live benchmark runs were performed.

## Primary evidence

1. [OpenAI computer-use integration guide](https://developers.openai.com/api/docs/guides/tools-computer-use): Current guidance recommends code execution for GPT-6 Astra and also supports structured computer actions. Persistent runtime state, fresh observations, bounded execution, cancellation, and checking actual outcomes are explicit integration concerns. A completed tool-call generation does not mean its action has executed. Limitation: integration guidance does not disclose a model-training recipe or prove a universal ranking of API, code, and visual control.

2. [OpenAI hosted browser guide](https://developers.openai.com/api/docs/guides/agents-api/tools/computer-use): Hosted browser sessions support session events, website access requests, activity review, and session recovery. Limitation: hosted browser capability is not equivalent to controlling the user's native Linux desktop; availability and account support must be checked when implementing.

3. [OSWorld-V2 official repository](https://github.com/xlang-ai/OSWorld-V2): The recommended release is now `osworld-v2.1`, released 16 September 2026. Reproducibility requires matching task files, assets, websites, and provider images. Official task classes are distributed through a gated dataset. Limitation: do not compare scores across releases or treat old website instances as current. Access and infrastructure requirements must be resolved before claiming a local baseline.

4. [WebArena project](https://webarena.dev/og/): Its task evaluators check functional correctness using reference answers and expected application-state properties. This supports outcome-oriented testing rather than click-count success. Limitation: benchmark websites and evaluator definitions are narrower than arbitrary live desktop work; evaluator correctness itself needs validation.

5. [AgentDojo paper](https://arxiv.org/abs/2406.13352): The original benchmark provides 97 realistic tasks and 629 security cases for agents consuming untrusted tool data. It evaluates utility and attacks rather than assuming fluent behavior is robust. Limitation: original counts describe the paper, not every current package version; this is not a native GUI-accuracy benchmark.

6. [XDG RemoteDesktop portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html): Sessions select devices and start through a user-facing grant flow. EIS is recommended; after connecting it, input must use EIS exclusively. Screen capture integrates through ScreenCast/PipeWire. Limitation: available backends, device grants, and persistence support vary; inspect the actual compositor rather than assuming global mouse/keyboard access.

7. [libei protocol documentation](https://libinput.pages.freedesktop.org/libei/): Emulated input is mediated by an EIS implementation, commonly the compositor, which can distinguish it and govern permission. Limitation: input delivery is not proof the intended application accepted the operation. A working input backend still needs observation, focus management, and outcome checks.

## Concrete local findings

Static inspection of `proactive/runtime.py` identifies three semantics that must be corrected before expanding autonomous execution:

- Line 59 derives `authorized` from high/critical priority. Urgency is not evidence of user authorization.
- Line 106 maps `authorized` to `LOCAL_REVERSIBLE`. Permission and actual effect are independent: an authorized operation can still transmit data or destroy state. Policy must evaluate the concrete proposed action, target, and current authorization scope.
- Lines 140–142 map a worker's `completed` state to ledger `SUCCEEDED`. Worker termination alone does not establish task success. A separate outcome record should distinguish execution finished, verification passed, verification failed, and unverified. Where multiple jobs share an activity, aggregate their terminal states and outcome evidence before closing it.

These are code-path concerns, not claims of demonstrated exploitation or failed live tasks. `proactive/policy.py` already distinguishes read-only, local reversible, external, destructive, and unknown effects; runtime wiring weakens that distinction.

## Debate and proposed resolution

**More agents versus shared-state interference.** OpenAI reviewer challenged whether parallel desktop workers improve accuracy. Resolution: one lease-holding controller per mutable desktop/session; independent research and isolated VMs can run in parallel. Handoffs invalidate stale observations. Compare a single controller with and without advisors under equal model, tools, seeds, time, and token budgets. This is an engineering proposal to test, not a published guarantee.

**API versus code versus visual actions.** My challenge to the OpenAI reviewer was not to infer a universal hierarchy from integration docs. Agreement: choose a transport according to task semantics, available permissions, observable state, and measured performance. A typed application API can offer strong validation, browser code can exploit structured elements, and visual interaction covers missing interfaces. Generated code still needs execution limits and observability. Keep the verifier independent of the chosen transport.

**Learning versus teaching the evaluator.** My challenge to the learning reviewer: clicks and the acting model's narrative cannot promote a procedure. Their counterchallenge: immutable tests are still gameable if the candidate can read them or repeatedly learn from heldout scores. Resolution: freeze candidate hashes before evaluation; keep external checkers and backend credentials inaccessible to the candidate; cap submissions; return aggregate promotion decisions; rotate and retire sealed batches; retain prospective tasks authored after candidate freezing. Evaluator versions change through a separate governed process between experiments.

For PDF export, verify file existence, parseability, expected text/tables and page constraints with an external reader. For a website change, inspect backend state or an independent authenticated read; do not trust the acting model's success banner alone. Visual tasks may need human adjudication or validated visual metrics. Report unverified when no trustworthy oracle exists.

## Proposed acceptance evidence

Maintain task success with uncertainty intervals, false-success rate, recovery rate after injected UI changes, action latency/cost, cancellation latency, and unauthorized-effect incidence. Include benign and prompt-injection variants, stale focus, changed resolution, unavailable portals, and interrupted sessions. Separate practice tasks from sealed promotion tasks. Record model version, controller version, environment image, observation/action modality, task-set revision, budgets, and verifier version with every result. Daily review may generate candidates; production promotion should depend on evidence, not the calendar.
