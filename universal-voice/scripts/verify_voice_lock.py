"""Verify the user-approved voice baseline; this command never unlocks files."""
import hashlib
import json
import os
from pathlib import Path
import sys


def verify(root):
    manifest = json.loads((root / '.voice_lock.json').read_text())
    locked = manifest['locked_files']
    if manifest.get('schema_version') != 1 or not locked:
        raise ValueError('Missing voice lock baseline')
    errors = []
    for relative, entry in locked.items():
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Invalid locked path: ' + relative)
        target = root / path
        if 'link_target' in entry:
            if (not target.is_symlink() or os.readlink(target) != entry['link_target']
                    or not target.resolve().is_relative_to(root.resolve())):
                errors.append('Changed link: ' + relative)
            continue
        if any((root / Path(*path.parts[:i])).is_symlink() for i in range(1, len(path.parts) + 1)):
            errors.append('Linked: ' + relative)
        elif not target.is_file():
            errors.append('Missing: ' + relative)
        elif hashlib.sha256(target.read_bytes()).hexdigest() != entry['sha256']:
            errors.append('Changed: ' + relative)
    for relative in manifest['protected_roots']:
        directory = Path(relative)
        if directory.is_absolute() or '..' in directory.parts:
            raise ValueError('Invalid protected root: ' + relative)
        for path in (root / directory).rglob('*'):
            if '__pycache__' in path.parts or path == root / '.voice_lock.json':
                continue
            if (path.is_file() or path.is_symlink()) and str(path.relative_to(root)) not in locked:
                errors.append('Added: ' + str(path.relative_to(root)))
    return errors


def main():
    try:
        errors = verify(Path(__file__).resolve().parents[1])
    except (OSError, ValueError, KeyError, TypeError) as error:
        print('Voice lock FAIL: ' + str(error), file=sys.stderr)
        return 1
    if errors:
        print('Voice lock FAIL:\n' + '\n'.join(errors), file=sys.stderr)
        return 1
    print('Voice lock PASS: the approved baseline is intact.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
