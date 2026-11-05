"""Isolated regression cases from the live memory audit; no user data writes."""
import asyncio
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from jarvis_memory.bridge import MemoryBridge, MemoryError
from jarvis_memory.config import Config, MemoryConfig
from jarvis_memory.skills import MemorySkills


@pytest.fixture
def memory(tmp_path):
    bridge = MemoryBridge(MemoryConfig(path=str(tmp_path / 'memory'), obsidian_auto_sync=False))
    bridge.start()
    yield bridge
    bridge.close()


def test_missing_query_does_not_manufacture_recent_matches(memory):
    memory.record_exchange('We discussed gardening.', 'Water plants tomorrow.')
    assert memory.recall_history('xylophonium-nonexistent-unique') == []
    assert memory.recall('xylophonium-nonexistent-unique')['conversation'] == []
    assert len(memory.recall_history('recent')) == 2


def test_conversation_query_respects_user_boundary(memory):
    memory.record_exchange('Our local notebook.', 'Saved our notes.')
    other = memory.sessions.get_or_create('another-user')
    memory.sessions.save_message(other.session_id, 'user', 'Private nebula project', channel='pc')
    assert memory.recall_history('nebula') == []
    assert all('nebula' not in row['content'] for row in memory.recall_history())
    assert all('nebula' not in row['text'] for row in memory._semantic_conversation_records())


@pytest.mark.asyncio
async def test_declared_device_filter_works_through_public_tools(tmp_path):
    config = Config(memory=MemoryConfig(path=str(tmp_path), obsidian_auto_sync=False))
    skills = MemorySkills(config)
    try:
        await skills.start()
        await skills._memory_operation('record_exchange', user_text='PC notebook', assistant_text='PC answer', device='pc')
        await skills._memory_operation('record_exchange', user_text='Mobile notebook', assistant_text='Mobile answer', device='mobile')
        for tool in ('recall_memory', 'recall_conversation'):
            result = await skills.execute(tool, {'query': 'notebook', 'device': 'mobile'})
            rows = result.get('conversation', result.get('messages'))
            assert rows and all(row['device'] == 'mobile' for row in rows)
    finally:
        await skills.close_agent_jobs()


def test_transcript_opt_out_prevents_all_raw_transcript_writes(tmp_path):
    root = tmp_path / 'opt-out'
    bridge = MemoryBridge(MemoryConfig(path=str(root), record_sessions=False, obsidian_auto_sync=False))
    try:
        bridge.start()
        bridge.record_exchange('I prefer English.', 'Synthetic assistant reply.')
        assert bridge.recall()['memories']
        assert not list(root.rglob('sessions.db'))
        assert not list(root.rglob('history.md'))
        assert not list(root.rglob('transcripts'))
        assert not bridge.status()['continuous_memory']
    finally:
        bridge.close()


def test_temporary_stores_cannot_retarget_workspace_links(memory):
    with patch.object(Path, 'symlink_to', side_effect=AssertionError('Implicit workspace relink')):
        memory.get_device_dir('pc')
        memory.record_exchange('A synthetic test turn.', 'Test response.')


def test_expired_memory_is_not_recalled_or_reintroduced_as_legacy_fact(memory):
    memory.knowledge.upsert('The test coupon expires today', key='coupon', expires_at=time.time() - 1)
    memory.store.add_with_trust('The test coupon expires today', trust='trusted')
    result = memory.recall('coupon')
    assert result['memories'] == [] and result['facts'] == []
    assert 'coupon' not in memory.context()


@pytest.mark.parametrize('kwargs', [{'limit': -1}, {'limit': True}, {'query': None},
                                  {'device': 'unknown-device'}, {'device': 17}])
def test_invalid_recall_arguments_fail_explicitly(memory, kwargs):
    with pytest.raises(MemoryError):
        memory.recall_history(**kwargs)


def test_disabled_status_is_truthful_and_does_not_create_state(tmp_path):
    root = tmp_path / 'disabled'
    bridge = MemoryBridge(MemoryConfig(path=str(root), enabled=False))
    try:
        status = bridge.status()
        assert not status['continuous_memory']
        assert not status['continuous_history']
        assert not root.exists()
    finally:
        bridge.close()


def test_corrupt_conversation_store_is_not_reported_as_empty_healthy_memory(tmp_path):
    (tmp_path / 'sessions.db').write_bytes(b'not a sqlite database')
    bridge = MemoryBridge(MemoryConfig(path=str(tmp_path)))
    try:
        with pytest.raises(MemoryError, match='counts are unavailable'):
            bridge.status()
    finally:
        bridge.close()


def test_device_mirror_preserves_original_event_time(memory):
    import sqlite3
    from datetime import datetime
    timestamp = time.time() - 3 * 86400
    memory.record_exchange('Synthetic offline phone note', '', device='mobile', timestamp=timestamp)
    with sqlite3.connect(memory.root / 'mobile/sessions.db') as connection:
        stored = connection.execute('SELECT timestamp FROM session_messages').fetchone()[0]
    assert stored == pytest.approx(timestamp)
    transcript = memory.root / 'mobile/transcripts' / (datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d') + '.md')
    assert transcript.exists()


@pytest.mark.asyncio
async def test_capture_failures_are_visible_in_status(tmp_path):
    skills = MemorySkills(Config(memory=MemoryConfig(path=str(tmp_path), obsidian_auto_sync=False)))
    try:
        await skills.start()
        with patch.object(skills.memory, 'record_exchange', side_effect=OSError('synthetic disk failure')):
            skills.queue_memory_exchange('Synthetic user text', 'Synthetic reply')
            await asyncio.gather(*tuple(skills._memory_writes), return_exceptions=True)
            await asyncio.sleep(0)
        status = await skills.execute('memory_status')
        assert status['capture_worker']['failed_exchanges'] == 1
        assert status['capture_worker']['pending'] == 0
    finally:
        await skills.close_agent_jobs()


@pytest.mark.asyncio
async def test_correction_reason_survives_public_adapter(tmp_path):
    skills = MemorySkills(Config(memory=MemoryConfig(path=str(tmp_path), obsidian_auto_sync=False)))
    try:
        await skills.start()
        saved = await skills.execute('remember_memory', {'text': 'I prefer English.'})
        await skills.execute('correct_memory', {'memory_id': saved['memory_id'], 'text': 'I prefer French.', 'reason': 'Explicit synthetic correction'})
        history = await skills.execute('memory_history', {'memory_id': saved['memory_id']})
        assert any(row.get('reason') == 'Explicit synthetic correction' for row in history['revisions'])
    finally:
        await skills.close_agent_jobs()
