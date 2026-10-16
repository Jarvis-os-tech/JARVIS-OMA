# Jarvis research debate: challenges, decisions and falsification tests

14 October 2026. This records the substantive challenges exchanged by the OpenAI-evidence, learning and desktop research agents, followed by the lead reviewer's synthesis. It is an edited decision record, not a verbatim transcript. The agents share model infrastructure; their agreement is not independent empirical corroboration.

The [main report](/home/g0pi/Projects/JARVIS-OMA/docs/research/jarvis-agi-2026-10-14/report.md) contains the evidence and build sequence. Separate [OpenAI](/home/g0pi/Projects/JARVIS-OMA/docs/research/jarvis-agi-2026-10-14/openai-review.md), [learning](/home/g0pi/Projects/JARVIS-OMA/docs/research/jarvis-agi-2026-10-14/learning-review.md) and [desktop](/home/g0pi/Projects/JARVIS-OMA/docs/research/jarvis-agi-2026-10-14/desktop-review.md) notes preserve each research position and its sources.

## 1. Does an agent framework get us to AGI?

**Builder's strongest case:** a capable model can use memory, tools and code generation to acquire abilities that the original application did not have. Composition may unlock tasks that no individual tool performs.

**Learning reviewer's challenge:** improved prompting or retrieval can expose latent competence without creating a new generally intelligent model. More retries can also look like learning when compute is not controlled.

**Decision:** system-level capability gains matter, but name their mechanism accurately. Keep the model fixed initially; separately measure retrieval, procedures, controller changes and inference budget. Broad generalization remains an open research question.

**Test that could change the assessment:** freeze a candidate learned on application A, then evaluate new compositions, unfamiliar application B and unrelated tasks at matched budgets. Compare against the same model with the same raw logs but no learned skills. Report each domain separately and inspect negative transfer. Strong transfer would support broader system competence; it would still not alone establish AGI.

## 2. Should Jarvis train its own foundation model first?

**Ownership argument:** local weights can enable offline use, data control and specialized training.

**OpenAI reviewer's challenge:** a public model announcement and API guide are not a reproducible training recipe. A training program adds data, infrastructure and evaluation requirements before solving Jarvis's existing execution failures.

**Decision:** use a replaceable existing model first. Preserve a later open-weight specialist path. Do not assert that hosted Astra can be fine-tuned through an unsupported API feature.

**Reconsider when:** a stable task gap survives tool/context improvements, a suitable lawful dataset exists, and a tuned specialist wins a held-out quality/cost or offline/privacy comparison. A general foundation-model project would require its own research plan and resources.

## 3. Do more agents make computer use more accurate?

**Parallelism argument:** specialists can propose alternatives and find mistakes; isolated tasks can run faster.

**Desktop reviewer's challenge:** two actors controlling one session invalidate each other's observations. One agent may type into a window another has just focused.

**Decision:** one action owner per mutable desktop or browser session. Parallelize independent research, read-only analysis and isolated environments. Separate an action lease from computation so a slow advisor does not unnecessarily block unrelated work.

**Test:** single controller versus controller plus advisors, with identical tools, model, seeded tasks and total budgets. Measure success, stale-target actions, cost and elapsed time. Add advisors only when the benefit survives these controls.

## 4. Is an immutable evaluator enough for safe self-improvement?

**Initial proposal:** prevent candidates from changing their tests and require passing results before promotion.

**Learning reviewer's counterexample:** a fixed test may have a weak proxy, exposed reference files or a loophole. Repeated holdout submissions can become indirect training even without editing tests.

**Desktop reviewer's refinement:** inspect actual output artifacts and backend state using credentials and execution privileges the candidate cannot access. Do not score a narrative claim that work succeeded.

**Decision:** protect evaluator code and access, validate its semantics, cap submissions, keep separate selection and sealed release pools, rotate exposed batches, and independently audit ambiguous outcomes. Evaluators can evolve through a separate process between experiments.

**Test:** deliberately submit candidates that claim success without doing work, produce empty-but-valid files, satisfy only superficial UI cues, or attempt to read scoring artifacts. The evaluator must reject them. Include human audits to detect errors in the test itself.

## 5. Should the system improve and deploy every day?

**Automation argument:** daily reflection, research and experimentation could compound incremental improvements.

**Statistical challenge:** selecting the luckiest candidate every day can create regressions. A calendar quota rewards unnecessary change and hides the cost of failed search.

**Decision:** daily is a possible experiment cadence, not a deployment obligation. “No candidate earned promotion” is valid. Record rejected candidates, total costs, practical effect thresholds and regression results. Production updates require a separate release decision and rollback evidence.

**Test:** compare promoted candidates against a contemporaneous incumbent and prospective tasks. Check whether apparent gains survive repeat trials and whether savings repay evaluation/search costs.

## 6. Must APIs always outrank visual interaction?

**Structured-tool argument:** APIs and DOM/accessibility objects often expose targets and results more directly than screen coordinates.

**Desktop reviewer's challenge:** availability, permissions and task semantics vary; official integration guidance does not establish a universal accuracy hierarchy. Code execution may combine multiple modalities.

**Decision:** choose the route based on measured suitability. Keep authorization, target checks and outcome verification independent of the transport. Capability detection on the user's actual Wayland environment precedes implementation assumptions.

**Test:** compare available transports on identical tasks, including layout changes, unsupported APIs and stale focus. Document coverage as well as success on supported cases.

## Lead reviewer's final decisions

Proceed first with explicit task contracts, action-level scope enforcement and independent completion verification. Preserve the existing voice and memory systems. Then add verified procedural memory and isolated improvement experiments.

Before broader autonomy, correct the runtime's priority-to-authorization inference and process-completion-to-success mapping. Aggregate all dependent jobs before declaring the parent task verified. Add interruption and crash recovery to the task lifecycle.

The unresolved question is how far these changes generalize. The decision is to investigate that question with controlled transfer experiments, not to assume the answer from model branding, agent consensus or a successful demo.
