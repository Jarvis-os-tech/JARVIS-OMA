"""Use the same deadline for direct, voice and domain-routed tool calls."""
SLOW_TOOLS = frozenset({
    'web_search', 'internet_search', 'open_page', 'read_page_text', 'read_screen',
    'browser_task', 'compose_windows', 'run_in_terminal', 'gui_observe_desktop',
    'gui_browser_navigate', 'gui_browser_snapshot', 'execute_platform_action',
    'composio_execute_tool', 'api_anything_propose', 'api_anything_learn',
    'api_anything_call', 'api_anything_search', 'api_anything_list_operations',
})


def tool_timeout(name, arguments=None):
    if name == 'execute_domain_tool':
        arguments = arguments if isinstance(arguments, dict) else {}
        name = arguments.get('tool_name')
        if not isinstance(name, str) or name == 'execute_domain_tool':
            return 15
    if name in ('api_anything_learn', 'cli_hub_matrix_install'):
        return 310
    if name in ('api_anything_propose', 'cli_hub_install'):
        return 135
    if name.startswith('cli_hub_'):
        return 75
    return 90 if name in SLOW_TOOLS else 30 if name == 'system_control' else 45
