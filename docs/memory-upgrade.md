# Memory upgrade work board

Shared workspace, disjoint file ownership; the main agent integrates and reviews.

| Work | Owner | Scope | Gate | State |
| --- | --- | --- | --- | --- |
| Evidence-grounded capture | Socrates | capture module and tests | Explicit user facts only; no assistant fabrication | Reviewed |
| Ranked retrieval | Nash | retrieval module and tests | Relevant paraphrases; no unrelated matches | Reviewed |
| Persistent corrections | Anscombe | knowledge ledger and tests | Restart/concurrency, evidence, supersession | Reviewed |
| Daily summaries | Wegener | summaries, Obsidian exporter, summary tests | Source IDs; transcripts and manual edits preserved | Reviewed |
| Recall acceptance tests | Averroes | end-to-end strength tests | Capture/correction/restart/forget/clear/trust/budget | Passed |
| Runtime integration | Main | bridge, config, skills, manifests, docs | Full regression suite and startup check | Running |

No cloud extraction, provider changes, or model installation is required.
Retrieval is ranked lexical/concept matching, not embedding-based semantic search.
Summaries are extractive views, not model-generated claims of completion.
