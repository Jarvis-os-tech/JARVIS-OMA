"""Apply only persona/analysis changes over the active managed voice release."""
from __future__ import annotations
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[1]


def function_text(body, name, class_name=None):
    scope = ast.parse(body).body
    if class_name:
        classes = [n for n in scope if isinstance(n, ast.ClassDef) and n.name == class_name]
        if len(classes) != 1:
            raise ValueError('Unexpected class boundary: ' + class_name)
        scope = classes[0].body
    nodes = [n for n in scope if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise ValueError("Unexpected function boundary: " + name)
    node = nodes[0]
    return ''.join(body.splitlines(keepends=True)[node.lineno - 1:node.end_lineno])


def replace_once(body, old, new):
    if body.count(old) != 1:
        raise ValueError("Installed integration point differs; prepare stopped")
    return body.replace(old, new, 1)


def refresh_worker_instruction(body, source):
    def assignment(text):
        matches = [node for node in ast.parse(text).body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == 'REASONING_INSTRUCTION' for target in node.targets)]
        if len(matches) > 1:
            raise ValueError('Duplicate reasoning instruction definitions')
        if not matches:
            return None
        node = matches[0]
        return ''.join(text.splitlines(keepends=True)[node.lineno - 1:node.end_lineno])
    fresh, old = assignment(source), assignment(body)
    if fresh is None:
        raise ValueError('Source reasoning instruction missing')
    if old is None:
        body = replace_once(body, '\n\nclass ModelJobs:', '\n\n' + fresh + '\n\nclass ModelJobs:')
    else:
        body = replace_once(body, old, fresh)
    legacy = "'Provide analysis only. You have no execution tools. Never claim computer actions were performed.'"
    if legacy in body:
        body = replace_once(body, legacy, 'REASONING_INSTRUCTION')
    return body


def prepare(destination):
    runtime = Path.home() / '.local/share/jarvis-runtime'
    parent = (runtime / 'current').resolve(strict=True)
    if not parent.is_relative_to(runtime / 'releases'):
        raise ValueError('Current runtime is not a managed release')
    target = Path(tempfile.mkdtemp(prefix='jarvis-persona-release-', dir=destination))
    shutil.copytree(parent, target, symlinks=True, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    changed = []

    def write(relative, body):
        path = target / relative
        if path.is_symlink(): raise ValueError('Refusing linked source file: ' + relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists(): path.chmod(path.stat().st_mode | 0o200)
        path.write_text(body)
        changed.append(relative)

    write('voice_layer/persona.py', (SOURCE / 'voice_layer/persona.py').read_text())
    relative = 'voice_layer/daemon.py'
    body, source = (target / relative).read_text(), (SOURCE / 'voice_layer/daemon.py').read_text()
    for name in ('build_instruction', 'live_config'):
        body = replace_once(body, function_text(body, name), function_text(source, name))
    body = replace_once(body, function_text(body, 'send_wake_confirmation', 'LiveVoice'),
                        function_text(source, 'send_wake_confirmation', 'LiveVoice'))
    addition = 'from .persona import system_persona, SPOKEN_UPDATES, MEMORY_RULES\n'
    if addition not in body:
        body = replace_once(body, 'from .config import Config, load as load_config, load_env\n',
                            'from .config import Config, load as load_config, load_env\n' + addition)
    # Respect an explicit CLI model override when forming its setup payload.
    body = body.replace('skills=skills, config=config, memory_context=context)',
                        'skills=skills, config=replace(config, model=model), memory_context=context)')
    write(relative, body)

    relative = 'core/harness_config.py'
    body, source = (target / relative).read_text(), (SOURCE / relative).read_text()
    if 'from voice_layer.persona import system_persona' not in body:
        old_start = body.index('        instruction = (', body.index('    elif skills is not None:'))
        end_marker = "            'Begin with the answer or execute the requested action immediately. '"
        old_end = body.index(end_marker, old_start)
        new_start = source.index("        declarations = getattr(skills, 'live_declarations', skills.declarations)")
        new_end = source.index(end_marker, new_start)
        body = body[:old_start] + source[new_start:new_end] + body[old_end:]
        body = replace_once(body, 'from pathlib import Path\n',
                            'from pathlib import Path\nfrom voice_layer.persona import system_persona\n')
    # Superseded hard-coded rules otherwise override the shared conversation policy.
    for start, end in (
        ('            \'Interpret a bare “mute”,', "            'JARVIS is never permitted"),
        ("            'When the user clearly asks for conversational silence", "            'For switching between production mode"),
    ):
        if start in body:
            if body.count(start) != 1 or body.count(end) != 1:
                raise ValueError('Installed conversation boundary differs; prepare stopped')
            first = body.index(start)
            last = body.index(end, first)
            body = replace_once(body, body[first:last], '')
    write(relative, body)

    relative = 'orchestration/model_routes.py'
    body = (target / relative).read_text()
    body = refresh_worker_instruction(body, (SOURCE / relative).read_text())
    write(relative, body)

    # Transplant only delivery methods, preserving other installed control work.
    relative = 'jarvis_control/skills.py'
    body, source = (target / relative).read_text(), (SOURCE / relative).read_text()
    old_class = next(n for n in ast.parse(body).body if isinstance(n, ast.ClassDef) and n.name == 'UnifiedSkills')
    new_class = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'UnifiedSkills')
    for name in ('background_events', 'acknowledge_event'):
        old_node = next(n for n in old_class.body if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
        new_node = next(n for n in new_class.body if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
        old = ''.join(body.splitlines(keepends=True)[old_node.lineno - 1:old_node.end_lineno])
        new = ''.join(source.splitlines(keepends=True)[new_node.lineno - 1:new_node.end_lineno])
        body = replace_once(body, old, new)
        old_class = next(n for n in ast.parse(body).body if isinstance(n, ast.ClassDef) and n.name == 'UnifiedSkills')
    write(relative, body)
    for relative in ('orchestration/model_notices.py', 'orchestration/release_manager.py',
                     'jarvis_control/nlu.py', 'skill_manifests/standby.json'):
        write(relative, (SOURCE / relative).read_text())
    relative = 'orchestration/tool_tiers.py'
    body = (target / relative).read_text()
    if "    'start_model_processing', 'model_processing_status'," not in body:
        marker = "    'cancel_task', 'open_input_bar', 'close_input_bar', 'show_widget', 'manage_canvas', 'manage_widget', 'widget_schema',\n"
        body = replace_once(body, marker, marker + "    'start_model_processing', 'model_processing_status',\n")
    write(relative, body)

    for name in changed:
        if name.endswith('.py'):
            compile((target / name).read_text(), name, 'exec')
    env = dict(os.environ, PYTHONPATH=str(target), PYTHONDONTWRITEBYTECODE='1')
    check = """from types import SimpleNamespace as NS
from pathlib import Path
from google.genai import types
from voice_layer.daemon import live_config
from skills.skills import DesktopSkills
from orchestration.tool_tiers import CORE_TOOLS
r=DesktopSkills.__new__(DesktopSkills);r.manifest_dirs=[Path('skill_manifests')]
specs=r._load_manifests()
required={'start_model_processing','model_processing_status','show_widget','widget_schema'}
assert required<=set(specs) and required<=CORE_TOOLS
c=live_config(config=NS(model='gemini-3.8-live'), tools=[{'function_declarations':[{'name':x} for x in sorted(required)]}])
assert 'thinking_config' not in c
assert 'system voice and interaction layer' in c['system_instruction']
assert 'GENERATED WIDGETS ARE PART OF THE OS' in c['system_instruction']
types.LiveConnectConfig.model_validate(c)
import asyncio
from jarvis_control.skills import UnifiedSkills
async def verify_delivery():
    jobs=NS(jobs={'fixture':{'id':'fixture','route':'reasoning','status':'completed','result':'Synthetic verification result'}})
    u=UnifiedSkills(desktop_skills=NS(_model_jobs=jobs))
    notices=await u.background_events()
    assert len(notices)==1 and notices[0]['id']=='model:fixture'
    await u.acknowledge_event(notices[0]['id'])
    assert not await u.background_events()
asyncio.run(verify_delivery())
print('Persona, reasoning tools and Live setup validated')
"""
    subprocess.run([str(runtime / 'venv/bin/python'), '-c', check], cwd=target, env=env, timeout=30, check=True)
    metadata = json.loads((target / 'release.json').read_text())
    metadata['persona_extension'] = {'parent': str(parent), 'created_at': datetime.now(timezone.utc).isoformat(),
        'sha256': {n: hashlib.sha256((target / n).read_bytes()).hexdigest() for n in changed}}
    (target / 'release.json').write_text(json.dumps(metadata, indent=2) + '\n')
    return target, parent


def activate(staged):
    staged = Path(staged).resolve(strict=True)
    metadata = json.loads((staged / 'release.json').read_text())['persona_extension']
    runtime = Path.home() / '.local/share/jarvis-runtime'
    if (runtime / 'current').resolve() != Path(metadata['parent']):
        raise ValueError('Active release changed; prepare again')
    for name, digest in metadata['sha256'].items():
        if hashlib.sha256((staged / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Staged source changed: ' + name)
    sys.path.insert(0, str(SOURCE))
    from orchestration.release_manager import ReleaseManager
    name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-system-persona'
    target = ReleaseManager(root_dir=runtime).install_prepared_release(
        staged, name, expected_current=Path(metadata['parent']), timeout=20,
        expected_hashes=metadata['sha256'])
    print(json.dumps({'activated': str(target), 'previous': metadata['parent']}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--prepare', type=Path)
    choice.add_argument('--activate', type=Path)
    args = parser.parse_args()
    if args.prepare:
        target, parent = prepare(args.prepare)
        print(json.dumps({'prepared': str(target), 'parent': str(parent)}))
    else: activate(args.activate)


if __name__ == '__main__': main()
