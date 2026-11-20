"""Short, grounded acknowledgements selected without a model round trip."""
from pathlib import Path
import re

PHRASES = {
    'ack_short_sure': 'Sure.',
    'ack_short_on_it': 'On it.',
    'ack_short_hmm': 'Hmm.',
    'ack_short_okay': 'Okay.',
    'ack_file': "I'll read through that file.",
    'ack_files': "I'll look through your files.",
    'ack_analysis': "I'll work through the details.",
    'ack_search': "I'll look that up.",
    'ack_screen': "I'll check what's on your screen.",
    'ack_browser': "I'll check that in the browser.",
    'ack_terminal': "I'll run that and check the result.",
    'ack_agent': "I'll get started on that task.",
    'ack_app': "I'll open that application.",
    'ack_volume': "I'll adjust the volume.",
    'ack_brightness': "I'll adjust the screen brightness.",
    'ack_workspace': "I'll switch to that workspace.",
    'ack_general_0': "Let me take a look.",
    'ack_general_1': "I'll work through that.",
    'ack_general_2': "Let me check that.",
}

# Criteria mapping for Gemini Decision 1 ack_clip choice question
DECISION_ACK_CRITERIA = {
    'ack_short_sure': 'Standard brief affirmative assent ("Sure.") for routine commands and requests.',
    'ack_short_on_it': 'Immediate execution assent ("On it.") for active tasks or immediate action.',
    'ack_short_okay': 'Neutral acknowledgement ("Okay.") for adjustments or state changes.',
    'ack_short_hmm': 'Reflective thinking sound ("Hmm.") for questions, inquiries, or contemplation.',
    'ack_file': 'Reading, opening, or inspecting a specific local file ("I\'ll read through that file.").',
    'ack_files': 'Searching or browsing filesystem directories ("I\'ll look through your files.").',
    'ack_analysis': 'Deep analysis, data crunching, or detailed reasoning ("I\'ll work through the details.").',
    'ack_search': 'Information retrieval, internet search, or looking something up ("I\'ll look that up.").',
    'ack_screen': 'Inspecting desktop display, vision, or reading screen ("I\'ll check what\'s on your screen.").',
    'ack_browser': 'Navigating web pages or browser interactions ("I\'ll check that in the browser.").',
    'ack_terminal': 'Executing terminal commands or shell operations ("I\'ll run that and check the result.").',
    'ack_agent': 'Delegating to autonomous background agents or multi-step goals ("I\'ll get started on that task.").',
    'ack_app': 'Opening or launching desktop applications ("I\'ll open that application.").',
    'ack_volume': 'Adjusting speaker volume settings ("I\'ll adjust the volume.").',
    'ack_brightness': 'Adjusting screen brightness settings ("I\'ll adjust the screen brightness.").',
    'ack_workspace': 'Switching virtual desktop workspaces ("I\'ll switch to that workspace.").',
    'none': 'Direct conversation, casual dialogue, follow-up, or no pre-rendered acknowledgement clip needed.',
}


def resolve_ack_asset(ack_clip: str, assets_dir: Path | None = None) -> Path | None:
    """Resolve an ack_clip choice to a .pcm or .wav asset Path, or None if 'none' or missing."""
    if not ack_clip or ack_clip == 'none':
        return None
    if assets_dir is None:
        assets_dir = Path(__file__).parent / 'assets'
    for ext in ('.pcm', '.wav'):
        candidate = assets_dir / f"{ack_clip}{ext}"
        if candidate.is_file():
            return candidate
    return None


def get_decision_ack_phrase(ack_clip: str) -> str:
    """Return the spoken phrase for a decision ack clip, or empty string if 'none'."""
    if not ack_clip or ack_clip == 'none':
        return ''
    return PHRASES.get(ack_clip, '')


_INQUIRY_PATTERN = re.compile(
    r'^(?:(?:(?:hey\s+)?jarvis|oma)[,\s]*)?(?:why|how|what|when|where|who|is|are|tell me|could you explain|can you explain)\b',
    re.IGNORECASE
)


def is_conversational_inquiry(text: str) -> bool:
    """Return True if the utterance is an informational question rather than an action command."""
    if not text or not isinstance(text, str):
        return False
    return bool(_INQUIRY_PATTERN.search(text.strip()))


def short_ack(context, previous=''):
    """Use compact task-sensitive acknowledgements without consecutive repeats."""
    reflective = context in {'ack_analysis', 'ack_file', 'ack_files', 'ack_screen'}
    choices = (('ack_short_hmm', 'ack_short_okay', 'ack_short_sure', 'ack_short_on_it')
               if reflective else
               ('ack_short_on_it', 'ack_short_sure', 'ack_short_okay', 'ack_short_hmm'))
    if context.startswith('ack_general_'):
        choices = ('ack_short_sure', 'ack_short_okay', 'ack_short_hmm')
    if previous in choices:
        return choices[(choices.index(previous) + 1) % len(choices)]
    return choices[0]


def select_ack(context, text='', serial=0, arguments=None):
    """Tool admission is authoritative; transcript hints only describe intent."""
    args = arguments or {}
    if context == 'system_control':
        action = str(args.get('action', ''))
        for control, actions in {
            'volume': {'volume_get', 'volume_set', 'volume_adjust'},
            'brightness': {'brightness_get', 'brightness_set', 'brightness_adjust'},
            'workspace': {'workspace_get', 'workspace_switch', 'workspace_back'},
        }.items():
            if action in actions:
                # A getter does not imply changing a user's setting.
                if action.endswith('_get'):
                    return 'ack_general_2'
                return 'ack_' + control
        return 'ack_general_2'
    tools = {
        'read_file': 'ack_file', 'search_files': 'ack_files',
        'search_file_content': 'ack_files', 'list_files': 'ack_files',
        'read_screen': 'ack_screen', 'inspect_screen': 'ack_screen',
        'web_search': 'ack_search', 'internet_search': 'ack_search',
        'open_page': 'ack_browser', 'read_page_text': 'ack_browser',
        'browser_task': 'ack_browser', 'run_in_terminal': 'ack_terminal',
        'execute_desktop_command': 'ack_terminal',
        'launch_app': 'ack_app', 'open_application': 'ack_app',
        'set_volume': 'ack_volume',
        'set_brightness': 'ack_brightness',
        'switch_workspace': 'ack_workspace', 'move_window_to_workspace': 'ack_workspace',
        'filesystem_grep': 'ack_files',
        'sub_agent_spawn': 'ack_agent', 'start_agent_goal': 'ack_agent',
    }
    if context in tools:
        return tools[context]
    if any(word in context for word in ('agent', 'hermes', 'delegate')):
        return 'ack_agent'
    # Transcript wording is intent, not evidence that a tool was admitted.
    return f'ack_general_{serial % 3}'
