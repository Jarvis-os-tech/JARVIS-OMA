"""Small voice-facing learning queries; no model-accessible lesson publication."""
from .experience import ExperienceLibrary, PROJECT
import os


class LearningService:
    def __init__(self, capture, project=PROJECT, events=None, api_key=None):
        self.capture, self.project = capture, project
        self.library = ExperienceLibrary(capture.store.root)
        from .jobs import LocalHarnessJobs
        self.jobs = LocalHarnessJobs(capture.store.root, events)
        self.api_key = api_key

    def feedback_items(self):
        rows = [row for row in self.library.entries() if row['kind'] == 'observation' and
                row['status'] == 'proposed' and row['scope'] == self.library._scope(self.project) and
                row['evidence'].get('bundle') == self.capture.bundle.digest and
                row['evidence'].get('model') == self.capture.model]
        return {'status': 'success', 'summary': 'Unverified feedback for the running research harness.',
                'items': [{'id': row['id'], 'text': row['text'][:1000],
                           'category': row['evidence'].get('category'),
                           'validation': 'unverified'} for row in rows[-10:]],
                'total': len(rows), 'next_actions': ['Select feedback IDs for a refinement proposal.'],
                'artifacts': {}}

    def prepare_refinement(self, feedback_ids):
        from orchestration.model_routes import ROUTES
        if (not isinstance(feedback_ids, list) or not 1 <= len(feedback_ids) <= 5 or
                any(not isinstance(item, str) for item in feedback_ids) or
                len(set(feedback_ids)) != len(feedback_ids)):
            raise ValueError('Select one to five distinct research feedback IDs')
        allowed = {row['id'] for row in self.library.entries() if row['kind'] == 'observation' and
                   row['status'] == 'proposed' and row['scope'] == self.library._scope(self.project) and
                   row['evidence'].get('bundle') == self.capture.bundle.digest and
                   row['evidence'].get('model') == self.capture.model}
        if not set(feedback_ids) <= allowed:
            raise ValueError('Feedback must match the running project, model and bundle')
        model = (os.environ.get('JARVIS_HARNESS_MODEL') or os.environ.get('JARVIS_BACKGROUND_MODEL')
                 or ROUTES['background'][0])
        return {'model': model, 'feedback_ids': feedback_ids, 'api_key': self.api_key}

    def harness_status(self):
        from .jobs import local_status
        return {**local_status(), 'learning_enabled': True,
                'running_bundle': self.capture.bundle.digest, 'check': self.jobs.status(),
                'mode': 'offline_checks_and_explicit_feedback_refinement', 'automatic_activation': False}

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
