"""Verify downloaded references without importing or executing upstream code.

Run from any directory. Prints JSON; does not install packages or write state.
"""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parent
PINS = {
    "ovos-number-parser": "8e527673eb0e0aae9776d33e38e05bc32fdd7dbb",
    "ovos-date-parser": "2c24a781d1869b05d96c6aca43847a08025f8b59",
    "ovos-color-parser": "34ae1cc3fdf3294f89547ddcbd1dbe89796ae292",
    "ovos-typed-slots-transformer": "f1154b9644ecc09aa6d26a01572c8ff471215377",
    "ovos-plugin-manager": "1cc719779d5f6bcbfb1f8d01243e4b47156ad45e",
    "ovos-pydantic-models": "ba2613757b7ef7bdb95290f62a5dbdad9ac1b8fa",
    "ovos-dinkum-listener": "fa93e250961666098fca915c45f3cd5d07660f18",
    "ovoscope": "80dd49b9639bcc776e8238d05a8ab45e228655e7",
    "ovos-test-harness": "b752659c25b2637f57095fa5a585a2a0c588550c",
    "ovos-eot-plugin-cuelight": "200fb4c38224ff87a6d87a4bc0b5fda844d82ada",
    "ovos-utterance-corrections-plugin": "b014118888886162527ec9b97bd2c947a9fc6a4b",
    "ovos-a2a-agent-plugin": "43ad75ad40e67fdd742f2e5a0d557e0e6ac2ca82",
}


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args], timeout=30
    ).decode("utf-8")


def main():
    report = {"review_date": "2026-11-03", "scope": "static collection verification",
              "runtime_tested": False, "repositories": [], "errors": []}
    inventory = []
    inventory_hashes = {}
    for path in sorted((ROOT / "inventory").glob("*.json")):
        raw = path.read_bytes()
        entries = json.loads(raw)
        if not isinstance(entries, list):
            raise ValueError(f"Invalid inventory: {path.name}")
        inventory.extend(entries)
        inventory_hashes[path.name] = hashlib.sha256(raw).hexdigest()
    grouped = {}
    for item in inventory:
        grouped.setdefault(item["owner"]["login"], set()).add(item["full_name"])
    report["inventory_counts"] = {owner: len(names) for owner, names in grouped.items()}
    report["inventory_sha256"] = inventory_hashes

    for name, expected in PINS.items():
        root = ROOT / name
        head = git(root, "rev-parse", "HEAD").strip()
        origin = git(root, "remote", "get-url", "origin").strip()
        clean = not git(root, "status", "--porcelain", "--untracked-files=all").strip()
        license_bytes = (root / "LICENSE").read_bytes()
        files = sorted(filter(None, git(root, "ls-files", "-z").split("\0")))
        digest = hashlib.sha256()
        python_files = 0
        for relative in files:
            path = root / relative
            if path.is_symlink() or not path.is_file():
                report["errors"].append(f"{name}/{relative}: not a regular file")
                continue
            data = path.read_bytes()
            digest.update(relative.encode() + b"\0" + hashlib.sha256(data).digest())
            if path.suffix == ".py":
                python_files += 1
                try:
                    ast.parse(data, filename=f"{name}/{relative}")
                except SyntaxError as error:
                    report["errors"].append(f"{name}/{relative}: {error.msg}")
        project_path = root / "pyproject.toml"
        project = (tomllib.loads(project_path.read_text()).get("project", {})
                   if project_path.exists() else {})
        if head != expected or not clean or b"Apache License" not in license_bytes:
            report["errors"].append(f"{name}: pin, cleanliness or license mismatch")
        report["repositories"].append({
            "name": name, "origin": origin, "commit": head,
            "license": "Apache-2.0", "license_sha256": hashlib.sha256(license_bytes).hexdigest(),
            "clean": clean, "tracked_files": len(files), "python_files_parsed": python_files,
            "tracked_content_sha256": digest.hexdigest(),
            "requires_python": project.get("requires-python"),
            "declared_dependencies": project.get("dependencies", []),
            "dynamic_fields": project.get("dynamic", []),
        })
    report["passed"] = not report["errors"] and report["inventory_counts"] == {
        "OpenVoiceOS": 391, "huwprosser": 40}
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
