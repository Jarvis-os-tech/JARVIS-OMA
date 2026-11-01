"""Comprehensive system monitoring and alert intimation engine for JARVIS OS.

Checks network connectivity, server status, hardware vitals, and systemd services,
playing distinct procedurally synthesized audio alerts and emitting desktop notifications.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import urllib.request
import urllib.error
import wave

# Supported alert types mapped to descriptive names
SUPPORTED_ALERTS: Dict[str, str] = {
    "network_down": "Alternating dual-frequency siren (880Hz / 587Hz)",
    "server_down": "Descending minor triad alert (900Hz -> 675Hz -> 450Hz)",
    "cpu_overload": "Rapid high-pitch pulsing trill (1200Hz)",
    "memory_critical": "Dissonant dual-tone warning buzz (700Hz + 740Hz)",
    "disk_exhaustion": "Deep resonant low thumps (300Hz)",
    "service_failure": "Staccato double burst (750Hz)",
    "thermal_critical": "Rising frequency sweep (800Hz -> 1500Hz)",
    "recovery": "Ascending major chord resolution chime (C5 -> E5 -> G5 -> C6)",
}


class DesktopNotifier:
    """Non-blocking desktop notification dispatcher using notify-send."""

    def __init__(self, app_name: str = "JARVIS System Monitor") -> None:
        self.app_name = app_name
        self.notify_bin = shutil.which("notify-send")

    def notify(
        self,
        title: str,
        message: str,
        urgency: str = "normal",
        timeout_ms: int = 5000,
        icon: Optional[str] = None,
    ) -> bool:
        if not self.notify_bin:
            return False

        urgency_level = urgency.lower()
        if urgency_level not in ("low", "normal", "critical"):
            urgency_level = "normal"

        cmd = [
            self.notify_bin,
            f"--app-name={self.app_name}",
            f"--urgency={urgency_level}",
            f"--expire-time={timeout_ms}",
        ]
        if icon:
            cmd.append(f"--icon={icon}")
        cmd.extend([title, message])

        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
        except (OSError, ValueError):
            return False


class AlertAudioEngine:
    """Generates procedural PCM WAV alert sounds and handles non-blocking playback."""

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        if cache_dir is None:
            self.cache_dir = Path.home() / ".cache" / "jarvis" / "alerts"
        else:
            self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._player_cmd = self.detect_player()

    @staticmethod
    def detect_player() -> Optional[List[str]]:
        """Detect available Linux audio playback binaries."""
        if shutil.which("pw-play"):
            return ["pw-play"]
        if shutil.which("paplay"):
            return ["paplay"]
        if shutil.which("aplay"):
            return ["aplay", "-q"]
        if shutil.which("mpv"):
            return ["mpv", "--no-video", "--really-quiet"]
        if shutil.which("ffplay"):
            return ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]
        if shutil.which("canberra-gtk-play"):
            return ["canberra-gtk-play", "-f"]
        return None

    def list_supported_alerts(self) -> List[str]:
        return list(SUPPORTED_ALERTS.keys())

    def _generate_pcm_samples(self, alert_type: str, sample_rate: int = 44100) -> List[int]:
        """Synthesize 16-bit signed PCM audio samples mathematically."""
        samples: List[int] = []
        max_amplitude = 28000  # Leave headroom below 32767 to avoid clipping

        def add_tone(
            freq: float,
            duration: float,
            attack: float = 0.02,
            decay: float = 0.03,
            volume: float = 1.0,
            freq_end: Optional[float] = None,
        ):
            n_samples = int(duration * sample_rate)
            att_samples = int(attack * sample_rate)
            dec_samples = int(decay * sample_rate)

            for i in range(n_samples):
                t = i / sample_rate
                # Frequency sweep if requested
                if freq_end is not None:
                    curr_freq = freq + (freq_end - freq) * (i / n_samples)
                else:
                    curr_freq = freq

                # Amplitude envelope to eliminate clicks
                env = 1.0
                if i < att_samples and att_samples > 0:
                    env = i / att_samples
                elif i > n_samples - dec_samples and dec_samples > 0:
                    env = max(0.0, (n_samples - i) / dec_samples)

                val = math.sin(2.0 * math.pi * curr_freq * t)
                sample = int(max_amplitude * volume * env * val)
                samples.append(max(-32768, min(32767, sample)))

        def add_dual_tone(
            freq1: float,
            freq2: float,
            duration: float,
            attack: float = 0.02,
            decay: float = 0.03,
            volume: float = 1.0,
        ):
            n_samples = int(duration * sample_rate)
            att_samples = int(attack * sample_rate)
            dec_samples = int(decay * sample_rate)

            for i in range(n_samples):
                t = i / sample_rate
                env = 1.0
                if i < att_samples and att_samples > 0:
                    env = i / att_samples
                elif i > n_samples - dec_samples and dec_samples > 0:
                    env = max(0.0, (n_samples - i) / dec_samples)

                val = 0.5 * math.sin(2.0 * math.pi * freq1 * t) + 0.5 * math.sin(2.0 * math.pi * freq2 * t)
                sample = int(max_amplitude * volume * env * val)
                samples.append(max(-32768, min(32767, sample)))

        def add_silence(duration: float):
            n_samples = int(duration * sample_rate)
            samples.extend([0] * n_samples)

        if alert_type == "network_down":
            # Alternating dual-frequency alarm siren
            for _ in range(3):
                add_tone(880.0, 0.12, attack=0.01, decay=0.01, volume=0.85)
                add_silence(0.02)
                add_tone(587.33, 0.12, attack=0.01, decay=0.01, volume=0.85)
                add_silence(0.02)

        elif alert_type == "server_down":
            # Descending minor triad alert: 900 Hz -> 675 Hz -> 450 Hz
            for freq in (900.0, 675.0, 450.0):
                add_tone(freq, 0.18, attack=0.01, decay=0.04, volume=0.9)
                add_silence(0.04)

        elif alert_type == "cpu_overload":
            # Rapid high-pitch triple chirp
            for _ in range(3):
                add_tone(1200.0, 0.08, attack=0.01, decay=0.02, volume=0.8)
                add_silence(0.04)

        elif alert_type == "memory_critical":
            # Dissonant warning buzz (700Hz + 740Hz dual tone)
            for _ in range(2):
                add_dual_tone(700.0, 740.0, 0.22, attack=0.02, decay=0.04, volume=0.9)
                add_silence(0.06)

        elif alert_type == "disk_exhaustion":
            # Low resonant double thump (300Hz)
            for _ in range(2):
                add_tone(300.0, 0.22, attack=0.01, decay=0.08, volume=1.0)
                add_silence(0.08)

        elif alert_type == "service_failure":
            # Staccato double beep (750Hz)
            for _ in range(2):
                add_tone(750.0, 0.11, attack=0.01, decay=0.02, volume=0.85)
                add_silence(0.05)

        elif alert_type == "thermal_critical":
            # Rising sweep
            for _ in range(2):
                add_tone(800.0, 0.35, attack=0.02, decay=0.03, volume=0.85, freq_end=1500.0)
                add_silence(0.05)

        elif alert_type == "recovery":
            # Ascending major triad resolution chime (C5 -> E5 -> G5 -> C6) with natural bell decay
            notes = (523.25, 659.25, 783.99, 1046.50)
            for i, freq in enumerate(notes):
                dur = 0.28 if i == len(notes) - 1 else 0.14
                add_tone(freq, dur, attack=0.01, decay=dur * 0.7, volume=0.8)

        else:
            # Fallback simple warning beep
            add_tone(600.0, 0.25, attack=0.01, decay=0.03, volume=0.8)

        return samples

    def synthesize_alert_wav(self, alert_type: str, force: bool = False) -> Path:
        """Create or return cached WAV file for the specified alert type."""
        safe_name = alert_type.replace("/", "_").replace("..", "")
        wav_path = self.cache_dir / f"{safe_name}.wav"

        if wav_path.exists() and not force and wav_path.stat().st_size > 500:
            return wav_path

        samples = self._generate_pcm_samples(alert_type, sample_rate=44100)
        temp_path = self.cache_dir / f"{safe_name}.tmp.wav"

        with wave.open(str(temp_path), "wb") as wf:
            wf.setnchannels(1)  # Mono
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(44100)
            raw_data = struct.pack(f"<{len(samples)}h", *samples)
            wf.writeframes(raw_data)

        temp_path.replace(wav_path)
        return wav_path

    def play_alert(
        self,
        alert_type: str,
        async_play: bool = True,
        custom_path: Optional[Path] = None,
    ) -> bool:
        """Play alert sound asynchronously or synchronously."""
        if not self._player_cmd:
            return False

        if custom_path and Path(custom_path).exists():
            target_wav = Path(custom_path)
        else:
            target_wav = self.synthesize_alert_wav(alert_type)

        cmd = list(self._player_cmd) + [str(target_wav)]

        def _runner():
            try:
                subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except (OSError, ValueError):
                pass

        if async_play:
            thread = threading.Thread(target=_runner, daemon=True)
            thread.start()
            return True
        else:
            _runner()
            return True


@dataclass
class ProbeResult:
    """Represents the observation of a single check."""
    name: str
    category: str  # "network", "server", "resource", "service"
    status: str    # "OK", "WARN", "CRITICAL"
    message: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    alert_type: Optional[str] = None


class NetworkProbe:
    """Probes default route, DNS resolution, and WAN HTTP reachability."""

    def __init__(
        self,
        dns_targets: Optional[List[str]] = None,
        wan_urls: Optional[List[str]] = None,
    ) -> None:
        self.dns_targets = dns_targets or ["cloudflare.com", "google.com", "1.1.1.1"]
        self.wan_urls = wan_urls or [
            "http://connectivitycheck.gstatic.com/generate_204",
            "https://1.1.1.1",
        ]

    def check_dns(self, hosts: Optional[List[str]] = None) -> ProbeResult:
        targets = hosts if hosts is not None else self.dns_targets
        failed = []
        latencies = []

        for host in targets:
            start = time.perf_counter()
            try:
                # Port 53 or 443 resolution check
                socket.getaddrinfo(host, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
                latency_ms = round((time.perf_counter() - start) * 1000, 2)
                latencies.append(latency_ms)
            except (socket.gaierror, socket.herror, OSError):
                failed.append(host)

        if len(failed) == len(targets):
            return ProbeResult(
                name="DNS Resolution",
                category="network",
                status="CRITICAL",
                message=f"DNS lookup failed for all targets: {', '.join(targets)}",
                metrics={"failed": failed, "total": len(targets)},
                alert_type="network_down",
            )
        elif failed:
            return ProbeResult(
                name="DNS Resolution",
                category="network",
                status="WARN",
                message=f"DNS lookup failed for: {', '.join(failed)} (partial)",
                metrics={"failed": failed, "avg_latency_ms": round(sum(latencies) / len(latencies), 2)},
                alert_type="network_down",
            )
        else:
            avg_lat = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
            return ProbeResult(
                name="DNS Resolution",
                category="network",
                status="OK",
                message=f"DNS resolved cleanly ({avg_lat} ms avg)",
                metrics={"avg_latency_ms": avg_lat, "tested": len(targets)},
            )

    def check_wan_http(self, urls: Optional[List[str]] = None, timeout: float = 3.0) -> ProbeResult:
        targets = urls if urls is not None else self.wan_urls
        for url in targets:
            start = time.perf_counter()
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "JARVIS-Monitor/1.0"},
                )
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    latency_ms = round((time.perf_counter() - start) * 1000, 2)
                    return ProbeResult(
                        name="WAN Internet Reachability",
                        category="network",
                        status="OK",
                        message=f"Internet reachable via {url} ({latency_ms} ms)",
                        metrics={"endpoint": url, "latency_ms": latency_ms, "status_code": response.status},
                    )
            except (urllib.error.URLError, OSError, TimeoutError):
                continue

        return ProbeResult(
            name="WAN Internet Reachability",
            category="network",
            status="CRITICAL",
            message="No internet connectivity detected across test endpoints",
            metrics={"tested_urls": targets},
            alert_type="network_down",
        )

    def check_gateway(self, proc_path: Path = Path("/proc")) -> ProbeResult:
        """Inspect /proc/net/route for default gateway."""
        route_file = proc_path / "net" / "route"
        if not route_file.exists():
            return ProbeResult(
                name="Default Gateway",
                category="network",
                status="OK",
                message="Route inspection bypassed (container/non-linux proc)",
            )

        try:
            with route_file.open("r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in lines[1:]:
                parts = line.strip().split()
                if len(parts) >= 3 and parts[1] == "00000000":
                    iface = parts[0]
                    # Parse hex IP
                    gw_hex = parts[2]
                    gw_ip = ".".join(str(int(gw_hex[i:i+2], 16)) for i in (6, 4, 2, 0))
                    return ProbeResult(
                        name="Default Gateway",
                        category="network",
                        status="OK",
                        message=f"Default route active on {iface} via {gw_ip}",
                        metrics={"interface": iface, "gateway": gw_ip},
                    )
            return ProbeResult(
                name="Default Gateway",
                category="network",
                status="CRITICAL",
                message="No default gateway found in routing table",
                alert_type="network_down",
            )
        except OSError as err:
            return ProbeResult(
                name="Default Gateway",
                category="network",
                status="WARN",
                message=f"Unable to read route table: {err}",
            )


class ServerProbe:
    """Probes remote or local TCP ports and HTTP/HTTPS server endpoints."""

    def check_tcp(self, host: str, port: int, timeout: float = 2.0) -> ProbeResult:
        name = f"TCP {host}:{port}"
        start = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                latency_ms = round((time.perf_counter() - start) * 1000, 2)
                return ProbeResult(
                    name=name,
                    category="server",
                    status="OK",
                    message=f"Port {port} reachable ({latency_ms} ms)",
                    metrics={"host": host, "port": port, "latency_ms": latency_ms},
                )
        except ConnectionRefusedError:
            return ProbeResult(
                name=name,
                category="server",
                status="CRITICAL",
                message=f"Connection refused on {host}:{port}",
                metrics={"host": host, "port": port},
                alert_type="server_down",
            )
        except (TimeoutError, socket.timeout):
            return ProbeResult(
                name=name,
                category="server",
                status="CRITICAL",
                message=f"Connection timed out after {timeout}s on {host}:{port}",
                metrics={"host": host, "port": port},
                alert_type="server_down",
            )
        except OSError as err:
            return ProbeResult(
                name=name,
                category="server",
                status="CRITICAL",
                message=f"Failed to connect to {host}:{port}: {err}",
                metrics={"host": host, "port": port, "error": str(err)},
                alert_type="server_down",
            )

    def check_http(
        self,
        url: str,
        expected_codes: Optional[List[int]] = None,
        timeout: float = 3.0,
    ) -> ProbeResult:
        name = f"HTTP {url}"
        codes = expected_codes or [200, 201, 204, 301, 302, 304, 307, 308]
        start = time.perf_counter()
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "JARVIS-Monitor/1.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status_code = getattr(response, "status", 200)
                latency_ms = round((time.perf_counter() - start) * 1000, 2)
                if status_code in codes:
                    return ProbeResult(
                        name=name,
                        category="server",
                        status="OK",
                        message=f"HTTP status {status_code} ({latency_ms} ms)",
                        metrics={"url": url, "http_code": status_code, "latency_ms": latency_ms},
                    )
                else:
                    return ProbeResult(
                        name=name,
                        category="server",
                        status="CRITICAL",
                        message=f"Unexpected HTTP status {status_code}",
                        metrics={"url": url, "http_code": status_code, "latency_ms": latency_ms},
                        alert_type="server_down",
                    )
        except urllib.error.HTTPError as err:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            if err.code in codes:
                return ProbeResult(
                    name=name,
                    category="server",
                    status="OK",
                    message=f"HTTP status {err.code} ({latency_ms} ms)",
                    metrics={"url": url, "http_code": err.code, "latency_ms": latency_ms},
                )
            return ProbeResult(
                name=name,
                category="server",
                status="CRITICAL",
                message=f"HTTP error {err.code}: {err.reason}",
                metrics={"url": url, "http_code": err.code},
                alert_type="server_down",
            )
        except (urllib.error.URLError, OSError, TimeoutError) as err:
            return ProbeResult(
                name=name,
                category="server",
                status="CRITICAL",
                message=f"HTTP request failed: {err}",
                metrics={"url": url, "error": str(err)},
                alert_type="server_down",
            )


class ResourceProbe:
    """Monitors CPU utilization, memory usage, disk capacity, and thermal sensors."""

    def __init__(
        self,
        proc_path: Optional[Path] = None,
        sys_path: Optional[Path] = None,
    ) -> None:
        self.proc_path = Path(proc_path) if proc_path else Path("/proc")
        self.sys_path = Path(sys_path) if sys_path else Path("/sys")

    def _read_cpu_counters(self) -> Tuple[int, int]:
        stat_path = self.proc_path / "stat"
        with stat_path.open("r", encoding="utf-8") as f:
            first_line = f.readline()
        fields = first_line.split()
        if fields[0] != "cpu" or len(fields) < 5:
            raise ValueError("Invalid CPU counters in /proc/stat")
        vals = [int(v) for v in fields[1:9]]
        total = sum(vals)
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
        return total, idle

    def check_cpu(
        self,
        threshold_percent: float = 90.0,
        sample_delay: float = 0.1,
    ) -> ProbeResult:
        try:
            total1, idle1 = self._read_cpu_counters()
            time.sleep(sample_delay)
            total2, idle2 = self._read_cpu_counters()

            delta_total = total2 - total1
            delta_idle = idle2 - idle1

            if delta_total <= 0:
                util_pct = 0.0
            else:
                util_pct = round(100.0 * (delta_total - delta_idle) / delta_total, 2)
                util_pct = max(0.0, min(100.0, util_pct))
        except (OSError, ValueError):
            util_pct = 0.0

        # Read load average
        load1, load5, load15 = 0.0, 0.0, 0.0
        load_path = self.proc_path / "loadavg"
        if load_path.exists():
            try:
                parts = load_path.read_text(encoding="utf-8").split()
                load1, load5, load15 = float(parts[0]), float(parts[1]), float(parts[2])
            except (OSError, ValueError, IndexError):
                pass

        metrics = {
            "utilization_percent": util_pct,
            "load_1m": load1,
            "load_5m": load5,
            "load_15m": load15,
        }

        if util_pct >= threshold_percent:
            return ProbeResult(
                name="CPU Utilization",
                category="resource",
                status="CRITICAL",
                message=f"CPU load critical: {util_pct}% (loadavg: {load1}, {load5}, {load15})",
                metrics=metrics,
                alert_type="cpu_overload",
            )
        elif util_pct >= threshold_percent * 0.85:
            return ProbeResult(
                name="CPU Utilization",
                category="resource",
                status="WARN",
                message=f"CPU load elevated: {util_pct}% (loadavg: {load1})",
                metrics=metrics,
                alert_type="cpu_overload",
            )
        else:
            return ProbeResult(
                name="CPU Utilization",
                category="resource",
                status="OK",
                message=f"CPU normal: {util_pct}% (loadavg: {load1})",
                metrics=metrics,
            )

    def check_memory(self, threshold_percent: float = 90.0) -> ProbeResult:
        meminfo_path = self.proc_path / "meminfo"
        if not meminfo_path.exists():
            return ProbeResult(
                name="Memory Usage",
                category="resource",
                status="OK",
                message="Memory check bypassed (/proc/meminfo missing)",
            )

        values: Dict[str, int] = {}
        try:
            with meminfo_path.open("r", encoding="utf-8") as f:
                for line in f:
                    if ":" in line:
                        k, v = line.split(":", 1)
                        parts = v.strip().split()
                        values[k] = int(parts[0]) * (1024 if len(parts) > 1 and parts[1] == "kB" else 1)
        except (OSError, ValueError):
            return ProbeResult(
                name="Memory Usage",
                category="resource",
                status="WARN",
                message="Could not read memory statistics",
            )

        total = values.get("MemTotal", 0)
        available = values.get("MemAvailable", values.get("MemFree", 0))

        if total <= 0:
            return ProbeResult(
                name="Memory Usage",
                category="resource",
                status="WARN",
                message="Invalid total memory reported",
            )

        used = total - available
        used_pct = round(100.0 * used / total, 2)
        avail_mb = round(available / (1024 * 1024), 1)
        total_mb = round(total / (1024 * 1024), 1)

        metrics = {
            "used_percent": used_pct,
            "available_mb": avail_mb,
            "total_mb": total_mb,
        }

        if used_pct >= threshold_percent:
            return ProbeResult(
                name="Memory Usage",
                category="resource",
                status="CRITICAL",
                message=f"Memory critical: {used_pct}% used ({avail_mb} MB available / {total_mb} MB total)",
                metrics=metrics,
                alert_type="memory_critical",
            )
        elif used_pct >= threshold_percent * 0.9:
            return ProbeResult(
                name="Memory Usage",
                category="resource",
                status="WARN",
                message=f"Memory high: {used_pct}% used ({avail_mb} MB available)",
                metrics=metrics,
                alert_type="memory_critical",
            )
        else:
            return ProbeResult(
                name="Memory Usage",
                category="resource",
                status="OK",
                message=f"Memory normal: {used_pct}% used ({avail_mb} MB free)",
                metrics=metrics,
            )

    def check_disk(self, mount_point: str = "/", threshold_percent: float = 90.0) -> ProbeResult:
        try:
            usage = shutil.disk_usage(mount_point)
            used_pct = round(100.0 * usage.used / usage.total, 2)
            free_gb = round(usage.free / (1024 ** 3), 2)
            total_gb = round(usage.total / (1024 ** 3), 2)
            metrics = {
                "mount": mount_point,
                "used_percent": used_pct,
                "free_gb": free_gb,
                "total_gb": total_gb,
            }
            if used_pct >= threshold_percent:
                return ProbeResult(
                    name=f"Disk Space ({mount_point})",
                    category="resource",
                    status="CRITICAL",
                    message=f"Disk {mount_point} critical: {used_pct}% used ({free_gb} GB free of {total_gb} GB)",
                    metrics=metrics,
                    alert_type="disk_exhaustion",
                )
            elif used_pct >= threshold_percent * 0.9:
                return ProbeResult(
                    name=f"Disk Space ({mount_point})",
                    category="resource",
                    status="WARN",
                    message=f"Disk {mount_point} high: {used_pct}% used ({free_gb} GB free)",
                    metrics=metrics,
                    alert_type="disk_exhaustion",
                )
            else:
                return ProbeResult(
                    name=f"Disk Space ({mount_point})",
                    category="resource",
                    status="OK",
                    message=f"Disk {mount_point} normal: {used_pct}% used ({free_gb} GB free)",
                    metrics=metrics,
                )
        except OSError as err:
            return ProbeResult(
                name=f"Disk Space ({mount_point})",
                category="resource",
                status="WARN",
                message=f"Could not read disk usage for {mount_point}: {err}",
            )

    def check_thermals(self, threshold_celsius: float = 85.0) -> List[ProbeResult]:
        results: List[ProbeResult] = []
        thermal_base = self.sys_path / "class" / "thermal"
        if not thermal_base.exists():
            return results

        try:
            for zone in sorted(thermal_base.glob("thermal_zone*")):
                temp_file = zone / "temp"
                type_file = zone / "type"
                if not temp_file.exists():
                    continue
                try:
                    raw_temp = int(temp_file.read_text(encoding="utf-8").strip())
                    celsius = round(raw_temp / 1000.0, 1)
                    sensor_type = type_file.read_text(encoding="utf-8").strip() if type_file.exists() else zone.name
                except (ValueError, OSError):
                    continue

                if celsius >= threshold_celsius:
                    results.append(
                        ProbeResult(
                            name=f"Thermal ({sensor_type})",
                            category="resource",
                            status="CRITICAL",
                            message=f"Temperature critical: {celsius}°C (limit {threshold_celsius}°C)",
                            metrics={"sensor": sensor_type, "celsius": celsius},
                            alert_type="thermal_critical",
                        )
                    )
        except OSError:
            pass

        return results


class ServiceProbe:
    """Monitors systemd user and system services."""

    def check_service(self, service_name: str, user_scope: bool = True) -> ProbeResult:
        name = f"Service {service_name}"
        cmd = ["systemctl"]
        if user_scope:
            cmd.append("--user")
        cmd.extend([
            "show",
            "--property=ActiveState,SubState,LoadState,Result",
            "--",
            service_name,
        ])

        try:
            output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=3.0)
            text = output.decode("utf-8", errors="replace")
            props = dict(line.split("=", 1) for line in text.splitlines() if "=" in line)
            active_state = props.get("ActiveState", "unknown")
            sub_state = props.get("SubState", "unknown")
            load_state = props.get("LoadState", "unknown")

            metrics = {
                "service": service_name,
                "active_state": active_state,
                "sub_state": sub_state,
                "load_state": load_state,
            }

            if active_state == "active":
                return ProbeResult(
                    name=name,
                    category="service",
                    status="OK",
                    message=f"Service running ({sub_state})",
                    metrics=metrics,
                )
            elif active_state in ("failed", "inactive", "dead"):
                return ProbeResult(
                    name=name,
                    category="service",
                    status="CRITICAL",
                    message=f"Service {service_name} is {active_state} ({sub_state})",
                    metrics=metrics,
                    alert_type="service_failure",
                )
            else:
                return ProbeResult(
                    name=name,
                    category="service",
                    status="WARN",
                    message=f"Service {service_name} state: {active_state}",
                    metrics=metrics,
                    alert_type="service_failure",
                )
        except subprocess.TimeoutExpired:
            return ProbeResult(
                name=name,
                category="service",
                status="WARN",
                message=f"systemctl query timed out for {service_name}",
            )
        except (subprocess.CalledProcessError, OSError) as err:
            return ProbeResult(
                name=name,
                category="service",
                status="WARN",
                message=f"Failed to inspect service {service_name}: {err}",
            )


@dataclass
class AlertAction:
    """Action to be executed when an alert condition or recovery occurs."""
    action_type: str  # "ALERT" or "RECOVERY"
    alert_type: str   # key in SUPPORTED_ALERTS
    category: str
    name: str
    message: str
    urgency: str = "normal"  # "low", "normal", "critical"


class AlertStateManager:
    """Tracks state transitions, suppresses alert flapping, and enforces alert cooldowns."""

    def __init__(self, cooldown_seconds: float = 300.0) -> None:
        self.cooldown_seconds = cooldown_seconds
        self._states: Dict[str, Dict[str, Any]] = {}

    def get_state(self, name: str) -> Optional[Dict[str, Any]]:
        return self._states.get(name)

    def process_results(self, results: List[ProbeResult]) -> List[AlertAction]:
        actions: List[AlertAction] = []
        now = time.monotonic()

        for res in results:
            prev = self._states.get(res.name)
            is_failure = (res.status == "CRITICAL")

            if is_failure:
                alert_type = res.alert_type or "server_down"
                if prev is None or prev.get("status") != "CRITICAL":
                    # Transition from non-failure to failure
                    self._states[res.name] = {
                        "status": "CRITICAL",
                        "last_alert_time": now,
                        "alert_type": alert_type,
                    }
                    actions.append(
                        AlertAction(
                            action_type="ALERT",
                            alert_type=alert_type,
                            category=res.category,
                            name=res.name,
                            message=res.message,
                            urgency="critical",
                        )
                    )
                else:
                    # Still failing; check cooldown
                    last_time = prev.get("last_alert_time", 0.0)
                    if now - last_time >= self.cooldown_seconds:
                        prev["last_alert_time"] = now
                        actions.append(
                            AlertAction(
                                action_type="ALERT",
                                alert_type=alert_type,
                                category=res.category,
                                name=res.name,
                                message=f"[Persistent] {res.message}",
                                urgency="critical",
                            )
                        )
            else:
                # Component is healthy
                if prev is not None and prev.get("status") == "CRITICAL":
                    # Transition from CRITICAL to OK (Recovery)
                    del self._states[res.name]
                    actions.append(
                        AlertAction(
                            action_type="RECOVERY",
                            alert_type="recovery",
                            category=res.category,
                            name=res.name,
                            message=f"{res.name} restored to normal state",
                            urgency="normal",
                        )
                    )

        return actions

    def dispatch_actions(
        self,
        actions: List[AlertAction],
        audio_engine: Optional[AlertAudioEngine] = None,
        notifier: Optional[DesktopNotifier] = None,
        jarvis_speaker: Optional[JarvisVoiceSpeaker] = None,
        voice_alert: bool = True,
        sound_alert: bool = False,
        desktop_notify: bool = True,
    ) -> None:
        for act in actions:
            if desktop_notify and notifier:
                title = f"[{'ALERT' if act.action_type == 'ALERT' else 'RESOLVED'}] {act.name}"
                notifier.notify(title, act.message, urgency=act.urgency)

            if voice_alert and jarvis_speaker:
                speech_text = format_alert_speech(act)
                jarvis_speaker.speak_alert(speech_text)

            if sound_alert and audio_engine:
                audio_engine.play_alert(act.alert_type, async_play=True)


def format_alert_speech(action: AlertAction) -> str:
    """Format an alert into natural conversational English for JARVIS to vocalize."""
    if action.action_type == "RECOVERY":
        return f"System update: {action.name} has recovered and is now back to a healthy state."

    t = action.alert_type
    if t == "network_down":
        return f"Network alert: Connectivity failure detected. {action.message}."
    elif t == "server_down":
        return f"Server alert: Monitored service {action.name} is offline. {action.message}."
    elif t == "cpu_overload":
        return f"System alert: High CPU workload detected. {action.message}."
    elif t == "memory_critical":
        return f"System alert: Memory resources are critically low. {action.message}."
    elif t == "disk_exhaustion":
        return f"Storage alert: Disk volume {action.name} is running out of space. {action.message}."
    elif t == "service_failure":
        return f"Service alert: {action.name} is down or failed. {action.message}."
    elif t == "thermal_critical":
        return f"Hardware warning: High temperature alert on {action.name}. {action.message}."
    else:
        return f"System alert: Failure detected in {action.name}. {action.message}."


class JarvisVoiceSpeaker:
    """Dispatches verbal alerts directly into JARVIS's live voice pipeline via Unix socket IPC."""

    def __init__(self, socket_path: Optional[Path] = None) -> None:
        if socket_path:
            self.socket_path = Path(socket_path)
        else:
            runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
            candidates = [
                runtime_dir / "jarvis" / "control.sock",
                runtime_dir / "jarvis.sock",
                Path.home() / ".local/state/jarvis" / "control.sock",
            ]
            self.socket_path = candidates[0]
            for cand in candidates:
                if cand.exists():
                    self.socket_path = cand
                    break

    def is_available(self) -> bool:
        if not self.socket_path.exists():
            return False
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                s.connect(str(self.socket_path))
                s.sendall(b"status\n")
                data = s.recv(512)
                return bool(data)
        except (OSError, socket.timeout):
            return False

    def speak_alert(self, text: str, timeout: float = 2.0) -> bool:
        """Tell JARVIS Voice to vocalize this announcement."""
        if not self.socket_path.exists():
            return False

        prompt = f"tell Announcement for user: {text.strip()} Please state this concisely.\n"
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                s.connect(str(self.socket_path))
                s.sendall(prompt.encode("utf-8"))
                resp = s.recv(1024)
                return bool(resp)
        except (OSError, socket.timeout):
            return False



