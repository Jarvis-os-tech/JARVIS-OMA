# Explicit feedback-driven Harness refinement

JARVIS can send selected research feedback to the installed Harness² proposer
using cloud inference. This improves research instructions around the model;
it does not train or change cloud model weights. No local model is required.

Record feedback, list its IDs, then explicitly request a proposal for one to
five selected IDs. The voice service requires notes from the running project,
bundle and voice model. It selects a text model using `JARVIS_HARNESS_MODEL`,
then `JARVIS_BACKGROUND_MODEL`, then the existing background route. Its current
Gemini key is supplied only to the cloud child environment. Other recognized
credential variables are removed; the key never enters command arguments or
job journals. The process uses the same 32-call, 120-second refinement budget
and 150-second supervisor limit as offline integration checks.

The standalone administrator route is:

```bash
.venv/bin/python -m learning --state-dir .jarvis-learning refine \
  --model YOUR_GEMINI_TEXT_MODEL --feedback-id FEEDBACK_ID --max-calls 32 --seconds 120
```

It requires `GEMINI_API_KEY`. Repeat `--feedback-id` for additional explicitly
selected notes. For an offline integration run with the same selected evidence,
replace `--model YOUR_GEMINI_TEXT_MODEL` with `--offline`. Offline results cannot
qualify for adoption.

Only bounded sanitized note text and its observation metadata are supplied;
this path does not export raw episode transcripts, audio, arbitrary files or
the whole feedback database. Notes remain unverified data, never instructions
or additional tool authority. Recognized secret redaction is not comprehensive
personal-data detection, so select only suitable notes for cloud processing.

`feedback.json` records the selected observations. Start and report records
bind their IDs and content digest, and the artifact manifest covers the file.
Only the proposer sees them. The executor and independent fixed/held-out checks
remain unchanged. Candidates are saved for review, not activated. Existing
candidate trial, manual voice review, lesson publication and rollback gates
continue to apply.

A completed proposal is **not evidence that a selected mistake is fixed**.
Reports and job statuses explicitly retain `feedback_addressed_verified: false`.
The current checks cover a narrow synthetic research corpus, and cannot verify
audio lag, desktop actions or arbitrary coding failures. Such issues require
their own reproducible tasks and independent acceptance evidence. Feedback is
never marked resolved and no application code or locked voice file is changed
by this route. General unattended self-evolution remains outside this scope.
