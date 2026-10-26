"""Local Harness readiness checks without model calls, installs or audio devices."""
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys

from .bundles import BundleRegistry
from .refinement import require_upstream, UPSTREAM_REVISION


def doctor(state_dir):
    root = Path(os.path.abspath(Path(state_dir).expanduser()))
    checks = []

    def check(name, action):
        try:
            details = action()
            checks.append({'name': name, 'status': 'pass', 'details': details})
        except (OSError, ValueError, ImportError, KeyError, TypeError, sqlite3.Error,
                subprocess.SubprocessError) as error:
            checks.append({'name': name, 'status': 'fail', 'error_type': type(error).__name__})

    def python_version():
        if sys.version_info[:2] not in {(3, 12), (3, 13)}:
            raise ValueError('Reviewed upstream requires Python 3.12 or 3.13')
        return {'version': sys.version.split()[0], 'executable': sys.executable}

    def dependency():
        require_upstream()
        return {'revision': UPSTREAM_REVISION, 'verified_core_modules': 7}

    def state():
        if not root.is_dir() or any(path.is_symlink() for path in (root, *root.parents)):
            raise ValueError('Initialize a private state directory without symlinks')
        if stat.S_IMODE(root.stat().st_mode) & 0o077:
            raise ValueError('State directory must be private')
        registry = BundleRegistry(root)
        selected = registry.active()
        if selected is None:
            raise ValueError('Initialize an active research bundle')
        for path in [root / 'active.json', *registry.bundles.glob('*.json')]:
            if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) & 0o077:
                raise ValueError('Learning artifacts must be private regular files')
        return {'active_bundle': selected.digest, 'role': selected.role}

    def databases():
        result = {}
        for filename in ('episodes.sqlite3', 'research-experience.sqlite3'):
            path = root / filename
            if not path.exists() and not path.is_symlink():
                result[filename] = 'not_created_yet'
                continue
            if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) & 0o077:
                raise ValueError('Database permissions or symlink check failed')
            connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=2)
            try:
                if connection.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                    raise ValueError('Database integrity check failed')
            finally:
                connection.close()
            result[filename] = 'ok'
        return result

    def tools():
        from skills.skills import DesktopSkills
        expected = {'harness-local.json': {'get_harness_status', 'start_harness_check',
                    'harness_check_status', 'cancel_harness_check'},
                    'research-learning.json': {'get_learning_status', 'list_research_lessons',
                                               'record_research_feedback'},
                    'harness-refinement.json': {'list_research_feedback', 'start_harness_refinement'},
                    'personal-agents.json': {'get_hermes_status', 'create_task_agent',
                        'task_agent_status', 'list_task_agents', 'cancel_task_agent',
                        'followup_task_agent'}}
        project = Path(__file__).resolve().parents[1]
        for filename, names in expected.items():
            specs = json.loads((project / 'skill_manifests' / filename).read_text())['skills']
            if {spec['name'] for spec in specs} != names:
                raise ValueError('Local voice tools are incomplete')
            if any(spec['adapter'] not in DesktopSkills.ADAPTERS or
                   not hasattr(DesktopSkills, DesktopSkills.ADAPTERS[spec['adapter']]) for spec in specs):
                raise ValueError('Local voice adapters are not wired')
        return {'voice_tools': sum(len(names) for names in expected.values())}

    def voice_lock():
        project = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, str(project / 'scripts/verify_voice_lock.py')],
            cwd=project, capture_output=True, timeout=15)
        if result.returncode:
            raise ValueError('Locked voice integrity check failed')
        return 'locked_voice_files_verified'

    for name, action in [('python', python_version), ('upstream', dependency),
                         ('state', state), ('databases', databases), ('voice_tools', tools),
                         ('voice_lock', voice_lock)]:
        check(name, action)
    ready = all(row['status'] == 'pass' for row in checks)
    return {'ready': ready, 'status': 'success' if ready else 'warning', 'checks': checks,
            'scope': 'Local offline integration readiness. No model, microphone or speaker quality test.',
            'next_actions': ['Run an offline Harness check through JARVIS.' if ready else
                             'Resolve the failed checks before starting refinement.']}
