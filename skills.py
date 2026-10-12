"""Allowlisted Omarchy desktop skills for the Gemini Live voice agent.

The model can only select a declared skill.  Arguments are validated here and
are always passed to subprocesses as an argv list; no shell is involved.

Adapters self-declare their command dependencies.  Only commands actually needed
by discovered skills are looked up.  Skills whose commands are unavailable are
excluded at load time with a warning (graceful degradation).
"""
from __future__ import annotations

import asyncio
import configparser
import ipaddress
import json
import logging
import os
from pathlib import Path
import re
import shutil
import time as _time
from urllib.parse import urlsplit

log = logging.getLogger(__name__)


class SkillError(ValueError):
    """A safe, user-presentable skill failure."""


def _normalized(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', value.casefold())


class DesktopSkills:
    """Small, auditable set of controls for an Omarchy/Hyprland desktop."""

    # ── Adapter → method mapping ──────────────────────────────────────
    ADAPTERS = {
        'applications.list': '_adapter_list_applications',
        'applications.open': '_adapter_open_application',
        'web.open': '_adapter_open_website',
        'audio.volume': '_adapter_adjust_volume',
        'display.brightness': '_adapter_adjust_brightness',
        'workspace.switch': '_adapter_switch_workspace',
        'notification.show': '_adapter_show_notification',
        'system.lock': '_adapter_lock_screen',
        'system.screenshot': '_adapter_take_screenshot',
        'window.manage': '_adapter_manage_window',
        'system.power': '_adapter_system_power',
        'network.wifi': '_adapter_toggle_wifi',
        'network.bluetooth': '_adapter_toggle_bluetooth',
        'clipboard.read': '_adapter_read_clipboard',
        'clipboard.write': '_adapter_write_clipboard',
    }

    # ── Adapter → required system commands ────────────────────────────
    ADAPTER_COMMANDS = {
        'applications.list': (),
        'applications.open': ('gtk-launch',),
        'web.open': ('omarchy-launch-webapp',),
        'audio.volume': ('omarchy-audio-output-volume',),
        'display.brightness': ('omarchy-brightness-display',),
        'workspace.switch': ('hyprctl',),
        'notification.show': ('notify-send',),
        'system.lock': ('loginctl',),
        'system.screenshot': ('grim',),
        'window.manage': ('hyprctl',),
        'system.power': ('systemctl',),
        'network.wifi': ('nmcli',),
        'network.bluetooth': ('rfkill',),
        'clipboard.read': ('wl-paste',),
        'clipboard.write': ('wl-copy',),
    }

    def __init__(self, manifest_dirs=None, *, config=None,
                 exclude_unavailable=False, app_name=None):
        """Initialize with dynamic command discovery.

        Args:
            manifest_dirs: Override skill manifest directories.
            config: Optional Config object for settings.
            exclude_unavailable: If True, skip skills whose adapters lack
                required commands (graceful degradation). If False (default),
                keep them and validate commands on execution.
            app_name: Application name for notifications. Defaults to config
                or 'Jarvis'.
        """
        if config is not None:
            self._app_name = app_name or config.agent.name
            self._command_timeout = config.audio.command_timeout
            self._command_overrides = dict(config.commands)
            if manifest_dirs is None and config.skills.manifest_dirs:
                manifest_dirs = config.skills.manifest_dirs
            exclude_unavailable = config.skills.exclude_unavailable
        else:
            self._app_name = app_name or 'Jarvis'
            self._command_timeout = 8
            self._command_overrides = {}

        if manifest_dirs is None:
            manifest_dirs = [Path(__file__).with_name('skill_manifests')]
        self.manifest_dirs = [Path(directory) for directory in manifest_dirs]
        self._skills = self._load_manifests()

        # Discover commands dynamically from active adapters
        self._commands = self._discover_commands()

        # Graceful degradation: exclude skills with missing commands
        if exclude_unavailable:
            self._exclude_unavailable_skills()

    def _discover_commands(self):
        """Build command registry from what active adapters actually need."""
        needed = set()
        for spec in self._skills.values():
            adapter = spec['adapter']
            needed.update(self.ADAPTER_COMMANDS.get(adapter, ()))

        commands = {}
        for name in sorted(needed):
            # Check for explicit override first
            override = self._command_overrides.get(name)
            if override and os.path.isfile(override) and os.access(override, os.X_OK):
                commands[name] = override
            else:
                commands[name] = shutil.which(name)
        return commands

    def _exclude_unavailable_skills(self):
        """Remove skills whose adapter commands are not installed."""
        to_remove = []
        for skill_name, spec in self._skills.items():
            adapter = spec['adapter']
            required = self.ADAPTER_COMMANDS.get(adapter, ())
            missing = [cmd for cmd in required if not self._commands.get(cmd)]
            if missing:
                log.warning('Skill %s excluded: missing commands %s',
                            skill_name, ', '.join(missing))
                to_remove.append(skill_name)
        for name in to_remove:
            del self._skills[name]
        if not self._skills:
            raise SkillError('no desktop skills available (all required commands missing)')

    @property
    def declarations(self):
        """Function declarations generated from discovered JSON manifests."""
        return [
            {'name': spec['name'], 'description': spec['description'],
             'parameters_json_schema': spec['parameters_json_schema']}
            for spec in self._skills.values()
        ]

    def _load_manifests(self):
        files = []
        for directory in self.manifest_dirs:
            if directory.is_dir():
                files.extend(directory.glob('*.json'))
        files = sorted(path for path in set(files) if path.is_file() and not path.is_symlink())
        if len(files) > 64:
            raise SkillError('too many skill manifest files (maximum 64)')
        loaded = {}
        for path in files:
            try:
                if path.stat().st_size > 64 * 1024:
                    raise SkillError(f'skill manifest is too large: {path.name}')
                document = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError, RecursionError) as error:
                raise SkillError(f'cannot load skill manifest {path.name}: {error}') from None
            if not isinstance(document, dict) or set(document) != {'version', 'skills'}:
                raise SkillError(f'invalid skill manifest structure: {path.name}')
            if document['version'] != 1 or not isinstance(document['skills'], list):
                raise SkillError(f'unsupported skill manifest: {path.name}')
            if len(document['skills']) > 128:
                raise SkillError(f'too many skills in manifest: {path.name}')
            for spec in document['skills']:
                self._validate_spec(spec, path.name)
                if spec['name'] in loaded:
                    raise SkillError(f'duplicate dynamic skill name: {spec["name"]}')
                loaded[spec['name']] = spec
        if not loaded:
            raise SkillError('no valid desktop skill manifests were found')
        return loaded

    def _validate_spec(self, spec, source):
        expected = {'name', 'description', 'adapter', 'parameters_json_schema'}
        if not isinstance(spec, dict) or set(spec) != expected:
            raise SkillError(f'invalid skill entry in {source}')
        if not isinstance(spec['name'], str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}', spec['name']):
            raise SkillError(f'invalid skill name in {source}')
        if not isinstance(spec['description'], str) or not 1 <= len(spec['description']) <= 500:
            raise SkillError(f'invalid description for {spec["name"]}')
        if spec['adapter'] not in self.ADAPTERS:
            raise SkillError(f'unapproved adapter for {spec["name"]}')
        self._validate_schema(spec['parameters_json_schema'], root=True, depth=0)

    def _validate_schema(self, schema, root=False, depth=0):
        if depth > 8 or not isinstance(schema, dict):
            raise SkillError('skill manifest contains an unsupported schema')
        if 'oneOf' in schema:
            if set(schema) != {'oneOf'} or not isinstance(schema['oneOf'], list) or not schema['oneOf']:
                raise SkillError('invalid oneOf skill schema')
            for option in schema['oneOf']:
                self._validate_schema(option, depth=depth + 1)
            return
        kind = schema.get('type')
        if kind not in ('object', 'string', 'integer', 'boolean'):
            raise SkillError('skill schema type is not allowed')
        allowed_by_type = {
            'object': {'type', 'properties', 'required', 'additionalProperties', 'description'},
            'string': {'type', 'description', 'enum'},
            'integer': {'type', 'description', 'enum', 'minimum', 'maximum'},
            'boolean': {'type', 'description', 'enum'},
        }
        if not set(schema) <= allowed_by_type[kind]:
            raise SkillError('skill manifest contains an unsupported schema')
        description = schema.get('description')
        if description is not None and (not isinstance(description, str) or len(description) > 300):
            raise SkillError('invalid skill parameter description')
        if root and (kind != 'object' or schema.get('additionalProperties') is not False):
            raise SkillError('skill arguments must be a strict object schema')
        if kind == 'object':
            properties = schema.get('properties', {})
            required = schema.get('required', [])
            if (not isinstance(properties, dict) or len(properties) > 32 or
                    not isinstance(required, list) or
                    not all(isinstance(item, str) for item in required) or
                    len(required) != len(set(required))):
                raise SkillError('invalid object skill schema')
            if not set(required) <= set(properties):
                raise SkillError('skill schema requires an unknown property')
            for key, value in properties.items():
                if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}', key):
                    raise SkillError('invalid skill parameter name')
                self._validate_schema(value, depth=depth + 1)
        if 'enum' in schema:
            enum = schema['enum']
            if not isinstance(enum, list) or not enum or len(enum) > 32:
                raise SkillError('invalid enum skill schema')
            check = {'string': lambda item: isinstance(item, str),
                     'integer': lambda item: isinstance(item, int) and not isinstance(item, bool),
                     'boolean': lambda item: isinstance(item, bool)}[kind]
            if not all(check(item) for item in enum):
                raise SkillError('enum values do not match the skill schema type')
        if kind == 'integer':
            for bound in ('minimum', 'maximum'):
                if bound in schema and (not isinstance(schema[bound], int) or
                                        isinstance(schema[bound], bool)):
                    raise SkillError('invalid integer bound in skill schema')
            if ('minimum' in schema and 'maximum' in schema and
                    schema['minimum'] > schema['maximum']):
                raise SkillError('skill schema minimum exceeds maximum')

    def _arguments_match(self, value, schema):
        if 'oneOf' in schema:
            return sum(self._arguments_match(value, option) for option in schema['oneOf']) == 1
        kind = schema['type']
        if kind == 'object':
            if not isinstance(value, dict) or not set(value) <= set(schema.get('properties', {})):
                return False
            if not set(schema.get('required', [])) <= set(value):
                return False
            return all(self._arguments_match(item, schema['properties'][key])
                       for key, item in value.items())
        if kind == 'string':
            valid = isinstance(value, str)
        elif kind == 'integer':
            valid = isinstance(value, int) and not isinstance(value, bool)
        else:
            valid = isinstance(value, bool)
        if not valid or ('enum' in schema and value not in schema['enum']):
            return False
        if kind == 'integer':
            if 'minimum' in schema and value < schema['minimum']:
                return False
            if 'maximum' in schema and value > schema['maximum']:
                return False
        return True

    def availability(self):
        """Per-command availability dictionary for backward compatibility."""
        return {name: path is not None for name, path in self._commands.items()}

    def adapter_availability(self):
        """Per-adapter availability dictionary indicating if all required commands are present."""
        return {
            adapter_name: (
                True if not required_cmds else
                all(self._commands.get(cmd) is not None for cmd in required_cmds)
            )
            for adapter_name, required_cmds in self.ADAPTER_COMMANDS.items()
        }

    def _command(self, name):
        path = self._commands.get(name)
        if not path:
            raise SkillError(f'{name} is not installed on this desktop')
        return path

    async def _run(self, *argv, timeout=None):
        if timeout is None:
            timeout = self._command_timeout
        process = await asyncio.create_subprocess_exec(
            *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            limit=64 * 1024)
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout)
        except TimeoutError:
            process.kill()
            await process.wait()
            raise SkillError('desktop command timed out') from None
        output = (stderr if process.returncode else stdout).decode(errors='replace').strip()
        if process.returncode:
            raise SkillError((output or 'desktop command failed')[:500])
        return output[:500]

    async def _launch(self, *argv):
        process = await asyncio.create_subprocess_exec(
            *argv, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True)
        try:
            code = await asyncio.wait_for(process.wait(), 2)
        except TimeoutError:
            # GUI apps can remain attached to their launcher. Reap it later without
            # delaying the Live receive loop or terminating the application.
            asyncio.create_task(process.wait())
            return
        if code:
            raise SkillError('application launcher failed')

    def _applications(self):
        """Discover installed .desktop applications via XDG directories."""
        # XDG Base Directory Specification compliant
        data_home = os.getenv('XDG_DATA_HOME') or str(Path.home() / '.local/share')
        data_dirs_str = os.getenv('XDG_DATA_DIRS', '/usr/local/share:/usr/share')
        data_dirs = [d.strip() for d in data_dirs_str.split(':') if d.strip()]

        directories = [Path(data_home) / 'applications']
        for d in data_dirs:
            directories.append(Path(d) / 'applications')

        apps = {}
        for directory in directories:
            if not directory.is_dir():
                continue
            for entry in directory.glob('*.desktop'):
                parser = configparser.ConfigParser(interpolation=None, strict=False)
                try:
                    parser.read(entry, encoding='utf-8')
                    section = parser['Desktop Entry']
                    if (section.get('Type', 'Application') != 'Application' or
                            section.getboolean('NoDisplay', fallback=False) or
                            section.getboolean('Hidden', fallback=False) or
                            not section.get('Exec')):
                        continue
                    name = section.get('Name', fallback=entry.stem).strip()
                except (OSError, configparser.Error, ValueError, KeyError):
                    continue
                apps.setdefault(entry.name, name)
        return apps

    async def execute(self, name, arguments=None):
        """Validate and execute one exact declared skill name."""
        if not isinstance(arguments, dict):
            raise SkillError('skill arguments must be an object')
        spec = self._skills.get(name)
        if spec is None:
            raise SkillError(f'unknown skill: {name}')
        if not self._arguments_match(arguments, spec['parameters_json_schema']):
            raise SkillError(f'invalid arguments for {name}')
        handler = getattr(self, self.ADAPTERS[spec['adapter']])
        try:
            return await handler(**arguments)
        except TypeError:
            raise SkillError(f'invalid arguments for {name}') from None

    # ── Existing adapters ─────────────────────────────────────────────

    async def _adapter_list_applications(self):
        names = sorted(set(self._applications().values()), key=str.casefold)
        return {'applications': names[:200], 'count': len(names)}

    async def _adapter_open_application(self, name):
        if not isinstance(name, str) or not (1 <= len(name.strip()) <= 100):
            raise SkillError('application name must be 1 to 100 characters')
        requested = _normalized(name)
        apps = self._applications()
        exact = [(app_id, label) for app_id, label in apps.items()
                 if requested in {_normalized(label), _normalized(Path(app_id).stem)}]
        if len(exact) != 1:
            suggestions = [label for app_id, label in apps.items()
                           if requested and requested in _normalized(label)][:8]
            detail = f'; possible matches: {", ".join(suggestions)}' if suggestions else ''
            raise SkillError(f'application name is not an exact unique match{detail}')
        app_id, label = exact[0]
        await self._launch(self._command('gtk-launch'), app_id)
        return {'status': 'opened', 'application': label}

    async def _adapter_open_website(self, url):
        if (not isinstance(url, str) or len(url) > 2048 or
                any(ord(character) < 32 for character in url)):
            raise SkillError('URL is invalid or too long')
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username:
            raise SkillError('only public HTTP or HTTPS URLs without embedded credentials are allowed')
        hostname = parsed.hostname.rstrip('.').casefold()
        if hostname == 'localhost' or hostname.endswith('.localhost'):
            raise SkillError('local and private network URLs are not allowed')
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise SkillError('local and private network URLs are not allowed')
        await self._launch(self._command('omarchy-launch-webapp'), url)
        return {'status': 'opened', 'url': url}

    async def _adapter_adjust_volume(self, action, amount=5):
        if action not in ('raise', 'lower', 'mute_toggle'):
            raise SkillError('volume action must be raise, lower, or mute_toggle')
        if isinstance(amount, bool) or not isinstance(amount, int) or not 1 <= amount <= 25:
            raise SkillError('volume amount must be from 1 to 25')
        command = 'mute-toggle' if action == 'mute_toggle' else ('+' if action == 'raise' else '-') + str(amount)
        await self._run(self._command('omarchy-audio-output-volume'), command)
        return {'status': 'done', 'action': action, 'amount': None if action == 'mute_toggle' else amount}

    async def _adapter_adjust_brightness(self, direction, amount=5):
        if direction not in ('raise', 'lower'):
            raise SkillError('brightness direction must be raise or lower')
        if isinstance(amount, bool) or not isinstance(amount, int) or not 1 <= amount <= 25:
            raise SkillError('brightness amount must be from 1 to 25')
        step = f'+{amount}%' if direction == 'raise' else f'{amount}%-'
        await self._run(self._command('omarchy-brightness-display'), step)
        return {'status': 'done', 'direction': direction, 'amount': amount}

    async def _adapter_switch_workspace(self, workspace):
        if isinstance(workspace, bool):
            raise SkillError('workspace must be 1 to 10, next, or previous')
        if isinstance(workspace, int) and 1 <= workspace <= 10:
            target = str(workspace)
        elif workspace in ('next', 'previous'):
            target = 'e+1' if workspace == 'next' else 'e-1'
        else:
            raise SkillError('workspace must be 1 to 10, next, or previous')
        await self._run(self._command('hyprctl'), 'dispatch', 'workspace', target)
        return {'status': 'switched', 'workspace': workspace}

    async def _adapter_show_notification(self, title, message):
        if not all(isinstance(value, str) for value in (title, message)):
            raise SkillError('notification title and message must be text')
        title, message = title.strip(), message.strip()
        if not title or len(title) > 80 or not message or len(message) > 300:
            raise SkillError('notification title or message has an invalid length')
        await self._run(self._command('notify-send'),
                        f'--app-name={self._app_name}', title, message)
        return {'status': 'shown'}

    # ── New system control adapters ───────────────────────────────────

    async def _adapter_lock_screen(self):
        """Lock the current session via loginctl."""
        await self._run(self._command('loginctl'), 'lock-session')
        return {'status': 'locked'}

    async def _adapter_take_screenshot(self, region='full'):
        """Capture a screenshot using grim."""
        if region not in ('full', 'active'):
            raise SkillError('screenshot region must be full or active')
        pictures_dir = os.environ.get(
            'XDG_PICTURES_DIR',
            str(Path.home() / 'Pictures'))
        Path(pictures_dir).mkdir(parents=True, exist_ok=True)
        filename = str(Path(pictures_dir) / f'screenshot_{int(_time.time())}.png')
        args = [self._command('grim')]
        if region == 'active':
            # Capture the active window by getting its geometry from hyprctl
            hyprctl = self._commands.get('hyprctl')
            if hyprctl:
                try:
                    info = await self._run(hyprctl, 'activewindow', '-j')
                    import json as _json
                    window = _json.loads(info)
                    at = window.get('at', [0, 0])
                    size = window.get('size', [1920, 1080])
                    args.extend(['-g', f'{at[0]},{at[1]} {size[0]}x{size[1]}'])
                except (SkillError, json.JSONDecodeError, KeyError):
                    pass  # Fall back to full screen
        args.append(filename)
        await self._run(*args, timeout=10)
        return {'status': 'captured', 'path': filename}

    async def _adapter_manage_window(self, action):
        """Manage the active window via hyprctl dispatch."""
        dispatch_map = {
            'fullscreen': 'fullscreen',
            'close': 'killactive',
            'minimize': 'movetospecialsilent',
            'float': 'togglefloating',
            'center': 'centerwindow',
            'maximize': 'fullscreen 1',
        }
        if action not in dispatch_map:
            valid = ', '.join(sorted(dispatch_map))
            raise SkillError(f'window action must be one of: {valid}')
        dispatch_arg = dispatch_map[action]
        # Handle compound dispatch arguments (e.g. 'fullscreen 1')
        parts = dispatch_arg.split(None, 1)
        await self._run(self._command('hyprctl'), 'dispatch', *parts)
        return {'status': 'done', 'action': action}

    async def _adapter_system_power(self, action):
        """Sleep or hibernate the system. Shutdown/reboot excluded for safety."""
        allowed = {
            'sleep': 'suspend',
            'hibernate': 'hibernate',
        }
        if action not in allowed:
            raise SkillError('power action must be sleep or hibernate '
                             '(shutdown and reboot are not available for safety)')
        await self._run(self._command('systemctl'), allowed[action])
        return {'status': 'done', 'action': action}

    async def _adapter_toggle_wifi(self, action):
        """Toggle or check Wi-Fi status via nmcli."""
        if action not in ('on', 'off', 'status'):
            raise SkillError('Wi-Fi action must be on, off, or status')
        if action == 'status':
            output = await self._run(self._command('nmcli'), 'radio', 'wifi')
            state = output.strip().lower()
            return {'status': state, 'wifi': state}
        await self._run(self._command('nmcli'), 'radio', 'wifi', action)
        return {'status': 'done', 'wifi': action}

    async def _adapter_toggle_bluetooth(self, action):
        """Toggle or check Bluetooth status via rfkill."""
        if action not in ('on', 'off', 'status'):
            raise SkillError('Bluetooth action must be on, off, or status')
        if action == 'status':
            output = await self._run(self._command('rfkill'), 'list', 'bluetooth')
            blocked = 'Soft blocked: yes' in output
            return {'status': 'off' if blocked else 'on', 'bluetooth': 'off' if blocked else 'on'}
        cmd = 'unblock' if action == 'on' else 'block'
        await self._run(self._command('rfkill'), cmd, 'bluetooth')
        return {'status': 'done', 'bluetooth': action}

    async def _adapter_read_clipboard(self):
        """Read current clipboard content via wl-paste."""
        try:
            output = await self._run(self._command('wl-paste'),
                                     '--no-newline', timeout=3)
        except SkillError:
            return {'status': 'empty', 'content': ''}
        return {'status': 'read', 'content': output[:500]}

    async def _adapter_write_clipboard(self, content):
        """Write text to clipboard via wl-copy."""
        if not isinstance(content, str):
            raise SkillError('clipboard content must be text')
        if len(content) > 10000:
            raise SkillError('clipboard content must be 10000 characters or fewer')
        if not content.strip():
            raise SkillError('clipboard content must not be empty')
        process = await asyncio.create_subprocess_exec(
            self._command('wl-copy'), '--',
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        try:
            _, stderr = await asyncio.wait_for(
                process.communicate(content.encode('utf-8')), 5)
        except TimeoutError:
            process.kill()
            await process.wait()
            raise SkillError('clipboard write timed out') from None
        if process.returncode:
            raise SkillError('clipboard write failed')
        return {'status': 'written', 'length': len(content)}
