"""Fast Groq function selection for the Live voice agent."""
from __future__ import annotations

import json
import logging
import os
import re
import time

import httpx
from orchestration.tool_tiers import (
    CORE_TOOLS, META_TOOLS, domain_for_tool, intent_domains, collision_safe_tools,
    routed_arguments_match,
)


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


REMOTE_TOOL_PREFIXES = (
    'github_',
    'gmail_',
    'calendar_',
    'tasks_',
    'drive_',
    'docs_',
    'sheets_',
    'google_',
    'phone_',
)

REMOTE_TOOL_NAMES = {
    'get_hermes_status',
    'create_task_agent',
    'task_agent_status',
    'list_task_agents',
    'cancel_task_agent',
    'followup_task_agent',
    'start_harness_refinement',
    'internet_search',
    'start_agent_goal',
    'list_system_agents',
    'delegate_agent',
    'delegate_team',
    'check_agent_team',
    'cancel_agent_team',
    'check_agent_job',
    'list_agent_jobs',
    'cancel_agent_job',
    'start_development',
    'development_status',
    'list_development_jobs',
    'cancel_development',
    'start_model_processing',
    'model_processing_status',
    'control_vision_mode',
    'check_vision_hardware',
}

# Compatibility alias
SYSTEM_TOOL_NAMES = frozenset({'open_application', 'switch_workspace', 'type_text', 'set_volume', 'manage_window'})


def is_local_tool(name: str) -> bool:
    """Return True if the tool operates on the local machine/OS."""
    if not name or name in REMOTE_TOOL_NAMES:
        return False
    if any(name.startswith(prefix) for prefix in REMOTE_TOOL_PREFIXES):
        return False
    return True


def partition_declarations_for_router(declarations: list[dict]) -> tuple[list[dict], list[dict]]:
    """Partition tool declarations into local tools (for Groq) and remote/cloud tools (for Gemini)."""
    local_decls = [d for d in declarations if is_local_tool(d.get('name', ''))]
    remote_decls = [d for d in declarations if not is_local_tool(d.get('name', ''))]
    return local_decls, remote_decls


ROUTER_DECLARATION = {
    'name': 'route_local_command',
    'description': (
        'Fast router for all local machine and desktop actions: opening/closing applications and websites, '
        'switching windows or workspaces, typing text, pressing keys, system settings (volume, brightness, power, wifi, bluetooth, night light, theme), '
        'clipboard, local files (read/write/search), local notes, native todos and reminders, and system info. '
        'Pass the user command faithfully. Do NOT call this for web searches, GitHub, Google services (Gmail, Calendar, Drive, Docs), or phone calls.'),
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
        """Select core schemas plus intent-matched domains, bounded to forty."""
        query = self._tokens(command)
        candidates = [item for item in self.declarations if item.get('name') not in META_TOOLS]
        requested = intent_domains(command)
        present = {domain_for_tool(item.get('name', '')) for item in candidates}
        activated = requested & present
        if activated:
            candidates = [item for item in candidates
                          if item.get('name') in CORE_TOOLS or domain_for_tool(item.get('name', '')) in activated]
        candidates = collision_safe_tools(command, candidates)
        ranked = []
        for index, item in enumerate(candidates):
            searchable = f"{item.get('name', '')} {item.get('description', '')}"
            ranked.append((len(query & self._tokens(searchable)),
                           domain_for_tool(item.get('name', '')) in activated,
                           is_local_tool(item.get('name', '')), -index, item))
        ranked.sort(reverse=True, key=lambda row: row[:4])
        # Large manifest schemas can exceed Groq's HTTP/context request limit well
        # before its theoretical 128-function maximum. Forty keeps routing fast.
        return [{'type': 'function', 'function': {
            'name': item['name'], 'description': item['description'],
            'parameters': item['parameters_json_schema'],
        }} for *_, item in ranked[:40]]

    async def route(self, command):
        tools = self._tools_for(command)
        if not tools:
            raise ValueError('No matching registered tool domain is available')
        selected = {item['function']['name']: item['function']['parameters'] for item in tools}
        payload = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': (
                    'Select the exact JARVIS local machine tool function needed for the user command. '
                    'Use only supplied functions (applications, window/workspace management, typing, local files, volume, system settings, todos, reminders). '
                    'Preserve names, paths, and requested values. '
                    'Prefer one direct call; use parallel calls only when independently required. '
                    'Bare mute means enter_standby; change speakers only for an explicit system audio target. '
                    'A timed appointment belongs in Calendar, never an untimed Tasks entry.')},
                {'role': 'user', 'content': command},
            ],
            'tools': tools, 'tool_choice': 'required',
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
        returned = response.json()['choices'][0]['message'].get('tool_calls') or []
        if len(returned) > 16:
            raise ValueError('Groq returned too many tool calls')
        for call in returned:
            function = call.get('function') or {}
            try:
                arguments = json.loads(function.get('arguments') or '{}')
            except (ValueError, TypeError, RecursionError) as error:
                raise ValueError('Groq returned invalid tool arguments') from error
            if not function.get('name') or not isinstance(arguments, dict):
                raise ValueError('Groq returned an invalid tool call')
            if function['name'] not in selected:
                raise ValueError('Groq returned a tool outside the selected registered domain')
            if not routed_arguments_match(arguments, selected[function['name']]):
                raise ValueError('Groq returned arguments outside the selected tool schema')
            calls.append({'name': function['name'], 'arguments': arguments})
        if not calls:
            raise ValueError('Groq returned no tool call')
        return calls
