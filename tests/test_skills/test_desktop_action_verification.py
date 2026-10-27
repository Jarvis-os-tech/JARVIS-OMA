"""Desktop actions require exact-target postconditions, not dispatch exit codes."""
import json
import unittest
from unittest.mock import AsyncMock, patch

from skills import system_control


WINDOW = {
    'address': '0x1234', 'pid': 42, 'class': 'example-editor',
    'floating': False, 'fullscreen': 0,
}


class DesktopRuntime:
    """A compositor fixture with independent dispatches and state observations."""

    def __init__(self, **observations):
        self.observations = {name: list(values) for name, values in observations.items()}
        self.dispatches = []
        self.dispatch_results = [(0, 'ok', '')]

    async def run(self, *args, **kwargs):
        if 'dispatch' in args:
            self.dispatches.append(args[args.index('dispatch') + 1:])
            if len(self.dispatch_results) > 1:
                return self.dispatch_results.pop(0)
            return self.dispatch_results[0]
        for name, values in self.observations.items():
            if name in args:
                value = values.pop(0) if len(values) > 1 else values[0]
                return value if isinstance(value, tuple) else (0, json.dumps(value), '')
        raise AssertionError(f'Unexpected compositor query: {args!r}')


class DesktopActionVerificationTests(unittest.IsolatedAsyncioTestCase):
    def runtime(self, **observations):
        runtime = DesktopRuntime(**observations)
        which = patch.object(system_control.shutil, 'which', return_value='/usr/bin/hyprctl')
        run = patch.object(system_control, '_run_command', new=AsyncMock(side_effect=runtime.run))
        which.start()
        run.start()
        self.addCleanup(which.stop)
        self.addCleanup(run.stop)
        return runtime

    def assert_not_verified(self, result):
        self.assertNotEqual(result['status'], 'success')
        self.assertIs(result.get('verified'), False)

    async def test_float_binds_dispatch_and_evidence_to_exact_window(self):
        target = {**WINDOW, 'floating': True}
        unrelated = {**WINDOW, 'address': '0x9999', 'pid': 99, 'floating': True}
        runtime = self.runtime(activewindow=[WINDOW], clients=[[unrelated, target]])

        result = await system_control.manage_window('float')

        self.assertEqual(result['status'], 'success')
        self.assertIs(result['verified'], True)
        self.assertEqual(len(runtime.dispatches), 1)
        self.assertIn('address:0x1234', runtime.dispatches[0][0])
        self.assertIn('float', runtime.dispatches[0][0])

    async def test_same_class_different_address_does_not_prove_float(self):
        unrelated = {**WINDOW, 'address': '0x9999', 'pid': 99, 'floating': True}
        self.runtime(activewindow=[WINDOW], clients=[[WINDOW, unrelated]])

        self.assert_not_verified(await system_control.manage_window('float'))

    async def test_reused_address_with_different_pid_does_not_prove_float(self):
        replacement = {**WINDOW, 'pid': 99, 'floating': True}
        self.runtime(activewindow=[WINDOW], clients=[[replacement]])

        self.assert_not_verified(await system_control.manage_window('float'))

    async def test_missing_window_readback_is_not_success(self):
        self.runtime(activewindow=[WINDOW], clients=[(1, '', 'readback unavailable')])

        self.assert_not_verified(await system_control.manage_window('float'))

    async def test_invalid_window_readback_is_not_success(self):
        self.runtime(activewindow=[WINDOW], clients=[(0, 'not valid JSON', '')])

        self.assert_not_verified(await system_control.manage_window('float'))

    async def test_missing_initial_target_never_dispatches(self):
        runtime = self.runtime(activewindow=[{}])

        self.assert_not_verified(await system_control.manage_window('float'))
        self.assertEqual(runtime.dispatches, [])

    async def test_both_window_dispatches_failing_returns_error(self):
        runtime = self.runtime(activewindow=[WINDOW], clients=[[WINDOW]])
        runtime.dispatch_results = [(1, '', 'Lua unavailable'), (1, '', 'legacy unavailable')]

        result = await system_control.manage_window('float')

        self.assertEqual(result['status'], 'error')
        self.assertIs(result['verified'], False)
        self.assertEqual(len(runtime.dispatches), 2)

    async def test_successful_window_fallback_still_requires_postcondition(self):
        runtime = self.runtime(activewindow=[WINDOW], clients=[[{**WINDOW, 'floating': True}]])
        runtime.dispatch_results = [(1, '', 'Lua unavailable'), (0, 'ok', '')]

        result = await system_control.manage_window('float')

        self.assertEqual(result['status'], 'success')
        self.assertIs(result['verified'], True)
        self.assertEqual(len(runtime.dispatches), 2)
        self.assertIn('address:0x1234', ' '.join(runtime.dispatches[1]))

    async def test_failed_lua_does_not_apply_active_only_fallback_to_new_focus(self):
        other = {**WINDOW, 'address': '0x9999', 'pid': 99}
        runtime = self.runtime(activewindow=[WINDOW, other], clients=[[WINDOW, other]])
        runtime.dispatch_results = [(1, '', 'Lua unavailable'), (0, 'ok', '')]

        self.assert_not_verified(await system_control.manage_window('fullscreen'))
        self.assertEqual(len(runtime.dispatches), 1)

    async def test_numeric_workspace_requires_exact_readback(self):
        runtime = self.runtime(activeworkspace=[{'id': 2}, {'id': 7}])

        result = await system_control.switch_workspace(7)

        self.assertEqual(result['status'], 'success')
        self.assertIs(result['verified'], True)
        self.assertEqual(result['target_workspace'], 7)
        self.assertIn('"7"', runtime.dispatches[0][0])

    async def test_relative_workspace_resolves_sparse_sorted_ids_before_dispatch(self):
        runtime = self.runtime(
            activeworkspace=[{'id': 2}, {'id': 4}],
            workspaces=[[{'id': 7}, {'id': 2}, {'id': -99}, {'id': 4}]],
        )

        result = await system_control.switch_workspace('next')

        self.assertEqual(result['status'], 'success')
        self.assertIs(result['verified'], True)
        self.assertEqual(result['target_workspace'], 4)
        self.assertIn('"4"', runtime.dispatches[0][0])
        self.assertNotIn('e+1', ' '.join(runtime.dispatches[0]))

    async def test_relative_workspace_wraps_and_resolves_previous(self):
        runtime = self.runtime(
            activeworkspace=[{'id': 2}, {'id': 7}],
            workspaces=[[{'id': 7}, {'id': 2}, {'id': 4}]],
        )

        result = await system_control.switch_workspace('previous')

        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['target_workspace'], 7)
        self.assertIn('"7"', runtime.dispatches[0][0])

    async def test_workspace_dispatch_success_with_wrong_target_is_not_success(self):
        self.runtime(activeworkspace=[{'id': 2}, {'id': 3}])

        self.assert_not_verified(await system_control.switch_workspace(7))

    async def test_workspace_readback_unavailable_is_not_success(self):
        self.runtime(activeworkspace=[{'id': 2}, (1, '', 'readback unavailable')])

        self.assert_not_verified(await system_control.switch_workspace(7))

    async def test_both_workspace_dispatches_failing_returns_error(self):
        runtime = self.runtime(activeworkspace=[{'id': 2}])
        runtime.dispatch_results = [(1, '', 'Lua unavailable'), (1, '', 'legacy unavailable')]

        result = await system_control.switch_workspace(7)

        self.assertEqual(result['status'], 'error')
        self.assertIs(result['verified'], False)
        self.assertEqual(len(runtime.dispatches), 2)

    async def test_workspace_fallback_verifies_resolved_numeric_target(self):
        runtime = self.runtime(activeworkspace=[{'id': 2}, {'id': 7}])
        runtime.dispatch_results = [(1, '', 'Lua unavailable'), (0, 'ok', '')]

        result = await system_control.switch_workspace(7)

        self.assertEqual(result['status'], 'success')
        self.assertIs(result['verified'], True)
        self.assertEqual(runtime.dispatches[1], ('workspace', '7'))

    async def test_invalid_workspace_never_dispatches(self):
        runtime = self.runtime(activeworkspace=[{'id': 2}])
        for invalid in (True, False, 0, 11, 'not-a-workspace'):
            with self.subTest(workspace=invalid):
                self.assert_not_verified(await system_control.switch_workspace(invalid))
        self.assertEqual(runtime.dispatches, [])

    async def test_fullscreen_and_maximize_verify_requested_mode_and_toggle_back(self):
        for action, before_mode, after_mode in (
            ('fullscreen', 0, 2), ('fullscreen', 2, 0),
            ('maximize', 0, 1), ('maximize', 1, 0),
        ):
            with self.subTest(action=action, before=before_mode):
                before = {**WINDOW, 'fullscreen': before_mode}
                after = {**WINDOW, 'fullscreen': after_mode}
                runtime = self.runtime(activewindow=[before], clients=[[after]])

                result = await system_control.manage_window(action)

                self.assertEqual(result['status'], 'success')
                self.assertIs(result['verified'], True)
                self.assertEqual(result['expected']['fullscreen'], after_mode)
                self.assertEqual(result['evidence']['address'], WINDOW['address'])
                self.assertTrue(result['evidence']['observed_at'])
                self.assertIn('address:0x1234', runtime.dispatches[0][0])

    async def test_fullscreen_wrong_mode_never_verifies(self):
        self.runtime(activewindow=[WINDOW], clients=[[{**WINDOW, 'fullscreen': 1}]])

        self.assert_not_verified(await system_control.manage_window('fullscreen'))

    async def test_graceful_close_verifies_target_disappears_while_same_class_remains(self):
        other = {**WINDOW, 'address': '0x9999', 'pid': 99, 'mapped': True}
        runtime = self.runtime(activewindow=[WINDOW], clients=[[other]])

        result = await system_control.manage_window('close')

        self.assertEqual(result['status'], 'success')
        self.assertIs(result['verified'], True)
        self.assertIn('address:0x1234', runtime.dispatches[0][0])

    async def test_close_request_still_open_does_not_verify(self):
        self.runtime(activewindow=[WINDOW], clients=[[{**WINDOW, 'mapped': True}]])

        self.assert_not_verified(await system_control.manage_window('close'))

    async def test_minimize_verifies_exact_scratchpad_not_an_arbitrary_special_workspace(self):
        for workspace_name, succeeds in (('special:scratchpad', True), ('special:other', False)):
            with self.subTest(workspace=workspace_name):
                after = {**WINDOW, 'workspace': {'id': -99, 'name': workspace_name}}
                runtime = self.runtime(activewindow=[WINDOW], clients=[[after]])

                result = await system_control.manage_window('minimize')

                if succeeds:
                    self.assertEqual(result['status'], 'success')
                    self.assertIs(result['verified'], True)
                else:
                    self.assert_not_verified(result)
                self.assertIn('address:0x1234', runtime.dispatches[0][0])

    async def test_center_uses_scaled_logical_monitor_geometry(self):
        before = {**WINDOW, 'floating': True, 'monitor': 1}
        monitor = {'id': 1, 'x': 1920, 'y': 0, 'width': 3840, 'height': 2160,
                   'scale': 2, 'transform': 0}
        after = {**before, 'at': [2480, 240], 'size': [800, 600]}
        self.runtime(activewindow=[before], monitors=[[monitor]], clients=[[after]])

        result = await system_control.manage_window('center')

        self.assertEqual(result['status'], 'success')
        self.assertIs(result['verified'], True)

    async def test_center_uses_rotated_monitor_geometry(self):
        before = {**WINDOW, 'floating': True, 'monitor': 1}
        monitor = {'id': 1, 'x': 100, 'y': 200, 'width': 1920, 'height': 1080,
                   'scale': 1.5, 'transform': 1}
        after = {**before, 'at': [260, 690], 'size': [400, 300]}
        self.runtime(activewindow=[before], monitors=[[monitor]], clients=[[after]])

        result = await system_control.manage_window('center')

        self.assertEqual(result['status'], 'success')
        self.assertIs(result['verified'], True)

    async def test_center_wrong_monitor_or_position_never_verifies(self):
        before = {**WINDOW, 'floating': True, 'monitor': 1}
        monitor = {'id': 1, 'x': 0, 'y': 0, 'width': 1920, 'height': 1080,
                   'scale': 1, 'transform': 0}
        for after in (
            {**before, 'monitor': 2, 'at': [560, 240], 'size': [800, 600]},
            {**before, 'at': [0, 0], 'size': [800, 600]},
        ):
            with self.subTest(after=after):
                self.runtime(activewindow=[before], monitors=[[monitor]], clients=[[after]])
                self.assert_not_verified(await system_control.manage_window('center'))

    async def test_center_tiled_window_does_not_dispatch(self):
        runtime = self.runtime(activewindow=[WINDOW])

        self.assert_not_verified(await system_control.manage_window('center'))
        self.assertEqual(runtime.dispatches, [])

    async def test_timed_out_window_dispatch_is_not_replayed_through_fallback(self):
        runtime = self.runtime(activewindow=[WINDOW])
        runtime.dispatch_results = [(-1, '', 'command timed out')]

        result = await system_control.manage_window('float')

        self.assertEqual(result['status'], 'unverified')
        self.assertIs(result['verified'], False)
        self.assertEqual(len(runtime.dispatches), 1)

    async def test_timed_out_workspace_dispatch_is_not_replayed_through_fallback(self):
        runtime = self.runtime(activeworkspace=[{'id': 2}])
        runtime.dispatch_results = [(-1, '', 'command timed out')]

        result = await system_control.switch_workspace(7)

        self.assertEqual(result['status'], 'unverified')
        self.assertIs(result['verified'], False)
        self.assertEqual(len(runtime.dispatches), 1)

    async def test_center_respects_reserved_work_area_after_scale_and_rotation(self):
        before = {**WINDOW, 'floating': True, 'monitor': 1}
        cases = (
            ({'id': 1, 'x': 1920, 'y': 0, 'width': 3840, 'height': 2160,
              'scale': 2, 'transform': 0, 'reserved': [80, 40, 20, 60]},
             {'at': [2510, 230], 'size': [800, 600]}, [2910, 530]),
            ({'id': 1, 'x': 100, 'y': 200, 'width': 1920, 'height': 1080,
              'scale': 1.5, 'transform': 1, 'reserved': [20, 60, 0, 20]},
             {'at': [270, 710], 'size': [400, 300]}, [470, 860]),
        )
        for monitor, geometry, expected_center in cases:
            with self.subTest(monitor=monitor):
                self.runtime(activewindow=[before], monitors=[[monitor]],
                             clients=[[{**before, **geometry}]])

                result = await system_control.manage_window('center')

                self.assertEqual(result['status'], 'success')
                self.assertIs(result['verified'], True)
                self.assertEqual(result['expected']['center'], expected_center)

    async def test_current_workspace_returns_verified_unchanged_without_dispatch(self):
        runtime = self.runtime(activeworkspace=[{'id': 2}])

        result = await system_control.switch_workspace(2)

        self.assertEqual(result['status'], 'success')
        self.assertIs(result['verified'], True)
        self.assertIs(result['unchanged'], True)
        self.assertIs(result['executed'], False)
        self.assertEqual(result['target_workspace'], 2)
        self.assertEqual(runtime.dispatches, [])

    async def test_single_workspace_relative_request_does_not_trigger_back_and_forth(self):
        for direction in ('next', 'previous'):
            with self.subTest(direction=direction):
                runtime = self.runtime(activeworkspace=[{'id': 2}],
                                       workspaces=[[{'id': 2}, {'id': -99}]])

                result = await system_control.switch_workspace(direction)

                self.assertEqual(result['status'], 'success')
                self.assertIs(result['verified'], True)
                self.assertIs(result['unchanged'], True)
                self.assertIs(result['executed'], False)
                self.assertEqual(runtime.dispatches, [])

    async def test_active_only_legacy_fallback_is_declined_even_when_focus_is_unchanged(self):
        before = {**WINDOW, 'floating': True, 'monitor': 1}
        monitor = {'id': 1, 'x': 0, 'y': 0, 'width': 1920, 'height': 1080,
                   'scale': 1, 'transform': 0}
        for action in ('fullscreen', 'maximize', 'center'):
            with self.subTest(action=action):
                runtime = self.runtime(activewindow=[before], monitors=[[monitor]], clients=[[before]])
                runtime.dispatch_results = [(1, '', 'Lua unavailable'), (0, 'ok', '')]

                self.assert_not_verified(await system_control.manage_window(action))
                self.assertEqual(len(runtime.dispatches), 1)
