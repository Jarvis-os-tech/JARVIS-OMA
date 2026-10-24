"""Local learning administration, bounded research refinement and scoped experience."""
import argparse
import asyncio
import json
from pathlib import Path

from .bundles import BundleRegistry
from .evidence import EpisodeStore
from .research import fixture_trial, seed_bundle
from .voice_tests import checklist, evidence_report, record_result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path, required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('init', help='Register the curated research seed; activate only if uninitialized')
    commands.add_parser('status')
    commands.add_parser('episodes', help='List the latest 20 captured task identities')
    commands.add_parser('voice-tests', help='Print spoken test requests and manual expectations')
    commands.add_parser('voice-report', help='Inspect captured test markers; manual verdicts remain pending')
    review = commands.add_parser('review', help='Attach your verdict and lag observation to an episode')
    review.add_argument('id')
    review.add_argument('result', choices=['pass', 'fail', 'partial'])
    review.add_argument('--lag', choices=['none', 'before_answer', 'during_speech', 'unknown'], default='none')
    review.add_argument('--note', default='')
    activate = commands.add_parser('activate')
    activate.add_argument('bundle', type=Path, help='A local instruction-only JSON bundle')
    commands.add_parser('restore', help='Select the previous bundle for the next JARVIS startup')
    episode = commands.add_parser('episode')
    episode.add_argument('id')
    feedback = commands.add_parser('feedback')
    feedback.add_argument('id')
    feedback.add_argument('text')
    commands.add_parser('demo', help='Run scripted corpus/config/tool/capture checks without cloud calls')
    refine = commands.add_parser('refine', help='Run one real upstream research refinement round; never activates')
    refine.add_argument('--offline', action='store_true', help='Scripted model transport; real upstream loop, no cloud')
    refine.add_argument('--model', help='Explicit Gemini text model for a cloud trial')
    refine.add_argument('--max-calls', type=int, default=32)
    refine.add_argument('--seconds', type=int, default=600)
    check = commands.add_parser('candidate-check', help='Recompute evidence eligibility for a controlled trial')
    check.add_argument('run_id')
    trial = commands.add_parser('trial-activate', help='Explicitly select an eligible candidate for the next startup')
    trial.add_argument('run_id')
    trial.add_argument('--note', required=True, help='Local administrator review note')
    rollback = commands.add_parser('trial-rollback', help='Restore the baseline only if this trial is still selected')
    rollback.add_argument('run_id')
    commands.add_parser('trial-voice-tests', help='Show selected bundle and spoken acceptance requests')
    proposal = commands.add_parser('lesson-propose', help='Archive a candidate as a pending procedure, not an active lesson')
    proposal.add_argument('run_id')
    proposal.add_argument('--cue', required=True)
    proposal.add_argument('--voice-model', required=True)
    publish = commands.add_parser('lesson-publish', help='Publish only after trial eligibility and six manually reviewed voice checks')
    publish.add_argument('proposal_id')
    publish.add_argument('--episodes', nargs=6, required=True)
    revoke = commands.add_parser('lesson-revoke', help='Suppress a published procedure while retaining its audit history')
    revoke.add_argument('lesson_id')
    revoke.add_argument('--reason', required=True)
    commands.add_parser('lesson-list', help='List local lesson/feedback metadata; never exposes feedback as reusable guidance')
    args = parser.parse_args()
    try:
        registry = BundleRegistry(args.state_dir)
        if args.command == 'init':
            bundle = registry.register(seed_bundle())
            result = registry.status()
            if result['active'] is None:
                result = registry.activate(bundle.digest)
        elif args.command == 'status':
            result = registry.status()
        elif args.command == 'activate':
            if args.bundle.stat().st_size > 32768:
                raise ValueError('Bundle exceeds size limit')
            bundle = registry.register(json.loads(args.bundle.read_text()))
            result = registry.activate(bundle.digest)
        elif args.command == 'restore':
            result = registry.restore()
        elif args.command == 'episode':
            result = EpisodeStore(args.state_dir).read(args.id)
        elif args.command == 'episodes':
            result = EpisodeStore(args.state_dir).recent()
        elif args.command == 'voice-tests':
            result = checklist()
        elif args.command == 'voice-report':
            result = evidence_report(EpisodeStore(args.state_dir))
        elif args.command == 'review':
            result = record_result(EpisodeStore(args.state_dir), args.id, args.result,
                                   lag=args.lag, note=args.note)
        elif args.command == 'feedback':
            EpisodeStore(args.state_dir).feedback(args.id, args.text)
            result = {'episode': args.id, 'feedback_recorded': True, 'diagnosis': 'unknown'}
        elif args.command == 'refine':
            from .refinement import run_refinement
            try:
                result = run_refinement(args.state_dir, offline=args.offline, model=args.model,
                                        max_calls=args.max_calls, seconds=args.seconds)
            except (OSError, ValueError):
                raise
            except Exception as error:
                parser.exit(2, 'Refinement failed: ' + type(error).__name__ +
                            '. Inspect the local refinement audit; provider details are omitted.\n')
        elif args.command in {'candidate-check', 'trial-activate', 'trial-rollback', 'trial-voice-tests'}:
            from .trials import candidate_check, activate_trial, rollback_trial, trial_voice_tests
            if args.command == 'candidate-check':
                result = candidate_check(args.state_dir, args.run_id)
            elif args.command == 'trial-activate':
                result = activate_trial(args.state_dir, args.run_id, args.note)
            elif args.command == 'trial-rollback':
                result = rollback_trial(args.state_dir, args.run_id)
            else:
                result = trial_voice_tests(args.state_dir)
        elif args.command in {'lesson-propose', 'lesson-publish', 'lesson-revoke', 'lesson-list'}:
            from .experience import ExperienceLibrary
            library = ExperienceLibrary(args.state_dir)
            if args.command == 'lesson-propose':
                result = library.propose(args.run_id, args.cue, args.voice_model)
            elif args.command == 'lesson-publish':
                result = library.publish(args.proposal_id, args.episodes)
            elif args.command == 'lesson-revoke':
                result = library.revoke(args.lesson_id, args.reason)
            else:
                result = [{'id': row['id'], 'kind': row['kind'], 'status': row['status'],
                           'source': row['source'], 'scope': row['scope']} for row in library.entries()]
        else:
            result = asyncio.run(fixture_trial(args.state_dir))
    except (OSError, ValueError) as error:
        parser.exit(2, f'Learning operation failed: {error}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
