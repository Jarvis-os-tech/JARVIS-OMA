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
import datetime as dt
import ipaddress
import json
import logging
import os
from pathlib import Path
import re
import shutil
import time
import uuid
from urllib.parse import urlsplit
import filesystem as fs
from task_runner import TaskPlanError, TaskRunner
from agent_orchestrator import AgentOrchestrator, OrchestrationError

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
        'reminder.create': '_adapter_create_reminder',
        'reminder.list': '_adapter_list_reminders',
        'reminder.clear': '_adapter_clear_reminders',
        'reminder.cancel': '_adapter_cancel_reminder',
        'todo.create': '_adapter_create_todo',
        'todo.list': '_adapter_list_todos',
        'todo.update': '_adapter_update_todo',
        'todo.complete': '_adapter_complete_todo',
        'todo.delete': '_adapter_delete_todo',
        'todo.clear_completed': '_adapter_clear_completed_todos',
        'todo.move': '_adapter_move_todo',
        'system.context': '_adapter_get_desktop_context',
        'filesystem.list': '_adapter_list_files',
        'filesystem.read': '_adapter_read_file',
        'filesystem.search': '_adapter_search_files',
        'filesystem.write': '_adapter_write_file',
        'filesystem.append': '_adapter_append_file',
        'filesystem.mkdir': '_adapter_make_directory',
        'filesystem.move': '_adapter_move_path',
        'filesystem.trash': '_adapter_trash_path',
        'filesystem.copy': '_adapter_copy_path',
        'filesystem.edit': '_adapter_edit_file',
        'task.start': '_adapter_start_task',
        'task.status': '_adapter_task_status',
        'task.list': '_adapter_list_tasks',
        'task.cancel': '_adapter_cancel_task',
        'agents.list': '_adapter_list_system_agents',
        'agents.delegate': '_adapter_delegate_agent',
        'agents.status': '_adapter_check_agent_job',
        'agents.jobs': '_adapter_list_agent_jobs',
        'agents.cancel': '_adapter_cancel_agent_job',
        'filesystem.delete': '_adapter_delete_path',
        'filesystem.info': '_adapter_inspect_path',
        'filesystem.grep': '_adapter_search_file_content',
        'screen.inspect': '_adapter_inspect_screen',
        'window.list': '_adapter_list_windows',
        'window.focus': '_adapter_focus_window',
        'workspace.list': '_adapter_list_workspaces',
        'system.resources': '_adapter_get_system_resources',
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
        'reminder.create': ('omarchy-reminder',),
        'reminder.list': ('omarchy-reminder',),
        'reminder.clear': ('omarchy-reminder',),
        'reminder.cancel': ('omarchy-reminder', 'systemctl'),
        'todo.create': (),
        'todo.list': (),
        'todo.update': (),
        'todo.complete': (),
        'todo.delete': (),
        'todo.clear_completed': (),
        'todo.move': (),
        'system.context': ('hyprctl', 'omarchy-battery-status', 'omarchy-network-status',
                           'omarchy-brightness-display', 'omarchy-hyprland-monitor-focused', 'pactl'),
        'filesystem.list': (),
        'filesystem.read': (),
        'filesystem.search': (),
        'filesystem.write': (),
        'filesystem.append': (),
        'filesystem.mkdir': (),
        'filesystem.move': (),
        'filesystem.trash': (),
        'filesystem.copy': (),
        'filesystem.edit': (),
        'task.start': (),
        'task.status': (),
        'task.list': (),
        'task.cancel': (),
        'agents.list': (),
        'agents.delegate': (),
        'agents.status': (),
        'agents.jobs': (),
        'agents.cancel': (),
        'filesystem.delete': (),
        'filesystem.info': (),
        'filesystem.grep': (),
        'screen.inspect': ('grim', 'tesseract'),
        'window.list': ('hyprctl',),
        'window.focus': ('hyprctl',),
        'workspace.list': ('hyprctl',),
        'system.resources': ('ps',),
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
        self._task_runner = TaskRunner(self.execute, self._valid_task_step)
        self._agent_orchestrator = AgentOrchestrator()

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

    async def _run(self, *argv, timeout=None, max_output=500):
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
        return output[:max_output]

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

    def _valid_task_step(self, name, arguments):
        spec = self._skills.get(name)
        return spec is not None and self._arguments_match(arguments, spec['parameters_json_schema'])

    async def _adapter_list_system_agents(self):
        return self._agent_orchestrator.discover()

    async def _adapter_delegate_agent(self, agent, prompt, workspace, timeout_seconds=900):
        try:
            return self._agent_orchestrator.delegate(agent, prompt, workspace, timeout_seconds)
        except OrchestrationError as error:
            raise SkillError(str(error)) from None

    async def _adapter_check_agent_job(self, job_id, max_chars=6000):
        try:
            return self._agent_orchestrator.status(job_id, max_chars)
        except OrchestrationError as error:
            raise SkillError(str(error)) from None

    async def _adapter_list_agent_jobs(self):
        return self._agent_orchestrator.list_jobs()

    async def _adapter_cancel_agent_job(self, job_id):
        try:
            return await self._agent_orchestrator.cancel(job_id)
        except OrchestrationError as error:
            raise SkillError(str(error)) from None

    async def close_agent_jobs(self):
        await self._agent_orchestrator.close()

    @property
    def agent_job_events(self):
        return self._agent_orchestrator.events

    async def _adapter_start_task(self, description, plan_json):
        try:
            return self._task_runner.start(description, plan_json)
        except TaskPlanError as error:
            raise SkillError(str(error)) from None

    async def _adapter_task_status(self, task_id):
        try:
            return self._task_runner.status(task_id)
        except TaskPlanError as error:
            raise SkillError(str(error)) from None

    async def _adapter_list_tasks(self):
        return self._task_runner.list_tasks()

    async def _adapter_cancel_task(self, task_id):
        try:
            return self._task_runner.cancel(task_id)
        except TaskPlanError as error:
            raise SkillError(str(error)) from None

    async def _file_operation(self, operation, *args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except fs.FileOperationError as error:
            raise SkillError(str(error)) from None

    async def _adapter_list_files(self, path, limit=100, include_hidden=True):
        return await self._file_operation(fs.list_directory, path, limit, include_hidden)

    async def _adapter_read_file(self, path, offset=0, max_chars=20000):
        return await self._file_operation(fs.read_text, path, offset, max_chars)

    async def _adapter_search_files(self, path, query, limit=50, include_hidden=False):
        return await self._file_operation(fs.search_files, path, query, limit, include_hidden)

    async def _adapter_search_file_content(self, path, query, limit=30):
        return await self._file_operation(fs.search_file_content, path, query, limit)

    async def _adapter_write_file(self, path, content, overwrite=False):
        return await self._file_operation(fs.write_text, path, content, overwrite)

    async def _adapter_append_file(self, path, content):
        return await self._file_operation(fs.append_text, path, content)

    async def _adapter_make_directory(self, path):
        return await self._file_operation(fs.make_directory, path)

    async def _adapter_move_path(self, source, destination, overwrite=False):
        return await self._file_operation(fs.move_path, source, destination, overwrite)

    async def _adapter_copy_path(self, source, destination, overwrite=False):
        return await self._file_operation(fs.copy_path, source, destination, overwrite)

    async def _adapter_trash_path(self, path):
        return await self._file_operation(fs.trash_path, path)

    async def _adapter_delete_path(self, path, recursive=False):
        return await self._file_operation(fs.delete_path, path, recursive)

    async def _adapter_inspect_path(self, path):
        return await self._file_operation(fs.inspect_path, path)

    async def _adapter_edit_file(self, path, old, new):
        return await self._file_operation(fs.replace_text, path, old, new)

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
        hypr = self._command('hyprctl')
        # Hyprland 0.56+ uses Lua dispatch: hl.dsp.focus({ workspace = "..." })
        # Older Hyprland used: hyprctl dispatch workspace <target>
        try:
            await self._run(hypr, 'dispatch', f'hl.dsp.focus({{ workspace = "{target}" }})')
        except SkillError:
            await self._run(hypr, 'dispatch', 'workspace', target)
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

    async def _adapter_create_reminder(self, minutes, message='Reminder'):
        """Create a reminder in Omarchy's native reminder system."""
        if isinstance(minutes, bool) or not isinstance(minutes, int) or not 1 <= minutes <= 10080:
            raise SkillError('reminder minutes must be from 1 to 10080')
        if not isinstance(message, str) or not 1 <= len(message.strip()) <= 300:
            raise SkillError('reminder message must be 1 to 300 characters')
        await self._run(self._command('omarchy-reminder'), str(minutes), message.strip())
        return {'status': 'created', 'minutes': minutes, 'message': message.strip(), 'system': 'omarchy'}

    async def _adapter_list_reminders(self):
        """Read reminders from Omarchy's native reminder system."""
        output = await self._run(self._command('omarchy-reminder'), 'show', '--json', max_output=65536)
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            raise SkillError('Omarchy returned invalid reminder data') from None
        if not isinstance(data, dict) or not isinstance(data.get('reminders'), list):
            raise SkillError('Omarchy returned invalid reminder data')
        return data

    async def _adapter_clear_reminders(self):
        """Clear reminders through Omarchy's native reminder system."""
        await self._run(self._command('omarchy-reminder'), 'clear')
        return {'status': 'cleared', 'system': 'omarchy'}

    async def _adapter_cancel_reminder(self, timer):
        reminders = (await self._adapter_list_reminders())['reminders']
        matching = [entry for entry in reminders if isinstance(entry, dict) and entry.get('timer') == timer]
        if len(matching) != 1 or not isinstance(timer, str) or not re.fullmatch(r'omarchy-reminder-[0-9]+m-[0-9]+\.timer', timer):
            raise SkillError('reminder was not found; list reminders and use its exact timer id')
        unit = timer.removesuffix('.timer')
        await self._run(self._command('systemctl'), '--user', 'stop', timer, unit + '.service')
        reminder_dir = Path(os.getenv('XDG_RUNTIME_DIR') or '/tmp') / 'omarchy-reminders'
        try:
            (reminder_dir / (unit + '.message')).unlink(missing_ok=True)
        except OSError:
            pass
        return {'status': 'cancelled', 'timer': timer, 'system': 'omarchy'}

    @staticmethod
    def _todo_path():
        return Path(os.getenv('XDG_STATE_HOME') or (Path.home() / '.local/state')) / 'omarchy/todos.json'

    def _read_todos(self):
        path = self._todo_path()
        try:
            data = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
        except (OSError, json.JSONDecodeError):
            raise SkillError('could not read Omarchy Todo List data') from None
        if not isinstance(data, dict) or not isinstance(data.get('tasks', []), list):
            raise SkillError('Omarchy Todo List data has an invalid format')
        data.setdefault('tasks', [])
        return data

    async def _adapter_create_todo(self, title, description='', priority='medium'):
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
            raise SkillError('todo title must be 1 to 200 characters')
        if not isinstance(description, str) or len(description) > 1000:
            raise SkillError('todo description must be at most 1000 characters')
        if priority not in ('critical', 'high', 'medium', 'low'):
            raise SkillError('todo priority is critical, high, medium, or low')
        data = self._read_todos()
        now = int(time.time() * 1000)
        task = {'id': f'{now:x}-{uuid.uuid4().hex[:8]}', 'title': title.strip(), 'description': description.strip(),
                'priority': priority, 'status': 'ongoing', 'completed': False,
                'createdAt': now, 'completedAt': 0}
        data['version'] = 1
        data.setdefault('activeTab', 'ongoing')
        data.setdefault('tasks', [])
        data['tasks'].insert(0, task)
        self._write_todos(data)
        return {'status': 'created', 'todo': task, 'system': 'omarchy'}

    async def _adapter_list_todos(self, query='', status='all'):
        if not isinstance(query, str) or len(query) > 200 or status not in ('all', 'backlog', 'ongoing', 'complete'):
            raise SkillError('invalid todo filter')
        data = self._read_todos()
        tasks = [item for item in data['tasks'] if isinstance(item, dict) and
                 (status == 'all' or item.get('status') == status) and
                 (not query or query.casefold() in str(item.get('title', '')).casefold() or
                  query.casefold() in str(item.get('description', '')).casefold())]
        return {'tasks': tasks, 'count': len(tasks), 'system': 'omarchy'}

    def _write_todos(self, data):
        path = self._todo_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
        try:
            temporary.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    def _find_todo(self, data, task):
        needle = str(task).strip().casefold()
        matches = [item for item in data['tasks'] if isinstance(item, dict) and
                   (str(item.get('id', '')).casefold() == needle or
                    str(item.get('title', '')).casefold() == needle)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise SkillError('multiple todos have that title; use an id from list_todos')
        raise SkillError('todo was not found; use its exact title or id')

    async def _adapter_update_todo(self, task, title=None, description=None, priority=None):
        data = self._read_todos(); item = self._find_todo(data, task)
        if title is not None:
            if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200: raise SkillError('invalid todo title')
            item['title'] = title.strip()
        if description is not None:
            if not isinstance(description, str) or len(description) > 1000: raise SkillError('invalid todo description')
            item['description'] = description.strip()
        if priority is not None:
            if priority not in ('critical', 'high', 'medium', 'low'): raise SkillError('invalid todo priority')
            item['priority'] = priority
        self._write_todos(data)
        return {'status': 'updated', 'todo': item, 'system': 'omarchy'}

    async def _adapter_complete_todo(self, task, completed=True):
        data = self._read_todos(); item = self._find_todo(data, task)
        item['completed'] = bool(completed); item['status'] = 'complete' if item['completed'] else 'ongoing'
        item['completedAt'] = int(time.time() * 1000) if item['completed'] else 0
        self._write_todos(data)
        return {'status': 'completed' if item['completed'] else 'reopened', 'todo': item, 'system': 'omarchy'}

    async def _adapter_delete_todo(self, task):
        data = self._read_todos(); item = self._find_todo(data, task)
        data['tasks'] = [candidate for candidate in data['tasks'] if candidate is not item]
        self._write_todos(data)
        return {'status': 'deleted', 'todo': item, 'system': 'omarchy'}

    async def _adapter_clear_completed_todos(self):
        data = self._read_todos(); before = len(data['tasks'])
        data['tasks'] = [item for item in data['tasks'] if item.get('status') != 'complete' and not item.get('completed')]
        self._write_todos(data)
        return {'status': 'cleared', 'count': before - len(data['tasks']), 'system': 'omarchy'}

    async def _adapter_move_todo(self, task, status):
        if status not in ('backlog', 'ongoing', 'complete'):
            raise SkillError('todo status must be backlog, ongoing, or complete')
        data = self._read_todos()
        item = self._find_todo(data, task)
        item['status'] = status
        item['completed'] = status == 'complete'
        item['completedAt'] = int(time.time() * 1000) if status == 'complete' else 0
        self._write_todos(data)
        return {'status': 'moved', 'todo': item, 'system': 'omarchy'}

    async def _adapter_get_desktop_context(self):
        """Return a compact read-only snapshot of the current Omarchy desktop."""
        context = {
            'time': dt.datetime.now().astimezone().isoformat(timespec='seconds'),
        }
        hypr = self._commands.get('hyprctl')
        try:
            if not hypr: raise SkillError('hyprctl is not installed')
            active = json.loads(await self._run(hypr, 'activewindow', '-j', max_output=65536))
            if not isinstance(active, dict): raise ValueError('active window is not an object')
            context['active_window'] = {
                'title': active.get('title', ''), 'class': active.get('class', ''),
                'workspace': active.get('workspace', {}).get('name', active.get('workspace', {}).get('id')),
            }
        except (SkillError, json.JSONDecodeError, AttributeError):
            context['active_window'] = None
        try:
            if not hypr: raise SkillError('hyprctl is not installed')
            workspace = json.loads(await self._run(hypr, 'activeworkspace', '-j', max_output=65536))
            if not isinstance(workspace, dict): raise ValueError('workspace is not an object')
            context['workspace'] = {'id': workspace.get('id'), 'name': workspace.get('name')}
        except (SkillError, json.JSONDecodeError, AttributeError, ValueError):
            context['workspace'] = None
        try:
            network = await self._run(self._command('omarchy-network-status'), '--verbose')
            parts = network.splitlines()
            context['network'] = {'raw': network, 'lines': parts}
        except SkillError:
            context['network'] = None
        try:
            audio = await self._run(self._command('pactl'), 'get-sink-mute', '@DEFAULT_SINK@')
            volume = await self._run(self._command('pactl'), 'get-sink-volume', '@DEFAULT_SINK@')
            context['audio'] = {'muted': audio.lower().endswith('yes'),
                                'volume': volume,
                                'sink': await self._run(self._command('pactl'), 'get-default-sink')}
        except SkillError:
            context['audio'] = None
        try:
            battery = await self._run(self._command('omarchy-battery-status'), '--shell')
            context['battery'] = {'raw': battery, 'available': bool(battery)}
        except SkillError:
            context['battery'] = None
        try:
            context['brightness'] = await self._run(self._command('omarchy-brightness-display'))
            context['brightness_monitor'] = await self._run(
                self._command('omarchy-hyprland-monitor-focused'))
        except SkillError:
            context['brightness'] = None
        try:
            if hypr:
                clients_raw = await self._run(hypr, 'clients', '-j', max_output=65536)
                clients = json.loads(clients_raw)
                context['open_windows_count'] = len(clients) if isinstance(clients, list) else None
            else:
                context['open_windows_count'] = None
        except (SkillError, json.JSONDecodeError, TypeError):
            context['open_windows_count'] = None
        return context

    # ── Desktop awareness adapters ────────────────────────────────────

    async def _adapter_inspect_screen(self, region='full', extract_text=True):
        """Inspect what is currently visible on screen or active window, capturing visual layout and OCR text."""
        if region not in ('full', 'active'):
            raise SkillError('screen inspection region must be full or active')
        screenshots_dir = Path(os.getenv('XDG_RUNTIME_DIR') or '/tmp') / 'jarvis_screen'
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        filename = str(screenshots_dir / f'inspect_{int(time.time() * 1000)}.png')

        args = [self._command('grim')]
        active_window_info = None
        hyprctl = self._commands.get('hyprctl')
        if hyprctl:
            try:
                raw_active = await self._run(hyprctl, 'activewindow', '-j', max_output=65536)
                parsed = json.loads(raw_active)
                if isinstance(parsed, dict):
                    ws = parsed.get('workspace', {})
                    ws_val = ws.get('name', ws.get('id')) if isinstance(ws, dict) else ws
                    active_window_info = {
                        'title': parsed.get('title', ''),
                        'class': parsed.get('class', ''),
                        'workspace': ws_val,
                    }
                    if region == 'active':
                        at = parsed.get('at', [0, 0])
                        size = parsed.get('size', [1920, 1080])
                        args.extend(['-g', f'{at[0]},{at[1]} {size[0]}x{size[1]}'])
            except (SkillError, json.JSONDecodeError, KeyError):
                pass

        args.append(filename)
        await self._run(*args, timeout=10)

        extracted_text = None
        if extract_text:
            try:
                tesseract = self._command('tesseract')
                raw_ocr = await self._run(tesseract, filename, 'stdout', '--oem', '1', '-l', 'eng', timeout=15)
                lines = [line.strip() for line in raw_ocr.splitlines()]
                cleaned_lines = [l for l in lines if l]
                extracted_text = '\n'.join(cleaned_lines)[:3000]
            except SkillError as err:
                log.warning('OCR extraction failed: %s', err)
                extracted_text = ''

        return {
            'status': 'inspected',
            'region': region,
            'active_window': active_window_info,
            'text_content': extracted_text,
            'screenshot_path': filename,
        }

    async def _adapter_list_windows(self, workspace=None):
        """List open application windows across workspaces."""
        if workspace is not None and (isinstance(workspace, bool) or not isinstance(workspace, int) or workspace < 1):
            raise SkillError('invalid workspace number')
        hypr = self._command('hyprctl')
        raw = await self._run(hypr, 'clients', '-j', max_output=131072)
        try:
            clients = json.loads(raw)
        except json.JSONDecodeError:
            raise SkillError('could not parse window list from Hyprland') from None
        if not isinstance(clients, list):
            raise SkillError('invalid window data received from Hyprland')

        windows = []
        for c in clients:
            if not isinstance(c, dict):
                continue
            ws = c.get('workspace', {})
            ws_id = ws.get('id') if isinstance(ws, dict) else ws
            if workspace is not None and ws_id != workspace:
                continue
            windows.append({
                'title': c.get('title', ''),
                'class': c.get('class', ''),
                'workspace': ws_id,
                'address': c.get('address', ''),
                'focused': bool(c.get('focusHistoryID') == 0),
                'floating': bool(c.get('floating', False)),
                'fullscreen': bool(c.get('fullscreen', 0) != 0),
            })
        return {'windows': windows, 'count': len(windows)}

    async def _adapter_focus_window(self, query):
        """Focus an open window by class, title substring, or address."""
        if not isinstance(query, str) or not query.strip():
            raise SkillError('query must be non-empty text')
        needle = query.strip().casefold()
        clients_res = await self._adapter_list_windows()
        windows = clients_res.get('windows', [])

        match = None
        # Priority 1: Exact address match or exact class match
        for w in windows:
            if w.get('address', '').casefold() == needle or w.get('class', '').casefold() == needle:
                match = w
                break

        # Priority 2: Substring class match
        if match is None:
            for w in windows:
                if needle in w.get('class', '').casefold():
                    match = w
                    break

        # Priority 3: Substring title match
        if match is None:
            for w in windows:
                if needle in w.get('title', '').casefold():
                    match = w
                    break

        if match is None:
            raise SkillError(f'no open window found matching "{query}"')

        hypr = self._command('hyprctl')
        address = match['address']
        lua_cmd = f'hl.dsp.focus({{ window = "address:{address}" }})'
        try:
            await self._run(hypr, 'dispatch', lua_cmd)
        except SkillError:
            await self._run(hypr, 'dispatch', 'focuswindow', f'address:{address}')

        return {'status': 'focused', 'window': match}

    async def _adapter_list_workspaces(self):
        """List active desktop workspaces, their window count, and focused workspace."""
        hypr = self._command('hyprctl')
        raw_ws = await self._run(hypr, 'workspaces', '-j', max_output=65536)
        raw_active = await self._run(hypr, 'activeworkspace', '-j', max_output=65536)
        try:
            workspaces = json.loads(raw_ws)
            active = json.loads(raw_active)
        except json.JSONDecodeError:
            raise SkillError('could not parse workspace list from Hyprland') from None

        formatted = []
        if isinstance(workspaces, list):
            for ws in workspaces:
                if isinstance(ws, dict):
                    formatted.append({
                        'id': ws.get('id'),
                        'name': ws.get('name', str(ws.get('id'))),
                        'windows': ws.get('windows', 0),
                    })
        formatted.sort(key=lambda item: item['id'] if isinstance(item.get('id'), int) else 0)
        active_id = active.get('id') if isinstance(active, dict) else None
        return {
            'active_workspace': active_id,
            'workspaces': formatted,
            'count': len(formatted),
        }

    async def _adapter_get_system_resources(self):
        """Check real-time hardware health and system performance metrics."""
        load1, load5, load15 = os.getloadavg()
        cpu_count = os.cpu_count() or 1
        cpu_pct = round((load1 / cpu_count) * 100, 1)

        mem = {}
        try:
            with open('/proc/meminfo', 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.split(':')
                    if len(parts) == 2:
                        mem[parts[0].strip()] = int(parts[1].strip().split()[0])
        except (OSError, ValueError):
            pass

        total_kb = mem.get('MemTotal', 1)
        avail_kb = mem.get('MemAvailable', 0)
        ram_pct = round(((total_kb - avail_kb) / total_kb) * 100, 1)

        disk = shutil.disk_usage('/')
        disk_total = getattr(disk, 'total', disk[0] if isinstance(disk, (list, tuple)) else 1)
        disk_used = getattr(disk, 'used', disk[1] if isinstance(disk, (list, tuple)) else 0)
        disk_pct = round((disk_used / disk_total) * 100, 1) if disk_total else 0.0

        uptime_hours = 0.0
        try:
            with open('/proc/uptime', 'r', encoding='utf-8') as f:
                uptime_hours = round(float(f.read().split()[0]) / 3600, 2)
        except (OSError, ValueError, IndexError):
            pass

        top_procs = []
        try:
            ps_cmd = self._command('ps')
            raw_ps = await self._run(ps_cmd, '-eo', 'comm,%cpu,%mem', '--sort=-%cpu', '--no-headers', timeout=5)
            for line in raw_ps.splitlines()[:5]:
                parts = line.split()
                if len(parts) >= 3:
                    top_procs.append({
                        'name': parts[0],
                        'cpu_percent': float(parts[1]),
                        'mem_percent': float(parts[2]),
                    })
        except (SkillError, ValueError):
            pass

        return {
            'cpu_load_percent': cpu_pct,
            'cpu_cores': cpu_count,
            'load_averages': [load1, load5, load15],
            'ram_total_gb': round(total_kb / 1024 / 1024, 2),
            'ram_used_gb': round((total_kb - avail_kb) / 1024 / 1024, 2),
            'ram_used_percent': ram_pct,
            'disk_total_gb': round(disk_total / 1024**3, 2),
            'disk_used_percent': disk_pct,
            'uptime_hours': uptime_hours,
            'top_processes': top_procs,
        }

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
        filename = str(Path(pictures_dir) / f'screenshot_{int(time.time())}.png')
        args = [self._command('grim')]
        if region == 'active':
            # Capture the active window by getting its geometry from hyprctl
            hyprctl = self._commands.get('hyprctl')
            if hyprctl:
                try:
                    info = await self._run(hyprctl, 'activewindow', '-j')
                    window = json.loads(info)
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
        lua_map = {
            'fullscreen': 'hl.dsp.window.fullscreen({ mode = "fullscreen" })',
            'maximize': 'hl.dsp.window.fullscreen({ mode = "maximized" })',
            'close': 'hl.dsp.window.close()',
            'minimize': 'hl.dsp.window.move({ workspace = "special:scratchpad", follow = false })',
            'float': 'hl.dsp.window.float({ action = "toggle" })',
            'center': 'hl.dsp.window.center()',
        }
        legacy_map = {
            'fullscreen': ['fullscreen'],
            'maximize': ['fullscreen', '1'],
            'close': ['killactive'],
            'minimize': ['movetospecialsilent'],
            'float': ['togglefloating'],
            'center': ['centerwindow'],
        }
        if action not in lua_map:
            valid = ', '.join(sorted(lua_map))
            raise SkillError(f'window action must be one of: {valid}')
        hypr = self._command('hyprctl')
        try:
            await self._run(hypr, 'dispatch', lua_map[action])
        except SkillError:
            await self._run(hypr, 'dispatch', *legacy_map[action])
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
