"""Deterministic, extractive views of dialogue; never evidence of completion."""
import re


def render_daily_summary(turns) -> str:
    """Quote source messages with IDs, without inferring tasks or outcomes.

    Categories are lexical cues only. The exporter escapes the returned text
    with its existing plain-text policy before publishing it.
    """
    buckets = {name: [] for name in (
        'User requests', 'User decisions', 'User preferences', 'Other user statements',
        'Assistant reported outcomes (unverified)', 'Other assistant statements',
        'Explicit follow-up mentions')}
    for turn in turns:
        if isinstance(turn, dict):
            identifier = turn.get('id')
            role = turn.get('role')
            text = turn.get('text', turn.get('content', ''))
        else:
            identifier, role, text, _ = turn
        if not isinstance(text, str) or role not in ('user', 'assistant'):
            continue
        excerpt = text if len(text) <= 400 else text[:400] + '\n[Excerpt ends; see source message for the remainder.]'
        quote = f'message {identifier} ({role}), verbatim excerpt:\n{excerpt}'
        if role == 'user':
            if re.search(r'\b(prefer|prefers|preference|favorite|favourite)\b', text, re.I):
                category = 'User preferences'
            elif re.search(r'\b(decided|choose|chosen|decision|let[’\']s|go with)\b', text, re.I):
                category = 'User decisions'
            elif re.search(r'\b(please|can you|could you|help me|i want|i need)\b', text, re.I):
                category = 'User requests'
            else:
                category = 'Other user statements'
        else:
            category = ('Assistant reported outcomes (unverified)' if re.search(
                r'\b(completed|finished|done|implemented|fixed|created|updated|tested|passed|failed)\b',
                text, re.I) else 'Other assistant statements')
        buckets[category].append(quote)
        if re.search(r'\b(follow[ -]?up|later|tomorrow|next step|next steps|todo|to-do)\b', text, re.I):
            buckets['Explicit follow-up mentions'].append(quote)
    sections = [
        'Extractive daily summary. Categories use wording cues only; each entry is a verbatim '
        'source message, not an inferred fact. Assistant reports are unverified claims, '
        'including any claims of completion. Follow-up mentions do not establish pending tasks.'
    ]
    for name, entries in buckets.items():
        if entries:
            section = '## ' + name + '\n\n' + '\n\n'.join(entries[:8])
            if len(entries) > 8:
                section += f'\n\n{len(entries) - 8} additional mentions retained in the linked daily transcript.'
            sections.append(section)
    if len(sections) == 1:
        sections.append('No supported dialogue messages to summarize.')
    return '\n\n'.join(sections)
