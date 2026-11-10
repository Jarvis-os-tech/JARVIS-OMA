# LinkedIn Department — JARVIS OS

A dedicated, isolated department within JARVIS OS whose exclusive mandate is executing LinkedIn operations: profile optimization, content strategy, post writing, AI-tell elimination, community engagement, and performance analytics.

Orchestrated by **Jarvis**, powered by **NVIDIA NIM**, and staffed by **12 specialized collaborative agents**.

---

## 🏛️ Department Structure

```
departments/linkedin/
├── README.md               # Department charter & guide
├── config.py               # Credentials, NIM model routes, paths
├── nim_client.py           # NVIDIA NIM client with auto-fallback
├── department.py           # Department Lead (Jarvis IPC & pipelines)
├── agents/                 # 12 Specialist Agents
│   ├── base_agent.py       # Base class with shared state/reference helpers
│   ├── a1_profile_optimizer.py
│   ├── a2_content_planner.py
│   ├── a3_post_writer.py
│   ├── a4_reply_handler.py
│   ├── a5_repurposer.py
│   ├── a6_thread_monitor.py
│   ├── a7_engager_analytics.py
│   ├── a8_employee_advocacy.py
│   ├── a9_hook_extractor.py
│   ├── a10_humanizer.py    # Mandatory Quality Airlock
│   ├── a11_interviewer.py
│   └── a12_content_scheduler.py
├── references/             # 2026-tested hook formulas, benchmarks, heuristics
│   ├── hook-formulas.md    # 20 tested hook formulas (F1–F20)
│   ├── founder-topics.md   # Angle libraries
│   ├── algorithm-heuristics.md
│   └── voice-rules.md
├── state/                  # Persistent Department Memory
│   ├── voice-profile.md    # User voice & tone constraints
│   ├── story-bank.md       # Anecdotes & technical breakthroughs
│   ├── content-calendar.json
│   ├── pillar-mix.json     # Ratio of Authority, Actionable, Story, Contrarian
│   └── review_queue/       # Staged post packages waiting for user review
└── tests/                  # Unit and integration test suite
```

---

## 🤖 The 12 Specialist Agents

| Agent ID | Name | Role | Primary Model |
| :--- | :--- | :--- | :--- |
| **A1** | **Profile Optimizer** | Audits 9 profile elements; writes positioning thesis | `nvidia/nemotron-3.5-lightning-30b-a3b` |
| **A2** | **Content Planner** | Designs multi-day calendar mapped to pillars & formulas | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` |
| **A3** | **Post Writer** | Crafts long-form posts using F1–F20 hook skeletons | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` |
| **A4** | **Reply Handler** | Drafts value-first replies to comments | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` |
| **A5** | **Repurposer** | Converts docs into carousels or concise posts | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` |
| **A6** | **Thread Monitor** | Flags high-visibility commenting opportunities | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` |
| **A7** | **Engager Analytics** | Diagnoses impressions, saves, CTR; guides A2 | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` |
| **A8** | **Employee Advocacy** | Creates role-specific variants for team members | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` |
| **A9** | **Hook Extractor** | Deconstructs viral posts into reusable formulas | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` |
| **A10** | **Humanizer** | **Mandatory Gate:** Strips AI-tells, corporate fluff | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` |
| **A11** | **Interviewer** | Mines founder stories & populates story bank | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` |
| **A12** | **Content Scheduler**| Validates readiness & generates Review Cards | Deterministic Stager |

---

## 🔄 User Review & Approval Flow

Per user requirements:
1. **Department Execution**: When tasked, the department runs the pipeline ($A3 \rightarrow A10 \rightarrow A12$).
2. **Review Package**: The post is formatted into a **Review Card** and placed in `state/review_queue/`.
3. **Jarvis Notification**: Jarvis receives the package and presents it to the user.
4. **User Sign-Off**: No post is published until the user explicitly reviews and confirms.

---

## 🚀 Usage via Python

```python
from departments.linkedin import linkedin_dept

# 1. Draft a post and stage it for user review
package = linkedin_dept.draft_and_stage_post(
    topic="Solving IPC concurrency in multi-agent operating systems",
    formula_code="F7",  # Odd-Precision Ledger
    pillar="Authority & Build Logs"
)
print("Staged Post ID:", package.post_id)
print("Review Card Path:", package.review_card_path)

# 2. Check pending posts awaiting review
pending = linkedin_dept.get_pending_reviews()

# 3. User approves
linkedin_dept.approve_post(package.post_id)
```
