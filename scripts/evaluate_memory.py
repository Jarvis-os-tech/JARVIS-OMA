"""Run a synthetic memory benchmark in fresh temporary stores."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from jarvis_memory.evaluation import compare_baseline, evaluate, load_suite

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, default=ROOT / 'tests/fixtures/memory_quality/cases.json')
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--strict', action='store_true', help='Fail on unmet quality targets, including existing gaps')
    parser.add_argument('--baseline', type=Path, help='Fail on new regressions against compatible prior evidence')
    parser.add_argument('--embedding', choices=('fixture', 'ollama'), default='fixture')
    parser.add_argument('--model', default='')
    parser.add_argument('--dimension', type=int, default=768)
    args = parser.parse_args()
    # Isolate auxiliary defaults as well as the explicitly configured stores.
    with tempfile.TemporaryDirectory(prefix='jarvis-memory-eval-home-') as home:
        for key, suffix in [('HOME', ''), ('XDG_CONFIG_HOME', 'config'), ('XDG_STATE_HOME', 'state'), ('XDG_CACHE_HOME', 'cache')]:
            os.environ[key] = str(Path(home) / suffix)
        try:
            provider = None
            if args.embedding == 'ollama':
                if not args.model:
                    parser.error('--model is required with --embedding ollama')
                from jarvis_memory.embeddings import OllamaEmbeddingProvider
                provider = OllamaEmbeddingProvider('http://127.0.0.1:11434', args.model, args.dimension)
            report = evaluate(load_suite(args.suite), provider)
            if args.baseline:
                report['regressions'] = compare_baseline(report, json.loads(args.baseline.read_text()))
        except Exception as error:
            report = {'schema_version': 1, 'evaluation_completed': False, 'quality_passed': False,
                      'error_type': type(error).__name__}
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
        print(json.dumps({k: report.get(k) for k in ('quality_passed', 'quality_checks', 'provider_identity', 'error_type')}))
        return 2 if 'error_type' in report else 1 if report.get('regressions') or (args.strict and not report['quality_passed']) else 0

if __name__ == '__main__':
    raise SystemExit(main())
