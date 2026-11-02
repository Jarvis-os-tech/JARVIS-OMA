# memory

Persistent memory implementation, retrieval, embeddings, session storage, Obsidian and standalone MCP packaging.

**Source snapshot:** imports and original behavior are preserved; this folder is not yet an independent package.

## Features

Feature folders contain complete original files, related tests/manifests and exact code extracts.

- [conversation](conversation/FEATURE.md)
- [embeddings](embeddings/FEATURE.md)
- [importers](importers/FEATURE.md)
- [obsidian](obsidian/FEATURE.md)
- [obsidian/tools](obsidian/tools/FEATURE.md)
- [obsidian/tools/legacy](obsidian/tools/legacy/FEATURE.md)
- [retrieval](retrieval/FEATURE.md)
- [security](security/FEATURE.md)
- [services](services/FEATURE.md)
- [shared](shared/FEATURE.md)
- [standalone](standalone/FEATURE.md)
- [storage](storage/FEATURE.md)
- [validation/legacy_tests](validation/legacy_tests/FEATURE.md)

## File index

| Original path | Organized copy |
|---|---|
| `docs/memory-upgrade.md` | [docs/docs/memory-upgrade.md](../../../../jarvis-os/implementation/docs/memory/memory-upgrade.md) |
| `docs/semantic-memory-board.md` | [docs/docs/semantic-memory-board.md](../../../../jarvis-os/implementation/docs/memory/semantic-memory-board.md) |
| `docs/universal-memory.md` | [docs/docs/universal-memory.md](../../docs/universal-memory.md) |
| `jarvis_memory/README.md` | [compatibility/jarvis_memory/README.md](../../jarvis_memory/README.md) |
| `jarvis_memory/__init__.py` | [compatibility/jarvis_memory/__init__.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/compatibility/jarvis_memory/__init__.py) |
| `memory/README.md` | [compatibility/memory/README.md](../../../../jarvis-os/implementation/memory/README.md) |
| `memory/__init__.py` | [compatibility/memory/__init__.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/compatibility/memory/__init__.py) |
| `memory/codes-dev/docs/memory-upgrade.md` | [docs/legacy/memory-upgrade.md](../../../../jarvis-os/implementation/docs/memory/memory-upgrade.md) |
| `memory/codes-dev/docs/semantic-memory-board.md` | [docs/legacy/semantic-memory-board.md](../../../../jarvis-os/implementation/docs/memory/semantic-memory-board.md) |
| `memory/codes-dev/jarvis_memory/README.md` | [docs/original_engine/README.md](../../memory/codes-dev/jarvis_memory/README.md) |
| `memory/codes-dev/jarvis_memory/__init__.py` | [shared/__init__.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/shared/__init__.py) |
| `memory/codes-dev/jarvis_memory/bridge.py` | [services/bridge.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/services/bridge.py) |
| `memory/codes-dev/jarvis_memory/capture.py` | [conversation/capture.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/conversation/capture.py) |
| `memory/codes-dev/jarvis_memory/chunking.py` | [embeddings/chunking.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/embeddings/chunking.py) |
| `memory/codes-dev/jarvis_memory/embeddings.py` | [embeddings/embeddings.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/embeddings/embeddings.py) |
| `memory/codes-dev/jarvis_memory/events.py` | [shared/events.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/shared/events.py) |
| `memory/codes-dev/jarvis_memory/extractor.py` | [conversation/extractor.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/conversation/extractor.py) |
| `memory/codes-dev/jarvis_memory/hybrid.py` | [retrieval/hybrid.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/retrieval/hybrid.py) |
| `memory/codes-dev/jarvis_memory/importers.py` | [importers/importers.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/importers/importers.py) |
| `memory/codes-dev/jarvis_memory/knowledge.py` | [storage/knowledge.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/storage/knowledge.py) |
| `memory/codes-dev/jarvis_memory/mcp_server.py` | [services/mcp_server.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/services/mcp_server.py) |
| `memory/codes-dev/jarvis_memory/obsidian.py` | [obsidian/obsidian.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/obsidian/obsidian.py) |
| `memory/codes-dev/jarvis_memory/paths.py` | [shared/paths.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/shared/paths.py) |
| `memory/codes-dev/jarvis_memory/registry.py` | [shared/registry.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/shared/registry.py) |
| `memory/codes-dev/jarvis_memory/retrieval.py` | [retrieval/retrieval.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/retrieval/retrieval.py) |
| `memory/codes-dev/jarvis_memory/scanner.py` | [security/scanner.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/security/scanner.py) |
| `memory/codes-dev/jarvis_memory/security_types.py` | [security/security_types.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/security/security_types.py) |
| `memory/codes-dev/jarvis_memory/service.py` | [services/service.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/services/service.py) |
| `memory/codes-dev/jarvis_memory/service_facade.py` | [services/service_facade.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/services/service_facade.py) |
| `memory/codes-dev/jarvis_memory/session.py` | [conversation/session.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/conversation/session.py) |
| `memory/codes-dev/jarvis_memory/store.py` | [storage/store.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/storage/store.py) |
| `memory/codes-dev/jarvis_memory/summaries.py` | [conversation/summaries.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/conversation/summaries.py) |
| `memory/codes-dev/jarvis_memory/types.py` | [shared/types.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/shared/types.py) |
| `memory/codes-dev/jarvis_memory/vector_store.py` | [storage/vector_store.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/storage/vector_store.py) |
| `memory/codes-dev/scripts/register_obsidian_vault.py` | [obsidian/tools/legacy/register_obsidian_vault.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/obsidian/tools/legacy/register_obsidian_vault.py) |
| `memory/codes-dev/scripts/sync_obsidian_memory.py` | [obsidian/tools/legacy/sync_obsidian_memory.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/obsidian/tools/legacy/sync_obsidian_memory.py) |
| `memory/codes-dev/tests/__init__.py` | [validation/legacy_tests/__init__.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/legacy_tests/__init__.py) |
| `memory/codes-dev/tests/test_memory_capture.py` | [validation/legacy_tests/test_memory_capture.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/legacy_tests/test_memory_capture.py) |
| `memory/codes-dev/tests/test_memory_config.py` | [validation/legacy_tests/test_memory_config.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/legacy_tests/test_memory_config.py) |
| `memory/codes-dev/tests/test_memory_embeddings.py` | [validation/legacy_tests/test_memory_embeddings.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/legacy_tests/test_memory_embeddings.py) |
| `memory/codes-dev/tests/test_memory_hybrid.py` | [validation/legacy_tests/test_memory_hybrid.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/legacy_tests/test_memory_hybrid.py) |
| `memory/codes-dev/tests/test_memory_integration.py` | [validation/legacy_tests/test_memory_integration.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/legacy_tests/test_memory_integration.py) |
| `memory/codes-dev/tests/test_memory_knowledge.py` | [validation/legacy_tests/test_memory_knowledge.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/legacy_tests/test_memory_knowledge.py) |
| `memory/codes-dev/tests/test_memory_retrieval.py` | [validation/legacy_tests/test_memory_retrieval.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/legacy_tests/test_memory_retrieval.py) |
| `memory/codes-dev/tests/test_memory_strength.py` | [validation/legacy_tests/test_memory_strength.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/legacy_tests/test_memory_strength.py) |
| `memory/codes-dev/tests/test_memory_summaries.py` | [validation/legacy_tests/test_memory_summaries.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/legacy_tests/test_memory_summaries.py) |
| `memory/codes-dev/tests/test_memory_upgrade_integration.py` | [validation/legacy_tests/test_memory_upgrade_integration.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/legacy_tests/test_memory_upgrade_integration.py) |
| `memory/codes-dev/tests/test_memory_vector_store.py` | [validation/legacy_tests/test_memory_vector_store.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/legacy_tests/test_memory_vector_store.py) |
| `memory/codes-dev/tests/test_obsidian_memory.py` | [validation/legacy_tests/test_obsidian_memory.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/legacy_tests/test_obsidian_memory.py) |
| `memory/codes-dev/tests/test_semantic_memory_eval.py` | [validation/legacy_tests/test_semantic_memory_eval.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/legacy_tests/test_semantic_memory_eval.py) |
| `scripts/register_obsidian_vault.py` | [obsidian/tools/register_obsidian_vault.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/obsidian/tools/register_obsidian_vault.py) |
| `scripts/sync_obsidian_memory.py` | [obsidian/tools/sync_obsidian_memory.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/obsidian/tools/sync_obsidian_memory.py) |
| `skill_manifests/memory.json` | [services/manifests/canonical/memory.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/services/manifests/canonical/memory.json) |
| `skills/manifests/memory.json` | [services/manifests/legacy_mirror/memory.json](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/services/manifests/legacy_mirror/memory.json) |
| `tests/test_memory/test_memory_capture.py` | [validation/tests/test_memory/test_memory_capture.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/tests/test_memory/test_memory_capture.py) |
| `tests/test_memory/test_memory_config.py` | [validation/tests/test_memory/test_memory_config.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/tests/test_memory/test_memory_config.py) |
| `tests/test_memory/test_memory_embeddings.py` | [validation/tests/test_memory/test_memory_embeddings.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/tests/test_memory/test_memory_embeddings.py) |
| `tests/test_memory/test_memory_hybrid.py` | [validation/tests/test_memory/test_memory_hybrid.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/tests/test_memory/test_memory_hybrid.py) |
| `tests/test_memory/test_memory_integration.py` | [validation/tests/test_memory/test_memory_integration.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/tests/test_memory/test_memory_integration.py) |
| `tests/test_memory/test_memory_knowledge.py` | [validation/tests/test_memory/test_memory_knowledge.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/tests/test_memory/test_memory_knowledge.py) |
| `tests/test_memory/test_memory_retrieval.py` | [validation/tests/test_memory/test_memory_retrieval.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/tests/test_memory/test_memory_retrieval.py) |
| `tests/test_memory/test_memory_strength.py` | [validation/tests/test_memory/test_memory_strength.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/tests/test_memory/test_memory_strength.py) |
| `tests/test_memory/test_memory_summaries.py` | [validation/tests/test_memory/test_memory_summaries.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/tests/test_memory/test_memory_summaries.py) |
| `tests/test_memory/test_memory_upgrade_integration.py` | [validation/tests/test_memory/test_memory_upgrade_integration.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/tests/test_memory/test_memory_upgrade_integration.py) |
| `tests/test_memory/test_memory_vector_store.py` | [validation/tests/test_memory/test_memory_vector_store.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/tests/test_memory/test_memory_vector_store.py) |
| `tests/test_memory/test_obsidian_memory.py` | [validation/tests/test_memory/test_obsidian_memory.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/tests/test_memory/test_obsidian_memory.py) |
| `tests/test_memory/test_semantic_memory_eval.py` | [validation/tests/test_memory/test_semantic_memory_eval.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/tests/test_memory/test_semantic_memory_eval.py) |
| `tests/test_memory/test_universal_memory_importers.py` | [validation/tests/test_memory/test_universal_memory_importers.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/tests/test_memory/test_universal_memory_importers.py) |
| `tests/test_memory/test_universal_memory_mcp.py` | [validation/tests/test_memory/test_universal_memory_mcp.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/tests/test_memory/test_universal_memory_mcp.py) |
| `tests/test_memory/test_universal_memory_service.py` | [validation/tests/test_memory/test_universal_memory_service.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/validation/tests/test_memory/test_universal_memory_service.py) |
| `universal-memory-mcp/README.md` | [standalone/README.md](standalone/README.md) |
| `universal-memory-mcp/agents/claude-code/README.md` | [standalone/agents/claude-code/README.md](standalone/agents/claude-code/README.md) |
| `universal-memory-mcp/agents/opencode/README.md` | [standalone/agents/opencode/README.md](standalone/agents/opencode/README.md) |
| `universal-memory-mcp/integrations/obsidian/README.md` | [standalone/integrations/obsidian/README.md](standalone/integrations/obsidian/README.md) |
| `universal-memory-mcp/pyproject.toml` | [standalone/pyproject.toml](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/pyproject.toml) |
| `universal-memory-mcp/src/universal_memory_mcp/__init__.py` | [standalone/src/universal_memory_mcp/__init__.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/__init__.py) |
| `universal-memory-mcp/src/universal_memory_mcp/bridge.py` | [standalone/src/universal_memory_mcp/bridge.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/bridge.py) |
| `universal-memory-mcp/src/universal_memory_mcp/capture.py` | [standalone/src/universal_memory_mcp/capture.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/capture.py) |
| `universal-memory-mcp/src/universal_memory_mcp/chunking.py` | [standalone/src/universal_memory_mcp/chunking.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/chunking.py) |
| `universal-memory-mcp/src/universal_memory_mcp/embeddings.py` | [standalone/src/universal_memory_mcp/embeddings.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/embeddings.py) |
| `universal-memory-mcp/src/universal_memory_mcp/events.py` | [standalone/src/universal_memory_mcp/events.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/events.py) |
| `universal-memory-mcp/src/universal_memory_mcp/extractor.py` | [standalone/src/universal_memory_mcp/extractor.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/extractor.py) |
| `universal-memory-mcp/src/universal_memory_mcp/hybrid.py` | [standalone/src/universal_memory_mcp/hybrid.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/hybrid.py) |
| `universal-memory-mcp/src/universal_memory_mcp/importers.py` | [standalone/src/universal_memory_mcp/importers.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/importers.py) |
| `universal-memory-mcp/src/universal_memory_mcp/knowledge.py` | [standalone/src/universal_memory_mcp/knowledge.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/knowledge.py) |
| `universal-memory-mcp/src/universal_memory_mcp/mcp_server.py` | [standalone/src/universal_memory_mcp/mcp_server.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/mcp_server.py) |
| `universal-memory-mcp/src/universal_memory_mcp/obsidian.py` | [standalone/src/universal_memory_mcp/obsidian.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/obsidian.py) |
| `universal-memory-mcp/src/universal_memory_mcp/obsidian_export.py` | [standalone/src/universal_memory_mcp/obsidian_export.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/obsidian_export.py) |
| `universal-memory-mcp/src/universal_memory_mcp/paths.py` | [standalone/src/universal_memory_mcp/paths.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/paths.py) |
| `universal-memory-mcp/src/universal_memory_mcp/registry.py` | [standalone/src/universal_memory_mcp/registry.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/registry.py) |
| `universal-memory-mcp/src/universal_memory_mcp/retrieval.py` | [standalone/src/universal_memory_mcp/retrieval.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/retrieval.py) |
| `universal-memory-mcp/src/universal_memory_mcp/scanner.py` | [standalone/src/universal_memory_mcp/scanner.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/scanner.py) |
| `universal-memory-mcp/src/universal_memory_mcp/security_types.py` | [standalone/src/universal_memory_mcp/security_types.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/security_types.py) |
| `universal-memory-mcp/src/universal_memory_mcp/server.py` | [standalone/src/universal_memory_mcp/server.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/server.py) |
| `universal-memory-mcp/src/universal_memory_mcp/service.py` | [standalone/src/universal_memory_mcp/service.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/service.py) |
| `universal-memory-mcp/src/universal_memory_mcp/service_facade.py` | [standalone/src/universal_memory_mcp/service_facade.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/service_facade.py) |
| `universal-memory-mcp/src/universal_memory_mcp/session.py` | [standalone/src/universal_memory_mcp/session.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/session.py) |
| `universal-memory-mcp/src/universal_memory_mcp/store.py` | [standalone/src/universal_memory_mcp/store.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/store.py) |
| `universal-memory-mcp/src/universal_memory_mcp/summaries.py` | [standalone/src/universal_memory_mcp/summaries.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/summaries.py) |
| `universal-memory-mcp/src/universal_memory_mcp/types.py` | [standalone/src/universal_memory_mcp/types.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/types.py) |
| `universal-memory-mcp/src/universal_memory_mcp/vector_store.py` | [standalone/src/universal_memory_mcp/vector_store.py](../../../../../../../Projects/JARVIS-OMA/Oma%20Jarvis/memory/standalone/src/universal_memory_mcp/vector_store.py) |
