# Google Workspace Department

* **Author:** Gopi
* **Date:** 2026-11-17

## Overview

Add one Google Workspace department to JARVIS OS. It will contain six service agents: Gmail, Calendar, Tasks, Drive, Docs, and Sheets. The department will route each request to the matching agent and coordinate the small number of workflows that use more than one Google service.

The first version will reuse the existing Google Workspace connector, public tool names, schemas, authorization, and 28-tool manifest. Each agent will have a fixed allowlist and will reject tools owned by another service. Google authorization and connection status will remain department-level controls.

## Analysis

The existing connector already provides the requested Google operations. A second connector or a general agent framework would add complexity without improving the core boundary. The smallest useful design is a thin department facade in front of the existing connector.

The main limitation is authorization. JARVIS currently stores one combined Google OAuth grant. Fixed tool allowlists can stop a Gmail agent from asking the department to run Calendar, Drive, Docs, Sheets, or Tasks operations. They do not provide separate operating-system processes or separate OAuth tokens. True credential isolation would require separate consent flows, token stores, migration logic, and account-status reporting.

Drive, Docs, and Sheets are read-only today. The first version should state that honestly rather than invent unsupported write agents. Gmail, Calendar, and Tasks include mutations. Their actions must keep the existing confirmation rules, and the department must not silently retry an action whose remote outcome is uncertain.

Offline tests should use an injected fake dispatcher. They must verify routing and rejection without opening a browser, reading personal tokens, contacting Google, or changing live data. A live read test can happen only after connection is available. Every live write still requires the user's explicit approval for the exact action.

## Goals vs. Non-Goals

### In-scope goals

* Register Gmail, Calendar, Tasks, Drive, Docs, and Sheets agents in the JARVIS agent catalog.
* Give every service agent an immutable tool allowlist.
* Keep Google authorization and connection status owned by the department.
* Route current Google tools through the department without changing their public names, arguments, defaults, or result shapes.
* Test complete tool ownership, off-service rejection, connector delegation, and zero-side-effect offline behavior.
* Keep Drive, Docs, and Sheets read-only.

### Out-of-scope non-goals

* Separate OAuth credentials or processes for every agent.
* New Google APIs, scopes, dependencies, or write tools.
* Autonomous inbox monitoring or background polling.
* A workflow language, durable queue, shared agent memory, or automatic rollback.
* Live writes during the offline test phase.

## Alternatives Weighed

* **Create six new Google connectors.** Rejected because it duplicates the existing API, auth, validation, and error handling and increases token exposure.
* **Give every agent the full Google tool set and rely on prompts.** Rejected because prompts are not a security boundary.
* **Split OAuth immediately.** Deferred because the user asked for service-bounded agents, and the current system has one working combined authorization path. Split OAuth is justified only if true credential isolation is required.
* **Add a general workflow engine.** Rejected because the requested service routing and a few sequential cross-service operations do not need one.

## Key Decisions & Staging for Next Steps

1. Build a thin `GoogleWorkspaceDepartment` with six service agents and one department control plane.
2. Use code-enforced capability isolation over the current shared OAuth grant for version one.
3. Preserve the existing connector and all public Google tool contracts.
4. Add offline boundary tests first, including exact ownership of every manifest tool and rejection of cross-service dispatch.
5. Register the six agents in the unified JARVIS catalog.
6. Run the existing connector and orchestration tests.
7. Check connection status only after offline tests pass. Run no live mutation without a new explicit approval.

The acceptance condition is that every declared Google tool has exactly one owner, except authorization and status which belong to the department, and no service agent can execute another service's tool.
