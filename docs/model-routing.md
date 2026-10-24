# Model routes

Voice uses the configured Live model (default gemini-3.8-live). Transient
provider errors or an unavailable model try gemini-3.8-live and then
gemini-3.1-flash-live-preview, with duplicate entries removed. Credentials and
invalid setup errors do not trigger fallback. A fallback starts a fresh session.

start_model_processing returns immediately and runs bounded asynchronous Gemini
requests outside the voice turn. Routes are:

| Route | Primary | Fallback |
| --- | --- | --- |
| fast | gemini-3.5-flash-lite | gemini-3.1-flash-lite |
| background | gemini-3.6-flash | gemini-3.8-flash |
| reasoning | gemini-4-argon | gemini-3.6-flash |

JARVIS_FAST_MODEL, JARVIS_BACKGROUND_MODEL and JARVIS_REASONING_MODEL can override
the primary. Each job permits two attempts, each limited to 60 seconds and 4096
output tokens. Two jobs can run concurrently. These models provide analysis and
cannot execute tools. Results enter the existing voice notification queue; use
model_processing_status for subsequent reads. Provider billing caps are not
enforced. Availability and quotas depend on the account.

Simple conversation should be answered directly by Live. Complex reasoning
should use the reasoning route; bulk processing should use background. Existing
coding-agent CLI routes remain separately configured.

References: https://ai.google.dev/gemini-api/docs/models and
https://ai.google.dev/gemini-api/docs/live-api/capabilities
