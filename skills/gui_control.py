"""Bounded Cua Driver bridge for Jarvis's Hyprland desktop.

The driver is optional.  The bridge keeps observations local to this agent and
requires a recent observation before sending pointer input.
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from core.secret_env import sanitized_subprocess_env
from skills import ground_truth


class GuiControlError(ValueError):
    pass


class GuiControl:
    def __init__(self, executable: str):
        self.executable = executable
        self.session = f'jarvis-{os.getpid()}'
        self._lock = asyncio.Lock()
        self._elements = {}
        self._desktop = None
        self._screenshots = None
        self._browser_tabs = {}
        self._browser_routes = {}
        self._isolated_pids = set()
        self._observation_tasks = set()

    async def _invoke(self, name: str, arguments: dict, timeout: int = 20) -> dict:
        try:
            proc = await asyncio.create_subprocess_exec(
                self.executable, 'call', name, json.dumps(arguments),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                env=sanitized_subprocess_env(),
            )
        except OSError as exc:
            detail = exc.strerror or 'could not start GUI driver'
            raise GuiControlError(detail[:500]) from None
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout)
        except BaseException as error:
            if proc.returncode is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
            try:
                await asyncio.wait_for(proc.communicate(), 1)
            except (TimeoutError, OSError):
                pass
            if isinstance(error, TimeoutError):
                raise GuiControlError('GUI driver timed out') from None
            raise
        if proc.returncode:
            detail = stderr.decode(errors='replace').strip() or stdout.decode(errors='replace').strip()
            raise GuiControlError((detail or 'GUI driver failed')[:500])
        if len(stdout) > 2_000_000:
            raise GuiControlError('GUI driver returned too much data')
        try:
            result = json.loads(stdout)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise GuiControlError('GUI driver returned an invalid response') from None
        if not isinstance(result, dict):
            raise GuiControlError('GUI driver returned an invalid response')
        if result.get('isError') or result.get('error') or result.get('code'):
            reason = result.get('error') or result.get('code') or result.get('content')
            detail = result.get('detail') or result.get('message')
            raise GuiControlError((f'{reason}: {detail}' if detail else str(reason))[:500])
        return result

    async def _call(self, name: str, arguments: dict, timeout: int = 20) -> dict:
        try:
            return await self._invoke(name, arguments, timeout)
        except GuiControlError as exc:
            if 'session' in str(exc).lower() and 'ended' in str(exc).lower():
                await self._invoke('start_session', {'session': self.session})
                return await self._invoke(name, arguments, timeout)
            if 'daemon is not running' not in str(exc).lower():
                raise
            async with self._lock:
                try:
                    return await self._invoke(name, arguments, timeout)
                except GuiControlError as retry_error:
                    if 'daemon is not running' not in str(retry_error).lower():
                        raise
                env = os.environ.copy()
                if env.get('XDG_CURRENT_DESKTOP', '').lower() == 'hyprland':
                    env['CUA_DRIVER_RS_ENABLE_WAYLAND'] = '1'
                await asyncio.create_subprocess_exec(
                    self.executable, 'serve', '--no-overlay', env=env,
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                    start_new_session=True,
                )
                for _ in range(20):
                    await asyncio.sleep(.25)
                    try:
                        return await self._invoke(name, arguments, timeout)
                    except GuiControlError as retry_error:
                        if 'daemon is not running' not in str(retry_error).lower():
                            raise
            raise GuiControlError('GUI driver could not start') from None

    async def list_windows(self) -> dict:
        result = await self._call('list_windows', {})
        windows = result.get('windows', [])
        if not isinstance(windows, list):
            raise GuiControlError('GUI driver returned an invalid window list')
        return {'windows': [{k: w.get(k) for k in ('pid', 'window_id', 'address', 'app_name', 'title', 'bounds', 'is_on_screen')}
                            for w in windows[:50] if isinstance(w, dict)]}

    async def inspect_window(self, pid: int, window_id: int) -> dict:
        if pid <= 0 or window_id <= 0:
            raise GuiControlError('Choose a window from gui_list_windows')
        result = await self._call('get_window_state', {
            'pid': pid, 'window_id': window_id, 'include_screenshot': False,
            'max_elements': 100, 'session': self.session,
        })
        elements = result.get('elements', [])
        if not isinstance(elements, list):
            elements = []
        tokens = {item.get('element_token') for item in elements if isinstance(item, dict) and
                  isinstance(item.get('element_token'), str)}
        snapshot_id = result.get('snapshot_id')
        reliable = bool(snapshot_id and tokens and not result.get('degraded'))
        self._elements[(pid, window_id)] = (time.monotonic(), snapshot_id, tokens) if reliable else None
        return {
            'pid': pid, 'window_id': window_id, 'snapshot_id': snapshot_id,
            'degraded': bool(result.get('degraded')), 'degraded_reason': result.get('degraded_reason'),
            'elements_complete': result.get('elements_complete'), 'elements': elements[:100],
            'element_click_available': reliable,
        }

    async def click_element(self, pid: int, window_id: int, element_token: str) -> dict:
        observed = self._elements.get((pid, window_id))
        if not observed or time.monotonic() - observed[0] > 15 or element_token not in observed[2]:
            raise GuiControlError('Inspect this window again before clicking the element')
        before = await self._surface_fingerprint((pid, window_id))
        await self._guard_dispatch_focus()
        result = await self._call('click', {
            'pid': pid, 'window_id': window_id, 'element_token': element_token,
            'snapshot_id': observed[1], 'button': 'left',
            'delivery_mode': 'foreground', 'session': self.session,
        })
        self._elements.pop((pid, window_id), None)
        effect = await self._verify_surface_effect(before, (pid, window_id))
        return {'route': result.get('route'), 'reobserve_required': True, **effect}

    async def _surface_fingerprint(self, target):
        if target is None:
            return None
        pid, window_id = target
        task = asyncio.create_task(self._call('get_window_state', {
                'pid': pid, 'window_id': window_id, 'include_screenshot': False,
                'max_elements': 100, 'session': self.session}, timeout=.1))
        self._observation_tasks.add(task)
        def finished(done):
            self._observation_tasks.discard(done)
            if not done.cancelled():
                done.exception()
        task.add_done_callback(finished)
        try:
            done, _ = await asyncio.wait({task}, timeout=.1)
            if not done:
                task.cancel()
                return None
            state = task.result()
            return ground_truth.accessibility_fingerprint(state)
        except (GuiControlError, TimeoutError):
            return None
        except BaseException:
            task.cancel()
            raise

    async def _verify_surface_effect(self, before, target):
        deadline = time.monotonic() + .3
        if before is not None and target is not None:
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                try:
                    after = await asyncio.wait_for(self._surface_fingerprint(target), remaining)
                except TimeoutError:
                    break
                if after is None:
                    break
                if after != before:
                    return {'status': 'effect_observed', 'effect': 'surface_changed',
                            'effect_verified': True, 'verified': False,
                            'verification_scope': 'accessibility_tree_change_only'}
                await asyncio.sleep(min(.04, max(0, deadline - time.monotonic())))
        return {'status': 'unverified_effect', 'effect': 'unverified', 'verified': False,
                'effect_verified': False, 'fallback': 'use_accessibility_or_cli'}

    async def close(self):
        tasks = list(self._observation_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 1.2)
        if self._screenshots is not None:
            screenshots, self._screenshots = self._screenshots, None
            await asyncio.to_thread(screenshots.cleanup)

    @staticmethod
    def _surface_target(verification):
        pid, window_id = verification.get('window_pid'), verification.get('window_id')
        return (pid, window_id) if type(pid) is int and pid > 0 and type(window_id) is int and window_id > 0 else None

    async def observe_desktop(self) -> dict:
        from pathlib import Path
        if self._screenshots is None:
            self._screenshots = tempfile.TemporaryDirectory(prefix='jarvis-gui-')
        path = Path(self._screenshots.name) / 'desktop.png'
        await self._call('get_desktop_state', {'screenshot_out_file': str(path),
                                               'session': self.session}, timeout=30)
        if not path.is_file() or path.stat().st_size == 0:
            raise GuiControlError('GUI driver did not capture the desktop')
        with path.open('rb') as stream:
            header = stream.read(24)
        if header[:8] != b'\x89PNG\r\n\x1a\n':
            raise GuiControlError('GUI driver returned an invalid screenshot')
        width = int.from_bytes(header[16:20], 'big')
        height = int.from_bytes(header[20:24], 'big')
        self._desktop = (time.monotonic(), width, height)
        return {'status': 'inspected', 'screenshot_path': str(path),
                'width': width, 'height': height, 'visual_input': 'pending_frame'}

    async def click_desktop(self, x: int, y: int,
                            target_window_id: int | None = None,
                            verify_active: bool = False) -> dict:
        if ground_truth.ACTION_TARGET.get() is not None:
            verify_active = True
        verification = await self._verify_action_point(
            x, y, target_window_id=target_window_id, verify_active=verify_active)
        target_window_id = verification.get('window_id', target_window_id)
        surface = self._surface_target(verification)
        before = await self._surface_fingerprint(surface)
        target = {'kind': 'desktop', 'display_id': 'primary'}
        action = 'click'
        if target_window_id is not None:
            target = {'kind': 'window', 'window_id': target_window_id}
        if verify_active:
            # This distinct driver action is an atomic verify-and-click contract;
            # a generic coordinate click cannot safely close the focus-change race.
            action = 'click_window'
            target['address'] = verification['window_address']
            target['require_active'] = True
        await self._guard_dispatch_focus()
        result = await self._call(action, {
            'x': x, 'y': y, 'target': target, 'button': 'left',
            'delivery_mode': 'foreground', 'session': self.session,
        })
        if verify_active:
            acknowledged = self._window_address(result.get('target_address'))
            if result.get('target_verified') is not True or acknowledged != verification['window_address']:
                raise GuiControlError('GUI driver did not atomically verify the target window')
        self._desktop = None
        effect = await self._verify_surface_effect(before, surface)
        return {**effect,
                'route': result.get('route'), 'reobserve_required': True,
                **verification,
                'target_verified': verification['bounds_verified'] and
                (not verify_active or verification['focus_verified'])}

    def _require_desktop_point(self, x: int, y: int):
        observed = self._desktop
        if not observed or time.monotonic() - observed[0] > 15:
            raise GuiControlError('Observe the desktop again before using coordinates')
        width, height = observed[1:]
        if x < 0 or y < 0 or x >= width or y >= height:
            raise GuiControlError('Coordinates are outside the observed desktop')

    async def _query_active_window(self) -> dict | None:
        import shutil
        hyprctl = shutil.which('hyprctl')
        if not hyprctl:
            return None
        code, stdout, _ = await ground_truth._run_command(hyprctl, 'activewindow', '-j', timeout=2)
        try:
            if code == 0 and stdout:
                result = json.loads(stdout)
                return result if isinstance(result, dict) else None
        except json.JSONDecodeError:
            pass
        return None

    async def _verify_action_point(self, x: int, y: int,
                                   target_window_id: int | None = None,
                                   verify_active: bool = False):
        self._require_desktop_point(x, y)
        context = ground_truth.ACTION_TARGET.get()
        if context is not None:
            target_window_id = target_window_id or context['window'].get('window_id')
            if target_window_id is None:
                raise GuiControlError('Exact target_window_id is required for verified coordinate input')
        if verify_active and target_window_id is None:
            raise GuiControlError('verify_active requires an exact target_window_id')
        target = None
        bounds_verified = False
        focus_verified = False
        if target_window_id is not None:
            windows = (await self.list_windows()).get('windows', [])
            target = next((w for w in windows if w.get('window_id') == target_window_id), None)
            if not target:
                raise GuiControlError(f'Target window {target_window_id} not found in window list')
            if context is not None and not ground_truth.same_window(context['window'], target):
                raise GuiControlError('Target identity changed before coordinate input')
            if not target.get('is_on_screen', True):
                raise GuiControlError(f'Target window {target_window_id} is not visible or on screen')
            bounds = target.get('bounds')
            if isinstance(bounds, dict):
                bx = bounds.get('x', 0)
                by = bounds.get('y', 0)
                bw = bounds.get('width', 0)
                bh = bounds.get('height', 0)
                if not (bx <= x < bx + bw and by <= y < by + bh):
                    raise GuiControlError(
                        f'Coordinates ({x}, {y}) are outside the bounds of target window {target_window_id} [x={bx}, y={by}, w={bw}, h={bh}]'
                    )
                bounds_verified = True
            elif isinstance(bounds, (list, tuple)) and len(bounds) == 4:
                bx, by, bw, bh = bounds
                if not (bx <= x < bx + bw and by <= y < by + bh):
                    raise GuiControlError(
                        f'Coordinates ({x}, {y}) are outside the bounds of target window {target_window_id} [x={bx}, y={by}, w={bw}, h={bh}]'
                    )
                bounds_verified = True
            else:
                raise GuiControlError(
                    f'Target window {target_window_id} has no verifiable bounds')

        if verify_active:
            active = await self._query_active_window()
            requested_identity = self._window_address(
                target.get('address') if isinstance(target, dict) else None)
            active_identity = self._window_address(
                active.get('address') if isinstance(active, dict) else None)
            if requested_identity is None or active_identity is None:
                raise GuiControlError('Active window could not be verified with exact window identity')
            if requested_identity != active_identity:
                raise GuiControlError(
                    f'Target window {target_window_id} is not the active window {active_identity}')
            focus_verified = True
        return {'bounds_verified': bounds_verified, 'focus_verified': focus_verified,
                'window_address': requested_identity if verify_active else None,
                'window_pid': target.get('pid') if isinstance(target, dict) else None,
                'window_id': target_window_id}

    @staticmethod
    def _window_address(value) -> str | None:
        """Normalize only canonical Hyprland address values, never numeric IDs."""
        if not isinstance(value, str):
            return None
        value = value.strip().lower()
        if not value.startswith('0x'):
            return None
        try:
            identity = int(value, 16)
        except ValueError:
            return None
        return f'0x{identity:x}' if identity > 0 else None

    async def scroll_desktop(self, direction: str, x: int, y: int, amount: int,
                             target_window_id: int | None = None) -> dict:
        if direction not in ('up', 'down', 'left', 'right') or not 1 <= amount <= 10:
            raise GuiControlError('Invalid scroll direction or amount')
        verification = await self._verify_action_point(x, y, target_window_id=target_window_id)
        surface = self._surface_target(verification)
        before = await self._surface_fingerprint(surface)
        await self._guard_dispatch_focus()
        result = await self._call('scroll', {
            'direction': direction, 'amount': amount, 'by': 'line', 'x': x, 'y': y,
            'target': {'kind': 'desktop', 'display_id': 'primary'},
            'delivery_mode': 'foreground', 'session': self.session,
        })
        self._desktop = None
        effect = await self._verify_surface_effect(before, surface)
        return {**effect,
                'route': result.get('route'), 'reobserve_required': True,
                **verification, 'target_verified': verification['bounds_verified']}

    async def type_at(self, x: int, y: int, text: str,
                      target_window_id: int | None = None) -> dict:
        verification = await self._verify_action_point(x, y, target_window_id=target_window_id)
        if not text or len(text) > 4000:
            raise GuiControlError('Text must contain 1 to 4000 characters')
        await self._guard_dispatch_focus()
        result = await self._call('type_text', {
            'text': text, 'x': x, 'y': y,
            'target': {'kind': 'desktop', 'display_id': 'primary'},
            'delivery_mode': 'foreground', 'session': self.session,
        })
        self._desktop = None
        return {'status': 'dispatched', 'effect': result.get('effect', 'unverified'),
                'route': result.get('route'), 'reobserve_required': True,
                **verification, 'target_verified': verification['bounds_verified']}

    async def press_key_at(self, x: int, y: int, key: str,
                           modifiers: list[str] | None = None,
                           target_window_id: int | None = None) -> dict:
        verification = await self._verify_action_point(x, y, target_window_id=target_window_id)
        if not key or len(key) > 30:
            raise GuiControlError('Invalid key')
        modifiers = modifiers or []
        if any(item not in ('ctrl', 'shift', 'alt', 'super') for item in modifiers):
            raise GuiControlError('Invalid key modifier')
        arguments = {'x': x, 'y': y,
                     'target': {'kind': 'desktop', 'display_id': 'primary'},
                     'delivery_mode': 'foreground', 'session': self.session}
        if modifiers:
            arguments['keys'] = [*modifiers, key]
            tool = 'hotkey'
        else:
            arguments['key'] = key
            tool = 'press_key'
        await self._guard_dispatch_focus()
        result = await self._call(tool, arguments)
        self._desktop = None
        return {'status': 'dispatched', 'effect': result.get('effect', 'unverified'),
                'route': result.get('route'), 'reobserve_required': True,
                **verification, 'target_verified': verification['bounds_verified']}

    async def _guard_dispatch_focus(self):
        verified, reason = await ground_truth.ensure_dispatch_focus()
        if not verified:
            raise GuiControlError(reason)

    async def browser_bind(self, pid: int, window_id: int) -> dict:
        if pid <= 0 or window_id <= 0:
            raise GuiControlError('Choose a browser window from gui_list_windows')
        result = await self._call('get_browser_state', {
            'pid': pid, 'window_id': window_id, 'session': self.session,
        })
        target_id = result.get('target_id')
        tabs = result.get('tabs', [])
        if not isinstance(target_id, str) or not isinstance(tabs, list):
            return result
        tab_ids = {tab.get('tab_id') for tab in tabs if isinstance(tab, dict) and
                   isinstance(tab.get('tab_id'), str)}
        self._browser_tabs[target_id] = tab_ids
        self._browser_routes[target_id] = 'dom_event' if pid in self._isolated_pids else 'trusted'
        return {'target_id': target_id, 'tabs': tabs[:30],
                'binding': result.get('binding'), 'status': result.get('status')}

    async def browser_open_isolated(self) -> dict:
        result = await self._call('browser_prepare', {
            'profile': {'mode': 'isolated_new'}, 'allow_launch': True,
            'session': self.session,
        }, timeout=30)
        pid = result.get('prepared_pid')
        if isinstance(pid, int) and result.get('prepared'):
            self._isolated_pids.add(pid)
        window = None
        if isinstance(pid, int):
            for _ in range(16):
                windows = (await self.list_windows())['windows']
                window = next((item for item in windows if item.get('pid') == pid), None)
                if window:
                    break
                await asyncio.sleep(.25)
        return {'prepared': result.get('prepared'), 'status': result.get('status'),
                'prepared_pid': pid, 'window_id': window.get('window_id') if window else None,
                'message': result.get('message')}

    def _check_browser_tab(self, target_id: str, tab_id: str):
        if tab_id not in self._browser_tabs.get(target_id, set()):
            raise GuiControlError('Bind the exact browser window and tab again')

    async def browser_snapshot(self, target_id: str, tab_id: str) -> dict:
        self._check_browser_tab(target_id, tab_id)
        result = await self._call('get_browser_state', {
            'target_id': target_id, 'tab_id': tab_id, 'snapshot_format': 'semantic_v2',
            'session': self.session,
        })
        if len(json.dumps(result)) > 80_000:
            raise GuiControlError('Browser snapshot is too large; narrow the page query')
        return result

    async def browser_click(self, target_id: str, tab_id: str, ref: str) -> dict:
        self._check_browser_tab(target_id, tab_id)
        if not ref or len(ref) > 100:
            raise GuiControlError('Use a current page element ref')
        route = self._browser_routes.get(target_id, 'trusted')
        result = await self._call('browser_click', {
            'target_id': target_id, 'tab_id': tab_id, 'ref': ref,
            'input_route': route, 'session': self.session,
        })
        if result.get('effect') == 'refused' and route == 'trusted':
            result = await self._call('browser_click', {
                'target_id': target_id, 'tab_id': tab_id, 'ref': ref,
                'input_route': 'dom_event', 'session': self.session,
            })
        if result.get('effect') == 'refused':
            raise GuiControlError('Browser refused the click route')
        return {'status': 'dispatched', 'driver_result': result,
                'reobserve_required': True}

    async def browser_type(self, target_id: str, tab_id: str, ref: str, text: str,
                           replace: bool = False) -> dict:
        self._check_browser_tab(target_id, tab_id)
        if not ref or len(ref) > 100 or len(text) > 4000:
            raise GuiControlError('Use a current editable ref and at most 4000 characters')
        result = await self._call('browser_type', {
            'target_id': target_id, 'tab_id': tab_id, 'ref': ref, 'text': text,
            'replace': replace, 'session': self.session,
        })
        if result.get('effect') == 'refused':
            raise GuiControlError('Browser refused text input')
        return {'status': 'dispatched', 'driver_result': result,
                'reobserve_required': True}

    async def browser_navigate(self, target_id: str, tab_id: str, url: str) -> dict:
        from urllib.parse import urlsplit
        self._check_browser_tab(target_id, tab_id)
        parts = urlsplit(url)
        if parts.scheme not in ('http', 'https', 'about') or len(url) > 2048:
            raise GuiControlError('Browser navigation requires an http, https, or about URL')
        result = await self._call('browser_navigate', {
            'target_id': target_id, 'tab_id': tab_id, 'url': url,
            'session': self.session,
        })
        return {'status': 'dispatched', 'driver_result': result,
                'reobserve_required': True}

    async def browser_double_click(self, target_id: str, tab_id: str, ref: str) -> dict:
        self._check_browser_tab(target_id, tab_id)
        if not ref or len(ref) > 100:
            raise GuiControlError('Use a current page ref')
        route = self._browser_routes.get(target_id, 'trusted')
        args = {'target_id': target_id, 'tab_id': tab_id, 'action': 'double_click',
                'ref': ref, 'session': self.session, 'input_route': route}
        result = await self._call('browser_pointer', args)
        if result.get('effect') == 'refused' and route == 'trusted':
            args['input_route'] = 'dom_event'
            result = await self._call('browser_pointer', args)
        if result.get('effect') == 'refused':
            raise GuiControlError('Browser refused the pointer action')
        return {'status': 'dispatched', 'driver_result': result,
                'reobserve_required': True}

    async def verify_window(self, pid: int, window_id: int,
                            role: str | None = None,
                            label_contains: str | None = None) -> dict:
        if pid <= 0 or window_id <= 0:
            raise GuiControlError('Choose an exact window from gui_list_windows')
        if role or label_contains:
            selector = {}
            if role:
                selector['role'] = role[:80]
            if label_contains:
                selector['label_contains'] = label_contains[:120]
            predicate = {'element': {'selector': selector, 'exists': True}}
        else:
            predicate = {'window': {'exists': True}}
        result = await self._call('verify_state', {
            'pid': pid, 'window_id': window_id, 'expect': [predicate],
            'stable_samples': 1, 'timeout_ms': 1000,
            'include_screenshot': False, 'session': self.session,
        }, timeout=5)
        return result
