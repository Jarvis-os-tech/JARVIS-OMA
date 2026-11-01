#!/usr/bin/env python3
"""JARVIS OS System Monitor CLI & Daemon.

Checks network connectivity, server status, hardware vitals, and systemd services,
playing distinct procedurally synthesized audio alerts and emitting desktop notifications.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import sys
import time
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.system_monitor import (
    AlertAction,
    AlertAudioEngine,
    AlertStateManager,
    DesktopNotifier,
    JarvisVoiceSpeaker,
    NetworkProbe,
    ProbeResult,
    ResourceProbe,
    ServerProbe,
    ServiceProbe,
    SUPPORTED_ALERTS,
    format_alert_speech,
)

# ANSI terminal formatting
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_CYAN = "\033[36m"
C_GRAY = "\033[90m"

DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "monitoring.json"


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    target_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if target_path.exists():
        try:
            with target_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as err:
            print(f"{C_YELLOW}[!] Warning: Failed to read config {target_path}: {err}. Using defaults.{C_RESET}", file=sys.stderr)

    return {
        "network": {
            "check_gateway": True,
            "dns_targets": ["cloudflare.com", "google.com", "1.1.1.1"],
            "wan_urls": [
                "http://connectivitycheck.gstatic.com/generate_204",
                "https://1.1.1.1",
            ],
        },
        "servers": {
            "tcp": [],
            "http": [
                {
                    "url": "https://cloudflare.com",
                    "name": "Cloudflare Edge",
                    "expected_codes": [200, 301, 302],
                }
            ],
        },
        "resources": {
            "cpu_threshold_percent": 90.0,
            "memory_threshold_percent": 90.0,
            "disk_threshold_percent": 90.0,
            "disks": ["/"],
            "thermal_threshold_celsius": 85.0,
        },
        "services": {
            "user": ["pipewire.service", "wireplumber.service"],
            "system": [],
        },
        "alerts": {
            "cooldown_seconds": 300,
            "enable_audio": True,
            "enable_desktop_notifications": True,
        },
    }


def run_checks(config: Dict[str, Any]) -> List[ProbeResult]:
    results: List[ProbeResult] = []

    # 1. Network checks
    net_cfg = config.get("network", {})
    net_probe = NetworkProbe(
        dns_targets=net_cfg.get("dns_targets"),
        wan_urls=net_cfg.get("wan_urls"),
    )
    if net_cfg.get("check_gateway", True):
        results.append(net_probe.check_gateway())
    results.append(net_probe.check_dns())
    if net_cfg.get("wan_urls"):
        results.append(net_probe.check_wan_http())

    # 2. Server checks
    srv_cfg = config.get("servers", {})
    srv_probe = ServerProbe()
    for tcp_srv in srv_cfg.get("tcp", []):
        host = tcp_srv.get("host", "127.0.0.1")
        port = tcp_srv.get("port", 80)
        timeout = float(tcp_srv.get("timeout", 2.0))
        results.append(srv_probe.check_tcp(host, port, timeout=timeout))

    for http_srv in srv_cfg.get("http", []):
        url = http_srv.get("url", "")
        if url:
            codes = http_srv.get("expected_codes", [200, 204, 301, 302])
            timeout = float(http_srv.get("timeout", 3.0))
            results.append(srv_probe.check_http(url, expected_codes=codes, timeout=timeout))

    # 3. Host resource checks
    res_cfg = config.get("resources", {})
    res_probe = ResourceProbe()
    results.append(res_probe.check_cpu(threshold_percent=float(res_cfg.get("cpu_threshold_percent", 90.0))))
    results.append(res_probe.check_memory(threshold_percent=float(res_cfg.get("memory_threshold_percent", 90.0))))

    for mount in res_cfg.get("disks", ["/"]):
        results.append(res_probe.check_disk(mount_point=mount, threshold_percent=float(res_cfg.get("disk_threshold_percent", 90.0))))

    thermal_results = res_probe.check_thermals(threshold_celsius=float(res_cfg.get("thermal_threshold_celsius", 85.0)))
    results.extend(thermal_results)

    # 4. Service checks
    svc_cfg = config.get("services", {})
    svc_probe = ServiceProbe()
    for svc in svc_cfg.get("user", []):
        results.append(svc_probe.check_service(svc, user_scope=True))
    for svc in svc_cfg.get("system", []):
        results.append(svc_probe.check_service(svc, user_scope=False))

    return results


def print_formatted_report(
    results: List[ProbeResult],
    actions: List[AlertAction],
    voice_connected: bool = False,
) -> None:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    voice_badge = f"{C_GREEN}CONNECTED{C_RESET}" if voice_connected else f"{C_YELLOW}OFFLINE{C_RESET}"

    print(f"\n{C_BOLD}{C_CYAN}═════════════════════════════════════════════════════════════════════════════════════{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}  JARVIS OS — SYSTEM INTEGRITY & HEALTH MONITOR [{now_str}]  {C_RESET}")
    print(f"{C_BOLD}{C_CYAN}  Voice Alerts: {voice_badge} (Announcements spoken by JARVIS)  {C_RESET}")
    print(f"{C_BOLD}{C_CYAN}═════════════════════════════════════════════════════════════════════════════════════{C_RESET}")

    current_cat = ""
    for res in results:
        if res.category != current_cat:
            current_cat = res.category
            print(f"\n  {C_BOLD}▶ {current_cat.upper()} INTEGRITY:{C_RESET}")

        if res.status == "OK":
            badge = f"{C_GREEN}[  OK  ]{C_RESET}"
        elif res.status == "WARN":
            badge = f"{C_YELLOW}[ WARN ]{C_RESET}"
        else:
            badge = f"{C_RED}[ FAIL ]{C_RESET}"

        print(f"    {badge} {res.name:<32} {C_GRAY}│{C_RESET} {res.message}")

    print(f"\n{C_GRAY}─────────────────────────────────────────────────────────────────────────────────────{C_RESET}")
    critical_count = sum(1 for r in results if r.status == "CRITICAL")
    warn_count = sum(1 for r in results if r.status == "WARN")
    ok_count = sum(1 for r in results if r.status == "OK")

    summary_color = C_GREEN if critical_count == 0 else C_RED
    print(f"  {C_BOLD}Status Summary:{C_RESET} {summary_color}{ok_count} OK, {warn_count} Warning, {critical_count} Critical{C_RESET}")

    if actions:
        print(f"\n  {C_BOLD}Dispatched Alerts & Vocalizations:{C_RESET}")
        for act in actions:
            act_color = C_RED if act.action_type == "ALERT" else C_GREEN
            speech = format_alert_speech(act)
            print(f"    • {act_color}{act.action_type}{C_RESET}: {act.name}")
            print(f"      {C_CYAN}JARVIS Spoken Announcement:{C_RESET} \"{speech}\"")

    print(f"{C_BOLD}{C_CYAN}═════════════════════════════════════════════════════════════════════════════════════{C_RESET}\n")


def test_voice_mode(jarvis_speaker: JarvisVoiceSpeaker) -> bool:
    print(f"\n{C_BOLD}{C_CYAN}Testing JARVIS Voice Announcement System...{C_RESET}")
    if not jarvis_speaker.is_available():
        print(f"{C_RED}[!] JARVIS Voice Core is not reachable at {jarvis_speaker.socket_path}.{C_RESET}")
        print(f"    Start the service with: {C_BOLD}systemctl --user start jarvis-voice.service{C_RESET}\n")
        return False

    sample_alert = (
        "This is JARVIS. All system diagnostics are complete, and your system monitoring "
        "alert intimation pipeline is functioning properly."
    )
    print(f"  • Sending alert to JARVIS voice pipeline: {C_CYAN}\"{sample_alert}\"{C_RESET}")
    ok = jarvis_speaker.speak_alert(sample_alert)
    if ok:
        print(f"{C_GREEN}[✓] Spoken alert successfully delivered to JARVIS Voice Core.{C_RESET}\n")
        return True
    else:
        print(f"{C_RED}[!] Failed to deliver spoken alert to JARVIS Voice.{C_RESET}\n")
        return False



def test_audio_mode(audio_engine: AlertAudioEngine, quiet: bool = False) -> None:
    player = audio_engine.detect_player()
    player_name = " ".join(player) if player else "None detected"

    print(f"\n{C_BOLD}{C_CYAN}Testing alert sounds ({player_name}):{C_RESET}\n")
    for alert_name, description in SUPPORTED_ALERTS.items():
        print(f"  • {C_BOLD}{alert_name:<18}{C_RESET} -> {description}")
        if not quiet:
            wav_path = audio_engine.synthesize_alert_wav(alert_name)
            audio_engine.play_alert(alert_name, async_play=False)
            time.sleep(0.35)
    print(f"\n{C_GREEN}All {len(SUPPORTED_ALERTS)} alert sounds synthesized and tested successfully.{C_RESET}\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Comprehensive system monitoring script with verbal JARVIS announcements and audio alerts.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Perform a single diagnostic check sweep and exit.",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run continuously as a monitoring daemon.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=15.0,
        help="Check interval in seconds for daemon mode (default: 15.0).",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to custom JSON configuration file.",
    )
    parser.add_argument(
        "--test-voice",
        action="store_true",
        help="Test verbal alert announcement through JARVIS Voice Core.",
    )
    parser.add_argument(
        "--test-audio",
        action="store_true",
        help="Preview and test all synthesized sound effects.",
    )
    parser.add_argument(
        "--no-voice",
        action="store_true",
        help="Disable spoken voice announcements from JARVIS.",
    )
    parser.add_argument(
        "--sound",
        action="store_true",
        help="Enable secondary sound effects in addition to JARVIS voice.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output check results in JSON format.",
    )
    parser.add_argument(
        "--quiet-audio",
        action="store_true",
        help="Mute all audio (voice announcements and sound effects).",
    )
    parser.add_argument(
        "--quiet-notify",
        action="store_true",
        help="Suppress desktop notifications.",
    )

    args = parser.parse_args()

    audio_engine = AlertAudioEngine()
    notifier = DesktopNotifier()
    jarvis_speaker = JarvisVoiceSpeaker()

    if args.test_voice:
        ok = test_voice_mode(jarvis_speaker)
        return 0 if ok else 1

    if args.test_audio:
        test_audio_mode(audio_engine, quiet=args.quiet_audio)
        return 0

    config = load_config(args.config)
    cooldown = float(config.get("alerts", {}).get("cooldown_seconds", 300))
    state_manager = AlertStateManager(cooldown_seconds=cooldown)

    enable_voice = (not args.no_voice) and (not args.quiet_audio) and config.get("alerts", {}).get("enable_voice", True)
    enable_sound = args.sound or (not args.quiet_audio and config.get("alerts", {}).get("enable_sound_effects", False))
    enable_notify = not args.quiet_notify and config.get("alerts", {}).get("enable_desktop_notifications", True)

    # Daemon loop handling
    running = True

    def handle_signal(sig, frame):
        nonlocal running
        running = False
        print(f"\n{C_YELLOW}[!] Shutting down system monitor gracefully...{C_RESET}")

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # If neither --daemon nor --once is explicitly passed, default to --once
    is_daemon = args.daemon

    while running:
        results = run_checks(config)
        actions = state_manager.process_results(results)

        # Dispatch alerts to JARVIS voice, notifications, and audio
        state_manager.dispatch_actions(
            actions,
            audio_engine=audio_engine,
            notifier=notifier,
            jarvis_speaker=jarvis_speaker,
            voice_alert=enable_voice,
            sound_alert=enable_sound,
            desktop_notify=enable_notify,
        )

        if args.json:
            critical_count = sum(1 for r in results if r.status == "CRITICAL")
            warn_count = sum(1 for r in results if r.status == "WARN")
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": {
                    "total": len(results),
                    "ok": sum(1 for r in results if r.status == "OK"),
                    "warn": warn_count,
                    "critical": critical_count,
                    "status": "healthy" if critical_count == 0 else "unhealthy",
                },
                "jarvis_voice_connected": jarvis_speaker.is_available(),
                "results": [
                    {
                        "name": r.name,
                        "category": r.category,
                        "status": r.status,
                        "message": r.message,
                        "metrics": r.metrics,
                        "alert_type": r.alert_type,
                    }
                    for r in results
                ],
                "actions": [
                    {
                        "action_type": a.action_type,
                        "alert_type": a.alert_type,
                        "category": a.category,
                        "name": a.name,
                        "message": a.message,
                        "speech": format_alert_speech(a),
                        "urgency": a.urgency,
                    }
                    for a in actions
                ],
            }
            print(json.dumps(payload, indent=2))
        else:
            print_formatted_report(
                results,
                actions,
                voice_connected=jarvis_speaker.is_available(),
            )

        if not is_daemon:
            # Exit code 1 if critical failures detected, 0 otherwise
            has_critical = any(r.status == "CRITICAL" for r in results)
            return 1 if has_critical else 0

        # Wait for next interval
        start_wait = time.time()
        while running and (time.time() - start_wait) < args.interval:
            time.sleep(0.5)

    return 0



if __name__ == "__main__":
    sys.exit(main())
