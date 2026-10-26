import pytest

from learning.bundles import BundleRegistry
from learning.evidence import EpisodeCapture, EpisodeStore
from learning.research import seed_bundle
from learning.service import LearningService


def service(root):
    registry = BundleRegistry(root)
    bundle = registry.register(seed_bundle())
    registry.activate(bundle.digest)
    capture = EpisodeCapture(EpisodeStore(root), bundle, 'voice-model')
    return LearningService(capture, api_key='unit-test-key')


def test_refinement_selection_is_scoped_and_model_is_text_route(tmp_path, monkeypatch):
    instance = service(tmp_path)
    monkeypatch.setenv('JARVIS_HARNESS_MODEL', 'explicit-text-model')
    note = instance.feedback('The research answer missed a source.', 'missing_source')
    prepared = instance.prepare_refinement([note['id']])
    assert prepared == {'model': 'explicit-text-model', 'feedback_ids': [note['id']],
                        'api_key': 'unit-test-key'}
    assert instance.feedback_items()['items'][0]['validation'] == 'unverified'
    other = instance.library.feedback('Other model feedback', 'other', model='different-model',
        project=instance.project, bundle=instance.capture.bundle.digest)
    for values in ([], ['unknown'], [other['id']], [note['id'], note['id']]):
        with pytest.raises(ValueError):
            instance.prepare_refinement(values)
