# API, CLI and connector service integration

Implemented and activated on 3 November 2026. This extends the earlier system
integration repairs; the earlier audit remains evidence for that release.

## Available routes

| Route | Role | Verified now |
| --- | --- | --- |
| API-Anything | Discover and execute learned web operations; propose and learn new APIs | Supervised service health and real catalog search through JARVIS |
| CLI-Anything | Discover, install and execute application CLI harnesses | CLI-Hub 0.4.1 installed; real catalog search through JARVIS |
| Composio | Existing account connectors, authorization and platform actions | Existing integration preserved; SDK installed and key configured |
| Agent-Reach | Retrieve and search platform content | Local health endpoint responding |

Configuration does not establish authorization for any specific account. Check
each platform with `check_platform_connection`. The service health endpoint
proves transport readiness, not that every API, browser, account or application
operation can run. Individual CLI harnesses and their parent applications still
need installation when required. No blanket application installation was done.

## Changes

- Added explicit `api_anything` and `integrations` discovery domains, keeping
  `cli_anything` and `composio` separate. Updated model routing guidance and hints.
- Added `integration_service_status`, available through normal specialist
  discovery and execution. It returns fresh local readiness, never credentials.
- Replaced the checked-in interactive API-agent service launch with a structured
  Python service. It listens only on a user-local Unix socket, mode 0600 inside
  a directory of mode 0700. No network listener or arbitrary shell endpoint.
- Enabled `jarvis-api-agent.service` for the user session. Systemd restarts it on
  failure and terminates its child processes on shutdown. At verification it was
  active/running with zero restarts.
- The API service admits at most two operations concurrently and rejects overload
  before execution. It checks request shape, bounds request/response size and
  operation time, and supports a transport-only health check.
- A missing service can use bounded local execution. Once a request is submitted,
  an interrupted response returns an unknown outcome, without a second local
  attempt. This prevents replay through the fallback path.
- API subprocess exit failure overrides success-shaped log output. Unstructured
  output is unverified. Cancellation and timeout terminate and reap the owned
  process group, including agent/MCP descendants.
- API arguments now use JSON, preserving booleans, arrays, nested objects and
  strings. Explicit API writes require `allow_writes=true` and a stable
  `request_key`, passed to upstream's idempotency mechanism. Accepted or possibly
  applied writes stay unverified; only actual readback can establish an effect.
- Shared deadlines now accommodate proposal, learning and CLI installation
  limits, including calls through `execute_domain_tool`.
- Installed the official CLI-Hub and its required pip into the isolated
  `~/.local/share/jarvis-integrations/venv`. The command resolver finds it even
  when the voice service PATH omits that directory. Dependencies are pinned in
  `configs/integration-requirements.txt`.
- Registry entry points are validated before launching. Installed harnesses in
  the isolated environment can be resolved directly. CLI actions with arguments
  are awaited rather than detached and falsely reported as finished. Plain-text
  process completion remains unverified until its application effect is checked.
- JARVIS disables CLI-Hub analytics in its child-command environment.
- Composio credentials, connector implementation and existing authorization
  state were preserved. This release does not replace the user's connector work.

## Verification

Full regression run: **1,506 passed, 146 subtests passed, 1 optional test skipped**,
79.17 seconds. Two existing warnings concern unavailable CUDA execution support.
Focused service/CLI run: **35 passed**.

Tests include actual owned subprocess cancellation, nonzero exit with JSON
success, invalid/missing machine output, typed API arguments, explicit stable
write keys, accepted-but-unverified writes, real local-socket routing, overload
rejection, missing-service fallback and no replay after uncertain service output.

Read-only live checks through the running JARVIS control socket:

| Check | Result | Observed round trip |
| --- | --- | --- |
| API domain discovery | 5 tools | 20.72 ms |
| CLI domain discovery | 9 tools | 18.65 ms |
| Composio specialist discovery | 5 tools, in addition to initial connector tools | 20.64 ms |
| Integration domain discovery | 1 tool | 26.12 ms |
| Integration service status | Successful | 200.67 ms |
| CLI catalog search | Successful | 554.76 ms |
| API catalog search | Successful | 2,585.16 ms |

These are individual observations, not latency guarantees. Catalog search does
not prove arbitrary application actions. No external messages, purchases,
account disconnections, API learning or account mutations were used as tests.

Installed release:
`/home/g0pi/.local/share/jarvis-runtime/releases/20261103T123444785625Z-system-integration`.
All ten changed runtime module/manifest hashes matched the release metadata.
The parent release is
`/home/g0pi/.local/share/jarvis-runtime/releases/20261103T121454952667Z-system-integration`.

Final voice state: standby preserved, unmuted, control enabled, no reported
error, 263 registered tools and 95 initial voice tools. Standby was already active
before deployment; deployment did not wake the microphone conversation.

## Installation and operation

Stage with `scripts/prepare_connector_services_release.py`, then activate its
prepared directory with `--activate PATH`. This overlays reviewed definitions
on the current managed release and uses the existing health/rollback mechanism.
It preserves unrelated current modules and voice standby/mute state.

After activating matching runtime code, run
`scripts/install_integration_services.py --install-cli` for a new installation.
It installs pinned CLI dependencies in the isolated environment, backs up a
changed existing service unit, enables the service and checks its private socket.
The dependency flag can be omitted when the CLI environment is already installed.

To inspect services, ask JARVIS to check integration service status. To operate
a supported account, discover the actual Composio action and verify the account.
For a learned API, inspect its operation schema before calling it. For an
application workflow, inspect the CLI registry and installed harness requirements.
Never retry a potentially applied write through another connector or the GUI
without first checking the actual effect.

Rollback restores the prior runtime through the managed release mechanism.
Because the new service depends on this release's `connectors.api_service`, stop
and disable `jarvis-api-agent.service` before rolling back to a release without
that module. Disabling the service alone leaves the bounded local API path usable
in releases that contain the updated connector. CLI dependencies are isolated
from system Python and can remain installed across a runtime rollback.

This improves routing and execution evidence; it does not guarantee every
application action or eliminate all model interpretation errors. Authentication,
upstream availability, operation readback and user intent remain real constraints.

Upstream installation and command reference:
[official CLI-Anything Hub documentation](https://github.com/HKUDS/CLI-Anything/blob/main/cli-hub/README.md).
Machine-interface details were verified against the installed API-Anything CLI
and daemon source under `/home/g0pi/Projects/api-anything`.

See [structured verification evidence](CONNECTOR-SERVICES-EVIDENCE-2026-11-03.json).
