"""Allowlisted Omarchy desktop skills for the Gemini Live voice agent.

The model can only select a declared skill.  Arguments are validated here and
are always passed to subprocesses as an argv list; no shell is involved.
"""
from __future__ import annotations

import asyncio
import configparser
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit


class SkillError(ValueError):
    """A safe, user-presentable skill failure."""


def _normalized(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', value.casefold())


class DesktopSkills:
    """Small, auditable set of controls for an Omarchy/Hyprland desktop."""

    ADAPTERS = {
        'applications.list': '_adapter_list_applications',
        'applications.open': '_adapter_open_application',
        'web.open': '_adapter_open_website',
        'audio.volume': '_adapter_adjust_volume',
        'display.brightness': '_adapter_adjust_brightness',
        'workspace.switch': '_adapter_switch_workspace',
        'notification.show': '_adapter_show_notification',
    }

    def __init__(self, manifest_dirs=None):
        self._commands = {
            name: shutil.which(name) for name in (
                'gtk-launch', 'hyprctl', 'notify-send',
                'omarchy-audio-output-volume', 'omarchy-brightness-display',
                'omarchy-launch-webapp',
            )
        }
        if manifest_dirs is None:
            manifest_dirs = [Path(__file__).with_name('skill_manifests')]
        self.manifest_dirs = [Path(directory) for directory in manifest_dirs]
        self._skills = self._load_manifests()

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
        return {name: path is not None for name, path in self._commands.items()}

    def _command(self, name):
        path = self._commands.get(name)
        if not path:
            raise SkillError(f'{name} is not installed on this desktop')
        return path

    async def _run(self, *argv, timeout=8):
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
        directories = [Path('/usr/share/applications'), Path('/usr/local/share/applications')]
        data_home = os.getenv('XDG_DATA_HOME')
        if data_home:
            directories.insert(0, Path(data_home) / 'applications')
        else:
            directories.insert(0, Path.home() / '.local/share/applications')
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
        await self._run(self._command('notify-send'), '--app-name=Jarvis', title, message)
        return {'status': 'shown'}
