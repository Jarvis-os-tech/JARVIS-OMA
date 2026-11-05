"""Bounded Cua Driver bridge for Jarvis's Hyprland desktop.

The driver is optional.  The bridge keeps observations local to this agent and
requires a recent observation before sending pointer input.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from core.secret_env import sanitized_subprocess_env


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
        except (TimeoutError,asyncio.CancelledError) as error:
            if proc.returncode is None:proc.kill()
            await proc.communicate()
            if isinstance(error,asyncio.CancelledError):raise
            raise GuiControlError('GUI driver timed out') from None
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
                env = sanitized_subprocess_env()
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
        if any(isinstance(w,dict) and not self._window_address(w.get('address')) for w in windows):
            from skills import system_control, ground_truth
            clients = await system_control._query_open_windows()
            for window in windows:
                if not isinstance(window,dict) or self._window_address(window.get('address')):
                    continue
                candidates = [client for client in clients if ground_truth.window_identity(client)
                              and type(window.get('pid')) is int and client.get('pid') == window['pid']]
                exact = [client for client in candidates if int(client['address'],16) == window.get('window_id')]
                # Native Wayland IDs can equal the compositor address, but X11
                # IDs need not. Only accept a unique PID + exact rectangle when
                # the native IDs differ; never bind by PID or title alone.
                if not exact:
                    bounds = window.get('bounds')
                    rectangle = ([bounds.get(k) for k in ('x','y','width','height')]
                                 if isinstance(bounds,dict) else bounds)
                    exact = [client for client in candidates if isinstance(rectangle,(list,tuple))
                             and list(rectangle) == [*client.get('at',[]), *client.get('size',[])]]
                if len(exact) == 1:
                    window['address'] = exact[0]['address']
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
        result = await self._call('click', {
            'pid': pid, 'window_id': window_id, 'element_token': element_token,
            'snapshot_id': observed[1], 'button': 'left',
            'delivery_mode': 'foreground', 'session': self.session,
        })
        self._elements.pop((pid, window_id), None)
        return {'status': 'dispatched', 'effect': result.get('effect', 'unverified'),
                'route': result.get('route'), 'reobserve_required': True}

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
        verification = await self._verify_action_point(
            x, y, target_window_id=target_window_id, verify_active=verify_active)
        global_x, global_y = x, y
        target, x, y = self._input_target(verification, x, y)
        # The installed driver supports click with an exact PID/window target;
        # it has no click_window action or atomic focus-acknowledgement API.
        try:
            result = await self._call('click', {
                'x': x, 'y': y, 'target': target, 'button': 'left',
                'delivery_mode': 'foreground', 'session': self.session,
            })
        except GuiControlError as error:
            # Only an explicit admission refusal permits an alternative. Never
            # replay a timed-out or otherwise uncertain driver operation.
            if not str(error).startswith('foreground_unavailable:') or target.get('kind')!='window':
                raise
            address=verification.get('window_address')
            if not address:
                windows=(await self.list_windows())['windows']
                observed=next((w for w in windows if w.get('window_id')==target_window_id and w.get('pid')==target['pid']),{})
                address=observed.get('address')
            if not self._window_address(address):raise
            process=await asyncio.create_subprocess_exec(sys.executable,
                str(Path(__file__).resolve().parents[1]/'jarvis_control/wayland_pointer.py'),
                '--click',address,str(target['pid']),str(global_x),str(global_y),
                stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,env=sanitized_subprocess_env())
            try:
                stdout,stderr=await asyncio.wait_for(process.communicate(),5)
            except (TimeoutError,asyncio.CancelledError):
                if process.returncode is None:process.kill()
                await process.communicate()
                raise
            if process.returncode:
                raise GuiControlError('Native click could not be verified; inspect before retrying: '+stderr.decode(errors='replace')[:250])
            result=json.loads(stdout)
        if verify_active:
            acknowledged = self._window_address(result.get('target_address'))
            if result.get('target_verified') is False or (acknowledged and acknowledged != verification['window_address']):
                raise GuiControlError('GUI driver reported a different or unverified target; inspect effects before retrying')
            after = await self._query_active_window()
            if (self._window_address((after or {}).get('address')) != verification['window_address']
                    or (after or {}).get('pid') != verification['target_pid']):
                self._desktop = None
                return {'status':'unverified_effect','verified':False,'reobserve_required':True,
                        'reason':'Focus changed during targeted click; inspect effects before retrying'}
        self._desktop = None
        return {'status': 'dispatched', 'verified': False, 'effect': result.get('effect', 'unverified'),
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
        try:
            proc = await asyncio.create_subprocess_exec(
                hyprctl, 'activewindow', '-j',
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=2)
            if proc.returncode == 0 and stdout:
                return json.loads(stdout.decode('utf-8', errors='replace'))
        except (OSError, asyncio.TimeoutError, json.JSONDecodeError):
            return None
        return None

    async def _verify_action_point(self, x: int, y: int,
                                   target_window_id: int | None = None,
                                   verify_active: bool = False):
        self._require_desktop_point(x, y)
        if verify_active and target_window_id is None:
            raise GuiControlError('verify_active requires an exact target_window_id')
        target = None
        bounds_verified = False
        focus_verified = False
        target_bounds = None
        if target_window_id is not None:
            windows = (await self.list_windows()).get('windows', [])
            target = next((w for w in windows if w.get('window_id') == target_window_id), None)
            if not target:
                raise GuiControlError(f'Target window {target_window_id} not found in window list')
            if not target.get('is_on_screen', True):
                raise GuiControlError(f'Target window {target_window_id} is not visible or on screen')
            if type(target.get('pid')) is not int or target['pid'] <= 0:
                raise GuiControlError('Target window has no verifiable process identity')
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
                target_bounds = (bx, by, bw, bh)
            elif isinstance(bounds, (list, tuple)) and len(bounds) == 4:
                bx, by, bw, bh = bounds
                if not (bx <= x < bx + bw and by <= y < by + bh):
                    raise GuiControlError(
                        f'Coordinates ({x}, {y}) are outside the bounds of target window {target_window_id} [x={bx}, y={by}, w={bw}, h={bh}]'
                    )
                bounds_verified = True
                target_bounds = (bx, by, bw, bh)
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
            if active.get('pid') != target['pid']:
                raise GuiControlError('Active window process identity could not be verified')
            focus_verified = True
        return {'bounds_verified': bounds_verified, 'focus_verified': focus_verified,
                'window_address': requested_identity if verify_active else None,
                'target_pid': target['pid'] if target else None,
                'target_window_id': target_window_id, 'target_bounds': target_bounds}

    @staticmethod
    def _input_target(verification, x, y):
        if verification.get('target_window_id') is None:
            return {'kind':'desktop','display_id':'primary'}, x, y
        bx, by, _, _ = verification['target_bounds']
        return {'kind':'window','pid':verification['target_pid'],
                'window_id':verification['target_window_id']}, x-bx, y-by

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
        target, x, y = self._input_target(verification, x, y)
        result = await self._call('scroll', {
            'direction': direction, 'amount': amount, 'by': 'line', 'x': x, 'y': y,
            'target': target,
            'delivery_mode': 'foreground', 'session': self.session,
        })
        self._desktop = None
        return {'status': 'dispatched', 'effect': result.get('effect', 'unverified'),
                'route': result.get('route'), 'reobserve_required': True,
                **verification, 'target_verified': verification['bounds_verified']}

    async def type_at(self, x: int, y: int, text: str,
                      target_window_id: int | None = None) -> dict:
        verification = await self._verify_action_point(x, y, target_window_id=target_window_id)
        if not text or len(text) > 4000:
            raise GuiControlError('Text must contain 1 to 4000 characters')
        target, x, y = self._input_target(verification, x, y)
        result = await self._call('type_text', {
            'text': text, 'x': x, 'y': y,
            'target': target,
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
        target, x, y = self._input_target(verification, x, y)
        arguments = {'x': x, 'y': y,
                     'target': target,
                     'delivery_mode': 'foreground', 'session': self.session}
        if modifiers:
            arguments['keys'] = [*modifiers, key]
            tool = 'hotkey'
        else:
            arguments['key'] = key
            tool = 'press_key'
        result = await self._call(tool, arguments)
        self._desktop = None
        return {'status': 'dispatched', 'effect': result.get('effect', 'unverified'),
                'route': result.get('route'), 'reobserve_required': True,
                **verification, 'target_verified': verification['bounds_verified']}

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
        try:
            parts = urlsplit(url)
            parts.port
        except (ValueError, TypeError):
            raise GuiControlError('Browser navigation requires a valid URL') from None
        if (parts.scheme not in ('http', 'https', 'about') or len(url) > 2048
                or any(ord(c) < 32 for c in url) or parts.username or parts.password
                or (parts.scheme in ('http', 'https') and not parts.hostname)):
            raise GuiControlError('Browser navigation requires an http, https, or about URL')
        result = await self._call('browser_navigate', {
            'target_id': target_id, 'tab_id': tab_id, 'url': url,
            'session': self.session,
        })
        if result.get('effect') == 'refused':
            return {'status': 'blocked', 'verified': False, 'driver_result': result}
        # Observe only the bound tab, and never replay navigation on a delayed
        # or failed readback. A different tab or redirect cannot prove this URL.
        def canonical(value):
            if not isinstance(value, str):
                return None
            try:
                parsed = urlsplit(value)
                port = parsed.port
                return (parsed.scheme.casefold(), (parsed.hostname or '').casefold(),
                        port or (443 if parsed.scheme == 'https' else 80 if parsed.scheme == 'http' else None),
                        parsed.path or '/', parsed.query, parsed.fragment, parsed.username, parsed.password)
            except ValueError:
                return None

        observed_url = None
        for attempt in range(4):
            try:
                snapshot = await self.browser_snapshot(target_id, tab_id)
            except GuiControlError:
                break
            if snapshot.get('target_id', target_id) != target_id:
                break
            tabs = snapshot.get('tabs')
            tabs = tabs if isinstance(tabs, list) else []
            tab = snapshot if snapshot.get('tab_id') == tab_id else next(
                (item for item in tabs if isinstance(item, dict) and item.get('tab_id') == tab_id), {})
            observed_url = tab.get('url')
            if observed_url and canonical(url) is not None and canonical(observed_url) == canonical(url):
                from datetime import datetime, timezone
                return {'status': 'navigated', 'verified': True, 'url': url,
                        'evidence': {'source': 'browser_snapshot', 'target_id': target_id, 'tab_id': tab_id,
                                     'observed_url': observed_url, 'observed_at': datetime.now(timezone.utc).isoformat()}}
            if attempt < 3:
                await asyncio.sleep(.08)
        return {'status': 'dispatched_unverified', 'verified': False,
                'url': url, 'observed_url': observed_url, 'reobserve_required': True,
                'reason': 'Requested URL was not observed in the bound tab; do not repeat navigation automatically.'}

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
