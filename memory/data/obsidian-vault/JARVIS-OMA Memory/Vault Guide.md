---
aliases: ["Vault structure and automatic links"]
tags: [jarvis-memory, index]
---
<!-- jarvis-oma-memory-generated:v1 -->

# Vault structure and automatic links

Reference: /home/g0pi/Downloads/jarvis/jarvis_memory_bundle/vault

Conversations: one YYYY-MM-DD - Weekday.md report per local calendar day, plus conversation.md for the continuous journal. Reports retain captured dialogue and message IDs; they are not AI summaries.

Summaries: separate extractive daily notes quote source messages with IDs and link to daily reports. Assistant reported outcomes are unverified; follow-up mentions are not inferred tasks.

Knowledge: active structured memories with evidence, kind, confidence and stable IDs. Facts and Profiles: trusted memory and core user/system profiles. Documents: indexed reference text. Topics and Entities: automatic shared-word and speaker links for Graph view. Daily reports link to neighboring days and related fact/profile notes.

SQLite remains the continuous source of truth across restarts. Day changes only organize the view. Old vault contents are not imported. Keep future custom skills and personal notes outside JARVIS-OMA Memory; Markdown skills are not automatically executed. Manual changes to generated notes are preserved and reported as sync conflicts. Use sync_memory_vault to refresh; background refresh runs while voice is connected.

[[JARVIS-OMA Memory/Memory Map]]
[[JARVIS-OMA Memory/Continuous Memory]]
[[JARVIS-OMA Memory/Summaries]]
[[JARVIS-OMA Memory/Knowledge]]
[[JARVIS-OMA Memory/Facts]]
[[JARVIS-OMA Memory/Profiles]]
[[JARVIS-OMA Memory/Documents]]
[[JARVIS-OMA Memory/Topics]]
