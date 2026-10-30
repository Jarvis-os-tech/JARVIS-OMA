import asyncio
import threading
from unittest.mock import patch

import pytest
from jarvis_memory.config import Config
from jarvis_memory.skills import MemorySkills


@pytest.mark.asyncio
async def test_memory_writes_leave_audio_loop_free_and_keep_order(tmp_path):
    config = Config()
    config.memory.path = str(tmp_path)
    skills = MemorySkills(config)
    entered, release = threading.Event(), threading.Event()
    writes, threads = [], []
    loop_thread = threading.get_ident()
    def record(user_text, assistant_text):
        threads.append(threading.get_ident())
        entered.set()
        assert release.wait(2)
        writes.append(user_text)
    try:
        with patch.object(skills.memory, 'record_exchange', side_effect=record):
            skills.queue_memory_exchange('first', 'reply')
            assert await asyncio.to_thread(entered.wait, 1)
            # We can run this coroutine while storage is still waiting in its worker.
            assert not release.is_set()
            assert threads[0] != loop_thread
            skills.queue_memory_exchange('second', 'reply')
            release.set()
            await skills.close_agent_jobs()
        assert writes == ['first', 'second']
        assert len(set(threads)) == 1
    finally:
        release.set()
        await skills.close_agent_jobs()
