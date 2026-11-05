# Conversational Natural Language Understanding & Safe Confirmation Engine

* **Author:** Gopi
* **Date:** 2026-11-05

## Overview

JARVIS OS requires an upgraded Natural Language Understanding (NLU) and confirmation processing architecture that supports fluid, human-like conversational interaction without requiring rigid confirmation keywords. Currently, actions held for confirmation (destructive system operations such as reboot, shutdown, and system package changes) fail unless the user recites one of seven hardcoded keywords (`yes`, `confirm`, `proceed`, `do it`, `yep`, `yeah`, `sure`) with strict trailing filler restrictions. Furthermore, command processing can misclassify polite conversational requests as advisory inquiries, and confirmation error messages instruct the assistant to demand explicit keywords.

This overhaul delivers conversational natural language understanding across `jarvis_control` by introducing a unified, deterministic confirmation and cancellation evaluator, expanding natural affirmative and negative vocabularies across English and Hinglish, updating tool schema contracts to prevent LLM keyword suppression, and establishing short-circuiting negation safety. The design strictly preserves the PC voice subsystem freeze (`audio/.voice_lock.json`), maintains zero cloud LLM runtime dependencies for local safety checks, and prevents architectural bloat.

## Analysis

### 1. Safety Airlock & Strict Negation Precedence
* **Destructive Scope**: Actions held for confirmation are exclusively high-risk operations (`shutdown`, `reboot`, `poweroff`, `suspend`, `omarchy update/install/reinstall`, `close-all`). An open desktop microphone is an untrusted channel subject to ambient chatter, phone calls, and ASR noise.
* **Fail-Closed Negation**: Conversational fluency must not compromise confirmation airlocks. Any utterance exhibiting negation, ambivalence, or hesitation (e.g., "no", "don't", "stop", "wait", "mat karo", "nahi", "ruko", "rehne do", "nah wait", "haan mat karo") must immediately short-circuit to `DECLINED` or `HELD`. Negation strictly takes precedence over any affirmative tokens.

### 2. Avoiding Shadow NLU Duplication (YAGNI & Code Minimization)
* **LLM Role vs. NLU Role**: Gemini Live and the OpenAI Realtime pipeline already serve as the primary conversational comprehension engine, transforming natural dialogue into structured tool calls. Building a massive secondary regex-based intent engine for general window management and navigation duplicates the cloud LLM and introduces unmaintainable shadow parsing.
* **Focused Mandate for `NLUEngine`**:
  1. ASR phonetic normalization (`normalize_text`).
  2. Security and hallucination guardrails (`validate_tool_intent`).
  3. Action request detection (`_is_action_request`) with polite and multilingual prefix stripping (e.g., "could you please...", "kya aap...", "ek baar...").
  4. Deterministic confirmation and cancellation evaluation (`evaluate_confirmation`).

### 3. Unified Confirmation Evaluator & Single Source of Truth
* **Decoupling Transport from Language**: Move linguistic matching and normalization out of the Unix domain socket transport (`jarvis_control/session.py`) into `jarvis_control/nlu.py`.
* **Standardized Evaluation Contract**: Implement `NLUEngine.evaluate_confirmation(heard_phrase: str, confirm_words: list[str], cancel_words: list[str]) -> ConfirmationDecision`. The decision returns a strongly typed result (`AFFIRMED`, `DECLINED`, `AMBIGUOUS`).
* **Multi-Dialect Assents & Declines**: Expand built-in vocabularies on `Config` to natively support natural conversational assents ("go ahead", "sounds good", "please do", "do that now", "haan kar do", "bilkul", "theek hai", "sure thing", "definitely") and declines ("nah", "never mind", "don't do that", "mat karo", "rehne do", "ruko").
* **Phonetic Normalization on Confirmation**: Pass `heard_phrase` through `NLUEngine.normalize_text()` prior to matching to correct ASR mishearings.
* **Conversational Filler Expansion**: Expand `_FILLERS` to include colloquial particles ("bhai", "yaar", "now", "jarvis", "please", "toh").
* **Active Cancellation Handling**: If the user's response matches a decline, `ControlSkills.confirm()` actively executes `self.cancel()` rather than trapping the user in a keyword rejection error loop.

### 4. Voice Subsystem Freeze & Public API Invariance
* **Frozen Baseline**: `audio/.voice_lock.json` strictly freezes `voice_layer/`, `jarvis_voice/`, `audio/`, and `core/agent.py`. All changes must be contained inside `jarvis_control/`.
* **Tool Schema Invariance**: `confirm_last` must retain its exact function name and argument signature (`heard_phrase: str`).
* **Tool Description Optimization**: Update the description of `confirm_last` in `jarvis_control/__init__.py:GATE_TOOLS` to inform the LLM that natural conversational assents and multilingual affirmations are valid inputs, preventing the model from suppressing natural confirmations.
* **Config Dataclass Invariance**: All new configuration properties must be explicitly typed on `jarvis_control.config.Config` to prevent `ValueError: Unsupported control setting` during `voice_layer` startup.
* **Backward-Compatible Return Contract**: Maintain the `"ERROR: ..."` prefix on ambiguous phrases to preserve existing test assertions while replacing the robotic keyword prompt with a natural conversational clarification request.

### 5. Observability, Telemetry & Pending State Lifecycle
* **Decision Audit Log**: Emit structured logs whenever a held action is evaluated (`raw_phrase`, `normalized_phrase`, `decision`, `matched_rule`, `held_action`).
* **Execution Latency SLA**: Precompile all linear regexes at module load time; enforce a strict P99 latency < 2.0ms to prevent real-time audio loop stalls.
* **Pending Action TTL**: Implement a 60-second time-to-live on `Executor.pending` to prevent stale actions from being accidentally executed by unrelated conversational assents minutes later.
* **Diagnostic Triage CLI**: Provide an offline evaluation helper (`python -m jarvis_control.nlu eval "<phrase>"`) for rapid local debugging.

## Goals vs. Non-Goals

* **In-Scope Goals:**
  * Build a unified, deterministic confirmation and cancellation evaluator in `jarvis_control/nlu.py`.
  * Support natural English and Hinglish conversational assents and declines in `jarvis_control/skills.py` and `jarvis_control/config.py`.
  * Strip polite and multilingual prefixes in `NLUEngine._is_action_request()` so polite requests are not misclassified as advice.
  * Update `confirm_last` tool descriptions in `GATE_TOOLS` to encourage natural assent forwarding by the LLM.
  * Implement short-circuiting negation precedence so negative or ambivalent phrases never confirm destructive actions.
  * Handle active cancellations cleanly via `cancel_last` and during `confirm_last` evaluation.
  * Add a 60-second safety TTL on pending confirmation state.
  * Maintain 100% compliance with `audio/.voice_lock.json` and pass all unit tests without regressions.

* **Out-of-Scope Non-Goals:**
  * Modifying any files protected by `audio/.voice_lock.json` (`voice_layer/`, `jarvis_voice/`, `audio/`, `core/agent.py`).
  * Building a secondary shadow NLU parser for general desktop navigation or window management (delegated to Gemini Live).
  * Adding external network dependencies or heavy neural NLP weights for local confirmation safety checks.
  * Removing safety gating on destructive commands.

## Alternatives Weighed

* *Fuzzy Semantic Embeddings / Cloud LLM for Confirmation*: Rejected by author. Adds 250ms–1200ms latency, token costs, network failure points, and ambient false-positive risks for critical safety operations.
* *Regex Expansion in `session.py` Only*: Rejected by author. Conflates low-level Unix domain socket transport with conversational natural language understanding.
* *Building Full Desktop NLU in `nlu.py`*: Rejected by author. Duplicates Gemini Live's core conversational capability, creating an unmaintainable shadow parser.
* *Unified Deterministic Semantic Evaluator with Negation Precedence*: Selected. Offline, executes in <2ms, unifies voice and CLI pathways, respects voice locks, and guarantees safety.

## Key Decisions & Staging for Next Steps

1. Review the synthesized brief with the user.
2. Advance to `/egm-draft` to initialize the formal design specification.
