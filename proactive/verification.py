"""Bounded artifact checks, specified before dispatch and run outside workers.

This verifies exact file bytes, not semantic correctness or their authorship.
The execution record and verifier must remain outside worker write permissions.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import stat
import sys
import tempfile
from asyncio import create_subprocess_exec as _verification_process

from core.secret_env import sanitized_subprocess_env

MAX_ARTIFACT_BYTES = 16 * 1024 * 1024


def validate_checks(checks):
    if checks is None:
        return []
    if not isinstance(checks, list) or len(checks) > 16:
        raise ValueError('verification must be a list of at most 16 file checks')
    result = []
    for check in checks:
        if not isinstance(check, dict) or set(check) != {'path', 'sha256'}:
            raise ValueError('each file check requires only path and sha256')
        path, digest = check['path'], check['sha256']
        if (not isinstance(path, str) or not path or len(path) > 1024 or '\x00' in path
                or PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts
                or not PurePosixPath(path).parts):
            raise ValueError('verification path must be relative to the workspace without traversal')
        if not isinstance(digest, str) or not re.fullmatch(r'[a-fA-F0-9]{64}', digest):
            raise ValueError('sha256 must contain 64 hexadecimal characters')
        result.append({'path': path, 'sha256': digest.lower()})
    return result


def _read_artifact(workspace, path):
    # Open every component relative to a pinned directory descriptor. No symlinks,
    # device files or blocking FIFO reads, even if a worker substitutes a path.
    directory = os.open(workspace, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    descriptor = None
    try:
        parts = PurePosixPath(path).parts
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_ARTIFACT_BYTES:
            raise ValueError('artifact must be a regular file at most 16 MiB')
        chunks = []
        total = 0
        while chunk := os.read(descriptor, 65536):
            total += len(chunk)
            if total > MAX_ARTIFACT_BYTES:
                raise ValueError('artifact exceeds verification byte budget')
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError('artifact changed during verification')
        return b''.join(chunks)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory)


def _digest(workspace, path):
    return hashlib.sha256(_read_artifact(workspace, path)).hexdigest()


def verify_files(workspace, checks):
    checks = validate_checks(checks)
    if not checks:
        return {'status': 'unverified', 'reason': 'No independent acceptance checks specified', 'checks': []}
    evidence = []
    for check in checks:
        try:
            actual = _digest(workspace, check['path'])
            evidence.append({**check, 'actual_sha256': actual, 'passed': actual == check['sha256']})
        except (OSError, ValueError) as error:
            evidence.append({**check, 'passed': False, 'error': type(error).__name__})
    return {'status': 'passed' if all(item['passed'] for item in evidence) else 'failed', 'checks': evidence}


MAX_CHANGED_FILES = 128
MAX_STATUS_BYTES = 1024 * 1024
MAX_WORKSPACE_BYTES = 32 * 1024 * 1024
_SKIP_DIRECTORIES = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.cache'}
_UNSUPPORTED_CODE = {'.c', '.h', '.cc', '.cpp', '.hpp', '.js', '.jsx', '.mjs', '.ts', '.tsx',
                     '.go', '.rs', '.java', '.kt', '.swift', '.lua', '.rb', '.php', '.pl', '.cs',
                     '.fs', '.vue', '.svelte'}
_GIT_OPTIONS = ('-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=/dev/null',
                '-c', 'core.untrackedCache=false', '-c', 'core.quotePath=false')


def _check_env():
    # Verification never inherits credential values, Python/plugin injection,
    # shell startup code, or caller-selected Git executables/config overrides.
    environment = {key: value for key, value in sanitized_subprocess_env().items()
                   if not key.startswith(('GIT_', 'PYTHON', 'PYTEST_', 'BASH_FUNC_'))
                   and key not in {'BASH_ENV', 'ENV', 'LD_PRELOAD', 'LD_LIBRARY_PATH'}}
    environment.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null',
                       GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0',
                       PYTHONNOUSERSITE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    return environment


async def _check_command(command, *, cwd=None, data=None, timeout=5):
    """Own and reap bounded verifier subprocesses on timeout/cancellation."""
    process = None
    readers = []
    try:
        process = await _verification_process(
            *command, cwd=cwd, env=_check_env(), start_new_session=True,
            stdin=asyncio.subprocess.PIPE if data is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

        async def read(stream):
            chunks, length = [], 0
            while chunk := await stream.read(65536):
                if not isinstance(chunk, bytes):
                    raise ValueError('invalid verifier subprocess output')
                length += len(chunk)
                if length > MAX_STATUS_BYTES:
                    raise ValueError('verification subprocess output exceeded its budget')
                chunks.append(chunk)
            return b''.join(chunks)

        readers = [asyncio.create_task(read(stream)) for stream in (process.stdout, process.stderr)]
        async with asyncio.timeout(timeout):
            if data is not None:
                process.stdin.write(data)
                await process.stdin.drain()
                process.stdin.close()
            output, error = await asyncio.gather(*readers)
            await process.wait()
        return process.returncode, output, error
    finally:
        if process is not None:
            # Kill the owned group even if the leader exited with live helpers.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()
        for reader in readers:
            if not reader.done():
                reader.cancel()
        if readers:
            await asyncio.gather(*readers, return_exceptions=True)


async def _git(workspace, *arguments):
    return await _check_command(['/usr/bin/git', *_GIT_OPTIONS, '-C', str(workspace), *arguments])


def _paths_from_status(raw):
    entries = raw.split(b'\0')
    paths = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        if len(entry) < 4 or entry[2:3] != b' ':
            raise ValueError('invalid git status record')
        paths.append(entry[3:].decode('utf-8', errors='surrogateescape'))
        if b'R' in entry[:2] or b'C' in entry[:2]:
            if index >= len(entries) or not entries[index]:
                raise ValueError('invalid git rename record')
            paths.append(entries[index].decode('utf-8', errors='surrogateescape'))
            index += 1
    return set(paths)


def _tree_paths(workspace):
    paths = []
    pending = [(os.open(workspace, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW), '')]
    try:
        while pending:
            directory, prefix = pending.pop()
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if entry.name in _SKIP_DIRECTORIES:
                            continue
                        relative = prefix + entry.name
                        if entry.is_dir(follow_symlinks=False):
                            descriptor = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                                 dir_fd=directory)
                            pending.append((descriptor, relative + '/'))
                        else:
                            paths.append(relative)
                        if len(paths) + len(pending) > MAX_CHANGED_FILES:
                            raise ValueError('workspace scan exceeds verification file budget')
            finally:
                os.close(directory)
    finally:
        for directory, _ in pending:
            os.close(directory)
    return set(paths)


def _fingerprints(workspace, paths):
    result, total = {}, 0
    for path in sorted(paths):
        validate_checks([{'path': path, 'sha256': '0' * 64}])
        try:
            raw = _read_artifact(workspace, path)
            total += len(raw)
            if total > MAX_WORKSPACE_BYTES:
                raise ValueError('workspace exceeds verification byte budget')
            result[path] = hashlib.sha256(raw).hexdigest()
        except FileNotFoundError:
            result[path] = None
    return result


async def capture_workspace(workspace, *, previous=None):
    """Capture independent dirty-file bytes before launch or after process exit."""
    try:
        async with asyncio.timeout(12):
            code, status, _ = await _git(workspace, 'status', '--porcelain=v1', '-z',
                                         '--untracked-files=all', '--ignore-submodules=all')
            tracked, head = set(), None
            if code == 0:
                paths = _paths_from_status(status)
                tracked_code, raw_tracked, _ = await _git(workspace, 'ls-files', '-z')
                if tracked_code:
                    raise ValueError('cannot read tracked workspace paths')
                tracked = set(raw_tracked.decode('utf-8', errors='surrogateescape').split('\0')) - {''}
                head_code, raw_head, _ = await _git(workspace, 'rev-parse', '--verify', 'HEAD')
                candidate = raw_head.decode().strip()
                if head_code == 0 and re.fullmatch('[0-9a-f]{40,64}', candidate):
                    head = candidate
                if previous and previous.get('head'):
                    diff_code, changed, _ = await _git(workspace, 'diff', '--no-ext-diff',
                        '--no-textconv', '--ignore-submodules=all', '--name-only', '-z', previous['head'], '--')
                    if diff_code:
                        raise ValueError('cannot compare the pre-dispatch Git revision')
                    paths.update(changed.decode('utf-8', errors='surrogateescape').split('\0'))
                    paths.discard('')
                git = True
            else:
                if (Path(workspace) / '.git').exists():
                    raise ValueError('Git status failed for a repository workspace')
                paths = await asyncio.to_thread(_tree_paths, workspace)
                git = False
            if previous:
                paths.update(previous.get('files', {}))
            if len(paths) > MAX_CHANGED_FILES:
                raise ValueError('too many modified files to verify automatically')
            files = await asyncio.to_thread(_fingerprints, workspace, paths)
            return {'status': 'passed', 'git': git, 'head': head, 'tracked': sorted(tracked), 'files': files}
    except (OSError, ValueError, TimeoutError) as error:
        return {'status': 'unverified', 'reason': type(error).__name__, 'files': {}}


async def _syntax_smoke(workspace, paths):
    """Compile changed sources as data; never import agent-authored project code."""
    checks, sources = [], {}
    for path in paths:
        if path.endswith(('.py', '.json', '.toml', '.sh')):
            raw = await asyncio.to_thread(_read_artifact, workspace, path)
            if path.endswith('.sh'):
                wrapper = ('import os,resource; '
                           'resource.setrlimit(resource.RLIMIT_AS,(536870912,536870912)); '
                           'resource.setrlimit(resource.RLIMIT_CPU,(5,5)); '
                           'os.execv("/usr/bin/bash",["bash","--noprofile","--norc","-n"])')
                code, _, _ = await _check_command([sys.executable, '-I', '-c', wrapper], data=raw)
                checks.append({'path': path, 'status': 'passed' if code == 0 else 'failed',
                               **({'error': 'SyntaxError'} if code else {})})
            else:
                # Parsing/compilation can consume CPU/GIL even without executing
                # code. Keep it out of the conversation process and cap resources.
                sources[path] = raw
                checks.append({'path': path, 'status': 'pending'})
        else:
            checks.append({'path': path,
                           'status': 'unverified' if Path(path).suffix.lower() in _UNSUPPORTED_CODE else 'not_applicable'})
    smoke = {'status': 'not_applicable', 'scope': 'No changed Python/JSON/TOML source'}
    if sources:
        # The test is trusted verifier code, with source bytes supplied as data.
        # Project conftest, plugins, fixtures and modified tests are never executed.
        with tempfile.TemporaryDirectory(prefix='jarvis-verify-') as directory:
            root = Path(directory)
            manifest = {}
            for index, (path, raw) in enumerate(sources.items()):
                name = f'source-{index}.bin'
                await asyncio.to_thread((root / name).write_bytes, raw)
                manifest[path] = name
            await asyncio.to_thread((root / 'sources.json').write_text, json.dumps(manifest))
            (root / 'test_syntax.py').write_text(
                "import json,resource,tomllib\nfrom pathlib import Path\n"
                "resource.setrlimit(resource.RLIMIT_AS,(536870912,536870912))\n"
                "resource.setrlimit(resource.RLIMIT_CPU,(5,5))\n"
                "def test_modified_sources_compile():\n"
                "    results=[]\n"
                "    for path, source in json.loads(Path(__file__).with_name('sources.json').read_text()).items():\n"
                "        try:\n"
                "            raw=Path(__file__).with_name(source).read_bytes()\n"
                "            if path.endswith('.py'): compile(raw,path,'exec',dont_inherit=True)\n"
                "            elif path.endswith('.json'): json.loads(raw)\n"
                "            else: tomllib.loads(raw.decode('utf-8'))\n"
                "            results.append({'path':path,'status':'passed'})\n"
                "        except (SyntaxError,ValueError,UnicodeError,MemoryError) as error:\n"
                "            results.append({'path':path,'status':'failed','error':type(error).__name__})\n"
                "    Path(__file__).with_name('results.json').write_text(json.dumps(results))\n"
                "    assert all(item['status']=='passed' for item in results)\n")
            code, _, _ = await _check_command([sys.executable, '-I', '-B', '-m', 'pytest', '-q',
                '--noconftest', '-p', 'no:cacheprovider', '-o', 'addopts=', str(root / 'test_syntax.py')],
                cwd=directory, timeout=8)
            try:
                reports = json.loads(await asyncio.to_thread((root / 'results.json').read_text))
                by_path = {item['path']: item for item in reports}
            except (OSError, ValueError, TypeError, KeyError):
                by_path = {}
            for item in checks:
                if item['status'] == 'pending':
                    item.update(by_path.get(item['path'], {'status': 'failed', 'error': 'VerificationProcessFailed'}))
            smoke = {'status': 'passed' if code == 0 else 'failed',
                     'scope': 'Isolated syntax-only pytest; no project code, conftest or plugins executed'}
    return checks, smoke


async def verify_workspace_changes(workspace, baseline):
    """Gate code-job completion on stable bytes and bounded structural checks.

    A passing result proves file integrity and checked syntax, not fulfillment of
    the task or functional behavior. Full project tests require explicit trusted
    acceptance checks; agent-authored code is not run as a verifier by default.
    """
    try:
        async with asyncio.timeout(20):
            if baseline.get('status') != 'passed':
                return {'status': 'unverified', 'reason': 'Pre-dispatch workspace baseline unavailable'}
            final = await capture_workspace(workspace, previous=baseline)
            if final['status'] != 'passed':
                return {'status': 'unverified', 'reason': 'Post-execution workspace state unavailable'}
            changed = [path for path, digest in final['files'].items()
                       if digest != baseline['files'].get(path, 'clean' if path in baseline.get('tracked', []) else None)]
            if not changed:
                return {'status': 'not_applicable', 'kind': 'response_received', 'changed_files': [],
                        'scope': 'Response received; no independently observed workspace change', 'functional_verified': False}
            existing = [path for path in changed if final['files'][path] is not None]
            manifest = [{'path': path, 'sha256': final['files'][path]} for path in existing]
            # verify_files has a deliberately smaller public acceptance-contract
            # limit; process the observer manifest in bounded contract batches.
            artifacts = []
            for index in range(0, len(manifest), 16):
                result = await asyncio.to_thread(verify_files, workspace, manifest[index:index+16])
                artifacts.extend(result['checks'])
            syntax, smoke = await _syntax_smoke(workspace, existing)
            passed = all(item['passed'] for item in artifacts) and all(item['status'] != 'failed' for item in syntax)
            passed = passed and smoke['status'] != 'failed'
            # Re-read after checks: helpers or concurrent edits cannot silently
            # replace bytes between digest evidence and syntax validation.
            stable = await asyncio.to_thread(_fingerprints, workspace, changed)
            passed = passed and all(stable[path] == final['files'][path] for path in changed)
            status = 'passed' if passed else 'failed'
            if passed and any(item['status'] == 'unverified' for item in syntax):
                status = 'unverified'
            return {'status': status, 'kind': 'verified_changes',
                    'changed_files': changed, 'checks': artifacts, 'syntax': syntax, 'smoke': smoke,
                    'deletions': [{'path': path, 'absent': True} for path in changed if path not in existing],
                    'scope': 'Stable SHA-256 file bytes and structural syntax checks only',
                    'functional_verified': False}
    except (OSError, ValueError, TimeoutError) as error:
        return {'status': 'failed', 'reason': type(error).__name__, 'functional_verified': False}


def completion_evidence(verification):
    """Project completion safely without treating a response as proven effects."""
    evidence = verification if isinstance(verification, dict) else {}
    passed = (evidence.get('status') == 'passed' and evidence.get('kind') == 'verified_changes'
              and bool(evidence.get('changed_files'))
              and bool(evidence.get('checks') or evidence.get('deletions'))
              and all(item.get('passed') is True for item in evidence.get('checks', []))
              and not any(item.get('status') in ('failed', 'unverified') for item in evidence.get('syntax', [])))
    return {'verified': passed,
            'completion_kind': 'verified_changes' if passed else 'response_received',
            'announcement_state': 'completed' if passed else 'response_received',
            'verification': evidence}


def verification_notice(verification):
    """Keep completion events small; full digest evidence stays in job status."""
    evidence = verification if isinstance(verification, dict) else {}
    return {name: evidence[name] for name in ('status', 'scope', 'functional_verified') if name in evidence} | {
        'changed_file_count': len(evidence.get('changed_files', [])),
        'smoke_status': evidence.get('smoke', {}).get('status'),
    }
