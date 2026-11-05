from types import SimpleNamespace as NS

import pytest

from voice_layer.progress import ProgressUpdates, announce_progress


@pytest.fixture(autouse=True)
def fake_snapshot_worker(monkeypatch):
    async def immediate(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr('voice_layer.progress.asyncio.to_thread', immediate)


def event(*, revision=1, generation=1, state='running', progress=None, terminal=False, **extra):
    return {
        'schema_version': 1, 'stream_id': 'a' * 32, 'sequence': revision,
        'task_id': 'file_task:one', 'widget_id': 'jtask_' + 'b' * 24, 'source': 'file_task',
        'revision': revision, 'generation': generation, 'state': state,
        'terminal': terminal, 'progress': progress, 'title': 'untrusted title', 'message': 'ignored prose',
        'evidence': {'verified': state == 'completed',
                     'scope': 'file_step_checks' if state == 'completed' else 'none'},
        'updated_at': '2026-11-04T00:00:00+00:00', **extra,
    }


def test_progress_is_measured_coalesced_and_stale_revisions_are_ignored():
    updates = ProgressUpdates()
    updates.observe([event()])
    assert updates.peek() == 'Background work is underway.'
    updates.observe([event()])
    assert updates.peek() == 'Background work is underway.'
    updates.observe([event(revision=2, progress={'completed': 2, 'total': 5})])
    updates.observe([event(revision=1, progress={'completed': 1, 'total': 5})])
    assert updates.peek() == 'Background work has completed 2 of 5 measured steps.'
    updates.acknowledge()
    assert updates.peek() is None


def test_waiting_confirmation_and_terminal_state_replace_or_clear_pending_progress():
    updates = ProgressUpdates()
    updates.observe([event()])
    updates.observe([event(revision=2, state='waiting_confirmation')])
    assert updates.peek() == 'Background work is waiting for your confirmation.'
    updates.observe([event(revision=3, state='completed', terminal=True)])
    assert updates.peek() is None


def test_disappeared_snapshot_drops_pending_progress():
    updates = ProgressUpdates()
    updates.observe([event()])
    assert updates.peek() == 'Background work is underway.'
    updates.observe([])
    assert updates.peek() is None


def test_new_generation_and_stream_are_fresh_but_malformed_events_are_skipped():
    updates = ProgressUpdates()
    updates.observe([event(), event(revision=2, state='running', progress={'completed': '3', 'total': 4})])
    assert updates.peek() == 'Background work is underway.'
    updates.acknowledge()
    updates.observe([event(generation=2, revision=1, state='waiting_confirmation')])
    assert updates.peek() == 'Background work is waiting for your confirmation.'
    updates.acknowledge()
    replacement = dict(event(state='waiting_confirmation'), stream_id='b' * 32)
    updates.observe([replacement])
    assert updates.peek() == 'Background work is waiting for your confirmation.'


def test_delivery_cooldown_is_global_and_starts_only_after_delivery():
    updates = ProgressUpdates()
    updates.observe([event()])
    assert updates.ready(now=0)
    updates.acknowledge(now=10)
    assert not updates.ready(now=29.99)
    assert updates.ready(now=30)


class Store:
    def __init__(self, snapshots):
        self.current = snapshots

    def snapshots(self):
        return self.current

    def lookup(self, task_id):
        return next((item for item in self.current if item['task_id'] == task_id), None)


class Voice:
    def __init__(self):
        self.connected = True
        self.muted = self.standby_active = False
        self.standby = NS(engaged=False)
        self.gate = NS(active=False)
        self.player = NS(is_playing=lambda *_: False)
        self._waiting = self._reply_authorized = self._model_active = False
        self._tools_in_flight = 0
        self._drop_response = self._barge_pending = self._background_active = False
        self.spoken = []

    async def announce_background(self, text, *, task_event=None):
        self.spoken.append(text)
        return True


@pytest.mark.asyncio
async def test_background_monitor_speaks_task_facts_only_when_idle_and_connected(monkeypatch):
    from voice_layer.background import monitor

    voice = Voice()
    desktop = NS(_task_presentation=NS(store=Store([event()])))
    control = NS(desktop=desktop, config=NS(notify=False))

    async def no_events():
        return []

    async def no_ack(_):
        return None

    control.background_events = no_events
    control.acknowledge_event = no_ack
    ticks = 0

    async def tick(_):
        nonlocal ticks
        ticks += 1
        if ticks > 1:
            raise asyncio.CancelledError

    import asyncio
    monkeypatch.setattr('voice_layer.background.asyncio.sleep', tick)
    with pytest.raises(asyncio.CancelledError):
        await monitor(voice, control, interval=2)
    assert voice.spoken == ['Background work is underway.']


@pytest.mark.asyncio
@pytest.mark.parametrize('blocked', ['muted', 'standby', 'speaking', 'wake_pending', 'wake_active', 'greeting'])
async def test_background_progress_respects_privacy_and_speech_state(blocked):
    voice = Voice()
    if blocked == 'muted':
        voice.muted = True
    elif blocked == 'standby':
        voice.standby.engaged = True
    else:
        attr = {'speaking': None, 'wake_pending': '_wake_confirmation_pending',
                'wake_active': '_wake_confirmation_in_flight', 'greeting': '_greeting_active'}[blocked]
        if attr is None:
            voice.gate.active = True
        else:
            setattr(voice, attr, True)
    control = NS(desktop=NS(_task_presentation=NS(store=Store([event()]))))
    assert not await announce_progress(voice, control, ProgressUpdates())
    assert not voice.spoken


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['completed', 'revision', 'revision_only', 'generation', 'stream', 'removed', 'muted', 'unchanged'])
async def test_progress_revalidates_selected_task_after_waiting_for_send_lock(change):
    import asyncio
    from unittest.mock import AsyncMock
    from voice_layer.daemon import LiveVoice
    from voice_layer.playback import Playback

    store = Store([event()])
    desktop = NS(_task_presentation=NS(store=store))
    control = NS(desktop=desktop)
    voice = LiveVoice(Playback('test'), skills=control)
    voice.connected = True
    voice._session = NS(send_client_content=AsyncMock())
    updates = ProgressUpdates()
    await voice.send_lock.acquire()
    worker = asyncio.create_task(announce_progress(voice, control, updates))
    try:
        async with asyncio.timeout(1):
            while updates.peek() is None:
                await asyncio.sleep(0)
        if change == 'completed':
            store.current = [event(state='completed', terminal=True, revision=2)]
        elif change == 'revision':
            store.current = [event(revision=2, progress={'completed': 2, 'total': 5})]
        elif change == 'revision_only':
            store.current = [event(revision=2, message='A different UI detail')]
        elif change == 'generation':
            store.current = [event(generation=2)]
        elif change == 'stream':
            store.current = [event(stream_id='b' * 32)]
        elif change == 'removed':
            store.current = []
        elif change == 'muted':
            voice.muted = True
        voice.send_lock.release()
        delivered = await asyncio.wait_for(worker, 1)
        assert delivered is (change == 'unchanged')
        assert voice._session.send_client_content.await_count == int(change == 'unchanged')
        if change != 'unchanged':
            assert not voice._reply_authorized
            assert updates.last_delivered_at is None
        if change == 'revision_only':
            assert await announce_progress(voice, control, updates)
            assert updates.last_delivered_at is not None
    finally:
        if voice.send_lock.locked():
            voice.send_lock.release()
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
