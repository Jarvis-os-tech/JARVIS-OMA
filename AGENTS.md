# CSE-OS — Agent Instructions

`CLAUDE.md` is the canonical master. Keep `AGENTS.md` synchronized with it.

CSE-OS is a personalized education command center for CSE students, spanning onboarding, semester planning, coursework, projects, exam preparation and career launch. Skills live in `skills/`; flows in `flows/`; loops in `loops/`; advisors in `agents/`. If the student's stage is unclear, use `start-here`; see `docs/STAGES.md`.

## Operating principles

1. Research before asserting: verify requirements, deadlines and market data; never invent grades, salaries or requirements.
2. A draft is not a decision: identify decisions requiring the student's judgment.
3. Batch, then decide: gather feedback and revise once.
4. Ask before assuming: one focused question is better than the wrong artifact.
5. Route to the earliest unvalidated gap: validate prerequisites and understanding before downstream work.
6. Stay domain-agnostic where possible; use the placeholder glossary without assuming a university or curriculum.
7. Protect the student: no secrets or PII in prompts; flag irreversible decisions; include a not-academic-advice caveat for degree requirements.

Read the knowledge base before substantive work. After a real outcome, use `capture-learning` to append a dated, sourced lesson to the relevant `knowledge-base/` file; append, never overwrite. Tool mappings are in `docs/cross-platform-guide.md`.

## Licensing and attribution

Content CC-BY-4.0; code Apache-2.0. Preserve attribution: **CSE-OS by CSE-OS Contributors, adapted from Founder OS by Adam M. Adamek (Impact Brussels ASBL)**. See `ATTRIBUTION.md`.

## Default EGM workflow — user preference, 2026-11-04

Use the installed `egm@egm` plugin by default for substantial feature planning, architecture, design specifications and its supported document workflows. This is the user's standing request to use EGM for those tasks. Discover the installed skill path from current plugin metadata/inventory rather than hardcoding a cache version, then read its SKILL.md and referenced Codex integration instructions before applying it.

Route by task:
- Explore requirements, ideas and trade-offs: `egm-brainstorm`.
- Write an agreed design/specification: `egm-draft`.
- Review a design document: `egm-review`; use `egm-review-loop` when an iterative review-and-resolution loop is requested or fits the task.
- Resolve Goldfish review findings: `egm-resolve`.
- Bootstrap directory documentation: `egm-bootstrap`.
- Check design/README consistency against implementation: `egm-drift-report`.

Use only the relevant workflow; do not run every stage for every request. Ordinary implementation, small clear bug fixes, commands and unrelated tasks keep the normal workflow. EGM is a design/document workflow, not a replacement model or a requirement to modify production code. Follow its explicit approval gates during design; leave the design workflow before separately authorized implementation. Do not invent automatic activation or simulate unavailable skills.

For Goldfish reviews, use actual fresh-context native subagents (`fork_turns: "none"` where supported), wait for completion and report isolation/tool limitations honestly. Never simulate independent reviewers in the parent. User and repository restrictions still apply: follow explicit repository constraints and user instructions.

## Dynamic Skill & Plugin Auto-Selector Mechanism

To ensure skills and plugins are automatically selected and invoked based on user prompts without requiring explicit `/skill-name` invocation:

1. **Prompt Submission Hook**: Configured in `~/.claude/settings.json` under `UserPromptSubmit`, the hook runs `/home/g0pi/.claude/hooks/dynamic_skill_selector.py` for every user message.
2. **Intent & Trigger Matching**: The selector script dynamically scans all installed skills in `~/.claude/skills/` (frontmatter descriptions, explicit triggers, and keyword overlap), scores them against the user's prompt text, and selects the best matching skill.
3. **Context Injection & Auto-Invocation**: When a match is found, the selector injects an `additionalContext` instruction into the turn. Claude Code receives this system instruction and automatically dispatches `Skill({ skill: '<matched_skill>' })` to execute the appropriate workflow seamlessly.

