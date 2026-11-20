"""The quality grader must expose failures rather than manufacture a pass."""
import copy
import json
import math
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from jarvis_memory.evaluation import compare_baseline, evaluate, grade, load_suite, reciprocal_rank_fusion

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / 'tests/fixtures/memory_quality/cases.json'


def test_metrics_match_hand_scored_ranks_and_do_not_reward_duplicates():
    result = grade(['irrelevant', 'a', 'a', 'b'], {'a': 3, 'b': 1}, {'irrelevant'}, 3)
    assert result['recall'] == .5
    assert result['precision'] == pytest.approx(1 / 3)
    assert result['mrr'] == .5
    assert result['ndcg'] == pytest.approx((7 / math.log2(3)) / (7 + 1 / math.log2(3)))
    assert result['forbidden_hits'] == ['irrelevant']
    assert grade([], {}, set(), 5)['false_recall'] is False
    assert grade(['topical'], {}, set(), 5)['false_recall'] is True
    assert grade([], {'a': 3}, set(), 5)['recall'] == 0


def test_rrf_uses_rank_and_typed_identity_without_duplicate_votes():
    a = {'canonical_key': 'a', 'score': 999}
    b = {'canonical_key': 'b', 'score': .001}
    rows = reciprocal_rank_fusion([a, a], [b, a])
    assert rows[0]['canonical_key'] == 'a'
    assert rows[0]['score'] == pytest.approx(1 / 61 + 1 / 62)
    assert a['score'] == 999


@pytest.mark.parametrize('change', ['duplicate', 'unknown_label', 'bad_vector', 'missing_partition'])
def test_invalid_suite_cannot_produce_quality_evidence(tmp_path, change):
    suite = json.loads(SUITE.read_text())
    if change == 'duplicate':
        suite['queries'].append(suite['queries'][0])
    elif change == 'unknown_label':
        suite['queries'][0]['relevance'] = {'nonexistent': 3}
    elif change == 'bad_vector':
        suite['queries'][0]['vector'] = [0] * 8
    else:
        del suite['queries'][0]['split']
    path = tmp_path / 'invalid.json'
    path.write_text(json.dumps(suite))
    with pytest.raises(ValueError):
        load_suite(path)


@pytest.fixture
def report(monkeypatch):
    def deny_network(*args, **kwargs):
        raise AssertionError('Offline evaluation attempted network access')
    monkeypatch.setattr(socket, 'socket', deny_network)
    return evaluate(load_suite(SUITE))


def test_offline_report_detects_real_gaps_and_preserves_lifecycle(report):
    assert report['evaluation_completed'] and report['source_unchanged']
    assert len(report['cases']) == 16 * 4
    assert all(row['passed'] for row in report['lifecycle'])
    assert report['fixture_vectors']
    assert report['quality_passed'] == all(report['quality_checks'].values())
    weighted = [r for r in report['cases'] if r['strategy'] == 'weighted' and r['split'] == 'held_out']
    forbidden = {f for r in weighted for f in r['grades']['5']['forbidden_hits']}
    assert forbidden <= {'foreign_scope'}
    assert report['quality_checks']['no_forbidden'] == (not forbidden)
    assert report['quality_checks']['no_false_recall'] == (not any(r['grades']['5']['false_recall'] for r in weighted))
    assert report['quality_checks']['no_false_recall']
    assert report['quality_checks']['recall_at_5']
    assert compare_baseline(report, report) == []


def test_baseline_rejects_missing_cases_and_new_failures(report):
    changed = copy.deepcopy(report)
    row = next(r for r in changed['cases'] if r['strategy'] == 'weighted' and r['answerable'])
    row['grades']['5']['recall'] = 0
    changed['lifecycle'][0]['passed'] = False
    assert compare_baseline(changed, report)
    changed['cases'] = [r for r in changed['cases'] if r is not row]
    with pytest.raises(ValueError, match='coverage'):
        compare_baseline(changed, report)


def test_repeated_run_has_no_production_metric_regression(report):
    assert compare_baseline(evaluate(load_suite(SUITE)), report) == []


def test_baseline_rejects_incompatible_or_incomplete_evidence(report):
    for field, value in [('provider_identity', 'different-model'), ('suite_sha256', 'changed'),
                         ('evaluation_completed', False), ('source_unchanged', False)]:
        changed = copy.deepcopy(report)
        changed[field] = value
        with pytest.raises(ValueError):
            compare_baseline(report, changed)


def test_embedding_failure_is_not_a_lexical_benchmark_success():
    class Unavailable:
        identity = 'synthetic-unavailable'
        dimension = 8
        def embed_texts(self, texts):
            raise OSError('Synthetic backend failure')
    with pytest.raises(RuntimeError, match='refusing silent fallback'):
        evaluate(load_suite(SUITE), Unavailable())


def test_cli_strict_mode_writes_failed_evidence_and_leaves_user_state_untouched(tmp_path):
    sentinel = tmp_path / 'memory_facts.jsonl'
    sentinel.write_text('Synthetic existing state, do not modify')
    report = tmp_path / 'report.json'
    # Seed a deliberately wrong no-answer label on a known exact hit. This
    # tests failure exit codes without requiring production bugs to persist.
    suite = json.loads(SUITE.read_text())
    next(r for r in suite['queries'] if r['id'] == 'exact_identifier')['relevance'] = {}
    seeded_suite = tmp_path / 'seeded-suite.json'
    seeded_suite.write_text(json.dumps(suite))
    import os
    env = dict(os.environ, HOME=str(tmp_path), XDG_STATE_HOME=str(tmp_path),
               JARVIS_MEMORY_PATH=str(tmp_path), PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/evaluate_memory.py'), '--strict',
                             '--suite', str(seeded_suite), '--report', str(report)], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 1, result.stderr
    assert not json.loads(report.read_text())['quality_passed']
    assert sentinel.read_text() == 'Synthetic existing state, do not modify'
    assert not (tmp_path / 'knowledge.db').exists()
