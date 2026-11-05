"""Deploy Composio platform integration to jarvis-runtime release."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[1]


def deploy():
    runtime = Path.home() / '.local/share/jarvis-runtime'
    parent = (runtime / 'current').resolve(strict=True)
    if not parent.is_relative_to(runtime / 'releases'):
        raise ValueError('Current runtime is not a managed release')

    target = Path(tempfile.mkdtemp(prefix='jarvis-composio-release-', dir=runtime / 'releases'))
    shutil.copytree(parent, target, symlinks=True, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))

    changed = []

    def write(dest_rel, source_rel):
        dest_path = target / dest_rel
        if dest_path.is_symlink():
            raise ValueError('Refusing linked destination: ' + dest_rel)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if dest_path.exists():
            dest_path.chmod(dest_path.stat().st_mode | 0o200)
        content = (SOURCE / source_rel).read_bytes()
        dest_path.write_bytes(content)
        changed.append(dest_rel)

    # Copy files
    write('connectors/composio.py', 'connectors/composio.py')
    write('skills/domains/composio.py', 'skills/domains/composio.py')
    write('skills/skills.py', 'skills/skills.py')
    write('skill_manifests/composio.json', 'skill_manifests/composio.json')
    write('skill_manifests/omarchy-defaults.json', 'skill_manifests/omarchy-defaults.json')
    write('orchestration/tool_tiers.py', 'orchestration/tool_tiers.py')
    write('jarvis_voice/daemon.py', 'voice_layer/daemon.py')
    write('jarvis_voice/persona.py', 'voice_layer/persona.py')
    write('jarvis_control/nlu.py', 'jarvis_control/nlu.py')
    write('jarvis_control/execution_policy.py', 'jarvis_control/execution_policy.py')
    write('jarvis_control/skills.py', 'jarvis_control/skills.py')
    write('jarvis_control/tools.py', 'jarvis_control/tools.py')
    write('jarvis_control/device_execution.py', 'jarvis_control/device_execution.py')
    write('jarvis_control/outcomes.py', 'jarvis_control/outcomes.py')
    write('jarvis_control/wayland_keyboard.py', 'jarvis_control/wayland_keyboard.py')
    write('bin/jarvis', 'bin/jarvis')
    write('scripts/connect_composio.py', 'scripts/connect_composio.py')

    # Copy .env if it exists so COMPOSIO_API_KEY is available
    if (SOURCE / '.env').exists():
        (target / '.env').write_bytes((SOURCE / '.env').read_bytes())
        (target / '.env').chmod(0o600)

    # Copy connectors/.secrets so native Google and credentials tokens are present
    if (SOURCE / 'connectors/.secrets').exists():
        secrets_dest = target / 'connectors/.secrets'
        secrets_dest.mkdir(parents=True, exist_ok=True)
        secrets_dest.chmod(0o700)
        for sfile in (SOURCE / 'connectors/.secrets').iterdir():
            if sfile.is_file():
                (secrets_dest / sfile.name).write_bytes(sfile.read_bytes())
                (secrets_dest / sfile.name).chmod(0o600)

    # Update persona in the runtime release with strict native vs composio instructions
    persona_target = target / 'jarvis_voice/persona.py'
    if persona_target.exists():
        persona_target.chmod(persona_target.stat().st_mode | 0o200)
        p_content = persona_target.read_text(encoding='utf-8')
        old_auth_section = """EXTERNAL PLATFORMS & AUTHORIZATIONS:
When the user asks to connect to an external service or platform (e.g. LinkedIn, GitHub, Slack, Notion, Spotify, Google, etc.), open its authorization/login page, or check if it is connected or connecting:
- ALWAYS invoke connect_platform or open_platform_authorization. NEVER use open_website or launch_app for platform connections or authorizations. JARVIS pops open the official OAuth approval page in the desktop browser automatically.
- ALWAYS invoke check_platform_connection to check if a platform is connected or connecting, and report whether it is ACTIVE, CONNECTING, or NOT_CONNECTED."""
        new_auth_section = """EXTERNAL PLATFORMS & AUTHORIZATIONS:
For third-party platforms (e.g. LinkedIn, Slack, Notion, Spotify, Linear, Jira, Discord, Twitter/X):
- ONLY invoke connect_platform or open_platform_authorization when the user explicitly commands authorization or mentions an authorization-related keyword (authorize, auth, login page, sign in, connect, link). NEVER open an authorization page for general questions, code discussion, or status inquiries.
- When the user asks whether a platform is connected or connecting (e.g. 'is it connecting to those or not', 'is slack connected', 'connection status'), ALWAYS invoke check_platform_connection and report whether it is ACTIVE, CONNECTING, or NOT_CONNECTED. NEVER open an authorization page on a status inquiry.

NATIVE GITHUB & GOOGLE WORKSPACE INTEGRATIONS:
GitHub and Google Workspace (Gmail, Calendar, Drive, Docs, Sheets) are configured natively on JARVIS OS with the user's pre-configured accounts:
- NEVER invoke Composio tools for GitHub or Google Workspace.
- For GitHub: invoke github_connection_status to check status. Invoke github_authorize ONLY when the user explicitly commands to authorize or link GitHub.
- For Google Workspace: invoke google_connection_status to check status. Invoke google_authorize ONLY when the user explicitly commands to authorize or link Google.
- If the user asks whether GitHub or Google is connected, report the connection status using the status tool without opening the browser."""
        if old_auth_section in p_content:
            p_content = p_content.replace(old_auth_section, new_auth_section)
            persona_target.write_text(p_content, encoding='utf-8')

    # Compile python files to verify syntax
    for item in changed:
        if item.endswith('.py'):
            compile((target / item).read_text(encoding='utf-8'), item, 'exec')

    # Ensure composio is installed in runtime .venv
    py_runtime = target / '.venv/bin/python'
    subprocess.run(['uv', 'pip', 'install', 'composio', '--python', str(py_runtime)], check=True, timeout=60)

    # Verification script
    check_code = """
from pathlib import Path
from skills.skills import DesktopSkills
from orchestration.tool_tiers import CORE_TOOLS
r = DesktopSkills.__new__(DesktopSkills)
r.manifest_dirs = [Path('skill_manifests')]
specs = r._load_manifests()
required = {'open_platform_authorization', 'check_platform_connection', 'connect_platform', 'execute_platform_action', 'list_connected_platforms'}
assert required <= set(specs), f"Missing in specs: {required - set(specs)}"
assert required <= CORE_TOOLS, f"Missing in CORE_TOOLS: {required - CORE_TOOLS}"

native_tools = {'github_authorize', 'github_connection_status', 'google_authorize', 'google_connection_status'}
assert native_tools <= CORE_TOOLS, f"Missing native tools in CORE_TOOLS: {native_tools - CORE_TOOLS}"

from connectors import composio
assert 'open_platform_authorization' in composio.TOOLS
assert 'check_platform_connection' in composio.TOOLS

from jarvis_control.nlu import NLUEngine
assert not NLUEngine.validate_tool_intent('github_authorize', {}, 'is github connected')[0]
assert NLUEngine.validate_tool_intent('github_connection_status', {}, 'is github connected')[0]
assert not NLUEngine.validate_tool_intent('open_platform_authorization', {'platform': 'notion'}, 'is notion connected or connecting')[0]
assert NLUEngine.validate_tool_intent('open_platform_authorization', {'platform': 'notion'}, 'open notion authorization page')[0]

print('Composio and native integrations verified in release!')
"""
    env = dict(os.environ, PYTHONPATH=str(target), PYTHONDONTWRITEBYTECODE='1')
    subprocess.run([str(py_runtime), '-c', check_code], cwd=target, env=env, timeout=30, check=True)

    metadata = json.loads((target / 'release.json').read_text())
    metadata['composio_extension'] = {
        'parent': str(parent),
        'created_at': datetime.now(timezone.utc).isoformat(),
        'sha256': {n: hashlib.sha256((target / n).read_bytes()).hexdigest() for n in changed},
    }
    (target / 'release.json').write_text(json.dumps(metadata, indent=2) + '\n')

    # Install using ReleaseManager
    sys.path.insert(0, str(SOURCE))
    from orchestration.release_manager import ReleaseManager
    rel_name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-composio-integrations'
    rm = ReleaseManager(root_dir=runtime)
    activated = rm.install_prepared_release(
        target,
        rel_name,
        expected_current=parent,
        timeout=40,
        expected_hashes=metadata['composio_extension']['sha256'],
    )
    print(f"Activated release: {activated}")

    # Restart jarvis-voice service
    print("Restarting jarvis-voice.service...")
    subprocess.run(['systemctl', '--user', 'restart', 'jarvis-voice.service'], check=True)
    print("jarvis-voice.service restarted successfully.")


if __name__ == '__main__':
    deploy()
