"""Shared memory taxonomy. Categorization never confers execution authority."""
import re

CATEGORIES = {
    'preferences': ('Preferences', 'preference'),
    'personal': ('Personal', 'identity'),
    'facts': ('Facts', 'fact'),
    'instructions': ('Instructions', 'instruction'),
    'projects': ('Projects', 'project'),
    'decisions': ('Decisions', 'decision'),
    'goals': ('Goals', 'goal'),
    'tasks': ('Tasks', 'task'),
    'procedures': ('Procedures', 'procedure'),
    'constraints': ('Constraints', 'constraint'),
    'observations': ('Observations', 'observation'),
    'episodes': ('Episodes', 'event'),
}

def category_for(entry):
    kind, key = entry.get('kind', 'fact'), entry.get('key', '')
    if kind == 'requirement':
        return 'constraints'
    if key.startswith('identity:'):
        return 'personal'
    for category, (_, typed_kind) in CATEGORIES.items():
        if kind == typed_kind and kind != 'fact':
            return category
    text = str(entry.get('text', '')).strip()
    if re.match(r'^(?:remember this instruction:|for future replies[, :])', text, re.I):
        return 'instructions'
    if re.match(r'^(?:I (?:now )?prefer\b|prefers?\b|my (?:preferred|favorite|favourite)\b)', text, re.I):
        return 'preferences'
    if re.match(r'^(?:my name is\b|call me\b|I (?:am|live in|work as|study)\b|my (?:birthday|occupation|timezone)\b)', text, re.I):
        return 'personal'
    return 'facts'

def validate_selection(category='all', scope='user'):
    if category not in ('all', 'conversations', 'documents', *CATEGORIES):
        raise ValueError('Unknown memory category')
    if not isinstance(scope, str) or (scope != 'user' and not re.fullmatch(r'project:[A-Za-z0-9_-]{1,80}', scope)):
        raise ValueError('scope must be user or project:NAME')
    return {'user', scope}
