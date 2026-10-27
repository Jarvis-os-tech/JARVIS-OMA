"""Tests for bounded GUI observations and pointer actions."""
import time
import unittest
from unittest.mock import AsyncMock

from skills.gui_control import GuiControl, GuiControlError
from skills.skills import DesktopSkills


class GuiControlTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_driver_is_reported_as_gui_control_error(self):
        control = GuiControl('/definitely/missing/cua-driver')
        with self.assertRaisesRegex(GuiControlError, 'No such file'):
            await control._invoke('list_windows', {})

    async def test_manifest_exposes_gui_tools(self):
        names = {item['name'] for item in DesktopSkills().declarations}
        self.assertTrue({'gui_list_windows', 'gui_inspect_window', 'gui_click_element',
                         'gui_observe_desktop', 'gui_click_desktop', 'gui_type_at',
                         'gui_key_at', 'gui_browser_bind', 'gui_browser_snapshot',
                         'gui_browser_click', 'gui_browser_type',
                         'gui_browser_navigate', 'gui_browser_double_click',
                         'gui_verify_window'} <= names)

    async def test_degraded_window_cannot_click(self):
        control = GuiControl('/usr/bin/cua-driver')
        control._call = AsyncMock(return_value={
            'snapshot_id': 's12345678', 'degraded': True, 'elements_complete': False,
            'elements': [{'element_token': 'token'}],
        })
        result = await control.inspect_window(123, 456)
        self.assertFalse(result['element_click_available'])
        with self.assertRaises(GuiControlError):
            await control.click_element(123, 456, 'token')

    async def test_element_click_requires_current_exact_token(self):
        control = GuiControl('/usr/bin/cua-driver')
        control._call = AsyncMock(side_effect=[
            {'snapshot_id': 's12345678', 'elements_complete': False,
             'elements': [{'element_token': 'token'}]},
            {'elements': [{'role': 'button', 'label': 'Run'}]},
            {'ok': True},
            {'elements': [{'role': 'button', 'label': 'Done'}]},
        ])
        result = await control.inspect_window(123, 456)
        self.assertTrue(result['element_click_available'])
        with self.assertRaises(GuiControlError):
            await control.click_element(123, 456, 'other')
        await control.click_element(123, 456, 'token')
        with self.assertRaises(GuiControlError):
            await control.click_element(123, 456, 'token')

    async def test_desktop_click_requires_fresh_in_bounds_observation(self):
        control = GuiControl('/usr/bin/cua-driver')
        control._call = AsyncMock(return_value={'ok': True})
        with self.assertRaises(GuiControlError):
            await control.click_desktop(10, 10)
        control._desktop = (time.monotonic() - 16, 1920, 1080)
        with self.assertRaises(GuiControlError):
            await control.click_desktop(10, 10)
        control._desktop = (time.monotonic(), 1920, 1080)
        with self.assertRaises(GuiControlError):
            await control.click_desktop(1920, 10)
        self.assertEqual((await control.click_desktop(10, 10))['status'], 'unverified_effect')
        self.assertIsNone(control._desktop)

    async def test_type_and_key_use_recent_visual_target(self):
        control = GuiControl('/usr/bin/cua-driver')
        control._call = AsyncMock(return_value={'route': 'global_input'})
        control._desktop = (time.monotonic(), 1920, 1080)
        await control.type_at(10, 20, 'hello')
        self.assertEqual(control._call.await_args.args[0], 'type_text')
        self.assertEqual(control._call.await_args.args[1]['text'], 'hello')
        with self.assertRaises(GuiControlError):
            await control.press_key_at(10, 20, 'Return')
        control._desktop = (time.monotonic(), 1920, 1080)
        await control.press_key_at(10, 20, 'a', ['ctrl'])
        self.assertEqual(control._call.await_args.args[0], 'hotkey')
        self.assertEqual(control._call.await_args.args[1]['keys'], ['ctrl', 'a'])

    async def test_browser_click_retries_explicit_dom_route(self):
        control = GuiControl('/usr/bin/cua-driver')
        control._browser_tabs['target'] = {'tab'}
        control._call = AsyncMock(side_effect=[
            {'effect': 'refused'}, {'effect': 'unverifiable', 'route': 'dom'},
        ])
        result = await control.browser_click('target', 'tab', 'p1:1')
        self.assertEqual(result['status'], 'dispatched')
        self.assertEqual(control._call.await_args.args[1]['input_route'], 'dom_event')

    async def test_isolated_browser_skips_refused_trusted_route(self):
        control = GuiControl('/usr/bin/cua-driver')
        control._browser_tabs['target'] = {'tab'}
        control._browser_routes['target'] = 'dom_event'
        control._call = AsyncMock(return_value={'effect': 'unverifiable', 'route': 'dom'})
        result = await control.browser_click('target', 'tab', 'p1:1')
        self.assertEqual(result['status'], 'dispatched')
        control._call.assert_awaited_once()
        self.assertEqual(control._call.await_args.args[1]['input_route'], 'dom_event')

    async def test_browser_rejects_unbound_tab_and_unsafe_navigation(self):
        control = GuiControl('/usr/bin/cua-driver')
        with self.assertRaises(GuiControlError):
            await control.browser_snapshot('target', 'tab')
        control._browser_tabs['target'] = {'tab'}
        with self.assertRaises(GuiControlError):
            await control.browser_navigate('target', 'tab', 'file:///etc/passwd')

    async def test_browser_double_click_uses_verified_route(self):
        control = GuiControl('/usr/bin/cua-driver')
        control._browser_tabs['target'] = {'tab'}
        control._browser_routes['target'] = 'dom_event'
        control._call = AsyncMock(return_value={'effect': 'unverifiable', 'route': 'dom'})
        result = await control.browser_double_click('target', 'tab', 'p1:1')
        self.assertEqual(result['status'], 'dispatched')
        self.assertEqual(control._call.await_args.args[1]['input_route'], 'dom_event')
        self.assertEqual(control._call.await_args.args[1]['action'], 'double_click')

    async def test_ended_driver_session_is_revived_once(self):
        control = GuiControl('/usr/bin/cua-driver')
        control._invoke = AsyncMock(side_effect=[
            GuiControlError(f"session '{control.session}' has ended"),
            {'active': True}, {'windows': []},
        ])
        result = await control._call('list_windows', {})
        self.assertEqual(result, {'windows': []})
        self.assertEqual(control._invoke.await_args_list[1].args[0], 'start_session')

    async def test_driver_rechecks_after_another_call_starts_it(self):
        control = GuiControl('/usr/bin/cua-driver')
        control._invoke = AsyncMock(side_effect=[
            GuiControlError('Cua Driver daemon is not running'), {'windows': []},
        ])
        self.assertEqual(await control._call('list_windows', {}), {'windows': []})
        self.assertEqual(control._invoke.await_count, 2)

    async def test_browser_connection_error_does_not_restart_daemon(self):
        control = GuiControl('/usr/bin/cua-driver')
        control._invoke = AsyncMock(side_effect=GuiControlError('Cannot connect to browser'))
        with self.assertRaisesRegex(GuiControlError, 'Cannot connect to browser'):
            await control._call('get_browser_state', {})
        control._invoke.assert_awaited_once()

    async def test_verify_window_uses_bounded_exact_predicate(self):
        control = GuiControl('/usr/bin/cua-driver')
        control._call = AsyncMock(return_value={'status': 'satisfied'})
        result = await control.verify_window(123, 456, 'button', 'Save')
        self.assertEqual(result['status'], 'satisfied')
        args = control._call.await_args.args[1]
        self.assertEqual(args['expect'], [{'element': {
            'selector': {'role': 'button', 'label_contains': 'Save'}, 'exists': True}}])

    async def test_pre_action_verification_within_window_bounds(self):
        control = GuiControl('/usr/bin/cua-driver')
        control._desktop = (time.monotonic(), 1920, 1080)
        control.list_windows = AsyncMock(return_value={'windows': [
            {'window_id': 100, 'address': '0x64', 'pid': 555,
             'bounds': {'x': 100, 'y': 100, 'width': 600, 'height': 400},
             'is_on_screen': True}
        ]})
        control._call = AsyncMock(return_value={
            'ok': True, 'target_verified': True, 'target_address': '0x64',
        })
        
        # In-bounds click
        result = await control.click_desktop(250, 250, target_window_id=100)
        self.assertEqual(result['status'], 'unverified_effect')
        self.assertTrue(result['target_verified'])
        self.assertTrue(result['bounds_verified'])
        self.assertFalse(result['focus_verified'])

        # Out-of-bounds click
        control._desktop = (time.monotonic(), 1920, 1080)
        with self.assertRaisesRegex(GuiControlError, 'outside the bounds of target window 100'):
            await control.click_desktop(800, 250, target_window_id=100)

    async def test_pre_action_verification_rejects_missing_or_offscreen_window(self):
        control = GuiControl('/usr/bin/cua-driver')
        control._desktop = (time.monotonic(), 1920, 1080)
        control.list_windows = AsyncMock(return_value={'windows': [
            {'window_id': 100, 'pid': 555, 'bounds': {'x': 100, 'y': 100, 'width': 600, 'height': 400}, 'is_on_screen': False}
        ]})

        # Offscreen window rejected
        with self.assertRaisesRegex(GuiControlError, 'not visible or on screen'):
            await control.click_desktop(250, 250, target_window_id=100)

        # Missing window rejected
        control._desktop = (time.monotonic(), 1920, 1080)
        with self.assertRaisesRegex(GuiControlError, 'not found in window list'):
            await control.click_desktop(250, 250, target_window_id=999)

    async def test_pre_action_verification_verifies_active_window(self):
        control = GuiControl('/usr/bin/cua-driver')
        control._desktop = (time.monotonic(), 1920, 1080)
        control.list_windows = AsyncMock(return_value={'windows': [
            {'window_id': 100, 'address': '0x64', 'pid': 555,
             'bounds': {'x': 100, 'y': 100, 'width': 600, 'height': 400},
             'is_on_screen': True}
        ]})
        control._call = AsyncMock(return_value={
            'ok': True, 'target_verified': True, 'target_address': '0x64',
        })

        # Active window matches by exact Hyprland window identity.
        control._query_active_window = AsyncMock(return_value={
            'pid': 555, 'address': '0x64', 'class': 'test-app',
        })
        result = await control.click_desktop(250, 250, target_window_id=100, verify_active=True)
        self.assertEqual(result['status'], 'unverified_effect')
        self.assertTrue(result['target_verified'])
        self.assertTrue(result['bounds_verified'])
        self.assertTrue(result['focus_verified'])

        # A different window from the same process is still the wrong target.
        control._desktop = (time.monotonic(), 1920, 1080)
        control._query_active_window = AsyncMock(return_value={
            'pid': 555, 'address': '0xc8', 'class': 'test-app',
        })
        with self.assertRaisesRegex(GuiControlError, 'not the active window'):
            await control.click_desktop(250, 250, target_window_id=100, verify_active=True)

    async def test_active_verification_requires_exact_target_and_positive_evidence(self):
        control = GuiControl('/usr/bin/cua-driver')
        control._call = AsyncMock(return_value={'ok': True})

        control._desktop = (time.monotonic(), 1920, 1080)
        with self.assertRaisesRegex(GuiControlError, 'target_window_id'):
            await control.click_desktop(250, 250, verify_active=True)

        control.list_windows = AsyncMock(return_value={'windows': [
            {'window_id': 100, 'address': '0x64', 'pid': 555,
             'bounds': {'x': 100, 'y': 100, 'width': 600, 'height': 400},
             'is_on_screen': True}
        ]})
        for active in (None, {'pid': 555}, {'address': 'not-a-window'}):
            with self.subTest(active=active):
                control._desktop = (time.monotonic(), 1920, 1080)
                control._query_active_window = AsyncMock(return_value=active)
                with self.assertRaisesRegex(GuiControlError, 'could not be verified'):
                    await control.click_desktop(
                        250, 250, target_window_id=100, verify_active=True)

        control._call.assert_not_awaited()

    async def test_active_click_requires_bounds_canonical_addresses_and_atomic_driver_ack(self):
        control = GuiControl('/usr/bin/cua-driver')
        control._query_active_window = AsyncMock(return_value={'address': '0x64'})

        for window in (
            {'window_id': 100, 'address': '0x64', 'is_on_screen': True},
            {'window_id': 100, 'address': 100,
             'bounds': {'x': 0, 'y': 0, 'width': 500, 'height': 500},
             'is_on_screen': True},
        ):
            with self.subTest(window=window):
                control._desktop = (time.monotonic(), 1920, 1080)
                control.list_windows = AsyncMock(return_value={'windows': [window]})
                with self.assertRaises(GuiControlError):
                    await control.click_desktop(100, 100, target_window_id=100,
                                                verify_active=True)

        control.list_windows = AsyncMock(return_value={'windows': [{
            'window_id': 100, 'address': '0x64', 'is_on_screen': True,
            'bounds': {'x': 0, 'y': 0, 'width': 500, 'height': 500},
        }]})
        for reply in (
            {'target_verified': False, 'target_address': '0x64'},
            {'target_verified': True, 'target_address': '0xc8'},
            {},
        ):
            with self.subTest(reply=reply):
                control._desktop = (time.monotonic(), 1920, 1080)
                control._call = AsyncMock(return_value=reply)
                with self.assertRaisesRegex(GuiControlError, 'atomically verify'):
                    await control.click_desktop(100, 100, target_window_id=100,
                                                verify_active=True)
                self.assertEqual(control._call.await_args.args[0], 'click_window')
                payload = control._call.await_args.args[1]
                self.assertEqual(payload['target']['address'], '0x64')
                self.assertTrue(payload['target']['require_active'])


if __name__ == '__main__':
    unittest.main()
