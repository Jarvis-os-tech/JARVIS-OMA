"""Bounded artifact checks, specified before dispatch and run outside workers.

This verifies exact file bytes, not semantic correctness or their authorship.
The execution record and verifier must remain outside worker write permissions.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import PurePosixPath
import re
import stat

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


def _digest(workspace, path):
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
        digest = hashlib.sha256()
        total = 0
        while chunk := os.read(descriptor, 65536):
            total += len(chunk)
            if total > MAX_ARTIFACT_BYTES:
                raise ValueError('artifact exceeds verification byte budget')
            digest.update(chunk)
        after = os.fstat(descriptor)
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError('artifact changed during verification')
        return digest.hexdigest()
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory)


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
