"""Small voice-facing learning queries; no model-accessible lesson publication."""
from .experience import ExperienceLibrary, PROJECT


class LearningService:
    def __init__(self, capture, project=PROJECT, events=None):
        self.capture, self.project = capture, project
        self.library = ExperienceLibrary(capture.store.root)
        from .jobs import LocalHarnessJobs
        self.jobs = LocalHarnessJobs(capture.store.root, events)

    def harness_status(self):
        from .jobs import local_status
        return {**local_status(), 'learning_enabled': True,
                'running_bundle': self.capture.bundle.digest, 'check': self.jobs.status(),
                'mode': 'offline_only', 'automatic_activation': False}

    async def close(self):
        await self.jobs.close()

    def status(self):
        capture = self.capture
        lessons = self.library.applicable(project=self.project, bundle=capture.bundle.digest,
                                           voice_model=capture.model)
        pending = [row for row in self.library.entries() if row['status'] == 'proposed' and
                   row['kind'] == 'observation' and row['scope'] == self.library._scope(self.project) and
                   row['evidence'].get('bundle') == capture.bundle.digest and
                   row['evidence'].get('model') == capture.model]
        return {'enabled': True, 'running_bundle': capture.bundle.digest, 'model': capture.model,
                'role': 'research', 'project': self.project, 'applicable_lessons': len(lessons),
                'unverified_feedback': len(pending), 'capture_dropped': capture.dropped,
                'capture_failed': capture.failed, 'automatic_refinement': False,
                'selected_bundle_matches_running': self.library.registry.status()['active'] == capture.bundle.digest}

    def lessons(self):
        rows = self.library.applicable(project=self.project, bundle=self.capture.bundle.digest,
                                       voice_model=self.capture.model)
        return {'lessons': [{'id': row['id'], 'cue': row['evidence']['cue'],
                            'excerpt': row['text'][:500], 'truncated': len(row['text']) > 500,
                            'evidence_run': row['evidence']['run_id']} for row in rows[:5]],
                'total_matching': len(rows), 'scope': 'Current project, research role, running model and bundle only',
                'authority': 'Reviewed procedural reference; does not grant permissions or override fixed rules'}

    def feedback(self, text, category='other', episode=None):
        return self.library.feedback(text, category, project=self.project, model=self.capture.model,
                                     bundle=self.capture.bundle.digest, episode=episode)
