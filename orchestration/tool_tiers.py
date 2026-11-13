"""Small initial voice catalog with explicitly discoverable capability domains.

This module imports neither the skill registry nor a model client. The same
domain vocabulary is shared by Gemini's typed meta tools and the Groq selector.
"""
from __future__ import annotations

import re


CORE_TOOLS = frozenset({
    'get_assistant_status', 'list_capabilities', 'enter_standby', 'pause_jarvis',
    'parse_command_values',
    'resume_jarvis', 'stop_all_jarvis_work', 'open_application', 'list_applications',
    'open_website', 'list_windows', 'focus_window', 'list_workspaces',
    'switch_workspace', 'manage_window', 'type_text', 'press_key', 'set_volume',
    'control_microphone', 'set_brightness', 'remember_memory', 'recall_memory',
    'memory_status', 'list_files', 'read_file', 'search_files', 'internet_search',
    'get_system_information', 'start_task', 'task_status', 'list_tasks',
    'cancel_task', 'open_input_bar', 'close_input_bar', 'control_vision_mode', 'show_widget', 'manage_canvas', 'manage_widget', 'widget_schema',
    'start_model_processing', 'model_processing_status', 'connect_platform', 'open_platform_authorization', 'check_platform_connection', 'execute_platform_action', 'list_connected_platforms',
    'github_authorize', 'github_connection_status', 'google_authorize', 'google_connection_status',
    'get_harness_status', 'start_harness_check', 'harness_check_status', 'cancel_harness_check',
    'get_learning_status', 'list_research_lessons', 'record_research_feedback',
    'shutdown_system', 'restart_system', 'lock_screen', 'confirm_system_action', 'cancel_system_action', 'system_power', 'control_power',
    'linkedin_draft_post', 'linkedin_plan_sprint', 'linkedin_audit_profile', 'linkedin_pending_reviews', 'linkedin_approve_post', 'linkedin_sync_profile', 'linkedin_propose_tool',
    'activate_teaching_mode', 'update_teaching_lesson', 'exit_teaching_mode', 'teaching_status',
    'reach_search', 'reach_read', 'reach_transcript', 'reach_status',
    'run_shell', 'run_in_terminal', 'read_terminal', 'watch_terminal',
    'hypr_dispatch', 'hypr_query', 'read_screen', 'click_text', 'file_operation', 'system_control',
    'omarchy_cli', 'omarchy_help',
})
META_TOOLS = frozenset({'discover_domain_tools', 'execute_domain_tool', 'parse_command_values'})
DOMAINS = ('core', 'desktop', 'filesystem', 'memory', 'workspace', 'github',
           'gui', 'cli_anything', 'api_anything', 'integrations', 'orchestration', 'learning', 'phone', 'vision', 'composio', 'linkedin', 'teaching', 'agent_reach')

_ORCHESTRATION = frozenset({
    'get_hermes_events',
    'respond_hermes_approval',
    'read_hermes_artifact', 'handoff_hermes_task',
    'call_hermes_api', 'get_hermes_features', 'run_hermes_command',
    'start_hermes_goal',
    'start_agent_goal', 'list_system_agents', 'delegate_agent', 'delegate_team',
    'check_agent_team', 'cancel_agent_team', 'check_agent_job', 'list_agent_jobs',
    'cancel_agent_job', 'get_hermes_status', 'create_task_agent', 'task_agent_status',
    'list_task_agents', 'cancel_task_agent', 'followup_task_agent', 'start_development',
    'request_capability', 'development_status', 'list_development_jobs',
    'cancel_development', 'start_model_processing', 'model_processing_status',
    'proactive_task', 'proactive_status',
})
_FILESYSTEM = frozenset({'write_file', 'append_file', 'edit_file', 'make_directory',
    'move_path', 'copy_path', 'trash_path', 'delete_path', 'inspect_file', 'search_file_content'})


def domain_for_tool(name):
    if name in META_TOOLS:
        return 'core'
    if name.startswith(('gmail_', 'calendar_', 'tasks_', 'drive_', 'docs_', 'sheets_', 'google_')):
        return 'workspace'
    for prefix, domain in (('github_', 'github'), ('gui_', 'gui'), ('cli_hub_', 'cli_anything'),
                           ('api_anything_', 'api_anything'), ('integration_', 'integrations'),
                           ('phone_', 'phone'), ('composio_', 'composio'), ('disconnect_platform', 'composio'),
                           ('linkedin_', 'linkedin'), ('reach_', 'agent_reach'), ('agent_reach_', 'agent_reach')):
        if name.startswith(prefix):
            return domain
    if name in _ORCHESTRATION:
        return 'orchestration'
    if ('harness' in name or 'research' in name or 'learning' in name):
        return 'learning'
    if name in _FILESYSTEM:
        return 'filesystem'
    if 'memory' in name or name == 'sync_memory_vault':
        return 'memory'
    if name in ('control_vision_mode', 'capture_camera_frame', 'check_vision_hardware'):
        return 'vision'
    if name in CORE_TOOLS:
        return 'core'
    return 'desktop'


def intent_domains(command):
    """Conservative hints for selecting schemas, never authorization to act."""
    text = command.casefold()
    hints = {
        'workspace': r'\b(gmail|email|calendar|meeting|appointment|schedule|drive|spreadsheet|google|tasks)\b',
        'github': r'\b(github|pull request|repository|repositories|issue)\b',
        'gui': r'\b(accessibility|cua|click|scroll|browser tab|double.click)\b',
        'cli_anything': r'\b(cli.anything|cli.hub|matrix|recipe)\b',
        'api_anything': r'\b(api.anything|api agent|web api|api operation|blueprint)\b',
        'integrations': r'\b(integration|integrations|service health|connector status)\b',
        'composio': r'\b(composio|connector|connectors|oauth)\b',
        'linkedin': r'\b(linkedin|linkedin post|linkedin profile|linkedin hook|linkedin draft)\b',
        'orchestration': r'\b(delegate|agent|codex|claude|hermes|kanban|kanboard|cron|cronjob|development|background job)\b',
        'learning': r'\b(harness|research feedback|refinement|learning)\b',
        'phone': r'\b(phone|call|contact|dtmf|hang up)\b',
        'vision': r'\b(camera|vision|video|webcam)\b',
        'teaching': r'\b(teach|teaching|lesson|tutor|tutorial|learn|explain code|walk me through|exit teaching)\b',
        'agent_reach': r'\b(agent.reach|reach|bilibili|xiaohongshu|xhs|reddit|v2ex|xueqiu|transcript|subtitles)\b',
        'filesystem': r'\b(file|directory|folder|path|copy|append|trash)\b',
        'memory': r'\b(memory|remember|recall|forget|obsidian)\b',
        'desktop': r'\b(volume|brightness|wifi|bluetooth|remind|reminder|todo|theme|desktop|notification|shutdown|shut down|restart|reboot|power|lock screen|screen lock)\b',
    }
    return {domain for domain, pattern in hints.items() if re.search(pattern, text)}


def collision_safe_tools(command, declarations):
    """Prefer standby for bare mute and Calendar for explicitly timed events."""
    text = command.casefold().strip(' .!?')
    bare_mute = text in {'mute', 'mute yourself', 'mute jarvis', 'standby', 'standby mode',
                        'go to sleep', 'be quiet', 'enter standby'}
    timed = bool(re.search(r'\b(meeting|appointment|calendar)\b|\bat\s+\d', text))
    if bare_mute:
        standby = [item for item in declarations if item.get('name') == 'enter_standby']
        if standby:
            return standby
    blocked = {'set_volume', 'control_microphone'} if bare_mute else set()
    if timed:
        blocked.add('tasks_create_task')
    return [item for item in declarations if item.get('name') not in blocked]


def routed_arguments_match(value, schema, depth=0):
    """Validate selected-provider calls before admitting them to the registry.

    The registry remains authoritative. This check handles its bounded schema
    vocabulary plus unspecified JSON-Schema additional properties for external
    router callers; it does not execute schema text or coerce argument types.
    """
    if depth > 8 or not isinstance(schema, dict):
        return False
    if 'oneOf' in schema:
        return sum(routed_arguments_match(value, option, depth + 1)
                   for option in schema['oneOf']) == 1
    kind = schema.get('type')
    if kind == 'object':
        if not isinstance(value, dict) or not set(schema.get('required', ())) <= set(value):
            return False
        properties = schema.get('properties', {})
        return all((name in properties and routed_arguments_match(item, properties[name], depth + 1))
                   or (name not in properties and schema.get('additionalProperties', True) is True)
                   for name, item in value.items())
    if kind == 'array':
        return (isinstance(value, list) and schema.get('minItems', 0) <= len(value) <= schema.get('maxItems', 16)
                and all(routed_arguments_match(item, schema.get('items', {}), depth + 1) for item in value))
    if kind == 'string':
        valid = isinstance(value, str)
        if valid:
            valid = schema.get('minLength', 0) <= len(value) <= schema.get('maxLength', 65536)
    elif kind == 'integer':
        valid = type(value) is int and schema.get('minimum', value) <= value <= schema.get('maximum', value)
    elif kind == 'boolean':
        valid = type(value) is bool
    else:
        return False
    return valid and ('enum' not in schema or value in schema['enum'])


META_SPECS = ({
    'name': 'discover_domain_tools',
    'description': 'Read exact available tool schemas before execute_domain_tool. Domains include workspace, github, gui, api_anything (learned web APIs), cli_anything (application harnesses), composio (account connectors), integrations (live service health), orchestration and learning. Discovery never executes an action.',
    'adapter': 'domains.discover',
    'parameters_json_schema': {'type': 'object', 'properties': {
        'domain': {'type': 'string', 'enum': list(DOMAINS)},
        'query': {'type': 'string', 'description': 'Optional words to narrow names and descriptions.'},
        'limit': {'type': 'integer', 'minimum': 1, 'maximum': 20},
    }, 'required': ['domain'], 'additionalProperties': False},
}, {
    'name': 'execute_domain_tool',
    'description': 'Execute one exact registered domain tool using a schema returned by discover_domain_tools or list_capabilities. Pass arguments_json as a JSON object string. Required permissions and normal argument/security checks still apply. Do not invent tool names or arguments.',
    'adapter': 'domains.execute',
    'parameters_json_schema': {'type': 'object', 'properties': {
        'domain': {'type': 'string', 'enum': list(DOMAINS)},
        'tool_name': {'type': 'string', 'description': 'Exact registered tool name returned by discovery.'},
        'arguments_json': {'type': 'string', 'description': 'JSON object matching that tool\'s exact parameter schema.'},
    }, 'required': ['domain', 'tool_name', 'arguments_json'], 'additionalProperties': False},
})
