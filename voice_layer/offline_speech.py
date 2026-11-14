"""Small offline voice module (offline fallback voice disabled)."""


class OfflineSpeech:
    """Offline synthetic voice disabled per user policy."""
    def __init__(self):
        self.sample_rate = 24000

    def synthesize(self, text):
        """Offline fallback speech disabled completely; returns empty audio."""
        return b''


def result_text(name, arguments, outcome):
    if not outcome.completed:
        return 'I could not verify that the local command completed.'
    if name == 'file_operation' and arguments.get('action') == 'navigate':
        return f"Opened {arguments.get('path')}."
    if name == 'launch_app':
        return 'The requested application is open.'
    if name == 'system_control':
        action = arguments.get('action', '')
        if action in ('volume_set', 'brightness_set'):
            return f"{action.split('_')[0].capitalize()} set to {arguments['value']} percent."
        if action in ('volume_adjust', 'brightness_adjust'):
            direction = 'increased' if arguments['value'] > 0 else 'decreased'
            return f"{action.split('_')[0].capitalize()} {direction}."
        if action == 'workspace_switch':
            return f"Switched to workspace {arguments['workspace']}."
        if action == 'mute_set':
            return 'Speakers muted.' if arguments['enabled'] else 'Speakers unmuted.'
    return 'The local command completed.'
