"""Input delivery, foreground identity and application effects are distinct."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from skills import action_verification, ground_truth, system_control


WINDOW = {'address': '0x123', 'pid': 42, 'class': 'editor'}


@pytest.fixture
def boundary(monkeypatch):
    before = AsyncMock(return_value={'verified': True, 'window': WINDOW, 'healed': False})
    after = AsyncMock(return_value=dict(WINDOW))
    monkeypatch.setattr(ground_truth, 'prepare_action_target', before)
    monkeypatch.setattr(system_control, '_query_active_window', after)
    return SimpleNamespace(_gui_control=lambda: object()), before, after


@pytest.mark.asyncio
@pytest.mark.parametrize('adapter', sorted(action_verification.VERIFIED_ADAPTERS - {'window.manage'}))
async def test_same_foreground_never_proves_input_effect(boundary, adapter):
    owner, _, _ = boundary
    dispatch = AsyncMock(return_value={'status': 'success'})

    result = await action_verification.verify_adapter_action(owner, adapter, {}, dispatch)

    assert result['status'] == 'unverified_effect'
    assert result['verified'] is False
    assert result['pre_action_verified'] and result['post_action_focus_verified']
    dispatch.assert_awaited_once_with()


@pytest.mark.asyncio
@pytest.mark.parametrize('response', [
    {'status': 'success', 'verified': False},
    {'status': 'success', 'verified': True, 'target_verified': True},
    {'status': 'effect_observed'},
    {'status': 'effect_observed', 'verified': False},
])
async def test_delivery_or_status_label_cannot_be_promoted_to_verified_effect(boundary, response):
    owner, _, _ = boundary
    result = await action_verification.verify_adapter_action(
        owner, 'input.type', {}, AsyncMock(return_value=response))
    assert result['status'] == 'unverified_effect'
    assert result['verified'] is False


@pytest.mark.asyncio
async def test_explicit_effect_observation_is_preserved(boundary):
    owner, _, _ = boundary
    result = await action_verification.verify_adapter_action(owner, 'gui.type_at', {},
        AsyncMock(return_value={'status': 'effect_observed', 'verified': True}))
    assert result['status'] == 'effect_observed' and result['verified'] is True


@pytest.mark.asyncio
async def test_same_address_with_different_pid_cannot_verify_input(boundary):
    owner, _, after = boundary
    after.return_value = {**WINDOW, 'pid': 99}
    result = await action_verification.verify_adapter_action(owner, 'input.key', {},
        AsyncMock(return_value={'status': 'effect_observed', 'verified': True}))
    assert result['status'] == 'unverified_effect'
    assert not result['verified'] and not result['post_action_focus_verified']


@pytest.mark.asyncio
async def test_unknown_target_blocks_dispatch(boundary):
    owner, before, after = boundary
    before.return_value = {'verified': False, 'reason': 'foreground identity unavailable'}
    dispatch = AsyncMock()
    result = await action_verification.verify_adapter_action(owner, 'input.type', {}, dispatch)
    assert result['status'] == 'blocked' and not result['dispatched']
    dispatch.assert_not_awaited()
    after.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ['close', 'minimize'])
async def test_verified_window_outcome_does_not_require_target_to_remain_focused(boundary, action):
    owner, _, after = boundary
    result = await action_verification.verify_adapter_action(owner, 'window.manage', {'action': action},
        AsyncMock(return_value={'status': 'success', 'verified': True, 'action': action}))
    assert result['verified'] and result['post_action_verified']
    after.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_failure_releases_bound_target(boundary):
    owner, _, _ = boundary
    with pytest.raises(OSError, match='input helper failed'):
        await action_verification.verify_adapter_action(owner, 'input.type', {},
            AsyncMock(side_effect=OSError('input helper failed')))
    assert ground_truth.ACTION_TARGET.get() is None


@pytest.mark.asyncio
@pytest.mark.parametrize('text', ['hello', 'first line\nsecond line'])
async def test_failed_return_after_typing_is_partial_failure(text):
    process = SimpleNamespace(returncode=0, communicate=AsyncMock(return_value=(None, None)))

    async def command(*args, **_kwargs):
        return (1, '', 'failed') if args[-1] == 'Return' else (0, '', '')

    with patch.object(system_control.shutil, 'which', side_effect=lambda name: '/bin/' + name), \
            patch.object(system_control, '_query_active_window', return_value=WINDOW), \
            patch.object(ground_truth, 'ensure_dispatch_focus', return_value=(True, 'focused')), \
            patch.object(system_control, '_run_command', new=AsyncMock(side_effect=command)) as run, \
            patch('asyncio.create_subprocess_exec', new=AsyncMock(return_value=process)):
        result = await system_control.type_text(text, press_enter=True)

    assert result['status'] == 'error'
    assert result['verified'] is False and result['partial'] is True
    assert sum(call.args[-1] == 'Return' for call in run.await_args_list) == 1


@pytest.mark.asyncio
async def test_failed_clipboard_copy_never_pastes_old_clipboard():
    process = SimpleNamespace(returncode=1, communicate=AsyncMock(return_value=(None, None)))
    with patch.object(system_control.shutil, 'which', side_effect=lambda name: '/bin/' + name), \
            patch.object(ground_truth, 'ensure_dispatch_focus', return_value=(True, 'focused')), \
            patch.object(system_control, '_query_active_window', return_value=WINDOW), \
            patch.object(system_control, '_run_command', new=AsyncMock(return_value=(0, '', ''))) as run, \
            patch('asyncio.create_subprocess_exec', new=AsyncMock(return_value=process)):
        result = await system_control.type_text('first line\nsecond line', press_enter=True)

    assert result['status'] == 'error' and result['dispatched'] is False
    run.assert_not_awaited()
