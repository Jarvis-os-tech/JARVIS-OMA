"""Bounded filesystem operations exposed to the voice skill registry."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import uuid
from datetime import datetime
from urllib.parse import quote


class FileOperationError(ValueError):
    pass


def path_for(value: str) -> Path:
    if not isinstance(value, str) or not value.strip() or '\x00' in value or len(value) > 4096:
        raise FileOperationError('invalid file path')
    return Path(value).expanduser().absolute()


def details(path: Path) -> dict:
    try:
        info = path.lstat()
    except OSError as error:
        raise FileOperationError(f'cannot inspect {path}: {error.strerror}') from None
    kind = 'symlink' if path.is_symlink() else 'directory' if path.is_dir() else 'file'
    return {'path': str(path), 'name': path.name, 'type': kind, 'size': info.st_size,
            'modified': datetime.fromtimestamp(info.st_mtime).astimezone().isoformat(timespec='seconds')}


def list_directory(value: str, limit: int = 100) -> dict:
    path = path_for(value)
    if not path.is_dir():
        raise FileOperationError('path is not a directory')
    if not 1 <= limit <= 200:
        raise FileOperationError('limit must be from 1 to 200')
    try:
        entries = sorted(path.iterdir(), key=lambda item: item.name.casefold())
        return {'path': str(path), 'entries': [details(item) for item in entries[:limit]],
                'count': len(entries), 'truncated': len(entries) > limit}
    except OSError as error:
        raise FileOperationError(f'cannot list directory: {error.strerror}') from None


def read_text(value: str, max_chars: int = 12000) -> dict:
    path = path_for(value)
    if not path.is_file():
        raise FileOperationError('path is not a file')
    if not 1 <= max_chars <= 20000:
        raise FileOperationError('max_chars must be from 1 to 20000')
    try:
        with path.open('r', encoding='utf-8') as stream:
            content = stream.read(max_chars + 1)
    except (OSError, UnicodeError) as error:
        raise FileOperationError(f'cannot read text file: {error}') from None
    return {'path': str(path), 'content': content[:max_chars], 'truncated': len(content) > max_chars}


def search_files(value: str, query: str, limit: int = 50) -> dict:
    path = path_for(value)
    if not path.is_dir() or not isinstance(query, str) or not query.strip() or len(query) > 200:
        raise FileOperationError('invalid directory or search query')
    if not 1 <= limit <= 100:
        raise FileOperationError('limit must be from 1 to 100')
    matches = []
    for current, directories, files in os.walk(path, followlinks=False):
        directories[:] = [name for name in directories if not name.startswith('.')]
        for name in files + directories:
            if query.casefold() in name.casefold():
                matches.append(str(Path(current) / name))
                if len(matches) >= limit:
                    return {'matches': matches, 'truncated': True}
    return {'matches': matches, 'truncated': False}


def write_text(value: str, content: str, overwrite: bool = False) -> dict:
    path = path_for(value)
    if not isinstance(content, str) or len(content.encode('utf-8')) > 1024 * 1024:
        raise FileOperationError('content must be text of at most 1 MiB')
    if path.exists() and not overwrite:
        raise FileOperationError('file exists; set overwrite to true to replace it')
    if path.exists() and not path.is_file():
        raise FileOperationError('path is not a regular file')
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
        try:
            temporary.write_text(content, encoding='utf-8')
            if path.exists():
                temporary.chmod(path.stat().st_mode & 0o777)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    except OSError as error:
        raise FileOperationError(f'cannot write file: {error.strerror}') from None
    return {'status': 'written', 'path': str(path), 'bytes': len(content.encode('utf-8'))}


def make_directory(value: str) -> dict:
    path = path_for(value)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise FileOperationError(f'cannot create directory: {error.strerror}') from None
    return {'status': 'created', 'path': str(path)}


def move_path(source: str, destination: str) -> dict:
    src, dst = path_for(source), path_for(destination)
    if not src.exists() and not src.is_symlink():
        raise FileOperationError('source does not exist')
    if dst.exists() or dst.is_symlink():
        raise FileOperationError('destination already exists')
    if src == dst or src in dst.parents:
        raise FileOperationError('cannot move a directory inside itself')
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
    except OSError as error:
        raise FileOperationError(f'cannot move path: {error.strerror}') from None
    return {'status': 'moved', 'source': str(src), 'destination': str(dst)}


def trash_path(value: str) -> dict:
    path = path_for(value)
    if path == Path('/') or path == Path.home() or not (path.exists() or path.is_symlink()):
        raise FileOperationError('cannot trash this path')
    data_home = Path(os.getenv('XDG_DATA_HOME') or Path.home() / '.local/share')
    trash = data_home / 'Trash'
    name = path.name + '.' + uuid.uuid4().hex[:8]
    target = trash / 'files' / name
    info = trash / 'info' / (name + '.trashinfo')
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        info.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(target))
        info.write_text('[Trash Info]\nPath=' + quote(str(path), safe='/') +
                        '\nDeletionDate=' + datetime.now().strftime('%Y-%m-%dT%H:%M:%S') + '\n', encoding='utf-8')
    except OSError as error:
        raise FileOperationError(f'cannot move path to Trash: {error.strerror}') from None
    return {'status': 'trashed', 'original': str(path), 'trash_path': str(target)}
