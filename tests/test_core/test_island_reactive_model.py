"""Exercise the actual QML JavaScript model against stale and missing telemetry."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest


def test_reactive_model_system_deltas_privacy_and_priority():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required to execute QML JavaScript helpers')
    root = Path(__file__).resolve().parents[2]
    source = (root / 'ui/omarchy-jarvis-island/ReactiveModel.js').read_text()
    script = source.replace('.pragma library', '') + '''
const assert = require('node:assert/strict');
assert.equal(state('listening', true, false), 'muted');
assert.equal(state('listening', false, true), 'standby');
assert.equal(state('offline', true, true), 'offline');
assert.equal(state('barged_in', false, false), 'listening');
assert.equal(audioLevel(0.1, true, true), 0);
assert.equal(audioLevel(NaN, true, false), 0);
assert.equal(audioLevel(1, true, false), 1);
assert.equal(cpuUsage(null, cpuSample('cpu 10 0 10 80 0 0 0 0')), -1);
const a = cpuSample('cpu 10 0 10 80 0 0 0 0 999 999');
const b = cpuSample('cpu 20 0 20 160 0 0 0 0 999 999');
assert.ok(Math.abs(cpuUsage(a,b)-0.2)<0.0001);
assert.equal(cpuUsage(b,a), -1);
assert.equal(cpuSample('cpu garbage'), null);
assert.equal(memoryUsage('MemTotal: 1000 kB\\nMemAvailable: 250 kB'), 0.75);
assert.equal(memoryUsage('MemTotal: 1000 kB'), -1);
assert.equal(memoryUsage('MemTotal: 0 kB\\nMemAvailable: 0 kB'), -1);
console.log(JSON.stringify({checked:true}));
'''
    result = subprocess.run([node, '-e', script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['checked'] is True
