"""Prepare only the widget additions over the active release; activation is explicit."""
from __future__ import annotations
import argparse
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


def replace_once(body, old, new):
    if body.count(old) != 1:
        raise RuntimeError("Installed source differs at a widget integration point; no activation attempted")
    return body.replace(old, new, 1)


def prepare(destination):
    runtime = Path.home() / ".local/share/jarvis-runtime"
    parent = (runtime / "current").resolve(strict=True)
    if not parent.is_relative_to(runtime / "releases"):
        raise RuntimeError("Active runtime is not a managed release")
    destination = Path(destination)
    target = Path(tempfile.mkdtemp(prefix="jarvis-widgets-release-", dir=destination))
    shutil.copytree(parent, target, symlinks=True, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    changed = []

    def write(relative, content):
        path = target / relative
        if path.is_symlink():
            raise RuntimeError("Refusing to write through a release symlink: " + relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists(): path.chmod(0o600)
        path.write_text(content)
        changed.append(relative)

    relative = "skills/skills.py"
    body = (target / relative).read_text()
    addition = "from skills.domains.widgets import WidgetsDomain, ADAPTERS as WIDGET_ADAPTERS, ADAPTER_COMMANDS as WIDGET_COMMANDS\n"
    body = replace_once(body, "from orchestration.tool_tiers import CORE_TOOLS", addition + "from orchestration.tool_tiers import CORE_TOOLS")
    body = replace_once(body, "class DesktopSkills(WorkspaceDomain, GithubDomain, OrchestrationDomain, ComposioDomain, ApiAnythingDomain):",
                        "class DesktopSkills(WorkspaceDomain, GithubDomain, OrchestrationDomain, ComposioDomain, ApiAnythingDomain, WidgetsDomain):")
    body = replace_once(body, "        **API_ANYTHING_ADAPTERS,", "        **API_ANYTHING_ADAPTERS,\n        **WIDGET_ADAPTERS,")
    body = replace_once(body, "        **API_ANYTHING_COMMANDS,", "        **API_ANYTHING_COMMANDS,\n        **WIDGET_COMMANDS,")
    # Copy only the two edited input handlers, not unrelated working-tree changes.
    local = (SOURCE / relative).read_text()
    for name, next_name in (("_adapter_open_input_bar", "_adapter_close_input_bar"),
                            ("_adapter_close_input_bar", None)):
        start = "    async def " + name + "(self):"
        source_start, target_start = local.index(start), body.index(start)
        if next_name:
            source_end = local.index("    async def " + next_name, source_start + 1)
            target_end = body.index("    async def " + next_name, target_start + 1)
        else:
            source_end = local.find("\n    async def ", source_start + len(start))
            target_end = body.find("\n    async def ", target_start + len(start))
            if source_end < 0 or target_end < 0:
                raise RuntimeError("Input handler boundary not found")
        body = body[:target_start] + local[source_start:source_end] + body[target_end:]
    write(relative, body)
    relative = "orchestration/tool_tiers.py"
    body = (target / relative).read_text()
    body = replace_once(body, "'cancel_task', 'open_input_bar', 'close_input_bar',",
                        "'cancel_task', 'open_input_bar', 'close_input_bar', 'show_widget', 'manage_canvas', 'manage_widget', 'widget_schema',")
    write(relative, body)
    relative = "bin/jarvis"
    body = (target / relative).read_text()
    body = replace_once(body, "  jarvis control [cmd]", "  jarvis widgets [cmd] Canvas, QR, PiP and input widgets in the existing shell\n  jarvis control [cmd]")
    body = replace_once(body, 'case "$cmd" in', 'case "$cmd" in\n    widgets)\n        shift || true\n        exec "${SCRIPT_DIR}/bin/jarvis-widgets" "$@"\n        ;;')
    write(relative, body)
    (target / relative).chmod(0o755)
    for relative in ("skills/domains/widgets.py", "skill_manifests/widgets.json", "ui/jarvis_widgets/backend.py", "ui/jarvis_widgets/view_schema.py", "bin/jarvis-widgets"):
        write(relative, (SOURCE / relative).read_text())
    (target / "bin/jarvis-widgets").chmod(0o755)
    env = dict(os.environ, PYTHONPATH=str(target), PYTHONDONTWRITEBYTECODE="1")
    check = (
        "from pathlib import Path; from skills.skills import DesktopSkills; "
        "from orchestration.tool_tiers import CORE_TOOLS; "
        "r=DesktopSkills.__new__(DesktopSkills); r.manifest_dirs=[Path('skill_manifests')]; "
        "s=r._load_manifests(); assert {'show_widget','manage_canvas','manage_widget'}<=set(s); "
        "assert {'show_widget','manage_canvas'}<=CORE_TOOLS; print('Widget adapters validated')"
    )
    subprocess.run([str(runtime / "venv/bin/python"), "-c", check], cwd=target, env=env,
                   timeout=30, check=True)
    metadata = json.loads((target / "release.json").read_text())
    metadata["widget_extension"] = {"parent": str(parent), "created_at": datetime.now(timezone.utc).isoformat(),
                                    "sha256": {name: hashlib.sha256((target / name).read_bytes()).hexdigest() for name in changed}}
    write("release.json", json.dumps(metadata, indent=2) + "\n")
    return target, parent


def activate(staged):
    staged = Path(staged).resolve(strict=True)
    metadata = json.loads((staged / "release.json").read_text())
    extension = metadata["widget_extension"]
    runtime = Path.home() / ".local/share/jarvis-runtime"
    parent = Path(extension["parent"])
    if (runtime / "current").resolve() != parent:
        raise RuntimeError("Active release changed; prepare again")
    for name, digest in extension["sha256"].items():
        if hashlib.sha256((staged / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError("Staged file changed: " + name)
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-existing-shell-widgets"
    sys.path.insert(0, str(SOURCE))
    from orchestration.release_manager import ReleaseManager
    manager = ReleaseManager(root_dir=runtime)
    # No data migration is involved; retain all prior releases and use the
    # manager's atomic pointers and automatic service-health rollback.
    target = manager.install_prepared_release(staged, name, expected_current=parent,
                                             timeout=20, expected_hashes=extension["sha256"])
    print(json.dumps({"activated": str(target), "previous": str(parent)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", type=Path, help="Writable directory for a checked staging copy")
    parser.add_argument("--activate", type=Path, help="Explicitly activate a previously prepared staging copy")
    args = parser.parse_args()
    if args.prepare:
        target, parent = prepare(args.prepare)
        print(json.dumps({"prepared": str(target), "parent": str(parent)}))
    elif args.activate:
        activate(args.activate)
    else:
        parser.error("Choose --prepare or --activate")


if __name__ == "__main__": main()
