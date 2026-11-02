# JARVIS OS Decision Log

This file records durable architectural choices. Add a dated entry whenever a choice changes the direction of the project.

## D001: Build an operating layer before building a new operating system

- **Date:** 2026-10-18
- **Decision:** JARVIS will first become an intelligent control plane above Linux and Omarchy.
- **Reason:** This gives useful system and GUI control sooner, preserves the existing working runtime, and avoids taking on kernel, driver, package, and distribution maintenance too early.
- **Revisit when:** The control plane is stable and there is a clear benefit to a custom distribution or shell.

## D002: Verification is part of every meaningful action

- **Date:** 2026-10-18
- **Decision:** JARVIS must verify outcomes instead of treating process completion or agent claims as success.
- **Reason:** GUI actions, external services, and coding agents can fail silently or produce incomplete results.
- **Revisit when:** Never remove this rule; only improve the evidence available for verification.

## D003: Keep capabilities declarative

- **Date:** 2026-10-18
- **Decision:** Capabilities will continue to have explicit manifests, schemas, adapters, permissions, and verification behavior.
- **Reason:** Declarative capabilities make discovery, testing, risk review, and future GUI/dashboard integration possible.
- **Revisit when:** The registry needs a versioned plugin protocol.
