"""Use the same deadline for direct, voice and domain-routed tool calls."""
import re

SLOW_TOOLS = frozenset({
    'web_search', 'internet_search', 'open_page', 'read_page_text', 'read_screen',
    'browser_task', 'compose_windows', 'run_in_terminal', 'gui_observe_desktop',
    'gui_browser_navigate', 'gui_browser_snapshot', 'execute_platform_action',
    'composio_execute_tool', 'api_anything_propose', 'api_anything_learn',
    'api_anything_call', 'api_anything_search', 'api_anything_list_operations',
})

CONFIRMATION_DECISION_CRITERIA = {
    'true_description': 'Destructive, irreversible, or high-impact desktop action requiring explicit user confirmation before execution.',
    'false_description': 'Safe, benign, read-only, informational, or non-destructive routine action.',
}

DESTRUCTIVE_COMMAND_PATTERNS = [
    re.compile(r'\b(?:shutdown|reboot|restart|poweroff)\b', re.IGNORECASE),
    re.compile(r'\b(?:lock[-_ ]?screen|lock\s+(?:pc|screen|computer)|suspend|hibernate)\b', re.IGNORECASE),
    re.compile(r'\brm\s+-[a-zA-Z]*[rf]', re.IGNORECASE),
    re.compile(r'\b(?:mkfs|shred|wipefs|cryptsetup|pkexec)\b', re.IGNORECASE),
    re.compile(r'\bdd\s+if=', re.IGNORECASE),
    re.compile(r'>\s*/dev/[sn][dv]', re.IGNORECASE),
    re.compile(r'\bcurl\b.*\|\s*(?:ba)?sh', re.IGNORECASE),
    re.compile(r'\bomarchy\s+(?:update|drive|pkg|install|refresh|reinstall)\b', re.IGNORECASE),
    re.compile(r'\b(?:close[-_ ]?all|uninstall|delete|erase|format|purge)\b', re.IGNORECASE),
]

DESTRUCTIVE_TOOL_NAMES = frozenset({
    'uninstall_app', 'execute_system_command', 'modify_system_config',
    'manage_system_service', 'privileged_exec',
})


def requires_confirmation(action_or_command: str, arguments: dict | None = None) -> bool:
    """Evaluate whether an action or desktop command requires explicit user confirmation before running."""
    if not action_or_command or not isinstance(action_or_command, str):
        return False
    normalized = action_or_command.strip()
    if normalized in DESTRUCTIVE_TOOL_NAMES:
        return True
    args = arguments or {}
    action = str(args.get('action', ''))
    if action in {'shutdown', 'reboot', 'poweroff', 'restart', 'suspend', 'hibernate', 'lock_screen'}:
        return True
    command_str = str(args.get('command', '')) or str(args.get('cmd', '')) or normalized
    for pattern in DESTRUCTIVE_COMMAND_PATTERNS:
        if pattern.search(command_str) or pattern.search(action):
            return True
    return False


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
