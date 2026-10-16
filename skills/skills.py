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
import contextlib
import datetime as dt
import ipaddress
import json
import logging
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import time
import uuid
from urllib.parse import urlsplit
import filesystem as fs
from task_runner import TaskPlanError, TaskRunner
from agent_orchestrator import AgentOrchestrator, OrchestrationError
from orchestration.desktop_execution import DesktopAgentOrchestrator
from orchestration.evolution import EvolutionManager
from connectors import google_workspace
from connectors import github
from connectors import internet_search as web_search
from config import MemoryConfig
from core.workers import BoundedWorker, WorkerBusyError
from jarvis_memory.bridge import MemoryBridge, MemoryError as BridgeMemoryError
try:
    from skills.input_bar import TestBar
except ImportError:
    from test_bar import TestBar
from proactive.runtime import ProactiveRuntime
from jarvis_memory.paths import get_config_dir
try:
    from skills import system_control
except ImportError:
    import system_control

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
        'web.search': '_adapter_internet_search',
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
        'evolution.start': '_adapter_start_development',
        'evolution.request': '_adapter_request_capability',
        'evolution.status': '_adapter_development_status',
        'evolution.list': '_adapter_list_development_jobs',
        'evolution.cancel': '_adapter_cancel_development',
        'google.gmail_search': '_adapter_google_gmail_search',
        'google.gmail_read': '_adapter_google_gmail_read',
        'google.gmail_create_draft': '_adapter_google_gmail_create_draft',
        'google.gmail_send_draft': '_adapter_google_gmail_send_draft',
        'google.gmail_list_labels': '_adapter_google_gmail_list_labels',
        'google.calendar_list_events': '_adapter_google_calendar_list_events',
        'google.calendar_get_event': '_adapter_google_calendar_get_event',
        'google.calendar_create_event': '_adapter_google_calendar_create_event',
        'google.calendar_list_calendars': '_adapter_google_calendar_list_calendars',
        'google.tasks_list_lists': '_adapter_google_tasks_list_lists',
        'google.tasks_list_tasks': '_adapter_google_tasks_list_tasks',
        'google.tasks_create_task': '_adapter_google_tasks_create_task',
        'google.tasks_complete_task': '_adapter_google_tasks_complete_task',
        'google.google_authorize': '_adapter_google_authorize',
        'google.google_connection_status': '_adapter_google_connection_status',
        'google.drive_search_files': '_adapter_google_drive_search_files',
        'google.drive_get_file': '_adapter_google_drive_get_file',
        'google.drive_read_text_file': '_adapter_google_drive_read_text_file',
        'google.docs_read_document': '_adapter_google_docs_read_document',
        'google.sheets_get_spreadsheet': '_adapter_google_sheets_get_spreadsheet',
        'google.sheets_read_range': '_adapter_google_sheets_read_range',
        'github.authorize': '_adapter_github_authorize',
        'github.status': '_adapter_github_connection_status',
        'github.repositories': '_adapter_github_list_repositories',
        'github.repository': '_adapter_github_get_repository',
        'github.files': '_adapter_github_list_repository_files',
        'github.file': '_adapter_github_read_repository_file',
        'github.find_relevant_files': '_adapter_github_find_relevant_files',
        'github.read_repository_files': '_adapter_github_read_repository_files',
        'github.analyze_repository': '_adapter_github_analyze_repository',
        'github.issues': '_adapter_github_list_issues',
        'github.issue': '_adapter_github_get_issue',
        'github.pulls': '_adapter_github_list_pull_requests',
        'github.pull': '_adapter_github_get_pull_request',
        'memory.remember': '_adapter_remember_memory',
        'memory.recall': '_adapter_recall_memory',
        'memory.forget': '_adapter_forget_memory',
        'memory.clear': '_adapter_clear_memory',
        'memory.profile': '_adapter_update_memory_profile',
        'memory.index': '_adapter_index_memory_document',
        'memory.status': '_adapter_memory_status',
        'memory.obsidian': '_adapter_sync_memory_vault',
        'memory.correct': '_adapter_correct_memory',
        'memory.history': '_adapter_memory_history',
        'filesystem.delete': '_adapter_delete_path',
        'filesystem.info': '_adapter_inspect_path',
        'filesystem.grep': '_adapter_search_file_content',
        'screen.inspect': '_adapter_inspect_screen',
        'window.list': '_adapter_list_windows',
        'window.focus': '_adapter_focus_window',
        'workspace.list': '_adapter_list_workspaces',
        'input_bar.open': '_adapter_open_input_bar',
        'input_bar.close': '_adapter_close_input_bar',
        'proactive.enqueue': '_adapter_proactive_task',
        'proactive.status': '_adapter_proactive_status',
        'proactive.pause': '_adapter_proactive_pause',
        'proactive.resume': '_adapter_proactive_resume',
        'proactive.stop': '_adapter_proactive_stop',
        'system.resources': '_adapter_get_system_resources',
        'input.type': '_adapter_type_text',
        'input.key': '_adapter_press_key',
        'system.keybindings_list': '_adapter_list_desktop_commands',
        'system.keybindings_exec': '_adapter_execute_desktop_command',
        'shell.bar_list': '_adapter_list_bar_panels',
        'shell.bar_open': '_adapter_open_bar_panel',
        'shell.bar_close': '_adapter_close_bar_panel',
        'audio.volume_set': '_adapter_set_volume',
        'audio.mic_control': '_adapter_control_microphone',
        'display.brightness_set': '_adapter_set_brightness',
        'window.move_workspace': '_adapter_move_window_workspace',
        'vision.control_mode': '_adapter_control_vision_mode',
        'vision.capture_frame': '_adapter_capture_camera_frame',
        'vision.check_hardware': '_adapter_check_vision_hardware',
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
        'evolution.start': ('git', 'bwrap'),
        'evolution.request': ('git', 'bwrap'),
        'evolution.status': (),
        'evolution.list': (),
        'evolution.cancel': (),
        'google.gmail_search': (), 'google.gmail_read': (),
        'google.gmail_create_draft': (), 'google.gmail_send_draft': (),
        'google.gmail_list_labels': (),
        'google.calendar_list_events': (), 'google.calendar_get_event': (),
        'google.calendar_create_event': (), 'google.calendar_list_calendars': (),
        'google.tasks_list_lists': (), 'google.tasks_list_tasks': (),
        'google.tasks_create_task': (), 'google.tasks_complete_task': (),
        'google.google_authorize': (), 'google.google_connection_status': (),
        'google.drive_search_files': (), 'google.drive_get_file': (),
        'google.drive_read_text_file': (), 'google.docs_read_document': (),
        'google.sheets_get_spreadsheet': (), 'google.sheets_read_range': (),
        'github.authorize': (), 'github.status': (), 'github.repositories': (), 'github.repository': (),
        'github.files': (), 'github.file': (),
        'github.issues': (), 'github.issue': (), 'github.pulls': (), 'github.pull': (),
        'memory.remember': (),
        'memory.recall': (),
        'memory.forget': (),
        'memory.clear': (),
        'memory.profile': (),
        'memory.index': (),
        'memory.status': (),
        'memory.obsidian': (),
        'memory.correct': (),
        'memory.history': (),
        'filesystem.delete': (),
        'filesystem.info': (),
        'filesystem.grep': (),
        'screen.inspect': ('grim', 'tesseract'),
        'window.list': ('hyprctl',),
        'window.focus': ('hyprctl',),
        'workspace.list': ('hyprctl',),
        'input_bar.open': ('omarchy-launch-webapp',),
        'input_bar.close': ('hyprctl',),
        'proactive.enqueue': (), 'proactive.status': (), 'proactive.pause': (),
        'proactive.resume': (), 'proactive.stop': (),
        'system.resources': ('ps',),
        'input.type': ('wtype',),
        'input.key': ('wtype',),
        'system.keybindings_list': ('bash',),
        'system.keybindings_exec': ('bash',),
        'shell.bar_list': ('omarchy-shell',),
        'shell.bar_open': ('omarchy-shell',),
        'shell.bar_close': ('omarchy-shell',),
        'audio.volume_set': ('wpctl',),
        'audio.mic_control': ('wpctl',),
        'display.brightness_set': ('brightnessctl',),
        'window.move_workspace': ('hyprctl',),
        'vision.control_mode': (),
        'vision.capture_frame': ('vision_ctrl',),
        'vision.check_hardware': ('vision_ctrl',),
    }

    def __init__(self, manifest_dirs=None, *, config=None,
                 exclude_unavailable=False, app_name=None, api_key=''):
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
            local_manifests = Path(__file__).resolve().parent / 'manifests'
            root_manifests = Path(__file__).resolve().parents[1] / 'skill_manifests'
            manifest_dirs = [local_manifests if local_manifests.is_dir() else root_manifests]
        self.manifest_dirs = [Path(directory) for directory in manifest_dirs]
        self._skills = self._load_manifests()
        self._memory_config = config.memory if config else MemoryConfig()
        self._memory_api_key = api_key
        self._search_key_cooldown = {}
        self._memory = None
        self._memory_worker = BoundedWorker('jarvis-memory', capacity=16)
        self._file_worker = BoundedWorker('jarvis-files', capacity=16)
        self._memory_writes = set()
        if not self._memory_config.enabled:
            self._skills = {name: spec for name, spec in self._skills.items()
                            if not spec['adapter'].startswith('memory.') or spec['adapter'] == 'memory.status'}
        self._task_runner = TaskRunner(self.execute, self._valid_task_step)
        self._agent_orchestrator = DesktopAgentOrchestrator()
        self._evolution = None
        self.test_bar = TestBar()
        self._proactive = None
        self.vision_mode = 'off'
        self.on_vision_mode_change = None

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
            elif name == 'vision_ctrl':
                local_native = Path(__file__).resolve().parent / 'native' / 'bin' / 'vision_ctrl'
                if local_native.is_file() and os.access(str(local_native), os.X_OK):
                    commands[name] = str(local_native)
                else:
                    commands[name] = shutil.which(name)
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
        if kind not in ('object', 'string', 'integer', 'boolean', 'array'):
            raise SkillError('skill schema type is not allowed')
        allowed_by_type = {
            'object': {'type', 'properties', 'required', 'additionalProperties', 'description'},
            'string': {'type', 'description', 'enum'},
            'integer': {'type', 'description', 'enum', 'minimum', 'maximum'},
            'boolean': {'type', 'description', 'enum'},
            'array': {'type', 'description', 'items', 'minItems', 'maxItems'},
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
        if kind == 'array':
            minimum, maximum = schema.get('minItems', 0), schema.get('maxItems', 16)
            if (type(minimum) is not int or type(maximum) is not int or
                    not 0 <= minimum <= maximum <= 16 or 'items' not in schema):
                raise SkillError('invalid bounded array skill schema')
            self._validate_schema(schema['items'], depth=depth + 1)
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
        if kind == 'array':
            return (isinstance(value, list) and
                    schema.get('minItems', 0) <= len(value) <= schema.get('maxItems', 16) and
                    all(self._arguments_match(item, schema['items']) for item in value))
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

    async def _adapter_delegate_agent(self, agent, prompt, workspace, timeout_seconds=900, task_type=None):
        try:
            options = {'task_type': task_type} if task_type is not None else {}
            return self._agent_orchestrator.delegate(agent, prompt, workspace, timeout_seconds, **options)
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

    async def _adapter_type_text(self, text):
        return await system_control.type_text(text)

    @property
    def evolution(self):
        if self._evolution is None:
            self._evolution = EvolutionManager(
                self._agent_orchestrator,
                can_run=lambda: self.proactive.control.get_state().can_run)
        return self._evolution

    async def _adapter_start_development(self, goal, workspace, agent='codex'):
        try:
            return await self.evolution.start(goal, workspace, agent)
        except (OrchestrationError, OSError) as error:
            raise SkillError(str(error)) from None

    async def _adapter_request_capability(self, request, workspace, agent='codex'):
        """Turn an unsupported user request into a tracked capability proposal."""
        goal = (
            'Build the missing JARVIS capability needed for this user request. '
            'Expose it as a declared skill with strict arguments, implement it using '
            'the existing approved adapter patterns, add tests, and document how it is used. '
            'Original user request: ' + request.strip()
        )
        try:
            return await self.evolution.start(goal, workspace, agent,
                                              requested_action=request.strip())
        except (OrchestrationError, OSError, AttributeError) as error:
            raise SkillError(str(error)) from None

    async def _adapter_development_status(self, job_id):
        try:
            manager = self._evolution or EvolutionManager(None, read_only=True)
            response = manager.status(job_id)
            job = response['job']
            # Keep voice tool context bounded; full evidence remains on disk/CLI.
            job.pop('commands', None)
            job['diff_truncated'] = job['diff_truncated'] or len(job['diff']) > 8000
            job['diff'] = job['diff'][:8000]
            for evidence in [*job['stages'], job['tests'], job['baseline_tests']]:
                if evidence:
                    output = evidence.get('output', '')
                    evidence['output_truncated'] = evidence.get('output_truncated', False) or len(output) > 3000
                    evidence['output'] = output[-3000:]
            return response
        except (OrchestrationError, OSError) as error:
            raise SkillError(str(error)) from None

    async def _adapter_list_development_jobs(self):
        try:
            manager = self._evolution or EvolutionManager(None, read_only=True)
            return manager.list_jobs()
        except (OrchestrationError, OSError) as error:
            raise SkillError(str(error)) from None

    async def _adapter_cancel_development(self, job_id):
        try:
            return await self.evolution.cancel(job_id)
        except (OrchestrationError, OSError) as error:
            raise SkillError(str(error)) from None

    async def _google(self, tool, arguments):
        try:
            result = await google_workspace.dispatch(tool, arguments)
            if isinstance(result, dict) and result.get('setup_required'):
                result.setdefault('message', result.get('error') or
                                  "Say 'open Google authorization' to connect your Google account.")
            return result
        except (OSError, RuntimeError, ValueError) as error:
            raise SkillError(str(error)) from None

    async def _adapter_google_gmail_search(self, query, max_results=10):
        return await self._google('gmail_search', {'query': query, 'max_results': max_results})

    async def _adapter_google_gmail_read(self, message_id):
        return await self._google('gmail_read', {'message_id': message_id})

    async def _adapter_google_gmail_create_draft(self, to, subject, body, cc=''):
        return await self._google('gmail_create_draft', {'to': to, 'subject': subject, 'body': body, 'cc': cc})

    async def _adapter_google_gmail_send_draft(self, draft_id):
        return await self._google('gmail_send_draft', {'draft_id': draft_id})

    async def _adapter_google_gmail_list_labels(self):
        return await self._google('gmail_list_labels', {})

    async def _adapter_google_calendar_list_events(self, **arguments):
        return await self._google('calendar_list_events', arguments)

    async def _adapter_google_calendar_get_event(self, event_id, calendar_id='primary'):
        return await self._google('calendar_get_event', {'event_id': event_id, 'calendar_id': calendar_id})

    async def _adapter_google_calendar_create_event(self, summary, start_datetime, end_datetime,
                                                    description='', location='', attendees=None,
                                                    calendar_id='primary'):
        return await self._google('calendar_create_event', {
            'summary': summary, 'start_datetime': start_datetime, 'end_datetime': end_datetime,
            'description': description, 'location': location,
            'attendees': ([item.strip() for item in attendees.split(',') if item.strip()]
                          if isinstance(attendees, str) else attendees),
            'calendar_id': calendar_id})

    async def _adapter_google_calendar_list_calendars(self):
        return await self._google('calendar_list_calendars', {})

    async def _adapter_google_tasks_list_lists(self):
        return await self._google('tasks_list_lists', {})

    async def _adapter_google_tasks_list_tasks(self, list_id='@default'):
        return await self._google('tasks_list_tasks', {'list_id': list_id})

    async def _adapter_google_tasks_create_task(self, title, list_id='@default'):
        return await self._google('tasks_create_task', {'title': title, 'list_id': list_id})

    async def _adapter_google_tasks_complete_task(self, task_id, list_id='@default'):
        return await self._google('tasks_complete_task', {'task_id': task_id, 'list_id': list_id})

    async def _adapter_google_authorize(self):
        return await self._google('google_authorize', {})

    async def _adapter_google_connection_status(self):
        return await self._google('google_connection_status', {})

    async def _adapter_google_drive_search_files(self, query='', max_results=10):
        return await self._google('drive_search_files', {'query': query, 'max_results': max_results})

    async def _adapter_google_drive_get_file(self, file_id):
        return await self._google('drive_get_file', {'file_id': file_id})

    async def _adapter_google_drive_read_text_file(self, file_id):
        return await self._google('drive_read_text_file', {'file_id': file_id})

    async def _adapter_google_docs_read_document(self, document_id):
        return await self._google('docs_read_document', {'document_id': document_id})

    async def _adapter_google_sheets_get_spreadsheet(self, spreadsheet_id):
        return await self._google('sheets_get_spreadsheet', {'spreadsheet_id': spreadsheet_id})

    async def _adapter_google_sheets_read_range(self, spreadsheet_id, cell_range='A1:J25'):
        return await self._google('sheets_read_range', {'spreadsheet_id': spreadsheet_id, 'cell_range': cell_range})

    async def _adapter_github_connection_status(self):
        return await github.dispatch('github_connection_status', {})

    async def _adapter_github_authorize(self):
        return await github.dispatch('github_authorize', {})

    async def _adapter_github_list_repositories(self, max_results=20):
        return await github.dispatch('github_list_repositories', {'max_results': max_results})

    async def _adapter_github_get_repository(self, owner, repository):
        return await github.dispatch('github_get_repository', {'owner': owner, 'repository': repository})

    async def _adapter_github_list_repository_files(self, owner, repository, path=''):
        return await github.dispatch('github_list_repository_files', {
            'owner': owner, 'repository': repository, 'path': path})

    async def _adapter_github_read_repository_file(self, owner, repository, path):
        return await github.dispatch('github_read_repository_file', {
            'owner': owner, 'repository': repository, 'path': path})

    async def _adapter_github_find_relevant_files(self, owner, repository, query='', max_results=20):
        return await github.dispatch('github_find_relevant_files', {
            'owner': owner, 'repository': repository, 'query': query,
            'max_results': max_results})

    async def _adapter_github_read_repository_files(self, owner, repository, ref, paths):
        return await github.dispatch('github_read_repository_files', {
            'owner': owner, 'repository': repository, 'ref': ref, 'paths': paths})

    async def _adapter_github_analyze_repository(self, owner, repository, query=''):
        return await github.dispatch('github_analyze_repository', {
            'owner': owner, 'repository': repository, 'query': query})

    async def _adapter_github_list_issues(self, owner, repository, state='open', max_results=20):
        return await github.dispatch('github_list_issues', {
            'owner': owner, 'repository': repository, 'state': state, 'max_results': max_results})

    async def _adapter_github_get_issue(self, owner, repository, number):
        return await github.dispatch('github_get_issue', {'owner': owner, 'repository': repository, 'number': number})

    async def _adapter_github_list_pull_requests(self, owner, repository, state='open', max_results=20):
        return await github.dispatch('github_list_pull_requests', {
            'owner': owner, 'repository': repository, 'state': state, 'max_results': max_results})

    async def _adapter_github_get_pull_request(self, owner, repository, number):
        return await github.dispatch('github_get_pull_request', {'owner': owner, 'repository': repository, 'number': number})

    async def _adapter_press_key(self, key, modifiers=None):
        return await system_control.press_key(key, modifiers)

    async def _adapter_list_desktop_commands(self, query=None, limit=25):
        return await system_control.list_desktop_commands(query=query, limit=limit)

    async def _adapter_execute_desktop_command(self, title):
        return await system_control.execute_desktop_command(title)

    async def _adapter_list_bar_panels(self):
        return await system_control.list_bar_panels()

    async def _adapter_open_bar_panel(self, panel_id):
        return await system_control.open_bar_panel(panel_id)

    async def _adapter_close_bar_panel(self, panel_id):
        return await system_control.close_bar_panel(panel_id)

    async def _adapter_set_volume(self, percent):
        return await system_control.set_volume(percent)

    async def _adapter_control_microphone(self, action):
        return await system_control.control_microphone(action)

    async def _adapter_set_brightness(self, percent):
        return await system_control.set_brightness(percent)

    async def _adapter_move_window_workspace(self, workspace):
        return await system_control.move_window_to_workspace(workspace)

    async def close_agent_jobs(self):
        try:
            if self._proactive is not None:
                await self._proactive.close()
            if self._evolution is not None:
                await self._evolution.close()
            await self._agent_orchestrator.close()
        finally:
            self.test_bar.close()
            if self._memory_writes:
                await asyncio.gather(*tuple(self._memory_writes), return_exceptions=True)
            try:
                await self._memory_worker.close(
                    finalizer=self._memory.close if self._memory is not None else None)
            finally:
                await self._file_worker.close()

    async def _adapter_open_input_bar(self):
        url = self.test_bar.start()
        overlay_script = os.path.join(os.path.dirname(__file__), 'overlay_client.py')
        if os.path.isfile(overlay_script) and os.path.isfile('/usr/bin/python3'):
            try:
                proc = await asyncio.create_subprocess_exec(
                    '/usr/bin/python3', '-c',
                    'import gi; gi.require_version("WebKit2", "4.1"); from gi.repository import WebKit2',
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                if await proc.wait() == 0:
                    await self._launch('/usr/bin/python3', overlay_script, url)
                    return {'status': 'opened', 'accepts': ['text', 'image', 'audio', 'pdf', 'file']}
            except Exception:
                pass
        await self._launch(self._command('omarchy-launch-webapp'), url)
        return {'status': 'opened', 'accepts': ['text', 'image', 'audio', 'pdf', 'file']}

    async def _adapter_close_input_bar(self):
        closed = self.test_bar.close()
        windows = await self._adapter_list_windows()
        matches = [item for item in windows['windows']
                   if 'jarvis input bar' in item.get('title', '').casefold()
                   or 'jarvisinputbar' in item.get('class', '').casefold()]
        hypr = self._command('hyprctl')
        for item in matches:
            addr = item.get('address', '')
            try:
                await self._run(hypr, 'dispatch', f'hl.dsp.window.close({{ window = "address:{addr}" }})')
            except SkillError:
                try:
                    await self._run(hypr, 'dispatch', 'closewindow', 'address:' + addr)
                except SkillError:
                    pass
        return {'status': 'closed' if closed or matches else 'already_closed',
                'windows_closed': len(matches)}

    async def _adapter_proactive_task(self, prompt, workspace, agent=None, artifact_check=None):
        runtime = await self.get_proactive()
        return await runtime.call('enqueue', prompt, workspace, agent, authorized=True,
                                  verification=[artifact_check] if artifact_check is not None else None)

    async def _adapter_proactive_status(self):
        runtime = await self.get_proactive()
        return await runtime.call('status')

    async def _adapter_proactive_pause(self):
        runtime = await self.get_proactive()
        result = await runtime.call('pause')
        await self._cancel_active_development()
        return result

    async def _adapter_proactive_resume(self):
        runtime = await self.get_proactive()
        return await runtime.call('resume')

    async def _adapter_proactive_stop(self):
        runtime = await self.get_proactive()
        result = await runtime.stop_all()
        await self._cancel_active_development()
        return result

    async def _cancel_active_development(self):
        if self._evolution is not None:
            for job_id in list(self._evolution.workers):
                await self._evolution.cancel(job_id)

    @property
    def memory(self):
        if self._memory is None:
            self._memory = MemoryBridge(self._memory_config, api_key=self._memory_api_key)
        return self._memory

    @property
    def proactive(self):
        if self._proactive is None:
            memory_root = (Path(self._memory_config.path).expanduser() if self._memory_config.path
                           else get_config_dir())
            self._proactive = ProactiveRuntime(memory_root / 'proactive', self._agent_orchestrator)
        return self._proactive

    def memory_context(self):
        try:
            return self.memory.context()
        except (OSError, ValueError, sqlite3.Error) as error:
            log.warning('Memory recall unavailable: %s', type(error).__name__)
            return ''

    async def memory_call(self, method, *args, **kwargs):
        def invoke():
            return getattr(self.memory, method)(*args, **kwargs)
        return await self._memory_worker.run(invoke)

    def queue_memory_exchange(self, user, assistant):
        if not user and not assistant:
            return
        self.queue_memory_job(self.memory_call('record_exchange', user, assistant))

    def queue_memory_job(self, operation):
        if len(self._memory_writes) >= 16:
            log.warning('Memory capture backlog full; dropping exchange')
            operation.close()
            return
        task = asyncio.create_task(operation)
        self._memory_writes.add(task)
        def finished(done):
            self._memory_writes.discard(done)
            try:
                done.result()
            except asyncio.CancelledError:
                pass
            except Exception as error:
                log.warning('Memory capture failed: %s', type(error).__name__)
        task.add_done_callback(finished)

    async def get_proactive(self):
        return await self._file_worker.run(lambda: self.proactive)

    async def _memory_operation(self, method, **arguments):
        try:
            return await self.memory_call(method, **arguments)
        except (BridgeMemoryError, OSError, UnicodeError, sqlite3.Error, WorkerBusyError) as error:
            raise SkillError(str(error)) from None

    async def _adapter_remember_memory(self, text):
        return await self._memory_operation('remember', text=text)

    async def _adapter_recall_memory(self, query='', limit=20):
        return await self._memory_operation('recall', query=query, limit=limit)

    async def _adapter_forget_memory(self, text):
        return await self._memory_operation('forget', text=text)

    async def _adapter_clear_memory(self):
        return await self._memory_operation('clear')

    async def _adapter_update_memory_profile(self, name, content):
        return await self._memory_operation('update_profile', name=name, content=content)

    async def _adapter_index_memory_document(self, path):
        return await self._memory_operation('index_document', path=path)

    async def _adapter_memory_status(self):
        return await self._memory_operation('status')

    async def _adapter_sync_memory_vault(self):
        return await self._memory_operation('sync_obsidian')

    async def _adapter_correct_memory(self, memory_id, text, reason=''):
        return await self._memory_operation('correct', memory_id=memory_id, text=text, reason=reason)

    async def _adapter_memory_history(self, memory_id):
        return await self._memory_operation('memory_history', memory_id=memory_id)

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
            return await self._file_worker.run(operation, *args, **kwargs)
        except (fs.FileOperationError, WorkerBusyError) as error:
            raise SkillError(str(error)) from None

    async def _adapter_list_files(self, path=None, limit=100, include_hidden=True):
        path = path or str(Path.home())
        return await self._file_operation(fs.list_directory, path, limit, include_hidden)

    async def _adapter_read_file(self, path, offset=0, max_chars=20000):
        return await self._file_operation(fs.read_text, path, offset, max_chars)

    async def _adapter_search_files(self, query, path=None, limit=50, include_hidden=False):
        path = path or str(Path.home())
        return await self._file_operation(fs.search_files, path, query, limit, include_hidden)

    async def _adapter_search_file_content(self, query, path=None, limit=30):
        path = path or str(Path.home())
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

    async def _adapter_internet_search(self, query):
        """Return bounded sources using Brave, Gemini grounding, or Wikipedia."""
        if not isinstance(query, str) or not query.strip() or len(query) > 500:
            raise SkillError('search query must be 1 to 500 characters')
        query = query.strip()
        if web_search.brave_available():
            try:
                return await web_search.brave_search(query)
            except web_search.SearchProviderError as error:
                log.warning('Brave Search unavailable: %s', error)
        configured = self._memory_api_key
        configured = configured if isinstance(configured, (list, tuple)) else [configured]
        keys = list(dict.fromkeys(key for key in configured if key))
        failure = 'internet search requires a configured Gemini or Brave Search API key'
        if keys:
            from google import genai
            deadline = time.monotonic() + 30
            for key in keys:
                if time.monotonic() >= deadline:
                    failure = 'internet search timed out; please try again'
                    break
                if self._search_key_cooldown.get(key, 0) > time.monotonic():
                    continue
                skip_key = False
                newer_model_quota = False
                for model in web_search.GROUNDING_MODELS:
                    if newer_model_quota and model.startswith('gemini-3.'):
                        continue
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        failure = 'internet search timed out; please try again'
                        break
                    try:
                        async with genai.Client(api_key=key).aio as client:
                            result = await asyncio.wait_for(client.models.generate_content(
                                model=model, contents=query,
                                config={'tools': [{'google_search': {}}], 'temperature': 0,
                                        'automatic_function_calling': {'disable': True}}),
                                timeout=min(8, remaining))
                    except TimeoutError:
                        failure = 'internet search timed out; please try again'
                        skip_key = True
                        break
                    except Exception as error:
                        code = getattr(error, 'code', getattr(error, 'status_code', None))
                        if code == 429:
                            failure = 'internet search quota is currently exhausted'
                            if model.startswith('gemini-3.'):
                                newer_model_quota = True
                                continue
                            self._search_key_cooldown[key] = time.monotonic() + 300
                            skip_key = True
                            break
                        if code in (401, 403):
                            failure = 'internet search API credentials cannot access Search'
                            self._search_key_cooldown[key] = time.monotonic() + 300
                            skip_key = True
                            break
                        if code in (400, 404):
                            failure = 'internet search model is unavailable for this account'
                            continue
                        log.warning('Internet search failed: %s (status %s)', type(error).__name__, code)
                        failure = 'internet search is temporarily unavailable'
                        skip_key = True
                        break
                    answer = (result.text or '').strip()
                    candidates = result.candidates or []
                    grounding = getattr(candidates[0], 'grounding_metadata', None) if candidates else None
                    sources = []
                    for chunk in getattr(grounding, 'grounding_chunks', None) or []:
                        web = getattr(chunk, 'web', None)
                        uri = getattr(web, 'uri', None)
                        if (web_search._public_url(uri) and
                                uri not in {source['url'] for source in sources}):
                            sources.append({'title': getattr(web, 'title', '') or uri, 'url': uri})
                        if len(sources) == 5:
                            break
                    if answer and sources:
                        return {'answer': answer[:6000], 'sources': sources,
                                'provider': 'Gemini grounded Search', 'model': model}
                    failure = 'internet search returned no source-backed answer'
                if newer_model_quota:
                    self._search_key_cooldown[key] = time.monotonic() + 300
                if time.monotonic() >= deadline:
                    break
                if skip_key:
                    continue
        if web_search.encyclopedia_eligible(query):
            try:
                return await web_search.wikipedia_search(query)
            except web_search.SearchProviderError as error:
                log.warning('Wikipedia background search unavailable: %s', error)
        raise SkillError(f'{failure}; configure BRAVE_SEARCH_API_KEY for general web search')

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

    def _create_todo(self, title, description='', priority='medium'):
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

    def _list_todos(self, query='', status='all'):
        if not isinstance(query, str) or len(query) > 200 or status not in ('all', 'backlog', 'ongoing', 'complete'):
            raise SkillError('invalid todo filter')
        data = self._read_todos()
        tasks = [item for item in data['tasks'] if isinstance(item, dict) and
                 (status == 'all' or item.get('status') == status) and
                 (not query or query.casefold() in str(item.get('title', '')).casefold() or
                  query.casefold() in str(item.get('description', '')).casefold())]
        return {'tasks': tasks, 'count': len(tasks), 'system': 'omarchy'}

    @staticmethod
    def _notify_quickshell_todos():
        for args in (
            ['qs', 'ipc', '-p', '/usr/share/omarchy/shell', '-n', 'call', 'dejan94.todos', 'reload'],
            ['qs', 'ipc', '-n', 'call', 'dejan94.todos', 'reload'],
        ):
            with contextlib.suppress(Exception):
                subprocess.run(args, capture_output=True, timeout=1)

    def _write_todos(self, data):
        path = self._todo_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
        try:
            temporary.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        self._notify_quickshell_todos()

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

    def _update_todo(self, task, title=None, description=None, priority=None):
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

    def _complete_todo(self, task, completed=True):
        data = self._read_todos(); item = self._find_todo(data, task)
        item['completed'] = bool(completed); item['status'] = 'complete' if item['completed'] else 'ongoing'
        item['completedAt'] = int(time.time() * 1000) if item['completed'] else 0
        self._write_todos(data)
        return {'status': 'completed' if item['completed'] else 'reopened', 'todo': item, 'system': 'omarchy'}

    def _delete_todo(self, task):
        data = self._read_todos(); item = self._find_todo(data, task)
        data['tasks'] = [candidate for candidate in data['tasks'] if candidate is not item]
        self._write_todos(data)
        return {'status': 'deleted', 'todo': item, 'system': 'omarchy'}

    def _clear_completed_todos(self):
        data = self._read_todos(); before = len(data['tasks'])
        data['tasks'] = [item for item in data['tasks'] if item.get('status') != 'complete' and not item.get('completed')]
        self._write_todos(data)
        return {'status': 'cleared', 'count': before - len(data['tasks']), 'system': 'omarchy'}

    def _move_todo(self, task, status):
        if status not in ('backlog', 'ongoing', 'complete'):
            raise SkillError('todo status must be backlog, ongoing, or complete')
        data = self._read_todos()
        item = self._find_todo(data, task)
        item['status'] = status
        item['completed'] = status == 'complete'
        item['completedAt'] = int(time.time() * 1000) if status == 'complete' else 0
        self._write_todos(data)
        return {'status': 'moved', 'todo': item, 'system': 'omarchy'}

    async def _todo_operation(self, method, *args, **kwargs):
        try:
            return await self._file_worker.run(method, *args, **kwargs)
        except WorkerBusyError as error:
            raise SkillError(str(error)) from None

    async def _adapter_create_todo(self, title, description='', priority='medium'):
        return await self._todo_operation(self._create_todo, title, description, priority)

    async def _adapter_list_todos(self, query='', status='all'):
        return await self._todo_operation(self._list_todos, query, status)

    async def _adapter_update_todo(self, task, title=None, description=None, priority=None):
        return await self._todo_operation(self._update_todo, task, title, description, priority)

    async def _adapter_complete_todo(self, task, completed=True):
        return await self._todo_operation(self._complete_todo, task, completed)

    async def _adapter_delete_todo(self, task):
        return await self._todo_operation(self._delete_todo, task)

    async def _adapter_clear_completed_todos(self):
        return await self._todo_operation(self._clear_completed_todos)

    async def _adapter_move_todo(self, task, status):
        return await self._todo_operation(self._move_todo, task, status)

    async def _adapter_get_desktop_context(self):
        """Return a compact read-only snapshot of the current Omarchy desktop."""
        context = {
            'time': dt.datetime.now().astimezone().isoformat(timespec='seconds'),
        }
        hypr = self._commands.get('hyprctl')

        async def _safe_run(coro):
            try:
                return await coro
            except Exception as e:
                return e

        # Prepare coroutines in exact order for deterministic execution and mock compatibility
        tasks = []
        # 1. activewindow
        tasks.append(_safe_run(self._run(hypr, 'activewindow', '-j', max_output=65536)) if hypr else asyncio.sleep(0, result=None))
        # 2. activeworkspace
        tasks.append(_safe_run(self._run(hypr, 'activeworkspace', '-j', max_output=65536)) if hypr else asyncio.sleep(0, result=None))
        # 3. network
        try:
            net_cmd = self._command('omarchy-network-status')
            tasks.append(_safe_run(self._run(net_cmd, '--verbose')))
        except SkillError as e:
            tasks.append(asyncio.sleep(0, result=e))
        # 4, 5, 6. audio (mute, volume, sink)
        try:
            pactl_cmd = self._command('pactl')
            tasks.append(_safe_run(self._run(pactl_cmd, 'get-sink-mute', '@DEFAULT_SINK@')))
            tasks.append(_safe_run(self._run(pactl_cmd, 'get-sink-volume', '@DEFAULT_SINK@')))
            tasks.append(_safe_run(self._run(pactl_cmd, 'get-default-sink')))
        except SkillError as e:
            tasks.append(asyncio.sleep(0, result=e))
            tasks.append(asyncio.sleep(0, result=e))
            tasks.append(asyncio.sleep(0, result=e))
        # 7. battery
        try:
            bat_cmd = self._command('omarchy-battery-status')
            tasks.append(_safe_run(self._run(bat_cmd, '--shell')))
        except SkillError as e:
            tasks.append(asyncio.sleep(0, result=e))
        # 8, 9. brightness & monitor
        try:
            b_cmd = self._command('omarchy-brightness-display')
            tasks.append(_safe_run(self._run(b_cmd)))
        except SkillError as e:
            tasks.append(asyncio.sleep(0, result=e))
        try:
            m_cmd = self._command('omarchy-hyprland-monitor-focused')
            tasks.append(_safe_run(self._run(m_cmd)))
        except SkillError as e:
            tasks.append(asyncio.sleep(0, result=e))
        # 10. clients
        tasks.append(_safe_run(self._run(hypr, 'clients', '-j', max_output=65536)) if hypr else asyncio.sleep(0, result=None))

        # Run all 10 concurrently
        results = await asyncio.gather(*tasks)
        active_raw, ws_raw, net_raw, mute_raw, vol_raw, sink_raw, bat_raw, bright_raw, mon_raw, clients_raw = results

        # Process active window
        if isinstance(active_raw, str):
            try:
                active = json.loads(active_raw)
                if isinstance(active, dict):
                    context['active_window'] = {
                        'title': active.get('title', ''), 'class': active.get('class', ''),
                        'workspace': active.get('workspace', {}).get('name', active.get('workspace', {}).get('id')),
                    }
                else:
                    context['active_window'] = None
            except (json.JSONDecodeError, AttributeError):
                context['active_window'] = None
        else:
            context['active_window'] = None

        # Process workspace
        if isinstance(ws_raw, str):
            try:
                workspace = json.loads(ws_raw)
                if isinstance(workspace, dict):
                    context['workspace'] = {'id': workspace.get('id'), 'name': workspace.get('name')}
                else:
                    context['workspace'] = None
            except (json.JSONDecodeError, AttributeError):
                context['workspace'] = None
        else:
            context['workspace'] = None

        # Process network
        if isinstance(net_raw, str):
            context['network'] = {'raw': net_raw, 'lines': net_raw.splitlines()}
        else:
            context['network'] = None

        # Process audio
        if isinstance(mute_raw, str) and isinstance(vol_raw, str):
            context['audio'] = {
                'muted': mute_raw.lower().endswith('yes'),
                'volume': vol_raw,
                'sink': sink_raw if isinstance(sink_raw, str) else None,
            }
        else:
            context['audio'] = None

        # Process battery
        if isinstance(bat_raw, str):
            context['battery'] = {'raw': bat_raw, 'available': bool(bat_raw)}
        else:
            context['battery'] = None

        # Process brightness
        context['brightness'] = bright_raw if isinstance(bright_raw, str) else None
        context['brightness_monitor'] = mon_raw if isinstance(mon_raw, str) else None

        # Process clients count
        if isinstance(clients_raw, str):
            try:
                clients = json.loads(clients_raw)
                context['open_windows_count'] = len(clients) if isinstance(clients, list) else None
            except (json.JSONDecodeError, TypeError):
                context['open_windows_count'] = None
        else:
            context['open_windows_count'] = None

        return context

    # ── Desktop awareness adapters ────────────────────────────────────

    async def _adapter_inspect_screen(self, region='full', extract_text=True):
        """Inspect what is currently visible on screen or active window, capturing visual layout and OCR text."""
        if region not in ('full', 'active'):
            raise SkillError('screen inspection region must be full or active')
        screenshots_dir = Path(os.getenv('XDG_RUNTIME_DIR') or '/tmp') / 'jarvis_screen'
        screenshots_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        if screenshots_dir.is_symlink() or screenshots_dir.stat().st_uid != os.getuid():
            raise SkillError('screen capture directory is not private to this user')
        screenshots_dir.chmod(0o700)
        # A bounded JPEG frame can be forwarded to Gemini Live as realtime
        # visual input; OCR still runs locally and remains the fallback.
        filename = str(screenshots_dir / f'inspect_{time.time_ns()}.jpg')

        args = [self._command('grim'), '-t', 'jpeg', '-q', '70']
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
        if Path(filename).exists():
            Path(filename).chmod(0o600)

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

    async def _adapter_control_vision_mode(self, mode, action='start'):
        """Control real-time video streaming mode (screen, camera, or off)."""
        clean_mode = str(mode).lower().strip()
        clean_action = str(action or 'start').lower().strip()
        if clean_mode not in ('screen', 'camera', 'off'):
            raise SkillError("vision mode must be 'screen', 'camera', or 'off'")
        if clean_action not in ('start', 'stop', 'status'):
            raise SkillError("action must be 'start', 'stop', or 'status'")

        if clean_action == 'status':
            return {
                'status': 'ok',
                'mode': self.vision_mode,
                'action': 'status',
                'active': self.vision_mode != 'off',
            }

        target_mode = 'off' if clean_action == 'stop' else clean_mode
        self.vision_mode = target_mode

        if callable(self.on_vision_mode_change):
            res = self.on_vision_mode_change(target_mode)
            if asyncio.iscoroutine(res):
                await res

        return {
            'status': 'ok',
            'mode': self.vision_mode,
            'action': clean_action,
            'active': self.vision_mode != 'off',
            'message': f"Real-time visual streaming set to '{self.vision_mode}'."
        }

    async def _adapter_capture_camera_frame(self, device='/dev/video0'):
        """Capture a single on-demand hardware camera snapshot using direct V4L2 MJPEG actuator."""
        if not device or not isinstance(device, str) or not device.startswith('/dev/video'):
            raise SkillError('invalid camera device path; expected /dev/videoN')

        webcam_dir = Path(os.getenv('XDG_RUNTIME_DIR') or '/tmp') / 'jarvis_webcam'
        webcam_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        if webcam_dir.is_symlink() or webcam_dir.stat().st_uid != os.getuid():
            raise SkillError('webcam directory is not private to this user')
        webcam_dir.chmod(0o700)

        filename = str(webcam_dir / f'webcam_{time.time_ns()}.jpg')
        cmd = self._command('vision_ctrl')
        raw = await self._run(cmd, 'capture_frame', filename, device, timeout=10, max_output=4096)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            raise SkillError('invalid response from vision_ctrl actuator') from None

        if parsed.get('status') != 'ok':
            err = parsed.get('error', 'camera capture failed')
            raise SkillError(err)

        if Path(filename).exists():
            Path(filename).chmod(0o600)

        actual_path = parsed.get('path') or filename
        return {
            'status': 'captured',
            'device': device,
            'screenshot_path': actual_path,
            'file_size': parsed.get('file_size', 0),
            'method': parsed.get('method', 'v4l2'),
        }

    async def _adapter_check_vision_hardware(self):
        """Check hardware cameras and display server environment."""
        cmd = self._command('vision_ctrl')
        raw_status = await self._run(cmd, 'status', timeout=5, max_output=4096)
        raw_cams = await self._run(cmd, 'check_camera', timeout=5, max_output=8192)
        try:
            status_data = json.loads(raw_status)
            cam_data = json.loads(raw_cams)
        except json.JSONDecodeError:
            raise SkillError('invalid JSON from vision_ctrl actuator') from None

        return {
            'status': 'ok',
            'vision_mode': self.vision_mode,
            'hardware_status': status_data,
            'cameras': cam_data.get('cameras', []),
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
