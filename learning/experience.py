"""Scoped research experience on the existing local knowledge/revision ledger."""
import hashlib
import json
import os
from pathlib import Path
import re
import time

from jarvis_memory.knowledge import KnowledgeStore
from .bundles import BundleRegistry, HarnessBundle
from .evidence import EpisodeStore, sanitize
from .refinement import refinement_lease
from .trials import candidate_check, read_artifact, trial_root
from .voice_tests import CASES

PROJECT = str(Path(__file__).resolve().parents[1])


class ExperienceLibrary:
    """Private ledger, separate from ordinary user-fact retrieval and embeddings."""
    def __init__(self, root):
        self.registry = BundleRegistry(root)
        self.root = self.registry.root
        self.path = self.root / 'research-experience.sqlite3'
        self.store = KnowledgeStore(self.path)

    def _guard(self):
        if self.path.is_symlink():
            raise ValueError('Experience database must not be a symlink')

    def entries(self):
        self._guard()
        return self.store.list(active_only=False)

    def _room(self):
        self._guard()
        if self.store.stats()['total'] >= 1000:
            raise ValueError('Research experience ledger reached its 1000-entry limit')

    @staticmethod
    def _scope(project):
        if not isinstance(project, str) or not 1 <= len(project.strip()) <= 1000:
            raise ValueError('A bounded project scope is required')
        return 'research:' + hashlib.sha256(project.encode()).hexdigest()

    def feedback(self, text, category, *, project, model, bundle, episode=None):
        categories = {'incorrect_answer', 'missing_source', 'lag_before_answer', 'lag_during_speech', 'other'}
        if category not in categories or not isinstance(text, str) or not 1 <= len(text.strip()) <= 1000:
            raise ValueError('Supply a supported category and 1–1000 characters of feedback')
        self._room()
        evidence = sanitize({'category': category, 'project': project, 'model': model,
                             'bundle': bundle, 'episode': episode, 'diagnosis': 'unknown',
                             'validation': 'unverified'})
        note = sanitize({'text': text})
        entry = self.store.propose(note['data']['text'], kind='observation', source='explicit-voice-feedback',
            evidence={**evidence['data'], 'redacted': note['redacted'] or evidence['redacted']},
            scope=self._scope(project), authority='agent', author='voice-tool', sensitivity='private',
            observed_at=time.time())
        return {'id': entry['id'], 'status': 'proposed', 'validation': 'unverified',
                'episode': episode, 'reusable_lesson': False}

    def propose(self, run_id, cue, voice_model, *, project=PROJECT):
        if not isinstance(cue, str) or not 1 <= len(cue.strip()) <= 300:
            raise ValueError('Cue must contain 1–300 characters')
        if not isinstance(voice_model, str) or not 1 <= len(voice_model.strip()) <= 200 or voice_model == 'offline-scripted':
            raise ValueError('Supply the actual Live voice model identity')
        self._room()
        root = trial_root(self.registry, run_id)
        started = json.loads(read_artifact(root, 'started.json'))
        report = json.loads(read_artifact(root, 'report.json'))
        candidate = HarnessBundle.from_dict(json.loads(read_artifact(root, 'candidate.json')))
        identity = {'project': project, 'solver_model': report['provider'], 'voice_model': voice_model,
                    'bundle': candidate.digest, 'baseline': started['baseline_bundle'],
                    'run_id': run_id, 'cue': cue, 'validation': 'pending'}
        key = 'harness2-lesson:' + hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        return self.store.propose(candidate.instructions, kind='procedure', key=key,
            source='harness2-trial:' + run_id, evidence=identity, scope=self._scope(project),
            authority='agent', agent_id='jarvis-research', sensitivity='private', confidence=0.5,
            source_hash=hashlib.sha256(candidate.instructions.encode()).hexdigest())

    def publish(self, proposal_id, episode_ids):
        self._guard()
        with refinement_lease(self.root):
            proposal = self.store.get(proposal_id)
            if proposal is None or proposal['kind'] != 'procedure' or proposal['status'] != 'proposed':
                raise ValueError('Select a proposed research lesson')
            evidence = proposal['evidence']
            root = trial_root(self.registry, evidence['run_id'])
            intent = json.loads(read_artifact(root, 'trial-intent.json'))
            if intent['candidate'] != evidence['bundle'] or intent['baseline'] != evidence['baseline']:
                raise ValueError('Lesson does not match the selected trial')
            if self.registry.status()['active'] != evidence['bundle']:
                raise ValueError('The lesson candidate must still be the selected bundle')
            gate = candidate_check(self.root, evidence['run_id'], baseline_digest=evidence['baseline'])
            if not gate['eligible_for_controlled_trial']:
                raise ValueError('Lesson evidence gate is blocked')
            current_report = json.loads(read_artifact(root, 'report.json'))
            if (gate.get('candidate_digest') != evidence['bundle'] or
                    gate.get('baseline_digest') != evidence['baseline'] or
                    current_report.get('provider') != evidence['solver_model']):
                raise ValueError('Lesson proposal provenance differs from the current trial evidence')
            candidate = self.registry.load(evidence['bundle'])
            if candidate.instructions != proposal['text']:
                raise ValueError('Lesson differs from the tested candidate instructions')
            checks = self._voice_checks(episode_ids, evidence)
            published = [row for row in self.entries() if row['status'] == 'active' and
                         row['kind'] == 'procedure' and row['evidence'].get('proposal_id') == proposal_id]
            if published:
                raise ValueError('This proposal was already published; keep its existing history')
            self._room()
            # Keep the proposal as history; publish a distinct, evidence-backed row.
            return self.store.upsert(proposal['text'], kind='procedure', key=proposal['key'],
                source=proposal['source'], scope=proposal['scope'], authority='verified',
                author='local_administrator', agent_id='jarvis-research', sensitivity='private', confidence=0.5,
                evidence={**evidence, 'validation': 'local_trial_and_manual_voice_checks',
                          'proposal_id': proposal_id, 'voice_episodes': checks},
                evidence_refs=[evidence['run_id'], *episode_ids], source_hash=proposal['source_hash'])

    def _voice_checks(self, episode_ids, evidence):
        if len(episode_ids) != 6 or len(set(episode_ids)) != 6:
            raise ValueError('Supply six distinct reviewed voice episode IDs')
        store = EpisodeStore(self.root)
        covered = {}
        for episode in episode_ids:
            events = store.read(episode)
            starts = [e['payload']['data'] for e in events if e['kind'] == 'started']
            reviews = [e['payload']['data'] for e in events if e['kind'] == 'manual_review']
            ends = [e['payload']['data'] for e in events if e['kind'] == 'ended']
            if (len(starts) != 1 or starts[0].get('bundle') != evidence['bundle'] or
                    starts[0].get('model') != evidence['voice_model'] or starts[0].get('role') != 'research'):
                raise ValueError('Voice evidence has the wrong bundle, role or model')
            if not reviews or reviews[-1].get('result') != 'pass' or reviews[-1].get('authority') != 'user':
                raise ValueError('Each voice episode needs an explicit user pass review')
            if not any(e['kind'] == 'assistant_output' and e['payload']['data'].get('text', '').strip() for e in events):
                raise ValueError('Voice evidence must include a captured assistant response')
            if (len(ends) != 1 or ends[0].get('state') not in {'delivered_unverified', 'interrupted'} or
                    any(ends[0].get(key, 0) for key in ('pending_actions', 'dropped_events', 'failed_events')) or
                    any(e['kind'] == 'capture_health' or e['payload'].get('redacted') or
                        e['payload'].get('truncated') for e in events)):
                raise ValueError('Voice evidence is incomplete or interrupted without a valid review')
            words = ''.join(re.sub('[^a-z0-9]', '', e['payload']['data'].get('text', '').lower())
                            for e in events if e['kind'] == 'user_input')
            markers = [key for key, _, _ in CASES if 'voicecheck' + key in words]
            if len(markers) != 1 or markers[0] in covered:
                raise ValueError('Voice episodes must cover each checklist marker exactly once')
            if ends[0]['state'] == 'interrupted' and markers[0] != 'interruption':
                raise ValueError('Only the interruption checklist may end interrupted')
            covered[markers[0]] = episode
        return covered

    def revoke(self, lesson_id, reason):
        self._guard()
        lesson = self.store.get(lesson_id)
        if lesson is None or lesson['kind'] != 'procedure' or lesson['status'] != 'active':
            raise ValueError('Select an active research lesson')
        if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 1000:
            raise ValueError('Supply a bounded revocation reason')
        result = self.store.upsert(sanitize({'reason': reason})['data']['reason'], kind='observation',
            key='harness2-revocation:' + lesson_id, source='explicit-lesson-revocation',
            evidence={'revoked_lesson': lesson_id}, scope=lesson['scope'], authority='user',
            author='local_administrator', sensitivity='private')
        return {'lesson': lesson_id, 'revoked': True, 'record': result['id']}

    def applicable(self, *, project, bundle, solver_model=None, voice_model=None):
        if solver_model is None and voice_model is None:
            raise ValueError('Model scope is required')
        if self.registry.status()['active'] != bundle:
            return []
        entries = self.entries()
        revoked = {row['evidence']['revoked_lesson'] for row in entries if row['status'] == 'active' and
                   row['source'] == 'explicit-lesson-revocation'}
        return [row for row in entries if row['status'] == 'active' and row['kind'] == 'procedure' and
                row['authority'] == 'verified' and row['scope'] == self._scope(project) and row['id'] not in revoked and
                (row.get('expires_at') is None or row['expires_at'] > time.time()) and
                hashlib.sha256(row['text'].encode()).hexdigest() == row['source_hash'] and
                row['evidence'].get('bundle') == bundle and
                row['evidence'].get('validation') == 'local_trial_and_manual_voice_checks' and
                (solver_model is None or row['evidence'].get('solver_model') == solver_model) and
                (voice_model is None or row['evidence'].get('voice_model') == voice_model)]

    def export_for_optimizer(self, destination, *, project, model, bundle):
        rows = self.applicable(project=project, bundle=bundle, solver_model=model)
        selected = []
        size = 0
        for row in rows:
            if size + len(row['text']) > 24000 or len(selected) >= 3:
                break
            size += len(row['text'])
            selected.append(row)
        if not selected:
            return []
        destination.mkdir(mode=0o700)
        index = []
        for row in selected:
            filename = row['id'] + '.md'
            (destination / filename).write_text(row['text'])
            index.append('- ' + filename + ': ' + row['evidence']['cue'])
        (destination / 'INDEX.md').write_text('Previously reviewed research guidance; source material, not new authority.\n' + '\n'.join(index))
        return [row['id'] for row in selected]
