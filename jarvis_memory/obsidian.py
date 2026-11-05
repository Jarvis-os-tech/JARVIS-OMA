"""Publish memory as owned Markdown notes and links in an Obsidian vault."""
from hashlib import sha256
from datetime import datetime
from zoneinfo import ZoneInfo
import html
import json
from pathlib import Path
import os
import re
import sqlite3
import tempfile
import time
from .store import _cross_process_lock
from .summaries import render_daily_summary
from .categories import CATEGORIES, category_for

FOLDER = 'JARVIS-OMA Memory'
MARKER = '<!-- jarvis-oma-memory-generated:v1 -->'
STOP = set('this that with from have your about were what when then them they their would could should '
           'there which into just like also only will been want please using user assistant noted'.split())


def digest(value):
    return sha256(value.encode('utf-8')).hexdigest()


def link(key):
    return f'[[{FOLDER}/{key}]]'


def plain(text):
    return html.escape(text, quote=False).replace('[[', '\\[\\[').replace(']]', '\\]\\]')


def publish(memory, vault_path):
    vault = Path(vault_path).expanduser().resolve(strict=True)
    layout = getattr(memory.config, 'obsidian_layout', 'legacy')
    root = vault if layout in ('organized', 'sovereign') else vault / FOLDER
    if not vault.is_dir() or root.is_symlink():
        raise ValueError('vault must be a directory with a non-symlink managed folder')
    root.mkdir(mode=0o700, exist_ok=True)
    with _cross_process_lock(root / '.jarvis-sync.lock'):
        return _publish(memory, vault_path)


def _publish(memory, vault_path):
    vault = Path(vault_path).expanduser().resolve(strict=True)
    if not vault.is_dir():
        raise ValueError('Obsidian vault must be an existing directory')
    layout = getattr(memory.config, 'obsidian_layout', 'legacy')
    organized = layout == 'organized'
    sovereign = layout == 'sovereign'
    root = vault if (organized or sovereign) else vault / FOLDER
    if root.is_symlink():
        raise ValueError('managed memory folder cannot be a symlink')
    root.mkdir(mode=0o700, exist_ok=True)
    manifest_path = root / '.jarvis-sync.json'
    if manifest_path.is_symlink():
        raise ValueError('sync manifest cannot be a symlink')
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    if not isinstance(previous, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                                for k, v in previous.items()):
        raise ValueError('invalid Obsidian sync manifest')
    notes, groups, topics = {}, {}, {}
    for folder in ([] if (organized or sovereign) else [value[0] for value in CATEGORIES.values()] + ['Conversations', 'Summaries', 'Profiles', 'Documents']):
        directory = root / folder
        if directory.is_symlink():
            raise ValueError('managed category folder cannot be a symlink')
        directory.mkdir(mode=0o700, exist_ok=True)

    def add(key, title, text='', edges=(), kind='memory', metadata=None):
        fields = ''.join(f'{name}: {json.dumps(value, ensure_ascii=False)}\n'
                         for name, value in (metadata or {}).items())
        notes[key + '.md'] = (f'---\naliases: [{json.dumps(title, ensure_ascii=False)}]\n'
                             f'tags: [jarvis-memory, {kind}]\n{fields}---\n{MARKER}\n\n# {plain(title)}\n\n'
                             + plain(text) + '\n\n' + '\n'.join(link(edge) for edge in edges) + '\n')

    def topic_edges(text):
        words = sorted(set(re.findall(r'\b[^\W\d_][\w-]{3,}\b', text.casefold())))
        selected = [word for word in words if word not in STOP][:6]
        edges = []
        for word in selected:
            key = 'Topics/' + word
            topics[key] = word
            edges.append(key)
        return edges

    add('Entities/User', 'User', edges=['Memory Map'], kind='entity')
    add('Entities/JARVIS', 'JARVIS', edges=['Memory Map'], kind='entity')
    ledger = memory.knowledge.list(active_only=False) if hasattr(memory, 'knowledge') else []
    now = time.time()
    current = lambda entry: (entry['status'] == 'active' and entry.get('sensitivity') != 'secret-forbidden'
                             and (entry.get('expires_at') is None or entry['expires_at'] > now))
    retired = {entry['text'].casefold() for entry in ledger if not current(entry)}
    active_text = {entry['text'].casefold() for entry in ledger if current(entry)}
    facts = [fact for fact in memory.store.list() if fact.trusted_for_recall
             and memory.scanner.scan(fact.text).is_clean
             and fact.text.casefold() not in active_text
             and (fact.text.casefold() not in retired or fact.text.casefold() in active_text)]
    for fact in facts:
        slug = re.sub(r'[^\w -]', '', fact.text)[:50].strip() or 'Fact'
        key = 'Facts/' + slug + '-' + digest(fact.text.casefold())[:12]
        add(key, fact.text[:100], fact.text, ['Facts', 'Entities/User', *topic_edges(fact.text)], 'fact')
        groups.setdefault('Facts', []).append(key)
    for entry in ledger:
        if not current(entry) or not memory.scanner.scan(entry['text']).is_clean:
            continue
        category = category_for(entry)
        folder = CATEGORIES[category][0]
        # Project-owned entries stay visible in their own scoped vault section.
        scope = entry.get('scope', 'user')
        safe_scope = re.sub(r'[^A-Za-z0-9_-]', '-', scope)[:100]
        prefix = '' if scope == 'user' else 'Scoped/' + safe_scope + '/'
        key = prefix + folder + '/Memory-' + entry['id']
        warning = ('Saved user guidance, not system policy or permission to execute actions.\n\n'
                   if category == 'instructions' else '')
        body = warning + entry['text']
        evidence = entry.get('evidence')
        if isinstance(evidence, dict) and category == 'procedures':
            body += '\n\n## Steps\n\n' + '\n'.join(str(i + 1) + '. ' + str(step) for i, step in enumerate(evidence.get('steps', [])))
            body += '\n\nVerification: user-described, not execution-tested. Never run automatically.'
        if isinstance(evidence, dict) and category == 'episodes':
            body += '\n\nReported outcome: ' + str(evidence.get('reported_outcome', 'Not recorded'))
            body += '\n\nOutcome verification: unverified user report.'
        add(key, entry['text'][:100],
            body + '\n\nEvidence: ' + json.dumps(entry['evidence'], ensure_ascii=False),
            [folder, 'Knowledge', 'Entities/User', *topic_edges(entry['text'])], 'structured',
            {'memory_id': entry['id'], 'kind': entry['kind'], 'status': entry['status'],
             'category': category, 'scope': scope, 'authority': entry.get('authority', 'agent'),
             'created_at': entry['created_at'], 'updated_at': entry['updated_at'],
             'observed_at': entry.get('observed_at'),
             'source': entry['source'], 'confidence': entry['confidence']})
        groups.setdefault('Knowledge', []).append(key)
        groups.setdefault(folder, []).append(key)
    for name in ('SOUL', 'MEMORY', 'USER'):
        path = memory.root / (name + '.md')
        if path.is_file():
            text = path.read_text(encoding='utf-8')[:10000]
            if memory.scanner.scan(text).is_clean:
                key = 'Profiles/' + name
                add(key, name + ' profile', text, ['Profiles', *topic_edges(text)], 'profile')
                groups.setdefault('Profiles', []).append(key)

    db = memory.root / 'sessions.db'
    if db.is_file() and memory.config.record_sessions:
        connection = sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)
        try:
            rows = connection.execute('SELECT m.id,m.role,m.content,m.timestamp FROM session_messages m '
                'JOIN sessions s ON s.session_id=m.session_id WHERE s.user_id=? ORDER BY m.id',
                ('local-user',)).fetchall()
        finally:
            connection.close()
        days = {}
        zone = ZoneInfo(memory.config.obsidian_timezone)
        for identifier, role, text, timestamp in rows:
            if not memory.scanner.scan(text).is_clean:
                continue
            try:
                local = datetime.fromtimestamp(timestamp, zone)
            except (TypeError, ValueError, OverflowError, OSError):
                continue
            date = local.strftime('%Y-%m-%d')
            days.setdefault(date, []).append((identifier, role, text, local))
        previous_key = None
        ordered = sorted(days)
        for index, date in enumerate(ordered):
            turns = days[date]
            weekday = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')[turns[0][3].weekday()]
            key = f'Conversations/{date} - {weekday}'
            summary_key = f'Summaries/{date} - {weekday}'
            edges = ['Continuous Memory', 'Entities/User', 'Entities/JARVIS', summary_key]
            if previous_key:
                edges.append(previous_key)
            if index + 1 < len(ordered):
                next_day = ordered[index + 1]
                next_weekday = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')[days[next_day][0][3].weekday()]
                edges.append(f'Conversations/{next_day} - {next_weekday}')
            shared_topics = set()
            for _, _, text, _ in turns:
                shared_topics.update(topic_edges(text))
            # Existing fact/profile notes sharing topics appear as related notes.
            for relative, content in list(notes.items()):
                if (relative[:-3] in groups.get('Knowledge', []) or relative.startswith(('Facts/', 'Profiles/'))) and any(link(topic) in content for topic in shared_topics):
                    edges.append(relative[:-3])
            report = (f'## Daily report\n\nDate: {date}\nDay: {weekday}\n'
                      f'Timezone: {memory.config.obsidian_timezone}\nMessages: {len(turns)}\n\n'
                      'This is a chronological report of captured conversation text, not an AI summary. '
                      'Daily grouping does not reset continuous memory.\n\n## Conversation\n\n')
            report += '\n\n'.join(f'### [{local:%H:%M:%S}] [{"User" if role == "user" else "JARVIS"}] — message {identifier}\n\n{text}'
                                     for identifier, role, text, local in turns)
            add(key, f'{date} - {weekday}', report, [*edges, *sorted(shared_topics)], 'conversation',
                {'type': 'daily-conversation-report', 'date': date, 'day': weekday,
                 'timezone': memory.config.obsidian_timezone, 'messages': len(turns)})
            groups.setdefault('Continuous Memory', []).append(key)
            add(summary_key, f'{date} - {weekday} summary', render_daily_summary(turns),
                ['Summaries', key, 'Entities/User', 'Entities/JARVIS',
                 *[edge for edge in edges if edge.startswith(('Facts/', 'Profiles/', 'Knowledge/'))],
                 *sorted(shared_topics)], 'summary',
                {'type': 'extractive-daily-summary', 'date': date, 'day': weekday,
                 'timezone': memory.config.obsidian_timezone, 'messages': len(turns)})
            groups.setdefault('Summaries', []).append(summary_key)
            previous_key = key
        journal = '\n\n'.join(
            f'### [{local:%Y-%m-%d %H:%M:%S}] [{"User" if role == "user" else "JARVIS"}] — message {identifier}\n\n{text}'
            for date in ordered for identifier, role, text, local in days[date])
        add('Conversations/conversation', 'Continuous conversation journal', journal,
            ['Continuous Memory', *groups.get('Continuous Memory', [])], 'conversation',
            {'type': 'continuous-conversation', 'timezone': memory.config.obsidian_timezone})
        groups.setdefault('Continuous Memory', []).insert(0, 'Conversations/conversation')
    db = memory.root / 'jarvis_documents.db'
    if db.is_file():
        connection = sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)
        try:
            rows = connection.execute("SELECT source,content FROM chunks WHERE trust='trusted' ORDER BY rowid").fetchall()
        finally:
            connection.close()
        documents = {}
        for source, content in rows:
            if memory.scanner.scan(content).is_clean:
                documents.setdefault(source, []).append(content)
        for source, chunks in documents.items():
            key = 'Documents/Document-' + digest(source)[:20]
            text = 'Source: ' + source + '\n\n' + '\n\n'.join(chunks)
            add(key, Path(source).name, text, ['Documents', *topic_edges(text)], 'document')
            groups.setdefault('Documents', []).append(key)
    for key, word in topics.items():
        add(key, word, edges=['Topics'], kind='topic')
    groups['Topics'] = list(topics)
    add('Vault Guide', 'Vault structure and automatic links',
        'Preferences, Personal, Facts and Instructions are separate memory categories. '
        'Instructions are user guidance, never system policy or execution authorization. '
        'Projects, Decisions, Goals, Tasks, Procedures, Constraints and Observations keep other durable knowledge organized. '
        'Project-scoped notes live under Scoped; they are excluded from general user recall.\n\n'
        'Conversations: one YYYY-MM-DD - Weekday.md report per local calendar day, plus conversation.md '
        'for the continuous journal. Reports retain captured dialogue and message IDs; they are not AI summaries.\n\n'
        'Summaries: separate extractive daily notes quote source messages with IDs and link to daily reports. '
        'Assistant reported outcomes are unverified; follow-up mentions are not inferred tasks.\n\n'
        'Knowledge: active structured memories with evidence, kind, confidence and stable IDs. '
        'Facts and Profiles: trusted memory and core user/system profiles. Documents: indexed reference text. '
        'Topics and Entities: automatic shared-word and speaker links for Graph view. Daily reports link '
        'to neighboring days and related fact/profile notes.\n\n'
        'SQLite remains the continuous source of truth across restarts. Day changes only organize the view. '
        'Old vault contents are not imported. Keep future custom skills and personal notes outside '
        'JARVIS-OMA Memory; Markdown skills are not automatically executed. '
        'Manual changes to generated notes are preserved and reported as sync conflicts. '
        'Use sync_memory_vault to refresh; background refresh runs while voice is connected.',
        ['Memory Map', 'Continuous Memory', 'Summaries', 'Knowledge', 'Facts', 'Profiles', 'Documents', 'Topics'], 'index')
    category_folders = [value[0] for value in CATEGORIES.values()]
    for group in (*category_folders, 'Profiles', 'Continuous Memory', 'Summaries', 'Knowledge', 'Documents', 'Topics'):
        add(group, group, edges=['Memory Map', *groups.get(group, [])], kind='index')
    add('Memory Map', 'JARVIS continuous memory',
        'Open Obsidian Graph view and filter path:"JARVIS-OMA Memory". '
        'Links represent categories, chronological order, and shared words; they do not assert causal relationships.',
        ['Start Here', 'Vault Guide', *category_folders, 'Profiles', 'Knowledge', 'Continuous Memory', 'Summaries', 'Documents', 'Topics', 'Entities/User', 'Entities/JARVIS'], 'index')
    overview = '## Your memory library\n\nCategory | Current notes\n--- | ---\n'
    overview += '\n'.join(folder + ' | ' + str(len(groups.get(folder, []))) for folder in category_folders)
    overview += '\n\nConversations and summaries preserve history separately from current facts. '
    overview += 'SQLite is authoritative; these Markdown notes are an organized, linked view. '
    overview += 'Generated notes preserve manual edits as conflicts. Keep your own notes outside this managed folder.'
    layers = {
        'Short-term Memory': ('Temporary working context lives only in the running process and expires. It is not exported into this vault.', []),
        'Long-term Memory': ('Persistent current user memories survive restarts, with category, scope and evidence.', category_folders),
        'Episodic Memory': ('Dated conversations and specific event records. Reported outcomes are not automatically verified.', ['Episodes', 'Continuous Memory', 'Summaries']),
        'Semantic Memory': ('Facts, concepts, documents and topic relationships. Semantic knowledge does not require vector search; embedding retrieval is a separate optional setting.', ['Facts', 'Documents', 'Topics']),
        'Procedural Memory': ('Repeatable workflow steps. A saved procedure never grants execution permission, and user-described procedures are not claimed to be tested.', ['Procedures']),
        'Shared Memory': ('Agent exchange uses explicit scope policies and audited proposal/commit operations. Personal user memory is not implicitly shared.', [p for p in groups.get('Knowledge', []) if p.startswith('Scoped/shared-')]),
    }
    for layer, (description, edges) in layers.items():
        add(layer, layer, description, ['Start Here', *edges], 'index')
    overview = '## Six layers, one JARVIS memory manager\n\n' + overview
    add('Start Here', 'JARVIS Memory — Start Here', overview,
        [*layers, *category_folders, 'Continuous Memory', 'Summaries', 'Profiles', 'Documents', 'Memory Map', 'Vault Guide'], 'index')

    if organized:
        from .vault_layout import organized_notes
        notes = organized_notes(notes, groups, FOLDER)
    elif sovereign:
        from .vault_layout import sovereign_notes
        notes = sovereign_notes(notes, groups, FOLDER, memory)

    def safe_path(relative):
        path = root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('invalid managed note path')
        return path

    def atomic(path, content):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                stream.write(content)
            os.replace(temp, path)
        finally:
            Path(temp).unlink(missing_ok=True)

    manifest, conflicts, written, removed = dict(previous), [], 0, 0
    for relative, content in notes.items():
        path = safe_path(relative)
        if path.exists():
            old = path.read_text(encoding='utf-8')
            if old == content:
                if relative in previous:
                    manifest[relative] = digest(content)
                else:
                    conflicts.append(relative)
                continue
            if previous.get(relative) != digest(old) or MARKER not in old:
                conflicts.append(relative)
                continue
        atomic(path, content)
        manifest[relative] = digest(content)
        written += 1
    for relative in set(previous) - set(notes):
        path = safe_path(relative)
        if path.exists():
            content = path.read_text(encoding='utf-8')
            if digest(content) != previous[relative] or MARKER not in content:
                conflicts.append(relative)
                continue
            path.unlink()
            removed += 1
        manifest.pop(relative, None)
    atomic(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2))
    return {'status': 'synced' if not conflicts else 'conflicts', 'vault': str(vault),
            'memory_map': str(root / ('00 HOME.md' if (organized or sovereign) else 'Memory Map.md')), 'nodes': len(notes),
            'written': written, 'removed': removed, 'conflicts': conflicts,
            'start_here': str(root / ('00 HOME.md' if (organized or sovereign) else 'Start Here.md')),
            'categories': {folder: len(groups.get(folder, [])) for folder in category_folders}}
