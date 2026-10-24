"""Bounded filesystem operations exposed to the voice skill registry with full autonomy."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import uuid
from datetime import datetime
from urllib.parse import quote

CRITICAL_PATHS = {
    Path('/'),
    Path.home(),
    Path('/bin'),
    Path('/boot'),
    Path('/dev'),
    Path('/etc'),
    Path('/lib'),
    Path('/lib64'),
    Path('/proc'),
    Path('/root'),
    Path('/sbin'),
    Path('/sys'),
    Path('/usr'),
}


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
    return {
        'path': str(path),
        'name': path.name,
        'type': kind,
        'size': info.st_size,
        'mode': oct(info.st_mode & 0o777),
        'modified': datetime.fromtimestamp(info.st_mtime).astimezone().isoformat(timespec='seconds'),
    }


def inspect_path(value: str) -> dict:
    path = path_for(value)
    if not path.exists() and not path.is_symlink():
        return {'exists': False, 'path': str(path)}
    item = details(path)
    item['exists'] = True
    item['is_readable'] = os.access(path, os.R_OK)
    item['is_writable'] = os.access(path, os.W_OK)
    if path.is_file() and not path.is_symlink() and item['size'] <= 1024 * 1024:
        try:
            with path.open('r', encoding='utf-8', errors='ignore') as stream:
                item['line_count'] = sum(1 for _ in stream)
        except Exception:
            pass
    return item


def list_directory(value: str, limit: int = 100, include_hidden: bool = True) -> dict:
    path = path_for(value)
    if not path.is_dir():
        raise FileOperationError('path is not a directory')
    if not 1 <= limit <= 500:
        raise FileOperationError('limit must be from 1 to 500')
    try:
        entries = [p for p in path.iterdir() if include_hidden or not p.name.startswith('.')]
        entries.sort(key=lambda item: (not item.is_dir(), item.name.casefold()))
        return {
            'path': str(path),
            'entries': [details(item) for item in entries[:limit]],
            'count': len(entries),
            'truncated': len(entries) > limit,
        }
    except OSError as error:
        raise FileOperationError(f'cannot list directory: {error.strerror}') from None


def read_text(value: str, offset: int = 0, max_chars: int = 20000) -> dict:
    path = path_for(value)
    if not path.is_file():
        raise FileOperationError('path is not a file')
    if offset < 0:
        raise FileOperationError('offset must be nonnegative')
    if not 1 <= max_chars <= 100000:
        raise FileOperationError('max_chars must be from 1 to 100000')
    try:
        file_size = path.stat().st_size
        with path.open('r', encoding='utf-8') as stream:
            # Text offsets count characters, not UTF-8 bytes. Skip in bounded
            # chunks so large offsets do not allocate the entire prefix.
            remaining = offset
            while remaining > 0:
                skipped = stream.read(min(remaining, 8192))
                if not skipped:
                    break
                remaining -= len(skipped)
            content = stream.read(max_chars + 1)
    except (OSError, UnicodeError) as error:
        raise FileOperationError(f'cannot read text file: {error}') from None
    has_more = len(content) > max_chars
    return {
        'path': str(path),
        'content': content[:max_chars],
        'offset': offset,
        'chars_read': len(content[:max_chars]),
        'total_bytes': file_size,
        'truncated': has_more,
        'has_more': has_more,
    }


def search_files(value: str, query: str, limit: int = 50, include_hidden: bool = False) -> dict:
    path = path_for(value)
    if not path.is_dir() or not isinstance(query, str) or not query.strip() or len(query) > 200:
        raise FileOperationError('invalid directory or search query')
    if not 1 <= limit <= 100:
        raise FileOperationError('limit must be from 1 to 100')
    matches = []
    inspected = 0
    for current, directories, files in os.walk(path, followlinks=False):
        if not include_hidden:
            directories[:] = [name for name in directories if not name.startswith('.')]
        for name in files + directories:
            if not include_hidden and name.startswith('.'):
                continue
            inspected += 1
            if inspected > 10000:
                return {'matches': matches, 'truncated': True}
            if query.casefold() in name.casefold():
                matches.append(str(Path(current) / name))
                if len(matches) >= limit:
                    return {'matches': matches, 'truncated': True}
    return {'matches': matches, 'truncated': False}


def search_file_content(value: str, query: str, limit: int = 30, max_file_size: int = 1024 * 1024) -> dict:
    path = path_for(value)
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        raise FileOperationError('invalid search query')
    if not 1 <= limit <= 100:
        raise FileOperationError('limit must be from 1 to 100')

    matches = []
    files_to_search = []
    if path.is_file():
        files_to_search = [path]
    elif path.is_dir():
        for root, dirs, files in os.walk(path, followlinks=False):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in files:
                if not f.startswith('.'):
                    files_to_search.append(Path(root) / f)
                    if len(files_to_search) >= 5000:
                        break
            if len(files_to_search) >= 5000:
                break
    else:
        raise FileOperationError('path does not exist or is not searchable')

    query_cf = query.casefold()
    for file_path in files_to_search:
        try:
            if file_path.stat().st_size > max_file_size:
                continue
            with file_path.open('r', encoding='utf-8', errors='ignore') as stream:
                for line_idx, line in enumerate(stream, start=1):
                    if query_cf in line.casefold():
                        matches.append({
                            'path': str(file_path),
                            'line_number': line_idx,
                            'line': line.strip()[:200]
                        })
                        if len(matches) >= limit:
                            return {'query': query, 'matches': matches, 'truncated': True}
        except Exception:
            continue

    return {'query': query, 'matches': matches, 'truncated': False}


def write_text(value: str, content: str, overwrite: bool = False) -> dict:
    path = path_for(value)
    if not isinstance(content, str) or len(content.encode('utf-8')) > 5 * 1024 * 1024:
        raise FileOperationError('content must be text of at most 5 MiB')
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


def append_text(value: str, content: str) -> dict:
    path = path_for(value)
    if not isinstance(content, str):
        raise FileOperationError('content must be text')
    encoded = content.encode('utf-8')
    if len(encoded) > 5 * 1024 * 1024:
        raise FileOperationError('content must be at most 5 MiB')
    if path.exists() and not path.is_file():
        raise FileOperationError('path is not a regular file')
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as stream:
            stream.write(content)
    except OSError as error:
        raise FileOperationError(f'cannot append to file: {error.strerror}') from None
    return {'status': 'appended', 'path': str(path), 'bytes_appended': len(encoded)}


def make_directory(value: str) -> dict:
    path = path_for(value)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise FileOperationError(f'cannot create directory: {error.strerror}') from None
    return {'status': 'created', 'path': str(path)}


def move_path(source: str, destination: str, overwrite: bool = False) -> dict:
    src, dst = path_for(source), path_for(destination)
    if src in CRITICAL_PATHS or src == Path('/'):
        raise FileOperationError('cannot move system root or home directory')
    if not src.exists() and not src.is_symlink():
        raise FileOperationError('source does not exist')
    if dst in CRITICAL_PATHS or dst == Path('/'):
        raise FileOperationError('cannot overwrite system root or home directory')
    if src == dst or src in dst.parents:
        raise FileOperationError('cannot move a directory inside itself')
    if dst.exists() or dst.is_symlink():
        if not overwrite:
            raise FileOperationError('destination already exists; set overwrite to true to replace it')
        if dst.is_dir() and not dst.is_symlink():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
    except OSError as error:
        raise FileOperationError(f'cannot move path: {error.strerror}') from None
    return {'status': 'moved', 'source': str(src), 'destination': str(dst)}


def copy_path(source: str, destination: str, overwrite: bool = False) -> dict:
    src, dst = path_for(source), path_for(destination)
    if not src.exists() and not src.is_symlink():
        raise FileOperationError('source does not exist')
    if dst in CRITICAL_PATHS or dst == Path('/'):
        raise FileOperationError('cannot overwrite system root or home directory')
    if src == dst or src in dst.parents:
        raise FileOperationError('cannot copy a directory inside itself')
    if dst.exists() or dst.is_symlink():
        if not overwrite:
            raise FileOperationError('destination already exists; set overwrite to true to replace it')
        if dst.is_dir() and not dst.is_symlink():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir() and not src.is_symlink():
            shutil.copytree(src, dst, symlinks=True)
        elif src.is_symlink():
            dst.symlink_to(os.readlink(src))
        else:
            shutil.copy2(src, dst)
    except OSError as error:
        raise FileOperationError(f'cannot copy path: {error.strerror}') from None
    return {'status': 'copied', 'source': str(src), 'destination': str(dst)}


def replace_text(value: str, old: str, new: str) -> dict:
    path = path_for(value)
    if not path.is_file() or not old or not isinstance(old, str) or not isinstance(new, str):
        raise FileOperationError('invalid text replacement')
    try:
        content = path.read_text(encoding='utf-8')
    except (OSError, UnicodeError) as error:
        raise FileOperationError(f'cannot read text file: {error}') from None
    if len(content.encode('utf-8')) > 5 * 1024 * 1024:
        raise FileOperationError('file is too large for text replacement')
    count = content.count(old)
    if count != 1:
        raise FileOperationError(f'expected exactly one matching passage; found {count}')
    result = write_text(str(path), content.replace(old, new, 1), overwrite=True)
    return {'status': 'edited', 'path': result['path']}


def trash_path(value: str) -> dict:
    path = path_for(value)
    if path in CRITICAL_PATHS or path == Path('/') or not (path.exists() or path.is_symlink()):
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


def delete_path(value: str, recursive: bool = False) -> dict:
    path = path_for(value)
    if path in CRITICAL_PATHS or path == Path('/'):
        raise FileOperationError('cannot delete system root or home directory')
    if not path.exists() and not path.is_symlink():
        raise FileOperationError('path does not exist')
    try:
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            if not recursive and any(path.iterdir()):
                raise FileOperationError('directory is not empty; set recursive to true to delete it')
            shutil.rmtree(path)
        else:
            path.unlink()
    except OSError as error:
        raise FileOperationError(f'cannot delete path: {error.strerror}') from None
    return {'status': 'deleted', 'path': str(path)}
