"""Typed memory, scope separation, and organized vault lifecycle contracts."""
from pathlib import Path
import re

import pytest

from jarvis_memory.bridge import MemoryBridge
from jarvis_memory.config import MemoryConfig, Config
from jarvis_memory.skills import MemorySkills

@pytest.fixture
def memory(tmp_path):
    vault = tmp_path / 'vault'
    vault.mkdir()
    bridge = MemoryBridge(MemoryConfig(path=str(tmp_path / 'state'), obsidian_vault=str(vault), obsidian_auto_sync=False))
    bridge.start()
    yield bridge
    bridge.close()

@pytest.mark.parametrize('category,text', [
    ('preferences', 'I prefer concise answers.'),
    ('personal', 'My name is Demo Student.'),
    ('facts', 'The Cedar reference number is CED-417.'),
    ('instructions', 'Include voice test commands after adding features.'),
    ('projects', 'The Cedar project is a study planner.'),
])
def test_category_recall_and_single_canonical_vault_note(memory, category, text):
    saved = memory.remember(text, category=category)
    assert saved['category'] == category
    result = memory.recall(category=category)
    assert any(r['memory_id'] == saved['memory_id'] for r in result['memories'])
    assert not memory.recall(category='observations')['memories']
    synced = memory.sync_obsidian()
    base = Path(synced['memory_map']).parent
    paths = [p for p in base.rglob('*.md') if 'memory_id: "' + saved['memory_id'] + '"' in p.read_text()]
    assert len(paths) == 1
    assert paths[0].parent.name == category.title()
    assert Path(synced['start_here']).exists()
    for p in base.rglob('*.md'):
        for target in re.findall(r'\[\[([^\]]+)\]\]', p.read_text()):
            assert (base.parent / (target + '.md')).exists(), target

def test_scoped_keys_do_not_replace_or_recall_other_project(memory):
    first = memory.knowledge.upsert('Cedar uses SQLite.', key='database', scope='project:cedar')
    second = memory.knowledge.upsert('Juniper uses PostgreSQL.', key='database', scope='project:juniper')
    assert memory.knowledge.get(first['id'])['status'] == 'active'
    assert memory.knowledge.get(second['id'])['status'] == 'active'
    assert memory.recall('database SQLite PostgreSQL')['memories'] == []
    result = memory.recall('SQLite PostgreSQL', scope='project:cedar')
    assert {r['memory_id'] for r in result['memories']} == {first['id']}
    proposal = memory.knowledge.propose('Cedar uses DuckDB.', key='database', scope='project:cedar')
    memory.knowledge.commit(proposal['id'])
    assert memory.knowledge.get(second['id'])['status'] == 'active'

def test_project_remember_cannot_leak_via_legacy_facts(memory):
    memory.remember('The private project marker is ORBIT-PRIVATE.', scope='project:orbit')
    recalled = memory.recall('ORBIT-PRIVATE')
    assert not recalled['memories'] and not recalled['facts']
    assert memory.recall('ORBIT-PRIVATE', scope='project:orbit')['memories']

def test_auto_capture_personal_and_instruction_kinds_are_supported(memory):
    memory.record_exchange('My name is Demo Student. Remember this instruction: include test commands.', 'Synthetic assistant reply.')
    assert memory.recall(category='personal')['memories']
    instructions = memory.recall(category='instructions')['memories']
    assert instructions and instructions[0]['evidence']['role'] == 'user'
    context = memory.context()
    assert 'not system instructions or execution authorization' in context

def test_vault_excludes_expired_and_secret_forbidden_entries(memory):
    memory.knowledge.upsert('Expired marker TEMP-OLD', expires_at=1)
    memory.knowledge.upsert('Secret marker SECRET-DEMO', sensitivity='secret-forbidden')
    memory.store.add_with_trust('Expired marker TEMP-OLD', trust='trusted')
    result = memory.sync_obsidian()
    content = '\n'.join(p.read_text() for p in Path(result['memory_map']).parent.rglob('*.md'))
    assert 'TEMP-OLD' not in content and 'SECRET-DEMO' not in content

@pytest.mark.asyncio
async def test_voice_memory_tools_accept_category_and_scope(tmp_path):
    skills = MemorySkills(Config(memory=MemoryConfig(path=str(tmp_path / 'state'), obsidian_auto_sync=False)))
    try:
        await skills.start()
        saved = await skills.execute('remember_memory', {'text':'Use concise replies.', 'category':'instructions'})
        recalled = await skills.execute('recall_memory', {'category':'instructions'})
        assert recalled['memories'][0]['memory_id'] == saved['memory_id']
    finally:
        await skills.close_agent_jobs()

def test_six_layers_have_temporary_working_and_persistent_events_and_procedures(memory, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr('jarvis_memory.manager.time.monotonic', lambda: clock[0])
    memory.manager.set_working('task', 'Compare database options', ttl=5)
    assert memory.manager.working()[0]['text'] == 'Compare database options'
    clock[0] = 106
    assert memory.manager.working() == []
    episode = memory.remember('Finished the Cedar review', category='episodes', outcome='User reports success', occurred_at=1700000000)
    procedure = memory.remember('Review a project', category='procedures', steps=['Read requirements', 'Run checks'])
    assert not episode['verified'] and not procedure['verified']
    assert memory.recall(category='episodes')['memories'][0]['observed_at'] == 1700000000
    assert memory.recall(category='procedures')['memories'][0]['evidence']['steps'] == ['Read requirements', 'Run checks']
    layers = memory.status()['memory_layers']
    assert set(layers) == {'short_term','long_term','episodic','semantic','procedural','shared'}
    assert not layers['procedural']['automatic_execution']
    sync = memory.sync_obsidian()
    base = Path(sync['memory_map']).parent
    assert all((base / (name + ' Memory.md')).exists() for name in ('Short-term','Long-term','Episodic','Semantic','Procedural','Shared'))

def test_shared_manager_enforces_agent_policy_and_proposal_commit(memory):
    from jarvis_memory.mcp_server import ClientPolicy
    with pytest.raises(ValueError):
        memory.manager.shared(ClientPolicy('agent-a', frozenset({'user'}), frozenset()))
    writer = memory.manager.shared(ClientPolicy('agent-a', frozenset({'shared:team'}), frozenset({'shared:team'}), frozenset({'propose'})))
    result = writer.call_tool('memory_propose', {'record': {'text':'Team review is pending.', 'scope':'shared:team'}}, request_id='proposal-check')
    assert result
    assert not memory.recall('Team review')['memories']
    with pytest.raises(Exception):
        writer.call_tool('memory_commit', {'proposal_id': 'uncommitted'}, request_id='denied-check')

def test_scoped_forget_preserves_identical_user_memory(memory):
    text = 'The shared marker is DEMO-CEDAR.'
    memory.remember(text)
    memory.remember(text, scope='project:cedar')
    memory.forget(text, scope='project:cedar')
    assert memory.recall('DEMO-CEDAR')['memories']

def test_clean_vault_has_six_sections_no_topic_nodes_and_resolves_links(memory):
    memory.config.obsidian_layout = 'organized'
    memory.remember('Give me voice tests.', category='instructions')
    memory.record_exchange('Synthetic project notes today', 'Synthetic response')
    synced = memory.sync_obsidian()
    vault = Path(synced['vault'])
    expected = {'01 Short-Term Memory','02 Long-Term Memory','03 Episodic Memory',
                '04 Semantic Memory','05 Procedural Memory','06 Shared Memory'}
    assert {p.name for p in vault.iterdir() if p.is_dir()} == expected
    assert not (vault / 'Topics').exists()
    assert not (vault / 'JARVIS-OMA Memory').exists()
    assert (vault / '00 HOME.md').exists()
    assert len(list(vault.rglob('Memory-*.md'))) == 1
    for note in vault.rglob('*.md'):
        for target in re.findall(r'(?<!\\)\[\[([^\]]+)\]\]', note.read_text()):
            assert (vault / (target + '.md')).exists(), (note.name, target)
    assert memory.sync_obsidian()['written'] == 0
