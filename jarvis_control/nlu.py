"""Natural Language Processing (NLP) & Natural Language Understanding (NLU) Engine.

Provides phonetic normalization, multilingual (Hindi/Hinglish/Indian English) understanding,
intent classification, entity extraction, and semantic tool gating for JARVIS.
"""
from __future__ import annotations

import enum
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

log = logging.getLogger(__name__)


class IntentCategory(enum.Enum):
    CONVERSATIONAL = "conversational"
    SYSTEM_CONTROL = "system_control"
    PHONE_CONTROL = "phone_control"
    PHONE_PAIRING = "phone_pairing"
    WEB_SEARCH = "web_search"
    STANDBY = "standby"
    MEMORY = "memory"
    VISION = "vision"
    UNKNOWN = "unknown"


class ConfirmationDecision(enum.Enum):
    AFFIRMED = "affirmed"
    DECLINED = "declined"
    AMBIGUOUS = "ambiguous"


@dataclass
class NLUResult:
    raw_text: str
    normalized_text: str
    category: IntentCategory
    confidence: float
    entities: dict[str, Any] = field(default_factory=dict)
    is_conversational_inquiry: bool = False
    suggested_action: Optional[str] = None


class NLUEngine:
    """Sovereign NLP/NLU Engine for speech normalization, intent extraction, and tool gating."""

    # Common ASR phonetic mishearings and phonetic corrections
    PHONETIC_REPLACEMENTS = [
        (r'\b(gervais|jarviss|jervis|jarves|java|charvis|jarvi)\b', 'Jarvis'),
        (r'\b(showingspot|show in spot|showing spot)\b', 'hotspot'),
        (r'\b(reserva|reservas)\b', 'reservations'),
        (r'\b(padmasan|padmasana)\b', 'Padmasana lotus pose'),
        (r'\b(stand by|stand-by|sleep mode)\b', 'standby'),
        (r'\b(testing mood|test mood)\b', 'test mode'),
        (r'\b(production mood|prod mood)\b', 'production mode'),
        (r'\b(actavtethe|actavte|activatethe)\b', 'activate the'),
        (r'\b(wi fi|wi-fi)\b', 'wifi'),
        (r'\b(shudown)\b', 'shutdown'),
        (r'\b(screnn|scren)\b', 'screen'),
        (r'\b(conformation)\b', 'confirmation'),
    ]

    # Multilingual / Hinglish conversational inquiry patterns
    HINGLISH_INQUIRY_PATTERNS = [
        r'\b(hum kya kare|kya kare|kya karu|main kya karu)\b',
        r'\b(kaise kare|kaise hoga|kaise set kare|kaise change kare)\b',
        r'\b(kya chal raha|kya haal|kya scene)\b',
        r'\b(batao|bataiye|samjhao)\b',
        r'\b(kyun|kyu|kaise|kahan|kab)\b',
    ]

    # Hinglish control commands
    HINGLISH_CONTROL_PATTERNS = [
        (r'\b(awaaz badhao|volume badhao|sound badhao|awaaz tez karo)\b', 'volume_up'),
        (r'\b(awaaz kam karo|volume kam karo|sound kam karo|dheeme karo)\b', 'volume_down'),
        (r'\b(chup raho|shant raho|ruko|ruk jao|band karo)\b', 'standby'),
        (r'\b(gaana chalao|song play karo|play karo)\b', 'media_play'),
    ]

    # Explicit phone pairing triggers (must be explicit intent, not just mentioning "connection")
    PAIRING_TRIGGERS = [
        r'\b(pair (my |the )?phone|open (the )?qr( code)?|show (the )?qr( code)?|connect phone via qr|pairing qr|pairing widget)\b',
        r'\b(start pairing|scan qr|display qr)\b',
    ]

    # Standby triggers
    STANDBY_TRIGGERS = [
        r'\b(enter standby|go to standby|standby mode|go to sleep|sleep now|shut up|be quiet|mute yourself)\b',
        r'\b(stop listening|standby jarvis|jarvis standby)\b',
        r"\b(?:don't|don’t|do not) (?:speak|talk|respond)(?: again)? until i (?:call|wake|recall|say hey jarvis)\b",
        r'\b(goodbye|bye jarvis|goodbye jarvis|bye bye|see you later|i have to go|i gotta go|alvida|chalta hoon)\b',
    ]

    # System control triggers
    SYSTEM_CONTROL_TRIGGERS = {
        'volume_up': r'\b(volume up|increase volume|raise volume|louder|turn it up)\b',
        'volume_down': r'\b(volume down|decrease volume|lower volume|quieter|turn it down)\b',
        'mute': r'\b(mute volume|mute sound|mute audio|silence audio)\b',
        'unmute': r'\b(unmute|restore volume)\b',
        'brightness_up': r'\b(increase brightness|raise brightness|brighter)\b',
        'brightness_down': r'\b(decrease brightness|lower brightness|dimmer|dim screen)\b',
        'lock_screen': r'\b(lock (the )?screen|lock pc|lock computer)\b',
        'shutdown': r'\b(shut down|shutdown|turn off the (pc|computer|system)|power off)\b',
        'restart': r'\b(restart|reboot|restart the (pc|computer|system)|reboot the (pc|computer|system))\b',
    }

    # Conversational statement / troubleshooting / status check patterns
    CONVERSATIONAL_INQUIRY_PATTERNS = [
        r'^(why|how|what|when|where|who|is|are|can you explain|tell me|could you)\b',
        r'\b(not working|showing|unavailable|failed|error|reason why|problem|issue|troubleshoot|help me with)\b',
        r'\b(what should (i|we) do|how do (i|we))\b',
    ]

    @staticmethod
    def device_targets(text: str) -> set[str]:
        """Select devices from this utterance, never from previous model context.

        Quoted content is data (e.g. text being typed), not a device instruction.
        Negated phone references cannot authorize the Android adapter.
        """
        text = re.sub(r'"[^"\n]*"|`[^`\n]*`|“[^”\n]*”|(?<!\w)\x27[^\x27\n]*\x27(?!\w)',
                      ' ', text or '').casefold()
        text = re.sub(
            r"\b(?:not|never|don't|do not|without)\s+"
            r'(?:(?:on|from|using|use|control|touch|the|my|this|a|your|android)\s+)*'
            r'(?:phone|mobile|smartphone)\b', ' ', text)
        targets = set()
        if re.search(r'\b(phone|mobile|android|smartphone|vivo)\b', text):
            targets.add('phone')
        if re.search(r'\b(pc|computer|desktop|laptop)\b', text):
            targets.add('pc')
        return targets or {'pc'}

    @staticmethod
    def _is_action_request(text: str) -> bool:
        text = re.sub(r'^\s*(?:hey\s+jarvis|jarvis|bhai|yaar)\b[\s,:-]*', '', text, flags=re.IGNORECASE)
        for _ in range(4):
            stripped = re.sub(
                r'^(?:(?:can|could|would|will) you\s+|'
                r'(?:kya aap|kya tum|zara|ek baar|bhai|yaar)\s+|'
                r'(?:please|kindly|first|then|now)\b[\s,:-]*)',
                '', text, flags=re.IGNORECASE
            )
            if stripped == text:
                break
            text = stripped
        return bool(re.match(
            r'^(open|launch|close|focus|switch|move|resize|maximize|minimize|set|increase|'
            r'decrease|reduce|raise|lower|turn|mute|unmute|play|pause|resume|stop|start|'
            r'click|tap|scroll|type|press|copy|paste|send|call|dial|pair|connect|disconnect)\b',
            text, flags=re.IGNORECASE
        ))

    @classmethod
    def normalize_text(cls, text: str) -> str:
        """Apply phonetic normalization, whitespace cleanup, and dialect corrections."""
        if not text or not isinstance(text, str):
            return ""
        leading_space = " " if text.startswith(" ") else ""
        trailing_space = " " if text.endswith(" ") else ""
        normalized = text.strip()

        from .command_values import transform_unprotected
        def clean(fragment):
            for pattern, replacement in cls.PHONETIC_REPLACEMENTS:
                fragment = re.sub(pattern, replacement, fragment, flags=re.IGNORECASE)
            return re.sub(r'\s+', ' ', fragment)
        normalized = transform_unprotected(normalized, clean)
        res = normalized.strip()
        if not res:
            return ""
        return leading_space + res + trailing_space

    @classmethod
    def analyze(cls, text: str) -> NLUResult:
        from .command_values import number_slots, parse_control_command
        result = cls._classify(text)
        command = parse_control_command(text)
        if command:
            result.entities.update(control_arguments=command[1], values=number_slots(text))
        return result

    @classmethod
    def _classify(cls, text: str) -> NLUResult:
        """Classify user utterance into semantic intent category with entity extraction."""
        normalized = cls.normalize_text(text)
        from .command_values import mask_protected
        lower = mask_protected(normalized).casefold()

        # 1. Check Standby Intent
        for pattern in cls.STANDBY_TRIGGERS:
            if re.search(pattern, lower):
                return NLUResult(
                    raw_text=text,
                    normalized_text=normalized,
                    category=IntentCategory.STANDBY,
                    confidence=0.95,
                    suggested_action="enter_standby",
                )

        # 2. Check Hinglish Control Commands
        for pattern, action in cls.HINGLISH_CONTROL_PATTERNS:
            if re.search(pattern, lower):
                if action == 'standby':
                    return NLUResult(
                        raw_text=text,
                        normalized_text=normalized,
                        category=IntentCategory.STANDBY,
                        confidence=0.90,
                        suggested_action="enter_standby",
                    )
                return NLUResult(
                    raw_text=text,
                    normalized_text=normalized,
                    category=IntentCategory.SYSTEM_CONTROL,
                    confidence=0.90,
                    suggested_action=action,
                )

        # 3. Check Explicit Phone Pairing Request
        is_explicit_pairing = any(re.search(pat, lower) for pat in cls.PAIRING_TRIGGERS)
        if is_explicit_pairing:
            return NLUResult(
                raw_text=text,
                normalized_text=normalized,
                category=IntentCategory.PHONE_PAIRING,
                confidence=0.95,
                suggested_action="phone_pair",
            )

        # 4. Check JARVIS Mode Intent (test mode / production mode / mode status)
        if re.search(r'\b(activate (the )?test(ing)? mode|switch to (the )?test(ing)? mode|enter test(ing)? mode|test(ing)? mode|dev mode|switch to (the )?dev(elopment)? mode)\b', lower):
            return NLUResult(
                raw_text=text,
                normalized_text=normalized,
                category=IntentCategory.SYSTEM_CONTROL,
                confidence=0.95,
                suggested_action="switch_to_test_mode",
            )
        if re.search(r'\b(activate (the )?production mode|switch to (the )?production mode|enter production mode|production mode|prod mode|switch to (the )?prod mode)\b', lower):
            return NLUResult(
                raw_text=text,
                normalized_text=normalized,
                category=IntentCategory.SYSTEM_CONTROL,
                confidence=0.95,
                suggested_action="switch_to_production_mode",
            )
        if re.search(r'\b(what mode are you in|check (jarvis )?mode|current (jarvis )?mode|jarvis mode status|which mode)\b', lower):
            return NLUResult(
                raw_text=text,
                normalized_text=normalized,
                category=IntentCategory.SYSTEM_CONTROL,
                confidence=0.95,
                suggested_action="get_jarvis_mode",
            )

        # Check explicit confirmation / cancellation of held actions
        stripped_short = lower.strip(' .!')
        if re.fullmatch(r'\b(yes|confirm|proceed|do it|sure|yeah|yep|go ahead|affirmative|yes please)\b', stripped_short):
            return NLUResult(
                raw_text=text,
                normalized_text=normalized,
                category=IntentCategory.SYSTEM_CONTROL,
                confidence=0.95,
                suggested_action="confirm_action",
            )
        if re.fullmatch(r'\b(no|cancel|stop|abort|don\'t|dont|nevermind|wait)\b', stripped_short):
            return NLUResult(
                raw_text=text,
                normalized_text=normalized,
                category=IntentCategory.SYSTEM_CONTROL,
                confidence=0.95,
                suggested_action="cancel_action",
            )

        # Check explicit shutdown / restart / lock triggers
        if re.search(r'\b(shut down|shutdown|turn off the (pc|computer|system)|power off)\b', lower):
            return NLUResult(
                raw_text=text,
                normalized_text=normalized,
                category=IntentCategory.SYSTEM_CONTROL,
                confidence=0.95,
                suggested_action="shutdown",
            )
        if re.search(r'\b(restart|reboot|restart the (pc|computer|system)|reboot the (pc|computer|system))\b', lower):
            return NLUResult(
                raw_text=text,
                normalized_text=normalized,
                category=IntentCategory.SYSTEM_CONTROL,
                confidence=0.95,
                suggested_action="restart",
            )
        if re.search(r'\b(lock (the )?screen|lock pc|lock computer)\b', lower):
            return NLUResult(
                raw_text=text,
                normalized_text=normalized,
                category=IntentCategory.SYSTEM_CONTROL,
                confidence=0.95,
                suggested_action="lock_screen",
            )

        # Polite action requests are commands, even when phrased as a question.
        # Keep explanatory questions such as "why/how does ..." conversational.
        if cls._is_action_request(lower):
            return NLUResult(
                raw_text=text, normalized_text=normalized,
                category=(IntentCategory.PHONE_CONTROL if 'phone' in cls.device_targets(normalized)
                          else IntentCategory.SYSTEM_CONTROL),
                confidence=0.90,
            )

        # 4. Check Conversational Inquiry or Troubleshooting Report
        # If the user is reporting a problem, error, or asking what to do (even if mentioning "connection" or "phone"):
        is_hinglish_inquiry = any(re.search(pat, lower) for pat in cls.HINGLISH_INQUIRY_PATTERNS)
        is_general_inquiry = any(re.search(pat, lower) for pat in cls.CONVERSATIONAL_INQUIRY_PATTERNS)
        
        # Check specifically for problem reporting like:
        # "But it's still showing the PC unavailable connection..."
        # "The reason why it's showing hotspot..."
        # "Hum kya kare ringtone..."
        is_status_or_problem_report = bool(re.search(
            r'\b(still showing|unavailable connection|why it\'s showing|reason why|not connecting|error|problem)\b',
            lower
        ))

        if is_hinglish_inquiry or is_general_inquiry or is_status_or_problem_report:
            entities = {}
            if 'ringtone' in lower:
                entities['topic'] = 'ringtone'
            if 'connection' in lower or 'hotspot' in lower:
                entities['topic'] = 'network_connection'
            return NLUResult(
                raw_text=text,
                normalized_text=normalized,
                category=IntentCategory.CONVERSATIONAL,
                confidence=0.90,
                entities=entities,
                is_conversational_inquiry=True,
            )

        # 5. Check System Control Triggers
        for action, pattern in cls.SYSTEM_CONTROL_TRIGGERS.items():
            if re.search(pattern, lower):
                return NLUResult(
                    raw_text=text,
                    normalized_text=normalized,
                    category=IntentCategory.SYSTEM_CONTROL,
                    confidence=0.85,
                    suggested_action=action,
                )

        # 6. Check Phone Control Actions
        if re.search(r'\b(call|dial|phone call|ring)\b', lower) and not is_status_or_problem_report:
            return NLUResult(
                raw_text=text,
                normalized_text=normalized,
                category=IntentCategory.PHONE_CONTROL,
                confidence=0.80,
                suggested_action="phone_call",
            )

        # 7. Check Memory Intent
        if re.search(r'\b(what did (we|i) (talk|say|discuss)|recall conversation|past conversation|yesterday)\b', lower):
            return NLUResult(
                raw_text=text,
                normalized_text=normalized,
                category=IntentCategory.MEMORY,
                confidence=0.90,
                suggested_action="recall_conversation",
            )

        # 8. Check Vision Intent
        if re.search(r'\b(look at my screen|screen share|vision mode|camera preview|picture in picture)\b', lower):
            return NLUResult(
                raw_text=text,
                normalized_text=normalized,
                category=IntentCategory.VISION,
                confidence=0.90,
                suggested_action="control_vision_mode",
            )


        # Default to Conversational / Unknown
        return NLUResult(
            raw_text=text,
            normalized_text=normalized,
            category=IntentCategory.CONVERSATIONAL,
            confidence=0.50,
            is_conversational_inquiry=True,
        )

    @classmethod
    def validate_tool_intent(cls, tool_name: str, arguments: dict, user_text: str) -> tuple[bool, str]:
        """Validate whether a model-proposed tool call matches the user's natural language intent.

        Returns (allowed: bool, guidance_message: str).
        """
        if tool_name == 'execute_domain_tool':
            nested_name = arguments.get('tool_name')
            payload = arguments.get('arguments_json', '{}')
            if (not isinstance(nested_name, str) or nested_name == tool_name
                    or not isinstance(payload, str) or len(payload) > 65536):
                return False, 'Invalid domain tool request.'
            try:
                nested_args = json.loads(payload)
            except (ValueError, RecursionError):
                return False, 'Invalid domain tool arguments.'
            if not isinstance(nested_args, dict):
                return False, 'Domain tool arguments must be an object.'
            return cls.validate_tool_intent(nested_name, nested_args, user_text)

        from .command_values import control_value_guidance
        guidance = control_value_guidance(tool_name, arguments, user_text)
        if guidance:
            return False, guidance

        targets = cls.device_targets(user_text)
        if tool_name.startswith('phone_') and tool_name != 'phone_pair' and 'phone' not in targets:
            conversational = (tool_name in {'phone_list_contacts', 'phone_call'} and
                              cls.analyze(user_text).is_conversational_inquiry)
            return False, (
                ('The user is asking a conversational question. Answer their inquiry. ' if conversational else '') +
                'This request targets the PC by default. Use the matching PC tool. '
                'Android phone control requires an explicit phone/mobile target in the current user request; '
                'previous phone requests do not change the default.'
            )
        pc_tools = {'launch_app', 'open_application', 'open_website', 'open_page', 'browser_task',
                    'system_control', 'system_control_extension', 'system_power', 'lock_screen',
                    'shutdown_system', 'restart_system', 'confirm_last', 'cancel_last',
                    'confirm_system_action', 'cancel_system_action', 'hypr_dispatch', 'hypr_query',
                    'list_applications', 'list_windows', 'list_workspaces', 'read_screen',
                    'type_text', 'press_key', 'send_shortcut', 'set_volume', 'set_brightness',
                    'switch_workspace', 'manage_window', 'focus_window'}
        if targets == {'phone'} and tool_name in pc_tools:
            return False, 'The user explicitly targeted the phone. Use phone_control; do not act on the PC.'

        if not user_text and tool_name != 'phone_pair':
            return True, ""

        from .command_values import mask_protected
        lower_user = mask_protected(user_text).casefold() if user_text else ''
        platform_names = [
            'linkedin', 'github', 'slack', 'notion', 'spotify', 'google calendar', 'gcal',
            'google drive', 'gdrive', 'google sheets', 'gsheets', 'google docs', 'gdocs',
            'google workspace', 'google', 'gmail', 'discord', 'linear', 'jira', 'trello',
            'twitter', 'asana', 'zoom', 'airtable', 'hubspot', 'salesforce', 'figma',
            'gitlab', 'reddit', 'dropbox', 'clickup', 'whatsapp', 'telegram', 'stripe',
            'zendesk', 'shopify', 'teams', 'outlook', 'todoist'
        ]
        detected_platform = None
        for p in platform_names:
            if re.search(r'\b' + re.escape(p) + r'\b', lower_user):
                detected_platform = p
                break

        auth_page_tools = {'github_authorize', 'google_authorize', 'open_platform_authorization', 'connect_platform'}
        auth_word_pattern = (
            r'\b(authori[zs]e|authori[zs]ation|authori[zs]ing|authori[zs]ed|'
            r'auth|authenticat(e|ion|ing|ed)|re-?authori[zs]e|re-?authenticat(e|ion)|'
            r'login\s*page|log\s*in|sign\s*in|connect|reconnect|link|re-?link|'
            r'integrat(e|ion)|set\s*up|setup|sync|access)\b'
        )
        has_auth_word = bool(re.search(auth_word_pattern, lower_user))

        is_connection_status_intent = bool(re.search(
            r'\b(is\s*it\s*connect(ed|ing)?|connecting\s*to\s*those\s*or\s*not|connected\s*or\s*not|connecting\s*or\s*not|check\s*connection|status\s*of\s*connection|connection\s*status)\b',
            lower_user
        ) or (re.search(r'\b(is|are|check|verify)\b.*\b(connect(ed|ing)?|linked)\b', lower_user) and (detected_platform or 'platform' in lower_user or 'service' in lower_user)))

        # Rule: Status inquiries must NEVER open an authorization page
        if is_connection_status_intent:
            if tool_name in auth_page_tools:
                target = detected_platform or arguments.get('platform') or 'the platform'
                if target in ('github', 'gh', 'git') or tool_name == 'github_authorize':
                    log.info('NLU Gate blocked %s: user asked for connection status ("%s")', tool_name, user_text)
                    return False, (
                        f"The user is asking whether GitHub is connected or not: '{user_text}'. "
                        "Do NOT open the authorization page or invoke github_authorize. "
                        "Invoke native 'github_connection_status' instead to check and report connection status."
                    )
                if target in ('google', 'google workspace', 'google calendar', 'gcal', 'calendar', 'google drive', 'gdrive', 'drive', 'google sheets', 'gsheets', 'sheets', 'google docs', 'gdocs', 'docs', 'gmail', 'mail') or tool_name == 'google_authorize':
                    log.info('NLU Gate blocked %s: user asked for connection status ("%s")', tool_name, user_text)
                    return False, (
                        f"The user is asking whether Google Workspace is connected or not: '{user_text}'. "
                        "Do NOT open the authorization page or invoke google_authorize. "
                        "Invoke native 'google_connection_status' instead to check and report connection status."
                    )
                log.info('NLU Gate blocked %s: user asked for connection status ("%s")', tool_name, user_text)
                return False, (
                    f"The user is asking whether {target} is connected or connecting: '{user_text}'. "
                    f"Do NOT open the authorization page or invoke {tool_name}. "
                    f"Invoke 'check_platform_connection' with platform='{target}' instead to check and report status."
                )

            if tool_name in ('open_website', 'open_application', 'launch_app', 'open_page', 'web_search'):
                target = detected_platform or 'the platform'
                log.info('NLU Gate redirected %s to status tool: "%s"', tool_name, user_text)
                if target in ('github', 'gh', 'git'):
                    return False, f"The user is asking whether GitHub is connected. Invoke 'github_connection_status' instead of {tool_name}."
                if target in ('google', 'google workspace', 'google calendar', 'gcal', 'calendar', 'google drive', 'gdrive', 'drive', 'google sheets', 'gsheets', 'sheets', 'google docs', 'gdocs', 'docs', 'gmail', 'mail'):
                    return False, f"The user is asking whether Google Workspace is connected. Invoke 'google_connection_status' instead of {tool_name}."
                return False, f"The user is asking whether {target} is connected or connecting. Invoke 'check_platform_connection' with platform='{target}' instead of {tool_name}."

        # Rule: Authorization page tools require an explicit authorization-related keyword
        if tool_name in auth_page_tools:
            if not has_auth_word:
                log.info('NLU Gate blocked %s: no authorization-related word in utterance ("%s")', tool_name, user_text)
                if tool_name == 'github_authorize':
                    return False, (
                        "Do NOT invoke github_authorize. The user asked: "
                        f"'{user_text}'. All repositories and agent architectures are local on this PC (/home/g0pi/JARVIS OS and ~/.gemini/config/plugins/agency-agents). "
                        "Use local inspection tools (such as list_files, search_files, read_file) or discuss the repository directly."
                    )
                return False, (
                    f"Do NOT invoke '{tool_name}' (do not open the authorization page). "
                    "The user did not mention any authorization-related keyword (authorize, auth, authenticate, login page, sign in, connect, link). "
                    f"Utterance was: '{user_text}'. Address their inquiry or use inspection/read tools without opening an authorization page."
                )

            # User DID mention an auth word; enforce native GitHub & Google routing
            if tool_name in ('open_platform_authorization', 'connect_platform'):
                target_platform = (arguments.get('platform') or detected_platform or '').strip().lower()
                if target_platform in ('github', 'gh', 'git'):
                    return False, "For GitHub authorization, invoke native 'github_authorize' instead of Composio tools."
                if target_platform in ('google', 'google workspace', 'workspace', 'google calendar', 'gcal', 'calendar', 'google drive', 'gdrive', 'drive', 'google sheets', 'gsheets', 'sheets', 'google docs', 'gdocs', 'docs', 'gmail', 'mail'):
                    return False, "For Google Workspace authorization, invoke native 'google_authorize' instead of Composio tools."

            if tool_name == 'github_authorize':
                if not any(w in lower_user for w in ('github', 'git', 'repo', 'code')):
                    return False, "The user did not request GitHub authorization."

            if tool_name == 'google_authorize':
                if not any(w in lower_user for w in ('google', 'workspace', 'gmail', 'calendar', 'drive', 'docs', 'sheets')):
                    return False, "The user did not request Google Workspace authorization."

            return True, ""

        # Gating check_platform_connection for native platforms
        if tool_name == 'check_platform_connection':
            target_platform = (arguments.get('platform') or detected_platform or '').strip().lower()
            if target_platform in ('github', 'gh', 'git'):
                return False, "For GitHub connection status, invoke native 'github_connection_status' instead of check_platform_connection."
            if target_platform in ('google', 'google workspace', 'workspace', 'google calendar', 'gcal', 'calendar', 'google drive', 'gdrive', 'drive', 'google sheets', 'gsheets', 'sheets', 'google docs', 'gdocs', 'docs', 'gmail', 'mail'):
                return False, "For Google Workspace connection status, invoke native 'google_connection_status' instead of check_platform_connection."
            return True, ""

        # Gating execute_platform_action for native platforms
        if tool_name == 'execute_platform_action':
            target_platform = (arguments.get('platform') or detected_platform or '').strip().lower()
            if target_platform in ('github', 'gh', 'git'):
                return False, "GitHub is configured natively on JARVIS OS. Use native GitHub tools (github_list_repositories, github_list_issues, etc.) instead of execute_platform_action."
            if target_platform in ('google', 'google workspace', 'workspace', 'google calendar', 'gcal', 'calendar', 'google drive', 'gdrive', 'drive', 'google sheets', 'gsheets', 'sheets', 'google docs', 'gdocs', 'docs', 'gmail', 'mail'):
                return False, "Google Workspace is configured natively on JARVIS OS. Use native Google Workspace tools (gmail_search, calendar_list_events, drive_search_files, etc.) instead of execute_platform_action."
            return True, ""

        if tool_name in ('list_connected_platforms', 'disconnect_platform', 'github_connection_status', 'google_connection_status'):
            return True, ""

        # Redirect open_website when user explicitly requested to connect/authorize a platform
        if has_auth_word and (detected_platform or any(w in lower_user for w in ('platform', 'service', 'account', 'authorization page', 'login page'))):
            if tool_name in ('open_website', 'open_application', 'launch_app', 'open_page', 'browser_task'):
                target = detected_platform or 'the platform'
                log.info('NLU Gate redirected %s to platform integration: "%s"', tool_name, user_text)
                if target in ('github', 'gh', 'git') or 'github' in lower_user:
                    return False, f"The user wants to connect to or authorize GitHub. Do NOT invoke {tool_name}. Invoke native 'github_authorize' instead, which opens the OAuth page."
                if target in ('google', 'google workspace', 'google calendar', 'gcal', 'calendar', 'google drive', 'gdrive', 'drive', 'google sheets', 'gsheets', 'sheets', 'google docs', 'gdocs', 'docs', 'gmail', 'mail') or 'google' in lower_user:
                    return False, f"The user wants to connect to or authorize Google Workspace. Do NOT invoke {tool_name}. Invoke native 'google_authorize' instead, which opens the OAuth page."
                return False, (
                    f"The user wants to connect to or authorize {target}. "
                    f"Do NOT invoke {tool_name}. "
                    f"Invoke 'connect_platform' (or 'open_platform_authorization') with platform='{target}' instead, "
                    "which generates the direct OAuth link and opens the authorization page."
                )

        analysis = cls.analyze(user_text)

        # Guard 1: Block phone_pair if user did NOT explicitly request pairing or QR display
        if tool_name == 'phone_pair':
            if analysis.category != IntentCategory.PHONE_PAIRING:
                log.info('NLU Gate blocked %s: user intent is %s ("%s")',
                         tool_name, analysis.category.value, user_text)
                return False, (
                    f"The user did NOT command to open or scan the pairing QR code. "
                    f"Their statement was: '{user_text}'. "
                    f"Please answer their inquiry or troubleshoot their connection status conversationally "
                    f"without opening the pairing widget."
                )

        # Guard 2: Block media or contact tools when asking conversational questions (e.g. "Hum kya kare ringtone")
        if analysis.is_conversational_inquiry and analysis.category == IntentCategory.CONVERSATIONAL:
            # If the user is asking a question or explaining an issue, block intrusive actions
            intrusive_tools = {'system_control_extension', 'phone_list_contacts', 'phone_call', 'phone_pair'}
            if tool_name in intrusive_tools:
                log.info('NLU Gate blocked %s for conversational query: "%s"', tool_name, user_text)
                topic = analysis.entities.get('topic', 'the topic')
                return False, (
                    f"The user is asking a conversational question or seeking advice regarding {topic}: '{user_text}'. "
                    f"Do NOT execute tool '{tool_name}'. "
                    f"Please respond directly in spoken words with clear advice or explanation."
                )

        # Guard 3: Standby gating
        if tool_name == 'enter_standby' and analysis.category != IntentCategory.STANDBY:
            lower = lower_user
            if not any(w in lower for w in ('standby', 'sleep', 'quiet', 'mute', 'chup', 'ruko', 'bye', 'goodbye', 'have to go', 'gotta go', 'alvida')):
                return False, "User did not command to enter standby mode."

        return True, ""

    CONFIRM_COLLOQUIAL_FILLERS = frozenset({
        "please", "pls", "plz", "thanks", "thank", "you", "yeah", "yep", "ok", "okay",
        "now", "bhai", "yaar", "jarvis", "toh", "sir", "just", "for sure", "right now",
        "man", "boss", "bro", "definitely", "sure", "well", "so", "actually",
        "to", "me", "with", "it", "that", "for", "all", "good",
    })

    @classmethod
    def evaluate_confirmation(
        cls,
        heard_phrase: str,
        confirm_words: list[str] | set[str] | None = None,
        cancel_words: list[str] | set[str] | None = None,
        held_action: str = "",
    ) -> ConfirmationDecision:
        """Deterministically evaluate if heard_phrase affirms, declines, or ambivalently addresses held_action.

        Enforces strict fail-closed negation precedence.
        """
        if not heard_phrase or not heard_phrase.strip():
            return ConfirmationDecision.AMBIGUOUS

        from .config import DEFAULT_CONFIRM_WORDS, DEFAULT_CANCEL_WORDS

        # 1. Phonetic normalization & whitespace stripping
        normalized = cls.normalize_text(heard_phrase)
        cleaned = re.sub(r"[^\w\s']+", " ", normalized.casefold()).strip()
        tokens = cleaned.split()
        if not tokens:
            return ConfirmationDecision.AMBIGUOUS

        confirm_set = {
            re.sub(r"[^\w\s']+", " ", c.casefold()).strip()
            for c in (confirm_words if confirm_words is not None else DEFAULT_CONFIRM_WORDS)
        }
        cancel_set = {
            re.sub(r"[^\w\s']+", " ", c.casefold()).strip()
            for c in (cancel_words if cancel_words is not None else DEFAULT_CANCEL_WORDS)
        }

        # 2. Strict Negation & Decline Precedence (Tier 1)
        # Any occurrence of cancel words or explicit negation tokens forces DECLINED.
        # This overrides any simultaneous affirmative words (e.g., "yeah no", "haan mat karo").
        for cancel_phrase in cancel_set:
            if cancel_phrase and (cleaned == cancel_phrase or re.search(r'\b' + re.escape(cancel_phrase) + r'\b', cleaned)):
                log.info("Confirmation decision DECLINED (cancel word match '%s'): '%s'", cancel_phrase, heard_phrase)
                return ConfirmationDecision.DECLINED

        # Check token-level negation patterns
        negation_pattern = re.compile(
            r"\b(don't|dont|do not|never|not|no|nope|nah|mat|nahi|nahin|ruko|ruk jao|rehne do|band karo|abort|cancel|forget it|leave it)\b",
            re.IGNORECASE,
        )
        if negation_pattern.search(cleaned):
            log.info("Confirmation decision DECLINED (negation match): '%s'", heard_phrase)
            return ConfirmationDecision.DECLINED

        # 3. Interrogative / Question Check (Tier 2)
        # Conversational questions about the action (e.g. "what time is it?", "why would I do that?", "are you sure?")
        # should remain AMBIGUOUS rather than accidentally affirming.
        if "?" in heard_phrase:
            log.info("Confirmation decision AMBIGUOUS (question mark present): '%s'", heard_phrase)
            return ConfirmationDecision.AMBIGUOUS

        interrogative_pattern = re.compile(
            r"\b(why|how|what|when|where|who|which|is it|will it|are you|can you|kya|kyun|kaise|kab|kahan)\b",
            re.IGNORECASE,
        )
        if interrogative_pattern.search(cleaned):
            log.info("Confirmation decision AMBIGUOUS (interrogative query): '%s'", heard_phrase)
            return ConfirmationDecision.AMBIGUOUS

        # 4. Affirmative Assent Alignment (Tier 3)
        # Check exact and substring match against confirm_set
        for conf in confirm_set:
            if not conf:
                continue
            if cleaned == conf:
                log.info("Confirmation decision AFFIRMED (exact match '%s'): '%s'", conf, heard_phrase)
                return ConfirmationDecision.AFFIRMED
            # Match prefix + fillers or fillers + suffix
            if cleaned.startswith(conf + " "):
                rest = cleaned[len(conf):].split()
                if rest and all(t in cls.CONFIRM_COLLOQUIAL_FILLERS for t in rest):
                    log.info("Confirmation decision AFFIRMED (prefix '%s' + fillers): '%s'", conf, heard_phrase)
                    return ConfirmationDecision.AFFIRMED
            if cleaned.endswith(" " + conf):
                lead = cleaned[:-len(conf)].split()
                if lead and all(t in cls.CONFIRM_COLLOQUIAL_FILLERS for t in lead):
                    log.info("Confirmation decision AFFIRMED (fillers + suffix '%s'): '%s'", conf, heard_phrase)
                    return ConfirmationDecision.AFFIRMED

        # Check if stripping all fillers leaves a known confirm word
        non_filler_tokens = [t for t in tokens if t not in cls.CONFIRM_COLLOQUIAL_FILLERS]
        if non_filler_tokens:
            reduced = " ".join(non_filler_tokens)
            if reduced in confirm_set:
                log.info("Confirmation decision AFFIRMED (reduced filler match '%s'): '%s'", reduced, heard_phrase)
                return ConfirmationDecision.AFFIRMED
            if all(t in confirm_set for t in non_filler_tokens):
                log.info("Confirmation decision AFFIRMED (all affirmative tokens): '%s'", heard_phrase)
                return ConfirmationDecision.AFFIRMED

        # Check contextual match with held action (e.g. "reboot now" or "reboot" when held is "reboot the system")
        if held_action:
            clean_held = re.sub(r"[^\w\s']+", " ", held_action.casefold()).strip()
            held_keywords = [
                kw for kw in clean_held.split()
                if kw not in ("the", "system", "pc", "computer", "action", "last") and len(kw) > 2
            ]
            if any(kw in non_filler_tokens for kw in held_keywords) and len(non_filler_tokens) <= 3:
                log.info("Confirmation decision AFFIRMED (held action keyword match in '%s'): '%s'", held_action, heard_phrase)
                return ConfirmationDecision.AFFIRMED

        log.info("Confirmation decision AMBIGUOUS: '%s'", heard_phrase)
        return ConfirmationDecision.AMBIGUOUS


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == "eval":
        phrase = sys.argv[2]
        action = sys.argv[3] if len(sys.argv) > 3 else ""
        analysis = NLUEngine.analyze(phrase)
        decision = NLUEngine.evaluate_confirmation(phrase, held_action=action)
        print(json.dumps({
            "raw": phrase,
            "normalized": analysis.normalized_text,
            "category": analysis.category.value,
            "decision": decision.value,
        }, indent=2))
