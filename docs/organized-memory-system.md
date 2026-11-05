# JARVIS organized memory

Implemented and installed on 2026-11-04. UI/dashboard development remains deferred.

`MemoryManager` coordinates six layers over the existing stores:

| Layer | Implementation | Vault view |
| --- | --- | --- |
| Short-term | Bounded in-process working context with TTL; cleared on close | 01 Short-Term Memory |
| Long-term | SQLite evidence ledger; preferences, personal details, instructions, projects, decisions and tasks | 02 Long-Term Memory |
| Episodic | Existing dated conversation records plus explicit event/outcome records | 03 Episodic Memory |
| Semantic | Facts, concepts, references and indexed documents; optional vector retrieval remains disabled | 04 Semantic Memory |
| Procedural | Saved text steps with verification metadata; never automatic execution | 05 Procedural Memory |
| Shared | Existing policy-controlled MCP facade with scoped, audited proposal/commit operations | 06 Shared Memory |

Vault: `/home/g0pi/Documents/JARVIS Memory`. Start at `00 HOME.md`.
The configured `obsidian_layout = "organized"` suppresses per-word topic nodes,
duplicate umbrella indexes and the duplicate all-days journal. Empty auxiliary
categories are created when needed; the core requested categories remain available.
`legacy` layout remains supported for existing integrations.

General recall defaults to user scope. Explicit `project:NAME` recall includes
that project and user memories. Scoped keys cannot replace another project's
entry. Project writes never enter the unscoped legacy fact store. Forgetting
within a project preserves an identical user memory. Instructions remain user
guidance rather than system policy or action authorization. Expired, superseded,
proposed and secret-forbidden entries are not exported as current memories.

Shared client handles require explicit project/shared scopes and cannot implicitly
read personal user memory. This does not grant new agents access or claim an
active multi-agent exchange. User-described procedures and reported event outcomes
remain unverified; execution evidence is not fabricated.

The new vault preserves 2,530 recorded conversation messages, four existing task
memories, and the user's explicit instruction to provide voice test commands.
Empty personal/fact/preference categories are not populated with invented details.
334 historical Markdown notes from the previous agent vault were preserved under
`03 Episodic Memory/Agent History`. They are historical data, not promoted facts.

Both previous vault registrations were removed. The existing `/home/g0pi/secondary memory`
folder was moved to Trash; the other registered vault directory was already absent.
The generated legacy folder and old landing pages were also moved to Trash during
cleanup. Memory database snapshots and configuration backups are retained under
`~/.local/state/jarvis/backups/`. A repeat sync wrote zero changes and found zero
broken managed navigation links. Generated nodes decreased from 2,231 to 32.

Installed package certification: 172 memory tests plus 81 subtests; 167 required
behavior checks. Installed-package category recall and vault export were verified.
The voice service stopped cleanly after the first deployment and was left stopped.
The cleanup release preserves that stopped state; no microphone-to-tool acceptance
test is claimed. The next voice start uses the new release and vault configuration.

An overbroad Hyprland title rule had matched Obsidian's “JARVIS Memory” title and
shrunk it into an input-bar overlay. Its match now also requires `JarvisInputBar`;
the prior configuration is backed up. Configuration reload reported no errors,
and Obsidian was restored to a visible, unpinned window. No new JARVIS GUI was kept.

## Voice tests

Start JARVIS, then say:

- “Show my memory system status and its six layers.”
- “Save this under preferences: I prefer short explanations during memory tests.”
- “What preferences have I saved?”
- “Remember this event: I completed a memory test today. Its reported outcome was successful.”
- “Save a procedure called Review my notes. First read the notes, then check the sources.”
- “Recall my saved procedures.”
- “Sync my memory vault.”

Expected: categorized notes, explicitly reported/unverified event outcomes and
procedures, and the same six-folder structure after sync. Voice command parsing
depends on the current conversation model; tool schemas and installed memory
operations were tested directly. The full guide is in the vault's
`02 Long-Term Memory/Instructions/Voice Test Commands.md`.

Attribution: CSE-OS by CSE-OS Contributors, adapted from Founder OS by Adam M.
Adamek (Impact Brussels ASBL).
