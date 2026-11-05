"""Required deterministic behavior contracts. Also serves as a pytest plugin.

Run: python scripts/behavior_gate.py --report /tmp/jarvis-behavior.json
No OVOS runtime is imported; its named-contract and observed-event approach is
adapted to JARVIS's own adapters and receipts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "tests/behavior/contracts.json"


def source_digest():
    """Fingerprint covered source and test inputs, excluding collected upstreams."""
    digest = hashlib.sha256()
    directories = ('core', 'connectors', 'jarvis_control', 'jarvis_memory', 'jarvis_voice',
                   'voice_layer', 'orchestration', 'skills', 'ui', 'scripts',
                   'skill_manifests', 'configs', 'contracts', 'tests')
    paths = [path for directory in directories for path in (ROOT / directory).rglob('*')
             if path.is_file() and '__pycache__' not in path.parts
             and path.suffix in {'.py', '.json', '.toml', '.qml', '.html', '.js'}]
    paths.extend(ROOT.glob('requirements*.txt'))
    for path in sorted(paths):
        digest.update(str(path.relative_to(ROOT)).encode() + b'\0')
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def load_contract(path=CONTRACT):
    value = json.loads(Path(path).read_text())
    cases = value["cases"]
    if value.get("schema_version") != 1 or not cases:
        raise ValueError("Missing or unsupported behavior contracts")
    ids, selectors = set(), set()
    for case in cases:
        if not case["id"] or case["id"] in ids or not case["expectation"]:
            raise ValueError("Invalid or duplicate contract ID")
        ids.add(case["id"])
        if not case["tests"]:
            raise ValueError("Contract has no tests: " + case["id"])
        for node in case["tests"]:
            file = node.split("::")[0]
            if not file.startswith("tests/") or ".." in Path(file).parts or "::" not in node or node in selectors:
                raise ValueError("Invalid or duplicate test selector: " + node)
            selectors.add(node)
    return cases


def selector_for(nodeid, selectors):
    return next((node for node in selectors if nodeid == node or nodeid.startswith(node + "[")), None)


class BehaviorResults:
    def __init__(self, cases, report):
        self.cases, self.report = cases, Path(report)
        self.selectors = [node for case in cases for node in case["tests"]]
        self.collected, self.events = [], []
        self.started = time.monotonic()

    def pytest_collection_finish(self, session):
        self.collected = [item.nodeid for item in session.items]

    def pytest_runtest_logreport(self, report):
        self.events.append({"nodeid": report.nodeid, "phase": report.when,
                            "outcome": report.outcome,
                            "expected_failure": hasattr(report, "wasxfail")})

    def pytest_sessionfinish(self, session, exitstatus):
        results = []
        for case in self.cases:
            nodes = [node for node in self.collected if selector_for(node, case["tests"])]
            missing = [node for node in case["tests"] if not any(selector_for(n, [node]) for n in nodes)]
            failures = []
            for node in nodes:
                events = [event for event in self.events if event["nodeid"] == node]
                if ({e["phase"] for e in events} != {"setup", "call", "teardown"}
                        or any(e["outcome"] != "passed" or e["expected_failure"] for e in events)):
                    failures.append(node)
            results.append({"id": case["id"], "expectation": case["expectation"],
                            "passed": bool(nodes) and not missing and not failures,
                            "tests": nodes, "missing": missing, "failed_or_incomplete": failures})
        passed = int(exitstatus) == 0 and all(case["passed"] for case in results)
        if not passed and int(exitstatus) == 0:
            session.exitstatus = 1
        payload = {"schema_version": 1, "passed": passed, "pytest_exit_code": int(session.exitstatus),
                   "duration_seconds": round(time.monotonic() - self.started, 3),
                   "collected_tests": len(self.collected), "cases": results,
                   "scope": "Deterministic local contracts; not live desktop or cloud acceptance"}
        self.report.parent.mkdir(parents=True, exist_ok=True)
        self.report.write_text(json.dumps(payload, indent=2) + "\n")


def pytest_addoption(parser):
    parser.addoption("--behavior-report")


def pytest_configure(config):
    report = config.getoption("--behavior-report")
    if report:
        config.pluginmanager.register(BehaviorResults(load_contract(), report), "behavior-results")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path("/tmp/jarvis-behavior-gate.json"))
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)
    report = args.report.resolve()
    started = time.monotonic()
    try:
        cases = load_contract()
        before = source_digest()
        selectors = [node for case in cases for node in case["tests"]]
        # Avoid credentials, user configurations and automatic third-party pytest plugins.
        with tempfile.TemporaryDirectory(prefix="jarvis-behavior-") as directory:
            home = Path(directory)
            env = {key: value for key, value in os.environ.items()
                   if key in {"PATH", "LANG", "LC_ALL", "SYSTEMROOT", "VIRTUAL_ENV"}}
            env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / "config"),
                       XDG_DATA_HOME=str(home / "data"), XDG_CACHE_HOME=str(home / "cache"),
                       XDG_RUNTIME_DIR=str(home), PYTHONPATH=str(ROOT),
                       PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", OMP_NUM_THREADS="1")
            temporary_report = home / "result.json"
            command = [sys.executable, "-m", "pytest", "-q", "-o", "addopts=--import-mode=importlib",
                       "-p", "pytest_asyncio.plugin", "-p", "scripts.behavior_gate",
                       "--behavior-report", str(temporary_report), *selectors]
            result = subprocess.run(command, cwd=ROOT, env=env, timeout=args.timeout, check=False)
            payload = json.loads(temporary_report.read_text())
            payload["source_sha256"] = before
            payload["source_unchanged"] = before == source_digest()
            payload["passed"] = payload["passed"] and result.returncode == 0 and payload["source_unchanged"]
            payload["contract_sha256"] = hashlib.sha256(CONTRACT.read_bytes()).hexdigest()
            code = 0 if payload["passed"] else 1
    except (ValueError, KeyError, OSError, subprocess.TimeoutExpired) as error:
        payload = {"schema_version": 1, "passed": False, "error": str(error),
                   "duration_seconds": round(time.monotonic() - started, 3)}
        code = 1
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Behavior gate {'PASS' if code == 0 else 'FAIL'} — {report}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
