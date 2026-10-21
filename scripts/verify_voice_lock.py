#!/usr/bin/env python3
"""Voice Core Integrity Verifier & Pre-Commit Validator.

Enforces cryptographic lock on JARVIS-OMA core voice features to prevent
accidental or unauthorized edits by agents or developers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def get_repo_root() -> Path:
    current = Path(__file__).resolve().parent
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists() or (candidate / "audio/.voice_lock.json").exists():
            return candidate
    return Path.cwd()


def load_manifest(repo_root: Path) -> dict:
    manifest_path = repo_root / "audio/.voice_lock.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Voice lock manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def verify_file_hashes(repo_root: Path, manifest: dict) -> list[str]:
    violations: list[str] = []
    locked_files = manifest.get("locked_files", {})
    for rel_path, meta in locked_files.items():
        file_path = repo_root / rel_path
        if not file_path.is_file():
            violations.append(f"MISSING: Locked file {rel_path} does not exist.")
            continue
        actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
        expected_hash = meta.get("sha256")
        if actual_hash != expected_hash:
            violations.append(
                f"MODIFIED: Locked file {rel_path} checksum mismatch!\n"
                f"  Expected: {expected_hash}\n"
                f"  Actual:   {actual_hash}"
            )
    return violations


def verify_git_diff(repo_root: Path, manifest: dict) -> list[str]:
    violations: list[str] = []
    locked_files = set(manifest.get("locked_files", {}).keys())
    try:
        cmd = ["git", "diff", "--name-only", "HEAD"]
        res = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
        if res.returncode == 0:
            changed = [line.strip() for line in res.stdout.splitlines() if line.strip()]
            for path in changed:
                if path in locked_files:
                    violations.append(f"GIT_DIFF: Working tree has uncommitted modifications to locked file: {path}")

        cmd_cached = ["git", "diff", "--cached", "--name-only"]
        res_cached = subprocess.run(cmd_cached, cwd=repo_root, capture_output=True, text=True)
        if res_cached.returncode == 0:
            staged = [line.strip() for line in res_cached.stdout.splitlines() if line.strip()]
            for path in staged:
                if path in locked_files:
                    violations.append(f"GIT_STAGED: Index has staged changes to locked file: {path}")
    except (OSError, subprocess.SubprocessError):
        pass
    return violations


def install_pre_commit_hook(repo_root: Path) -> int:
    hooks_dir = repo_root / ".git" / "hooks"
    if not hooks_dir.is_dir():
        print(f"Error: Git hooks directory not found at {hooks_dir}", file=sys.stderr)
        return 1
    hook_file = hooks_dir / "pre-commit"
    hook_script = (
        "#!/usr/bin/env bash\n"
        "# JARVIS-OMA voice core integrity guard\n"
        "python3 scripts/verify_voice_lock.py || exit 1\n"
    )
    hook_file.write_text(hook_script, encoding="utf-8")
    hook_file.chmod(0o755)
    print(f"Pre-commit hook successfully installed to {hook_file}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify integrity of locked voice core files.")
    parser.add_argument("--install-hook", action="store_true", help="Install as git pre-commit hook")
    parser.add_argument("--ignore-git", action="store_true", help="Only verify disk checksums, ignore git diff")
    args = parser.parse_args(argv)

    repo_root = get_repo_root()

    if args.install_hook:
        return install_pre_commit_hook(repo_root)

    try:
        manifest = load_manifest(repo_root)
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1

    violations = verify_file_hashes(repo_root, manifest)

    if not args.ignore_git:
        violations.extend(verify_git_diff(repo_root, manifest))

    if violations:
        print("=" * 70, file=sys.stderr)
        print("VOICE CORE LOCK VIOLATION DETECTED!", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        for v in violations:
            print(f"- {v}", file=sys.stderr)
        print("\nExisting voice core code is locked. Implement new features in", file=sys.stderr)
        print("audio/extension.py or separate modules without modifying locked files.", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        return 1

    print("Voice core lock verified: all 7 core files are intact and unmodified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
