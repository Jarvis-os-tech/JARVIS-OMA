import os
from pathlib import Path
import socket
import urllib.request
import pytest

from core.system_monitor import (
    ProbeResult,
    NetworkProbe,
    ServerProbe,
    ResourceProbe,
    ServiceProbe,
)


def test_server_probe_tcp_success():
    # Start a temporary local TCP listener
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind(("127.0.0.1", 0))
    server_sock.listen(1)
    port = server_sock.getsockname()[1]

    probe = ServerProbe()
    result = probe.check_tcp("127.0.0.1", port, timeout=1.0)
    server_sock.close()

    assert result.status == "OK"
    assert result.category == "server"
    assert "reachable" in result.message.lower()
    assert result.metrics.get("latency_ms") is not None


def test_server_probe_tcp_failure():
    # Pick a port that is not listening
    probe = ServerProbe()
    result = probe.check_tcp("127.0.0.1", 54321, timeout=0.2)
    assert result.status == "CRITICAL"
    assert result.alert_type == "server_down"
    assert "refused" in result.message.lower() or "timeout" in result.message.lower()


def test_server_probe_http_mock(monkeypatch):
    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return b"OK"

    def fake_urlopen(req, timeout=None):
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    probe = ServerProbe()
    result = probe.check_http("https://mock-api.local/health", timeout=1.0)
    assert result.status == "OK"
    assert result.metrics["http_code"] == 200


def test_network_probe_dns():
    probe = NetworkProbe()
    # Mocking getaddrinfo for test predictability
    def fake_getaddrinfo(host, port, *args, **kwargs):
        if host == "fail.local":
            raise socket.gaierror(-2, "Name or service not known")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 53))]

    import socket as sock_mod
    orig = sock_mod.getaddrinfo
    sock_mod.getaddrinfo = fake_getaddrinfo
    try:
        ok_res = probe.check_dns(["success.local"])
        assert ok_res.status == "OK"

        fail_res = probe.check_dns(["fail.local"])
        assert fail_res.status == "CRITICAL"
        assert fail_res.alert_type == "network_down"
    finally:
        sock_mod.getaddrinfo = orig


def test_resource_probe_memory_parsing(tmp_path):
    meminfo_file = tmp_path / "meminfo"
    # 8GB total, 800MB available -> 90% used
    meminfo_file.write_text("MemTotal: 8000000 kB\nMemAvailable: 800000 kB\n")

    probe = ResourceProbe(proc_path=tmp_path)
    res = probe.check_memory(threshold_percent=85.0)

    assert res.status == "CRITICAL"
    assert res.alert_type == "memory_critical"
    assert res.metrics["used_percent"] == 90.0


def test_resource_probe_cpu_parsing(tmp_path):
    stat_file = tmp_path / "stat"
    loadavg_file = tmp_path / "loadavg"
    stat_file.write_text("cpu  100 0 50 850 0 0 0 0 0 0\n")
    loadavg_file.write_text("1.50 1.20 0.90 1/200 12345\n")

    probe = ResourceProbe(proc_path=tmp_path)
    res = probe.check_cpu(threshold_percent=90.0, sample_delay=0.01)
    # Since stat does not change between samples, utilization is 0%
    assert res.status == "OK"
    assert res.metrics["utilization_percent"] == 0.0
    assert res.metrics["load_1m"] == 1.50


def test_service_probe(monkeypatch):
    def fake_check_output(cmd, *args, **kwargs):
        # cmd: ['systemctl', '--user', 'show', '--property=ActiveState,SubState,LoadState', 'test.service']
        return b"ActiveState=active\nSubState=running\nLoadState=loaded\n"

    import subprocess as sub_mod
    monkeypatch.setattr(sub_mod, "check_output", fake_check_output)

    probe = ServiceProbe()
    res = probe.check_service("test.service", user_scope=True)
    assert res.status == "OK"
    assert res.metrics["active_state"] == "active"
