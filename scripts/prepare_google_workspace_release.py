"""Stage the tested Google Workspace department over the active runtime."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from prepare_system_integration_release import RUNTIME, SOURCE, activate, splice


def prepare() -> Path:
    parent = (RUNTIME / "current").resolve(strict=True)
    if not parent.is_relative_to(RUNTIME / "releases"):
        raise ValueError("Unmanaged current release")
    target = Path(tempfile.mkdtemp(prefix="jarvis-google-workspace-", dir="/tmp"))
    subprocess.run(["cp", "--archive", "--reflink=auto", str(parent) + "/.", str(target)], check=True)
    hashes = {}

    def put(relative: str, content: str) -> None:
        destination = target / relative
        if destination.is_symlink():
            raise ValueError("Linked target " + relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            destination.chmod(destination.stat().st_mode | 0o200)
        if relative.endswith(".py"):
            compile(content, relative, "exec")
        destination.write_text(content, encoding="utf-8")
        hashes[relative] = hashlib.sha256(destination.read_bytes()).hexdigest()

    for relative in (
        "departments/google_workspace/__init__.py",
        "departments/google_workspace/agents.py",
        "departments/google_workspace/department.py",
        "skills/domains/workspace.py",
    ):
        put(relative, (SOURCE / relative).read_text(encoding="utf-8"))

    for relative, names in (
        ("skills/domains/orchestration.py", ["OrchestrationDomain._adapter_list_system_agents"]),
        ("voice_layer/persona.py", ["system_persona"]),
    ):
        put(relative, splice(
            (target / relative).read_text(encoding="utf-8"),
            (SOURCE / relative).read_text(encoding="utf-8"),
            names,
        ))

    metadata = json.loads((target / "release.json").read_text(encoding="utf-8"))
    extension = {
        "parent": str(parent),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sha256": hashes,
    }
    metadata["google_workspace_department"] = extension
    metadata["system_integration_extension"] = extension
    put("release.json", json.dumps(metadata, indent=2) + "\n")

    check = """
import asyncio
from skills.skills import DesktopSkills
async def main():
    skills = DesktopSkills()
    try:
        result = await skills.execute('list_system_agents', {})
        names = {agent['name'] for agent in result['agents'] if agent.get('department') == 'Google Workspace'}
        assert names == {'Gmail Agent', 'Calendar Agent', 'Tasks Agent', 'Drive Agent', 'Docs Agent', 'Sheets Agent'}
        print('Packaged Google Workspace department check passed')
    finally:
        await skills.close_agent_jobs()
asyncio.run(main())
"""
    subprocess.run(
        [str(RUNTIME / "venv/bin/python"), "-c", check],
        cwd=target,
        env=dict(os.environ, PYTHONPATH=str(target), PYTHONDONTWRITEBYTECODE="1"),
        check=True,
        timeout=30,
    )
    return target


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare", action="store_true")
    group.add_argument("--activate", type=Path)
    arguments = parser.parse_args()
    if arguments.prepare:
        print(json.dumps({"prepared": str(prepare())}))
    else:
        activate(arguments.activate)
