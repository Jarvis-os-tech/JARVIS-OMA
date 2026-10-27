"""Exact focus and bounded surface evidence at the adapter boundary."""
import asyncio
import time
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from skills import ground_truth, system_control
from skills.action_verification import verify_adapter_action
from skills.gui_control import GuiControl


TARGET = {'address': '0x123', 'pid': 44, 'class': 'editor', 'title': 'Document'}
OTHER = {'address': '0x456', 'pid': 55, 'class': 'editor', 'title': 'Other document'}


class ActionBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_unavailable_focus_blocks_input_before_dispatch(self):
        dispatch = AsyncMock(return_value={'status': 'success'})
        with patch.object(system_control, '_query_active_window', return_value=None):
            result = await verify_adapter_action(NS(), 'input.type', {'text': 'hello'}, dispatch)
        self.assertEqual(result['status'], 'blocked')
        self.assertFalse(result['dispatched'])
        dispatch.assert_not_awaited()

    async def test_same_class_wrong_window_is_healed_once_and_rechecked(self):
        dispatch = AsyncMock(return_value={'status': 'success'})
        with patch.object(system_control, '_focus_window_target', return_value=(True, 'verified_active', TARGET)), \
             patch.object(system_control, '_query_active_window', side_effect=[OTHER, OTHER, TARGET, TARGET]), \
             patch('skills.modal_healing.heal_window_focus', return_value={'recovered': True}) as heal:
            result = await verify_adapter_action(NS(), 'input.type',
                                                {'target_window': 'editor', 'text': 'hello'}, dispatch)
        heal.assert_awaited_once_with('0x123')
        dispatch.assert_awaited_once()
        self.assertTrue(result['pre_action_verified'])
        self.assertTrue(result['focus_healed'])
        self.assertFalse(result['verified'])
        self.assertEqual(result['status'], 'unverified_effect')
        self.assertIsNone(ground_truth.ACTION_TARGET.get())

    async def test_healing_ack_without_exact_readback_never_dispatches(self):
        dispatch = AsyncMock()
        with patch.object(system_control, '_focus_window_target', return_value=(True, 'verified_active', TARGET)), \
             patch.object(system_control, '_query_active_window', return_value=OTHER), \
             patch('skills.modal_healing.heal_window_focus', return_value={'recovered': True}) as heal:
            result = await verify_adapter_action(NS(), 'input.key', {'target_window': 'editor', 'key': 'Return'}, dispatch)
        self.assertEqual(result['status'], 'blocked')
        heal.assert_awaited_once()
        dispatch.assert_not_awaited()

    async def test_authentication_prompt_blocks_even_focus_healing(self):
        auth = {'address': '0xabc', 'pid': 99, 'class': 'pinentry', 'title': 'Enter password'}
        dispatch = AsyncMock()
        with patch.object(system_control, '_query_active_window', return_value=auth), \
             patch.object(system_control, '_focus_window_target') as focus, \
             patch('skills.modal_healing.heal_window_focus') as heal:
            result = await verify_adapter_action(NS(), 'input.type', {'target_window': 'editor'}, dispatch)
        self.assertEqual(result['status'], 'blocked')
        focus.assert_not_awaited()
        heal.assert_not_awaited()
        dispatch.assert_not_awaited()

    async def test_second_focus_theft_does_not_trigger_another_retry(self):
        calls = []

        async def dispatch():
            permitted, reason = await ground_truth.ensure_dispatch_focus()
            if permitted:
                calls.append('typed')
            return {'status': 'blocked' if not permitted else 'success', 'reason': reason}

        with patch.object(system_control, '_focus_window_target', return_value=(True, 'verified_active', TARGET)), \
             patch.object(system_control, '_query_active_window', side_effect=[OTHER, OTHER, TARGET, OTHER]), \
             patch('skills.modal_healing.heal_window_focus', return_value={'recovered': True}) as heal:
            result = await verify_adapter_action(NS(), 'input.type', {'target_window': 'editor'}, dispatch)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(calls, [])
        heal.assert_awaited_once()

    async def test_post_focus_theft_is_not_silently_retried(self):
        dispatch = AsyncMock(return_value={'status': 'success', 'length': 5})
        with patch.object(system_control, '_query_active_window', side_effect=[TARGET, TARGET, OTHER]):
            result = await verify_adapter_action(NS(), 'input.type', {'text': 'hello'}, dispatch)
        dispatch.assert_awaited_once()
        self.assertEqual(result['status'], 'unverified_effect')
        self.assertFalse(result['post_action_focus_verified'])

    async def test_window_mutation_rejects_target_change_before_dispatch(self):
        async def compositor(*args, **kwargs):
            if 'activewindow' in args:
                import json
                return 0, json.dumps(OTHER), ''
            raise AssertionError('No mutation should be dispatched')

        token = ground_truth.ACTION_TARGET.set({'verified': True, 'window': TARGET, 'healed': False})
        try:
            with patch.object(system_control.shutil, 'which', return_value='/usr/bin/hyprctl'), \
                 patch.object(system_control, '_run_command', side_effect=compositor):
                result = await system_control.manage_window('float')
        finally:
            ground_truth.ACTION_TARGET.reset(token)
        self.assertFalse(result['verified'])
        self.assertNotEqual(result['status'], 'success')

    async def test_post_focus_check_detects_address_reuse(self):
        self.assertFalse(ground_truth.same_window(TARGET, {**TARGET, 'pid': 999}))
        self.assertFalse(ground_truth.same_window(TARGET, {'class': 'editor', 'pid': 44}))

    async def test_named_focus_never_accepts_another_window_of_same_class(self):
        with patch.object(system_control.shutil, 'which', return_value='/usr/bin/hyprctl'), \
             patch.object(system_control, '_query_open_windows', return_value=[TARGET, OTHER]), \
             patch.object(system_control, '_query_active_window', return_value=OTHER), \
             patch.object(system_control, '_run_command', return_value=(0, '', '')), \
             patch('skills.modal_healing.heal_window_focus', return_value={'recovered': True}) as heal:
            focused, _, _ = await system_control._focus_window_target('0x123')
        self.assertFalse(focused)
        heal.assert_awaited_once_with('0x123')


class SurfaceEvidenceTests(unittest.IsolatedAsyncioTestCase):
    def control(self, changes):
        control = GuiControl('/unused/cua-driver')
        control._desktop = (time.monotonic(), 1920, 1080)
        control._verify_action_point = AsyncMock(return_value={
            'window_pid': 44, 'window_id': 11, 'bounds_verified': True, 'focus_verified': True})
        self.actions = []
        observations = 0

        async def call(name, arguments, timeout=20):
            nonlocal observations
            if name == 'get_window_state':
                observations += 1
                return {'snapshot_id': str(observations), 'elements': [
                    {'role': 'text', 'label': 'after' if changes and observations > 1 else 'before',
                     'element_token': str(observations)}]}
            self.actions.append(name)
            return {'effect': 'success'}  # A driver assertion is not evidence.

        control._call = call
        return control

    async def test_unchanged_click_has_explicit_fallback_within_deadline(self):
        control = self.control(False)
        started = time.monotonic()
        result = await control.click_desktop(10, 10)
        self.assertLess(time.monotonic() - started, .45)
        self.assertEqual(result['status'], 'unverified_effect')
        self.assertEqual(result['fallback'], 'use_accessibility_or_cli')
        self.assertFalse(result['verified'])
        self.assertEqual(self.actions, ['click'])

    async def test_unchanged_scroll_has_explicit_fallback_and_is_not_replayed(self):
        control = self.control(False)
        result = await control.scroll_desktop('down', 10, 10, 3)
        self.assertEqual(result['status'], 'unverified_effect')
        self.assertEqual(self.actions, ['scroll'])

    async def test_changed_accessibility_tree_reports_only_observed_effect(self):
        control = self.control(True)
        result = await control.click_desktop(10, 10)
        self.assertEqual(result['status'], 'effect_observed')
        self.assertTrue(result['effect_verified'])
        self.assertFalse(result['verified'])
        self.assertEqual(result['verification_scope'], 'accessibility_tree_change_only')

    def test_fingerprint_ignores_ephemeral_tokens_and_never_trusts_degraded_state(self):
        first = {'snapshot_id': '1', 'elements': [{'role': 'button', 'label': 'Save', 'element_token': 'one'}]}
        second = {'snapshot_id': '2', 'elements': [{'role': 'button', 'label': 'Save', 'element_token': 'two'}]}
        self.assertEqual(ground_truth.accessibility_fingerprint(first), ground_truth.accessibility_fingerprint(second))
        self.assertIsNone(ground_truth.accessibility_fingerprint({**first, 'degraded': True}))
        self.assertIsNone(ground_truth.accessibility_fingerprint({'elements': [{'element_token': 'token'}]}))

    async def test_stalled_accessibility_probe_has_bounded_latency_and_owned_cleanup(self):
        control = self.control(False)
        stopped = asyncio.Event()

        async def call(name, arguments, timeout=20):
            if name != 'get_window_state':
                self.actions.append(name)
                return {'effect': 'success'}
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                try:
                    await asyncio.sleep(.1)  # A child's output pipe takes time to close.
                finally:
                    stopped.set()
                raise

        control._call = call
        started = time.monotonic()
        result = await control.click_desktop(10, 10)
        self.assertLess(time.monotonic() - started, .3)
        self.assertEqual(result['status'], 'unverified_effect')
        self.assertEqual(self.actions, ['click'])
        self.assertTrue(control._observation_tasks)
        await control.close()
        self.assertTrue(stopped.is_set())
        self.assertFalse(control._observation_tasks)
