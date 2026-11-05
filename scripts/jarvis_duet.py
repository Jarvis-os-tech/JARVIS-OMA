#!/usr/bin/env python3
"""JARVIS OS - OpenDuet Sovereign Coworker Controller & Bridge.

Provides status inspection, service control, and health monitoring
for the de-copilotized local OpenDuet stack.
"""

import argparse
import json
import subprocess
import sys
import urllib.request
import urllib.error

API_BASE = "http://localhost:3001"
APP_URL = "http://localhost:3010"
MOCK_BASE = "http://localhost:3009"


def check_endpoint(url: str, timeout: float = 2.0) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS-OS/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                body = resp.read().decode("utf-8")
                try:
                    return json.loads(body)
                except json.JSONDecodeError:
                    return {"raw": body[:200]}
    except Exception:
        return None


def show_status() -> None:
    print("==================================================")
    print("     JARVIS OS - OpenDuet Sovereign Coworker      ")
    print("==================================================")

    # Check Web UI
    app_status = check_endpoint(APP_URL)
    app_icon = "🟢 UP" if app_status is not None else "🔴 DOWN"
    print(f"Web UI:          {APP_URL:<26} [{app_icon}]")

    # Check Core API Server
    api_status = check_endpoint(f"{API_BASE}/health")
    api_icon = "🟢 UP" if api_status is not None else "🔴 DOWN"
    print(f"Core Server:     {API_BASE:<26} [{api_icon}]")

    # Check License / Info
    info = check_endpoint(f"{API_BASE}/api/copilotkit/info")
    if info:
        license_status = info.get("licenseStatus", "unknown")
        mode = info.get("mode", "unknown")
        bots = list(info.get("agents", {}).keys())
        print(f"License Status:  {license_status} (Mode: {mode})")
        print(f"Available Bots:  {', '.join(bots)}")
    else:
        print("License Status:  N/A")

    # Check Capabilities
    caps = check_endpoint(f"{API_BASE}/api/capabilities")
    if caps:
        print(f"Single-User:     {caps.get('localEvaluation', False)} (Zero OAuth)")
        print(f"Generative UI:   {caps.get('generativeUi', False)}")

    # Check Mock Server
    mock_status = check_endpoint(f"{MOCK_BASE}/health")
    mock_icon = "🟢 UP" if mock_status is not None else "🔴 DOWN"
    print(f"Intelligence:    {MOCK_BASE:<26} [{mock_icon}] (Sovereign Local)")

    # Systemd Service Status
    print("\n--- systemd status ---")
    res = subprocess.run(
        ["systemctl", "--user", "is-active", "jarvis-duet.service"],
        capture_output=True,
        text=True,
    )
    print(f"Service Unit:    jarvis-duet.service [{res.stdout.strip()}]")
    print("==================================================")


def main() -> None:
    parser = argparse.ArgumentParser(description="JARVIS OpenDuet Controller")
    parser.add_argument("action", choices=["status", "start", "stop", "restart", "logs"], default="status", nargs="?")
    args = parser.parse_args()

    if args.action == "status":
        show_status()
    elif args.action == "start":
        print("Starting jarvis-duet.service...")
        subprocess.run(["systemctl", "--user", "start", "jarvis-duet.service"], check=True)
        show_status()
    elif args.action == "stop":
        print("Stopping jarvis-duet.service...")
        subprocess.run(["systemctl", "--user", "stop", "jarvis-duet.service"], check=True)
        print("Stopped.")
    elif args.action == "restart":
        print("Restarting jarvis-duet.service...")
        subprocess.run(["systemctl", "--user", "restart", "jarvis-duet.service"], check=True)
        show_status()
    elif args.action == "logs":
        subprocess.run(["journalctl", "--user", "-u", "jarvis-duet.service", "-n", "30", "--no-pager"])


if __name__ == "__main__":
    main()
