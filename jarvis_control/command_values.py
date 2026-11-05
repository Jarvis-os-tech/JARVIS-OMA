"""Bounded typed values with original transcript offsets; never executes actions.

Uses public OVOS span APIs. JARVIS owns protection, ambiguity and action scope.
Only English is admitted in this pilot; unsupported language is explicit.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import re

from connectors.calendar_time import DEFAULT_ZONE, calendar_datetime, calendar_zone

MAX_TEXT = 512
_COMMAND_PREFIX = r'(?:(?:(?:hey|okay|ok)\s+)?jarvis[,\s]+)?(?:(?:can|could|would|will) you\s+)?(?:please\s+)?'
_PROTECTED = re.compile(
    r'```[\s\S]*?(?:```|$)|`[^`\n]*(?:`|$)|'
    r'"(?:\\.|[^"\\])*(?:"|$)|“[^”]*(?:”|$)|‘[^’]*(?:’|$)|'
    r"(?<!\w)'(?:\\.|[^'\\\n])*(?:'|$)|"
    r'https?://[^\s<>]+|www\.[^\s<>]+|'
    r'(?<!\w)(?:~?/|[A-Za-z]:\\)[^\s<>"`]+|'
    r'\b[A-Za-z_][\w.-]*\d[\w.-]*\b|'
    r'\b[^\s/]+\.(?:txt|py|md|json|pdf|csv|toml|png|jpg|mp3|wav)\b', re.IGNORECASE)


def protected_ranges(text):
    return [match.span() for match in _PROTECTED.finditer(text)]


def mask_protected(text):
    chars = list(text)
    for start, end in protected_ranges(text):
        chars[start:end] = ' ' * (end - start)
    return ''.join(chars)


def transform_unprotected(text, transform):
    result, cursor = [], 0
    for start, end in protected_ranges(text):
        result.extend((transform(text[cursor:start]), text[start:end]))
        cursor = end
    result.append(transform(text[cursor:]))
    return ''.join(result)


def _slot(raw, masked, span, kind, value):
    if not (type(span.start) is int and type(span.end) is int
            and 0 <= span.start < span.end <= len(raw)
            and masked[span.start:span.end] == span.surface
            and raw[span.start:span.end] == span.surface):
        raise ValueError('Invalid parser offsets')
    return dict(kind=kind, start=span.start, end=span.end,
                surface=raw[span.start:span.end], value=value)


def number_slots(text, language='en-US'):
    from ovos_number_parser import extract_number_spans
    masked = mask_protected(text)
    slots = []
    for span in extract_number_spans(masked, language):
        value = span.value
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('Invalid parser number')
        slot = _slot(text, masked, span, 'number', value)
        # Upstream spans omit a spoken minus sign. Preserve its source evidence.
        sign = re.search(r'\b(?:minus|negative)\s+$', masked[:span.start], re.IGNORECASE)
        if sign:
            slot.update(start=sign.start(), surface=text[sign.start():span.end], value=-abs(value))
        slots.append(slot)
    return slots


def parse_control_command(text):
    """Exact single PC command only. No clamping, rounding or discarded suffixes."""
    if not isinstance(text, str) or len(text) > MAX_TEXT or protected_ranges(text):
        return None
    prefix = _COMMAND_PREFIX
    match = re.fullmatch(prefix + r'(?:set\s+)?(?:the\s+)?(volume|brightness)(?:\s+to)?\s+(.+?)(?:\s+please)?[.!?]?\s*',
                         text.strip(), re.IGNORECASE)
    workspace = re.fullmatch(prefix + r'(?:(?:switch|go)\s+to\s+)?workspace\s+(.+?)(?:\s+please)?[.!?]?\s*',
                             text.strip(), re.IGNORECASE)
    if not match and not workspace:
        return None
    noun, fragment = (match[1].lower(), match[2]) if match else ('workspace', workspace[1])
    if noun != 'workspace':
        fragment = re.sub(r'\s*(?:%|percent)\s*$', '', fragment, flags=re.IGNORECASE).strip()
    try:
        slots = number_slots(fragment)
    except (ImportError, ValueError, NotImplementedError):
        return None
    if len(slots) != 1 or slots[0]['start'] != 0 or slots[0]['end'] != len(fragment):
        return None
    value = slots[0]['value']
    if value != int(value) or not (1 if noun in ('brightness', 'workspace') else 0) <= value <= (10 if noun == 'workspace' else 100):
        return None
    args = ({'action': 'workspace_switch', 'workspace': str(int(value))} if noun == 'workspace'
            else {'action': noun + '_set', 'value': int(value)})
    return 'system_control', args


def _dedupe(slots):
    kept = []
    for slot in sorted(slots, key=lambda s: (-(s['end'] - s['start']), s['start'])):
        if not any(k['kind'] == slot['kind'] and k['start'] <= slot['start']
                   and slot['end'] <= k['end'] and k['value'] == slot['value'] for k in kept):
            kept.append(slot)
    return sorted(kept, key=lambda s: (s['start'], s['end'], s['kind']))


def control_value_guidance(tool_name, arguments, text):
    """Reject mismatched model arguments for this pilot's exact numeric commands."""
    if tool_name not in {'system_control', 'set_volume', 'set_brightness', 'switch_workspace'}:
        return ''
    parsed = parse_control_command(text)
    if not parsed:
        # These are candidate absolute controls, but their entire value could
        # not be resolved. Do not let a model silently pick a number or clamp it.
        candidate = re.fullmatch(
            _COMMAND_PREFIX +
            r'(?:set\s+)?(?:the\s+)?(?:volume|brightness)(?:\s+to)?\s+(.+?)[.!?]?\s*',
            text.strip(), re.IGNORECASE)
        if candidate and candidate[1].casefold() not in {'up', 'down'}:
            return 'The requested numeric control is ambiguous, unsupported or out of range. Ask for one explicit valid whole-number value; do not guess, round or clamp.'
        return ''
    expected = parsed[1]
    if tool_name == 'system_control':
        if isinstance(arguments.get('action'), str) and arguments['action'].endswith('_status'):
            return ''
        fields = ('action', 'workspace') if expected['action'] == 'workspace_switch' else ('action', 'value')
        valid = all(arguments.get(key) == expected[key] and not isinstance(arguments.get(key), bool) for key in fields)
    elif expected['action'] == 'workspace_switch':
        valid = tool_name == 'switch_workspace' and str(arguments.get('workspace')) == expected['workspace']
    else:
        valid = (tool_name == 'set_' + expected['action'].removesuffix('_set')
                 and type(arguments.get('percent')) is int and arguments['percent'] == expected['value']
                 and not any(key in arguments for key in ('action', 'direction', 'delta')))
    return '' if valid else 'Tool arguments disagree with the explicit spoken value. Use the exact parsed control and value; do not substitute a different setting.'


def parse_values(text, *, language='en-US', include_temporal=False, anchor=None, time_zone=DEFAULT_ZONE):
    result = dict(status='ok', raw_text=text, language=language, values=[], diagnostics=[],
                  requires_clarification=False, candidate_only=True)

    def diagnose(code):
        result['diagnostics'].append(code)
        result['requires_clarification'] = True

    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT or len(text.split()) > 64:
        result.update(status='invalid_input', raw_text=text if isinstance(text, str) else '')
        return result
    if not isinstance(language, str) or language.lower().split('-')[0] != 'en':
        result['status'] = 'unsupported_language'
        return result
    try:
        result['values'] = number_slots(text, language)
        if include_temporal:
            zone = calendar_zone(time_zone)
            if not isinstance(anchor, datetime) or anchor.tzinfo is None or anchor.utcoffset() is None:
                raise ValueError('Temporal parsing requires an aware anchor')
            anchor = anchor.astimezone(zone)
            result.update(anchor=anchor.isoformat(), time_zone=zone.key)
            masked = mask_protected(text)
            # Timezone text must agree with the explicit zone parameter. Never
            # silently ignore a timezone the upstream language parser drops.
            zones = re.findall(r'\b(?:[A-Za-z_]+/[A-Za-z_]+(?:/[A-Za-z_]+)?|IST|PST|PDT|EST|EDT|CST|CDT|MST|MDT|BST|CET|CEST|GMT|UTC)\b', masked, re.IGNORECASE)
            aliases = {'IST': DEFAULT_ZONE, 'UTC': 'UTC', 'GMT': 'UTC'}
            if (any(aliases.get(z.upper(), z) != zone.key for z in zones)
                    or re.search(r'\b(?:eastern|pacific|central|mountain|aest|aedt|jst|kst|bst)\b', masked, re.IGNORECASE)):
                diagnose('timezone_needs_clarification')
                return result
            iso = list(re.finditer(r'\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?\b', masked))
            if iso:
                if len(iso) != 1:
                    diagnose('multiple_datetime_candidates')
                    return result
                match = iso[0]
                value = calendar_datetime(match[0], zone)
                result['values'].append(dict(kind='datetime', start=match.start(), end=match.end(),
                                             surface=match[0], value=value.isoformat()))
                return result
            if re.search(r'\b\d{1,4}[/-]\d{1,2}[/-]\d{1,4}\b', masked):
                diagnose('numeric_date_needs_explicit_iso_datetime')
                return result
            from ovos_date_parser import extract_datetime_spans, extract_duration_spans
            temporal = []
            duration_spans = extract_duration_spans(masked, language)
            for span in extract_datetime_spans(masked, language, anchor_date=anchor):
                value = span.value
                if not isinstance(value, datetime) or value.tzinfo is None:
                    raise ValueError('Invalid parser datetime')
                # Upstream local-time guesses must pass existing DST validation.
                local = value.astimezone(zone)
                elapsed = next((d for d in duration_spans if
                                span.start <= d.start and d.end == span.end
                                and re.search(r'\b(?:in|after)\s*$', masked[:d.start], re.IGNORECASE)
                                and re.fullmatch(r'\s*(?:(?:in|after)\s*)?', masked[span.start:d.start], re.IGNORECASE)), None)
                if elapsed is not None:
                    # A duration counts elapsed seconds across a DST transition,
                    # unlike calendar wall-clock addition in the upstream parser.
                    local = (anchor.astimezone(timezone.utc) + elapsed.value).astimezone(zone)
                else:
                    calendar_datetime(local.replace(tzinfo=None).isoformat(), zone)
                temporal.append(_slot(text, masked, span, 'datetime', local.isoformat()))
            for span in duration_spans:
                seconds = span.value.total_seconds()
                if (not math.isfinite(seconds) or seconds <= 0 or
                        any(s['value'] < 0 and s['end'] <= span.end and s['start'] >= span.start
                            for s in result['values'])):
                    diagnose('duration_must_be_positive')
                    continue
                temporal.append(_slot(text, masked, span, 'duration', seconds))
            temporal = _dedupe(temporal)
            dates = [s for s in temporal if s['kind'] == 'datetime']
            for slot in dates:
                surface = slot['surface']
                relative = re.search(r'\b(?:seconds?|minutes?|hours?)\b', surface, re.IGNORECASE)
                ampm = re.search(r'\b(?:a\.?m\.?|p\.?m\.?|noon|midnight)\b', surface, re.IGNORECASE)
                clock24 = re.search(r'\b(?:[01]\d|2[0-3]):[0-5]\d\b', surface)
                if not (relative or ampm or clock24):
                    diagnose('date_or_clock_needs_explicit_time_and_ampm')
            if len(dates) > 1:
                diagnose('multiple_datetime_candidates')
            result['values'].extend(temporal)
        if not result['values']:
            result['status'] = 'no_match'
    except ImportError:
        result['status'] = 'dependency_unavailable'
        diagnose('install_parsing_dependencies')
    except NotImplementedError:
        result['status'] = 'unsupported_language'
    except (ValueError, OverflowError, TypeError):
        result['status'] = 'invalid_parse'
        diagnose('invalid_or_ambiguous_value')
    return result
