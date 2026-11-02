# CLI-Anything Integration Design

## Intent & Why

Integrate the CLI-Anything framework into JARVIS-OMA to give the voice-first multi-agent OS access to 40+ agent-native CLI harnesses for professional software (GIMP, Blender, Inkscape, LibreOffice, Audacity, OBS Studio, etc.). This extends JARVIS's desktop control capabilities from basic system operations to full creative/professional workflow automation.

## Goals

1. **Add `cli-hub` package manager** as a dependency for discovering/installing CLI-Anything harnesses
2. **Expose CLI-Hub operations as JARVIS skills** so voice agents can browse, search, install, and launch CLIs
3. **Enable matrix workflows** for multi-tool creative pipelines (video creation, 3D modeling, etc.)
4. **Maintain voice-lock compliance** - no modifications to locked audio files
5. **Follow existing skill patterns** - JSON manifests + adapter methods in skills.py

## Non-Goals / Anti-Goals

- ❌ Do NOT modify locked voice files (audio/engine.py, audio/downstream.py, audio/echo_cancel.py, audio/__init__.py, echo_cancel.py)
- ❌ Do NOT bundle individual CLIs (gimp, blender, etc.) - they install on-demand via cli-hub
- ❌ Do NOT create a custom CLI generator - use upstream cli-hub registry
- ❌ Do NOT add GUI for CLI management - voice-first, CLI-driven

## Constraints

- Python ≥ 3.10 (already satisfied)
- Must work within existing skill manifest system (version 1, max 64 files, 128 skills/file)
- Adapter commands must be discoverable via `shutil.which()` or explicit override
- Skills gracefully degrade when commands unavailable (existing pattern)

## Architecture

### New Skill Manifest: `skill_manifests/cli-anything.json`

```json
{
  "version": 1,
  "skills": [
    {
      "name": "cli_hub_list",
      "description": "Browse all available CLI-Anything harnesses in the registry. Returns categorized list with install commands.",
      "adapter": "cli_hub.list",
      "parameters_json_schema": {
        "type": "object",
        "properties": {
          "category": {"type": "string", "description": "Optional category filter (image, video, audio, 3d, productivity, ai, communication)"}
        },
        "required": [],
        "additionalProperties": false
      }
    },
    {
      "name": "cli_hub_search",
      "description": "Search CLI-Anything registry by keyword. Returns matching harnesses with descriptions and install commands.",
      "adapter": "cli_hub.search",
      "parameters_json_schema": {
        "type": "object",
        "properties": {
          "query": {"type": "string", "description": "Search terms (e.g. 'video editing', '3d modeling', 'image generation')"}
        },
        "required": ["query"],
        "additionalProperties": false
      }
    },
    {
      "name": "cli_hub_info",
      "description": "Show detailed information about a specific CLI harness including capabilities, commands, and requirements.",
      "adapter": "cli_hub.info",
      "parameters_json_schema": {
        "type": "object",
        "properties": {
          "name": {"type": "string", "description": "CLI harness name (e.g. 'gimp', 'blender', 'kdenlive')"}
        },
        "required": ["name"],
        "additionalProperties": false
      }
    },
    {
      "name": "cli_hub_install",
      "description": "Install a CLI-Anything harness via pip. Idempotent - skips if already installed.",
      "adapter": "cli_hub.install",
      "parameters_json_schema": {
        "type": "object",
        "properties": {
          "name": {"type": "string", "description": "CLI harness name to install"},
          "dry_run": {"type": "boolean", "description": "Show install plan without executing", "default": false}
        },
        "required": ["name"],
        "additionalProperties": false
      }
    },
    {
      "name": "cli_hub_uninstall",
      "description": "Uninstall a CLI-Anything harness.",
      "adapter": "cli_hub.uninstall",
      "parameters_json_schema": {
        "type": "object",
        "properties": {
          "name": {"type": "string", "description": "CLI harness name to uninstall"}
        },
        "required": ["name"],
        "additionalProperties": false
      }
    },
    {
      "name": "cli_hub_launch",
      "description": "Launch an installed CLI harness with arguments. Supports --json for machine-readable output.",
      "adapter": "cli_hub.launch",
      "parameters_json_schema": {
        "type": "object",
        "properties": {
          "name": {"type": "string", "description": "CLI harness name (e.g. 'gimp')"},
          "args": {"type": "array", "items": {"type": "string"}, "description": "Arguments to pass to the CLI"},
          "json_output": {"type": "boolean", "description": "Request JSON output", "default": false}
        },
        "required": ["name"],
        "additionalProperties": false
      }
    },
    {
      "name": "cli_hub_matrix_list",
      "description": "List available workflow matrices (capability × provider bundles like video-creation, 3d-modeling).",
      "adapter": "cli_hub.matrix_list",
      "parameters_json_schema": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": false
      }
    },
    {
      "name": "cli_hub_matrix_preflight",
      "description": "Check what's usable for a matrix capability. Exit code 3 = gaps with install hints.",
      "adapter": "cli_hub.matrix_preflight",
      "parameters_json_schema": {
        "type": "object",
        "properties": {
          "matrix": {"type": "string", "description": "Matrix name (e.g. 'video-creation')"},
          "capability": {"type": "string", "description": "Optional capability filter (e.g. 'text.transcribe')"},
          "fix_hints": {"type": "boolean", "description": "Show install hints for gaps", "default": false}
        },
        "required": ["matrix"],
        "additionalProperties": false
      }
    },
    {
      "name": "cli_hub_matrix_install",
      "description": "Install a matrix workflow (or scoped subset via --capability/--recipe/--only).",
      "adapter": "cli_hub.matrix_install",
      "parameters_json_schema": {
        "type": "object",
        "properties": {
          "matrix": {"type": "string", "description": "Matrix name (e.g. 'video-creation')"},
          "capability": {"type": "string", "description": "Install only CLIs for this capability"},
          "recipe": {"type": "string", "description": "Install only CLIs used by this recipe"},
          "only": {"type": "string", "description": "Comma-separated CLI names to install"},
          "dry_run": {"type": "boolean", "description": "Show plan without executing", "default": false}
        },
        "required": ["matrix"],
        "additionalProperties": false
      }
    }
  ]
}
```

### New Adapter Methods in `skills/skills.py`

Add to `ADAPTERS` dict:
```python
'cli_hub.list': '_adapter_cli_hub_list',
'cli_hub.search': '_adapter_cli_hub_search',
'cli_hub.info': '_adapter_cli_hub_info',
'cli_hub.install': '_adapter_cli_hub_install',
'cli_hub.uninstall': '_adapter_cli_hub_uninstall',
'cli_hub.launch': '_adapter_cli_hub_launch',
'cli_hub.matrix_list': '_adapter_cli_hub_matrix_list',
'cli_hub.matrix_preflight': '_adapter_cli_hub_matrix_preflight',
'cli_hub.matrix_install': '_adapter_cli_hub_matrix_install',
```

Add to `ADAPTER_COMMANDS` dict:
```python
'cli_hub.list': ('cli-hub',),
'cli_hub.search': ('cli-hub',),
'cli_hub.info': ('cli-hub',),
'cli_hub.install': ('cli-hub',),
'cli_hub.uninstall': ('cli-hub',),
'cli_hub.launch': ('cli-hub',),
'cli_hub.matrix_list': ('cli-hub',),
'cli_hub.matrix_preflight': ('cli-hub',),
'cli_hub.matrix_install': ('cli-hub',),
```

### Adapter Implementation Pattern

```python
async def _adapter_cli_hub_list(self, category=None):
    """Browse CLI-Anything registry."""
    cmd = [self._command('cli-hub'), 'list']
    if category:
        cmd.extend(['-c', category])
    cmd.append('--json')
    output = await self._run(*cmd, max_output=10000)
    return json.loads(output)

async def _adapter_cli_hub_search(self, query):
    """Search CLI-Anything registry."""
    if not isinstance(query, str) or not query.strip() or len(query) > 200:
        raise SkillError('search query must be 1 to 200 characters')
    output = await self._run(self._command('cli-hub'), 'search', query.strip(), '--json', max_output=10000)
    return json.loads(output)

async def _adapter_cli_hub_info(self, name):
    """Show CLI harness details."""
    if not isinstance(name, str) or not name.strip() or len(name) > 100:
        raise SkillError('CLI name must be 1 to 100 characters')
    output = await self._run(self._command('cli-hub'), 'info', name.strip(), '--json', max_output=10000)
    return json.loads(output)

async def _adapter_cli_hub_install(self, name, dry_run=False):
    """Install CLI harness."""
    if not isinstance(name, str) or not name.strip() or len(name) > 100:
        raise SkillError('CLI name must be 1 to 100 characters')
    cmd = [self._command('cli-hub'), 'install', name.strip()]
    if dry_run:
        cmd.append('--dry-run')
    cmd.append('--json')
    output = await self._run(*cmd, timeout=120, max_output=10000)
    return json.loads(output)

async def _adapter_cli_hub_uninstall(self, name):
    """Uninstall CLI harness."""
    if not isinstance(name, str) or not name.strip() or len(name) > 100:
        raise SkillError('CLI name must be 1 to 100 characters')
    cmd = [self._command('cli-hub'), 'uninstall', name.strip(), '--json']
    output = await self._run(*cmd, timeout=60, max_output=10000)
    return json.loads(output)

async def _adapter_cli_hub_launch(self, name, args=None, json_output=False):
    """Launch installed CLI harness."""
    if not isinstance(name, str) or not name.strip() or len(name) > 100:
        raise SkillError('CLI name must be 1 to 100 characters')
    cli_name = f'cli-anything-{name.strip()}'
    cmd = [cli_name]
    if args:
        cmd.extend(args)
    if json_output:
        cmd.append('--json')
    # Use _launch for interactive REPL, _run for one-shot
    if not args or (args and '--json' in args):
        output = await self._run(*cmd, timeout=60, max_output=10000)
        return json.loads(output) if json_output else {'output': output}
    else:
        await self._launch(*cmd)
        return {'status': 'launched', 'cli': cli_name}

async def _adapter_cli_hub_matrix_list(self):
    """List workflow matrices."""
    output = await self._run(self._command('cli-hub'), 'matrix', 'list', '--json', max_output=10000)
    return json.loads(output)

async def _adapter_cli_hub_matrix_preflight(self, matrix, capability=None, fix_hints=False):
    """Preflight check for matrix capability."""
    if not isinstance(matrix, str) or not matrix.strip():
        raise SkillError('matrix name required')
    cmd = [self._command('cli-hub'), 'matrix', 'preflight', matrix.strip()]
    if capability:
        cmd.extend(['-c', capability])
    if fix_hints:
        cmd.append('--fix-hints')
    cmd.append('--json')
    try:
        output = await self._run(*cmd, timeout=60, max_output=10000)
        return json.loads(output)
    except SkillError as e:
        # Exit code 3 = partial/gaps, return structured info
        if 'exit code 3' in str(e).lower() or 'partial' in str(e).lower():
            return {'status': 'partial', 'gaps': str(e)}
        raise

async def _adapter_cli_hub_matrix_install(self, matrix, capability=None, recipe=None, only=None, dry_run=False):
    """Install matrix workflow."""
    if not isinstance(matrix, str) or not matrix.strip():
        raise SkillError('matrix name required')
    cmd = [self._command('cli-hub'), 'matrix', 'install', matrix.strip()]
    if capability:
        cmd.extend(['--capability', capability])
    if recipe:
        cmd.extend(['--recipe', recipe])
    if only:
        cmd.extend(['--only', only])
    if dry_run:
        cmd.append('--dry-run')
    cmd.append('--json')
    output = await self._run(*cmd, timeout=300, max_output=20000)
    return json.loads(output)
```

## Dependencies

Add to `requirements.txt`:
```
cli-anything-hub>=0.1.0
```

## Acceptance Criteria

### Functional
- [ ] `cli-hub` command available after `pip install -r requirements.txt`
- [ ] All 9 skills declared in manifest load without error
- [ ] `cli_hub_list` returns categorized registry (at least 3 categories)
- [ ] `cli_hub_search "video"` returns relevant results
- [ ] `cli_hub_info gimp` shows harness details
- [ ] `cli_hub_install gimp --dry-run` shows install plan
- [ ] `cli_hub_matrix_list` returns available matrices
- [ ] `cli_hub_matrix_preflight video-creation` returns capability status
- [ ] Skills gracefully handle missing `cli-hub` command (excluded when unavailable)

### Integration
- [ ] Skills appear in `DesktopSkills.capability_context()` output
- [ ] Skills excluded when `exclude_unavailable=True` and cli-hub not installed
- [ ] No modifications to locked voice files
- [ ] No breaking changes to existing skills

### Testing
- [ ] Unit tests for all 9 adapter methods (mocking cli-hub subprocess)
- [ ] Manifest validation test (schema, naming, adapter approval)
- [ ] Integration test: skill discovery + execution flow
- [ ] Offline tests pass (`pytest tests/test_skills/test_skills.py -m offline`)

## Test Strategy

### Unit Tests (offline, fast)
Location: `tests/test_skills/test_cli_anything.py`

```python
class CLIAnythingSkillTests(unittest.IsolatedAsyncioTestCase):
    # Manifest loading
    def test_manifest_loads_valid_schema(self)
    def test_all_adapters_approved(self)
    
    # Adapter mocking
    async def test_cli_hub_list_returns_parsed_json(self)
    async def test_cli_hub_search_validates_query(self)
    async def test_cli_hub_info_validates_name(self)
    async def test_cli_hub_install_validates_name_and_dry_run(self)
    async def test_cli_hub_uninstall_validates_name(self)
    async def test_cli_hub_launch_validates_name(self)
    async def test_cli_hub_matrix_list_returns_parsed_json(self)
    async def test_cli_hub_matrix_preflight_handles_exit_3(self)
    async def test_cli_hub_matrix_install_validates_params(self)
    
    # Graceful degradation
    async def test_skills_excluded_when_cli_hub_missing(self)
```

### Integration Tests (require cli-hub installed)
Location: `tests/test_skills/test_cli_anything_integration.py`

```python
class CLIAnythingIntegrationTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        # Skip if cli-hub not installed
        if not shutil.which('cli-hub'):
            raise unittest.SkipTest('cli-hub not installed')
    
    async def test_full_list_search_install_flow(self)
    async def test_matrix_preflight_and_install(self)
```

### Test Commands
```bash
# Offline unit tests
pytest tests/test_skills/test_cli_anything.py -v

# Integration (when cli-hub available)
pytest tests/test_skills/test_cli_anything_integration.py -v -m live_desktop

# Full skill test suite
pytest tests/test_skills/ -v -m offline
```

## Implementation Phases

### Phase 1: Core Integration (this assignment)
- [ ] Add `cli-anything-hub` to requirements.txt
- [ ] Create `skill_manifests/cli-anything.json`
- [ ] Add adapters to `skills/skills.py` (ADAPTERS, ADAPTER_COMMANDS, implementations)
- [ ] Write unit tests in `tests/test_skills/test_cli_anything.py`

### Phase 2: Polish & Matrix Support (next assignment)
- [ ] Add matrix workflow helpers
- [ ] Add skill for discovering installed CLIs (`cli-hub list --installed`)
- [ ] Add REPL session management for long-running CLIs

### Phase 3: Voice UX (future)
- [ ] Natural language → CLI mapping (e.g., "edit this photo in GIMP" → cli_hub_launch)
- [ ] Preview/live-preview/trajectory integration for supported harnesses

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| cli-hub not installed | Graceful degradation via `exclude_unavailable` |
| CLI install timeout | Configurable timeout (120s install, 300s matrix) |
| Large JSON output | Bounded `max_output` (10KB-20KB) |
| Invalid CLI names | Input validation (length, chars) |
| Voice lock violation | No audio file modifications; separate skill manifest |

## Verification Checklist

Before claiming complete:
- [ ] `python3 scripts/verify_voice_lock.py` passes
- [ ] `pytest tests/test_skills/test_cli_anything.py -v` passes
- [ ] `pytest tests/test_skills/test_skills.py -v -m offline` passes (no regressions)
- [ ] `DesktopSkills()` instantiates without error
- [ ] All 9 skills appear in `capability_context()`