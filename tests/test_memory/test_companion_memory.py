import tempfile
import time
from pathlib import Path

import pytest

from jarvis_memory.bridge import MemoryBridge
from jarvis_memory.config import MemoryConfig
from jarvis_memory.session import SessionStore


def record(identifier='mobile-1', content='I prefer concise answers.'):
    return dict(id=identifier, role='user', content=content, timestamp=int(time.time() * 1000) - 60000)


def test_acknowledges_durable_history_once_across_restart(tmp_path):
    config = MemoryConfig(enabled=True, record_sessions=True, path=str(tmp_path))
    memory = MemoryBridge(config)
    memory.start()
    source = record()
    first = memory.sync_companion([source])
    assert first['acknowledged'] == [source['id']]
    turns = memory.recall_history('', 50)
    assert len(turns) == 1
    assert turns[0]['device'] == 'mobile'
    assert turns[0]['timestamp'] == pytest.approx(source['timestamp'] / 1000)
    restarted = MemoryBridge(config)
    restarted.start()
    result = restarted.sync_companion([source])
    assert result['acknowledged'] == [source['id']]
    assert len(restarted.recall_history('', 50)) == 1
    assert source['content'] in result['context']


def test_roundtrip_includes_pc_and_mobile_and_pull_without_upload(tmp_path):
    memory = MemoryBridge(MemoryConfig(enabled=True, record_sessions=True, path=str(tmp_path)))
    memory.start()
    memory.record_exchange('PC project discussion', 'PC response')
    result = memory.sync_companion([record()])
    assert {turn['device'] for turn in result['history']} == {'pc', 'mobile'}
    pulled = memory.sync_companion([])
    assert pulled['acknowledged'] == []
    assert len(pulled['history']) == 3


def test_invalid_batch_is_not_partly_saved_or_acknowledged(tmp_path):
    memory = MemoryBridge(MemoryConfig(enabled=True, record_sessions=True, path=str(tmp_path)))
    memory.start()
    with pytest.raises(ValueError):
        memory.sync_companion([record(), record('bad', '')])
    assert memory.recall_history('', 50) == []


def test_ack_does_not_succeed_if_memory_disabled(tmp_path):
    memory = MemoryBridge(MemoryConfig(enabled=False, path=str(tmp_path)))
    with pytest.raises(ValueError, match='disabled'):
        memory.sync_companion([record()])


def test_failed_write_does_not_acknowledge_or_consume_stable_id(tmp_path):
    import sqlite3
    store = SessionStore(tmp_path / 'sessions.db', consolidation_threshold=0)
    session = store.get_or_create('test-user')
    with pytest.raises(sqlite3.IntegrityError):
        store.save_message(session.session_id, None, 'not saved', external_id='retry-same-id')
    assert store.save_message(session.session_id, 'user', 'saved after retry', external_id='retry-same-id')
    assert store.count_messages() == 1


def test_offline_backlog_retains_original_chronology(tmp_path):
    memory = MemoryBridge(MemoryConfig(enabled=True, record_sessions=True, path=str(tmp_path)))
    memory.start()
    memory.record_exchange('Newest PC question', 'Newest PC reply')
    older = record('older-mobile', 'Older phone question')
    result = memory.sync_companion([older])
    assert result['history'][0]['content'] == 'Older phone question'
    assert result['history'][-1]['content'] == 'Newest PC reply'
