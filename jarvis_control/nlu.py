"""Natural Language Processing (NLP) & Natural Language Understanding (NLU) Engine.

Provides phonetic normalization, multilingual (Hindi/Hinglish/Indian English) understanding,
intent classification, entity extraction, and semantic tool gating for JARVIS.
"""
from __future__ import annotations

import enum
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
        (r'\b(wi fi|wi-fi)\b', 'wifi'),
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
    ]

    # System control triggers
    SYSTEM_CONTROL_TRIGGERS = {
        'volume_up': r'\b(volume up|increase volume|raise volume|louder|turn it up)\b',
        'volume_down': r'\b(volume down|decrease volume|lower volume|quieter|turn it down)\b',
        'mute': r'\b(mute volume|mute sound|mute audio|silence audio)\b',
        'unmute': r'\b(unmute|restore volume)\b',
        'brightness_up': r'\b(increase brightness|raise brightness|brighter)\b',
        'brightness_down': r'\b(decrease brightness|lower brightness|dimmer|dim screen)\b',
        'lock_screen': r'\b(lock screen|lock pc|lock computer)\b',
    }

    # Conversational statement / troubleshooting / status check patterns
    CONVERSATIONAL_INQUIRY_PATTERNS = [
        r'^(why|how|what|when|where|who|is|are|can you explain|tell me|could you)\b',
        r'\b(not working|showing|unavailable|failed|error|reason why|problem|issue|troubleshoot|help me with)\b',
        r'\b(what should (i|we) do|how do (i|we))\b',
    ]

    @classmethod
    def normalize_text(cls, text: str) -> str:
        """Apply phonetic normalization, whitespace cleanup, and dialect corrections."""
        if not text or not isinstance(text, str):
            return ""
        normalized = text.strip()

        # Phonetic replacements
        for pattern, replacement in cls.PHONETIC_REPLACEMENTS:
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

        # Clean multiple spaces and trailing punctuation artifacts
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized.strip()

    @classmethod
    def analyze(cls, text: str) -> NLUResult:
        """Classify user utterance into semantic intent category with entity extraction."""
        normalized = cls.normalize_text(text)
        lower = normalized.casefold()

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
        if not user_text:
            return True, ""

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
            # Only allow if explicitly commanded
            lower = user_text.casefold()
            if not any(w in lower for w in ('standby', 'sleep', 'quiet', 'mute', 'chup', 'ruko')):
                return False, "User did not command to enter standby mode."

        return True, ""
