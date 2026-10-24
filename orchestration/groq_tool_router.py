"""Fast Groq function selection for the Live voice agent."""
from __future__ import annotations

import json
import logging
import os
import re
import time

import httpx


log = logging.getLogger(__name__)


def configured_groq_api_keys(environ=None):
    """Return unique Groq keys without exposing their values in configuration."""
    env = os.environ if environ is None else environ
    keys = []
    for name in ('GROQ_API_KEY', 'GROQ_API_KEY_1', 'GROQ_API_KEY_2'):
        value = (env.get(name) or '').strip()
        if value and value not in keys:
            keys.append(value)
    return keys


ROUTER_DECLARATION = {
    'name': 'route_tool_command',
    'description': (
        'Route a clear user request that requires a JARVIS desktop, file, web, todo, '
        'calendar, memory, phone, or system tool. Pass the user request faithfully. '
        'Do not call this for greetings or conversation that needs no tool.'),
    'parameters_json_schema': {
        'type': 'object',
        'properties': {'command': {'type': 'string', 'minLength': 1, 'maxLength': 4000}},
        'required': ['command'], 'additionalProperties': False,
    },
}


class GroqToolRouter:
    def __init__(self, api_key, declarations, *, model='openai/gpt-oss-20b', timeout=8):
        keys = [api_key] if isinstance(api_key, str) else list(api_key)
        self.api_keys = [key.strip() for key in keys if key and key.strip()]
        if not self.api_keys:
            raise ValueError('At least one Groq API key is required')
        self.declarations = list(declarations)
        self.model = model
        self.timeout = timeout
        self._next_key = 0
        self._cooldown_until = [0.0] * len(self.api_keys)

    @staticmethod
    def _retry_after(response):
        try:
            return max(1.0, float(response.headers.get('Retry-After', '60')))
        except (TypeError, ValueError):
            return 60.0

    def _available_key_indexes(self):
        now = time.monotonic()
        return [index for offset in range(len(self.api_keys))
                if self._cooldown_until[index := (self._next_key + offset) % len(self.api_keys)] <= now]

    @staticmethod
    def _tokens(text):
        return set(re.findall(r'[a-z0-9]+', text.lower()))

    def _tools_for(self, command):
        """Stay below Groq's 128-function limit while retaining common controls."""
        query = self._tokens(command)
        common = {'open_application', 'close_application', 'list_applications',
                  'list_windows', 'focus_window', 'type_text', 'press_key',
                  'internet_search', 'add_todo', 'list_todos', 'complete_todo',
                  'update_todo', 'delete_todo', 'enter_standby', 'set_volume',
                  'get_system_information', 'inspect_screen', 'read_file',
                  'write_file', 'edit_file', 'list_files', 'search_files',
                  'search_file_content'}
        ranked = []
        for index, item in enumerate(self.declarations):
            searchable = f"{item.get('name', '')} {item.get('description', '')}"
            ranked.append((item.get('name') in common,
                           len(query & self._tokens(searchable)), -index, item))
        ranked.sort(reverse=True, key=lambda row: row[:3])
        # Large manifest schemas can exceed Groq's HTTP/context request limit well
        # before its theoretical 128-function maximum. Forty keeps routing fast.
        return [{'type': 'function', 'function': {
            'name': item['name'], 'description': item['description'],
            'parameters': item['parameters_json_schema'],
        }} for *_, item in ranked[:40]]

    async def route(self, command):
        payload = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': (
                    'Select the exact JARVIS function needed for the user command. Use only '
                    'supplied functions. Preserve names, paths, dates, and requested values. '
                    'Prefer one direct call; use parallel calls only when independently required.')},
                {'role': 'user', 'content': command},
            ],
            'tools': self._tools_for(command), 'tool_choice': 'required',
            'parallel_tool_calls': True, 'temperature': 0, 'max_completion_tokens': 512,
        }
        indexes = self._available_key_indexes()
        if not indexes:
            remaining = min(self._cooldown_until) - time.monotonic()
            raise RuntimeError(f'All Groq API keys are rate-limited; retry in {max(1, round(remaining))}s')
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = None
            for index in indexes:
                response = await client.post(
                    'https://api.groq.com/openai/v1/chat/completions', json=payload,
                    headers={'Authorization': f'Bearer {self.api_keys[index]}'})
                if response.status_code != 429:
                    response.raise_for_status()
                    self._next_key = (index + 1) % len(self.api_keys)
                    break
                cooldown = self._retry_after(response)
                self._cooldown_until[index] = time.monotonic() + cooldown
                log.warning('Groq key %d/%d rate-limited; cooling down for %.0fs',
                            index + 1, len(self.api_keys), cooldown)
            else:
                response.raise_for_status()
        calls = []
        for call in response.json()['choices'][0]['message'].get('tool_calls') or []:
            function = call.get('function') or {}
            try:
                arguments = json.loads(function.get('arguments') or '{}')
            except json.JSONDecodeError as error:
                raise ValueError('Groq returned invalid tool arguments') from error
            if not function.get('name') or not isinstance(arguments, dict):
                raise ValueError('Groq returned an invalid tool call')
            calls.append({'name': function['name'], 'arguments': arguments})
        if not calls:
            raise ValueError('Groq returned no tool call')
        return calls
