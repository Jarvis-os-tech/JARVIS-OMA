"""Readable task labels; transport identities remain internal."""
import re


def task_name(text, limit=72):
    lines = str(text or '').splitlines()
    lines = [line.strip(' #*-\t') for line in lines]
    lines = [line for line in lines if line and line.lower() not in
             {'task', 'goal', 'context', 'expected result', 'constraints'}]
    label = re.sub(r'\s+', ' ', lines[0] if lines else 'Untitled task')
    label = re.sub(r'^(?:task|goal)\s*:\s*', '', label, flags=re.I)
    if len(label) > limit:
        label = label[:limit - 1].rsplit(' ', 1)[0].rstrip(' ,;:') + '…'
    return label
