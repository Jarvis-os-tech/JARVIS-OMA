"""Delivery receipts for native Hermes scheduled results; never a scheduler."""
from datetime import datetime
import json
from pathlib import Path
import time

from orchestration.hermes_setup import atomic_text


class NativeNotices:
    def __init__(self, root, bridge):
        self.path = Path(root) / 'native-notices.json'
        self.bridge = bridge
        self.last_poll = 0
        if self.path.is_symlink():
            raise ValueError('Native notice state must not be a symlink')
        if self.path.exists():
            if self.path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError('Native notice state exceeded its budget')
            self.state = json.loads(self.path.read_text())
        else:
            self.state = {'started_at': time.time(), 'seen': [], 'pending': {}}
            self.save()

    def save(self):
        atomic_text(self.path, json.dumps(self.state))

    async def events(self):
        if time.monotonic() - self.last_poll >= 15:
            self.last_poll = time.monotonic()
            try:
                results = await self.bridge.scheduled_results()
            except (OSError, ValueError, TimeoutError):
                results = {}
            for row in results.get('events', []):
                identity = 'hermes-cron:' + str(row['id']) + ':' + row['state']
                if identity in self.state['seen'] or identity in self.state['pending']:
                    continue
                try:
                    finished = datetime.fromisoformat(row['finished_at']).timestamp()
                except (TypeError, ValueError):
                    continue
                if finished < self.state['started_at']:
                    continue  # no replay of historic reminders after activation
                state = {'completed': 'completed', 'failed': 'failed', 'unknown': 'needs inspection; outcome is unknown'}[row['state']]
                self.state['pending'][identity] = {'id': identity, 'text': f"{row['name']}: scheduled run {state}."}
            self.save()
        return list(self.state['pending'].values())[:10]

    def acknowledge(self, identity):
        if self.state['pending'].pop(identity, None) is not None:
            self.state['seen'] = (self.state['seen'] + [identity])[-5000:]
            self.save()
