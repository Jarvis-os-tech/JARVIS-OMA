"""Independent completion checks never execute agent-authored project code."""
import asyncio
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

from proactive.verification import (
    _check_command, _check_env, capture_workspace, completion_evidence, verify_workspace_changes,
)


def git(root, *arguments):
    return subprocess.run(['/usr/bin/git', '-c', 'core.hooksPath=/dev/null', '-C', str(root),
                           *arguments], check=True, capture_output=True, env=_check_env(), timeout=5)


def repository(root):
    git(root, 'init', '--quiet')
    (root / 'module.py').write_text('answer = 1\n')
    git(root, 'add', '--', 'module.py')
    git(root, '-c', 'user.name=Verifier Test', '-c', 'user.email=verifier@localhost',
        '-c', 'commit.gpgsign=false', 'commit', '--quiet', '-m', 'baseline')


@pytest.mark.asyncio
async def test_valid_changed_python_gets_digest_and_isolated_syntax_smoke(tmp_path):
    repository(tmp_path)
    before = await capture_workspace(tmp_path)
    (tmp_path / 'module.py').write_text('answer = 2\n')
    result = await verify_workspace_changes(tmp_path, before)
    assert result['status'] == 'passed'
    assert result['changed_files'] == ['module.py']
    assert result['checks'][0]['actual_sha256'] == result['checks'][0]['sha256']
    assert result['smoke']['status'] == 'passed'
    assert result['functional_verified'] is False
    assert 'syntax-only' in result['smoke']['scope']
    assert completion_evidence(result)['verified'] is True


@pytest.mark.asyncio
async def test_existing_dirty_invalid_code_is_not_attributed_to_new_job(tmp_path):
    repository(tmp_path)
    (tmp_path / 'already_broken.py').write_text('def broken(\n')
    before = await capture_workspace(tmp_path)
    (tmp_path / 'result.txt').write_text('A requested report\n')
    result = await verify_workspace_changes(tmp_path, before)
    assert result['status'] == 'passed'
    assert result['changed_files'] == ['result.txt']


@pytest.mark.asyncio
async def test_new_syntax_error_fails_even_when_agent_claimed_success(tmp_path):
    before = await capture_workspace(tmp_path)
    (tmp_path / 'bad.py').write_text('return 42\n')
    result = await verify_workspace_changes(tmp_path, before)
    assert result['status'] == 'failed'
    assert result['syntax'][0]['error'] == 'SyntaxError'
    assert not completion_evidence(result)['verified']


@pytest.mark.asyncio
async def test_response_without_observed_changes_has_no_verified_effect(tmp_path):
    before = await capture_workspace(tmp_path)
    result = await verify_workspace_changes(tmp_path, before)
    assert result['status'] == 'not_applicable'
    assert completion_evidence(result)['announcement_state'] == 'response_received'


@pytest.mark.asyncio
async def test_committed_changes_are_checked_even_when_git_status_is_clean(tmp_path):
    repository(tmp_path)
    before = await capture_workspace(tmp_path)
    (tmp_path / 'module.py').write_text('answer = 3\n')
    git(tmp_path, 'add', '--', 'module.py')
    git(tmp_path, '-c', 'user.name=Verifier Test', '-c', 'user.email=verifier@localhost',
        '-c', 'commit.gpgsign=false', 'commit', '--quiet', '-m', 'agent update')
    result = await verify_workspace_changes(tmp_path, before)
    assert result['status'] == 'passed' and result['changed_files'] == ['module.py']


@pytest.mark.asyncio
async def test_changed_symlink_is_not_followed_outside_workspace(tmp_path):
    root = tmp_path / 'work'
    root.mkdir()
    outside = tmp_path / 'private.py'
    outside.write_text('private_value = 1\n')
    before = await capture_workspace(root)
    (root / 'result.py').symlink_to(outside)
    result = await verify_workspace_changes(root, before)
    assert result['status'] == 'unverified'
    assert 'checks' not in result


@pytest.mark.asyncio
async def test_verifier_cannot_import_project_conftest_or_agent_authored_tests(tmp_path, monkeypatch):
    marker = tmp_path / 'executed'
    (tmp_path / 'conftest.py').write_text('raise RuntimeError("must never be imported")\n')
    before = await capture_workspace(tmp_path)
    (tmp_path / 'test_agent_output.py').write_text(
        f'from pathlib import Path\nPath({str(marker)!r}).write_text("executed")\n')
    monkeypatch.setenv('PYTEST_ADDOPTS', '--not-a-valid-argument')
    monkeypatch.setenv('PYTEST_PLUGINS', 'malicious_plugin')
    monkeypatch.setenv('PYTHONPATH', str(tmp_path))
    result = await verify_workspace_changes(tmp_path, before)
    assert result['status'] == 'passed'
    assert result['functional_verified'] is False
    assert not marker.exists()


@pytest.mark.asyncio
async def test_language_without_safe_parser_cannot_claim_verified_code(tmp_path):
    before = await capture_workspace(tmp_path)
    (tmp_path / 'module.ts').write_text('not valid typescript ???\n')
    result = await verify_workspace_changes(tmp_path, before)
    assert result['status'] == 'unverified'
    assert not completion_evidence(result)['verified']


@pytest.mark.asyncio
@pytest.mark.parametrize('name, content', [('data.json', '{bad'), ('settings.toml', 'a = [')])
async def test_invalid_configuration_syntax_fails_without_project_execution(tmp_path, name, content):
    before = await capture_workspace(tmp_path)
    (tmp_path / name).write_text(content)
    result = await verify_workspace_changes(tmp_path, before)
    assert result['status'] == 'failed'
    assert result['syntax'][0]['status'] == 'failed'


@pytest.mark.asyncio
async def test_cancelled_verifier_command_is_killed_and_reaped(tmp_path):
    original = asyncio.create_subprocess_exec
    spawned = asyncio.Event()
    processes = []

    async def launch(*arguments, **kwargs):
        process = await original(*arguments, **kwargs)
        processes.append(process)
        spawned.set()
        return process

    with patch('proactive.verification._verification_process', side_effect=launch):
        worker = asyncio.create_task(_check_command([sys.executable, '-I', '-c',
                                                    'import time; time.sleep(30)']))
        await asyncio.wait_for(spawned.wait(), 2)
        worker.cancel()
        result = await asyncio.gather(worker, return_exceptions=True)
    assert isinstance(result[0], asyncio.CancelledError)
    assert processes[0].returncode is not None
    with pytest.raises(ProcessLookupError):
        os.killpg(processes[0].pid, 0)


def test_verification_environment_and_self_reported_pass_are_not_trusted(monkeypatch):
    monkeypatch.setenv('JARVIS_TEST_API_KEY', 'private-value')
    monkeypatch.setenv('GIT_EXTERNAL_DIFF', 'untrusted-executable')
    monkeypatch.setenv('BASH_ENV', 'untrusted-shell-file')
    environment = _check_env()
    assert 'JARVIS_TEST_API_KEY' not in environment
    assert 'GIT_EXTERNAL_DIFF' not in environment
    assert 'BASH_ENV' not in environment
    assert environment['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] == '1'
    assert not completion_evidence({'status': 'passed'})['verified']
