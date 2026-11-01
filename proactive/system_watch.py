"""Small local system observations and edge-triggered attention signals.

Collection is synchronous and belongs on a worker, never the voice loop. Missing
readings remain unknown. The observer stores only threshold state and counters,
without paths, process names, application content or network traffic.
"""
from __future__ import annotations

from itertools import islice
import math
from pathlib import Path
import shutil


def _percent(value):
    if type(value) not in (int, float) or not 0 <= value <= 100 or not math.isfinite(value):
        return None
    return float(value)


def _read(path, limit=512):
    try:
        with path.open('r', encoding='utf-8') as stream:
            return stream.read(limit).strip()
    except (OSError, UnicodeError):
        return None


def sample_system(*, home=None, power_supply_root=Path('/sys/class/power_supply'),
                  meminfo_path=Path('/proc/meminfo')):
    """Return cheap local readings; callers should run this off the voice loop.

    Battery readings describe the first present system battery. Peripheral
    device batteries are excluded, and multiple batteries are not silently
    presented as a fabricated combined percentage.
    """
    snapshot = {'battery_percent': None, 'battery_charging': None,
                'disk_free_percent': None, 'memory_available_percent': None}
    try:
        supplies = sorted(islice(Path(power_supply_root).iterdir(), 32))
    except OSError:
        supplies = []
    for supply in supplies:
        if (_read(supply / 'type') != 'Battery' or
                _read(supply / 'present') == '0' or
                _read(supply / 'scope') == 'Device'):
            continue
        try:
            charge = _percent(float(_read(supply / 'capacity')))
        except (TypeError, ValueError):
            charge = None
        status = _read(supply / 'status')
        snapshot['battery_percent'] = charge
        snapshot['battery_charging'] = (
            True if status in ('Charging', 'Full') else
            False if status in ('Discharging', 'Not charging') else None)
        break

    try:
        usage = shutil.disk_usage(Path.home() if home is None else home)
        if usage.total > 0:
            snapshot['disk_free_percent'] = _percent(100 * usage.free / usage.total)
    except OSError:
        pass

    raw = _read(Path(meminfo_path), limit=16384)
    if raw:
        memory = {}
        for line in raw.splitlines():
            name, _, value = line.partition(':')
            if name not in ('MemTotal', 'MemAvailable'):
                continue
            fields = value.split()
            if len(fields) != 2 or fields[1] != 'kB':
                continue
            try:
                memory[name] = int(fields[0])
            except ValueError:
                continue
        total, available = memory.get('MemTotal'), memory.get('MemAvailable')
        if total is not None and total > 0 and available is not None:
            snapshot['memory_available_percent'] = _percent(100 * available / total)
    return snapshot


class SystemWatch:
    """Emit one factual alert per low-resource episode, with recovery hysteresis.

    Keys identify transitions within this observer's lifetime. Repeated critical
    samples stay silent; another alert needs a confirmed recovery first.
    """
    def __init__(self, *, battery_low=15, battery_recover=20,
                 disk_low=5, disk_recover=8, memory_low=5, memory_recover=10):
        self.thresholds = {
            'battery': (battery_low, battery_recover),
            'disk': (disk_low, disk_recover),
            'memory': (memory_low, memory_recover),
        }
        for low, recover in self.thresholds.values():
            if _percent(low) is None or _percent(recover) is None or low >= recover:
                raise ValueError('system-watch thresholds require 0 <= low < recovery <= 100')
        self._active = {kind: False for kind in self.thresholds}
        self._generation = {kind: 0 for kind in self.thresholds}
        self._memory_low_samples = 0
        self._last_observed = None

    def is_current(self, key):
        """Whether a queued alert still describes an active resource episode."""
        return any(self._active[kind] and key == f'system:{kind}:{self._generation[kind]}'
                   for kind in self.thresholds)

    def observe(self, snapshot, now):
        if type(now) not in (int, float) or not math.isfinite(now):
            raise ValueError('system observation requires a finite monotonic timestamp')
        if self._last_observed is not None and now < self._last_observed:
            raise ValueError('system observation clock must not move backwards')
        self._last_observed = now
        alerts = []
        values = {
            'battery': _percent(snapshot.get('battery_percent')),
            'disk': _percent(snapshot.get('disk_free_percent')),
            'memory': _percent(snapshot.get('memory_available_percent')),
        }
        charging = snapshot.get('battery_charging')
        for kind, value in values.items():
            low, recover = self.thresholds[kind]
            recovered = (value is not None and
                         (value > recover if kind == 'battery' else value >= recover))
            if kind == 'battery' and charging is True:
                recovered = True
            if recovered:
                self._active[kind] = False
            critical = value is not None and value <= low
            if kind == 'battery':
                critical = critical and charging is False
            if kind == 'memory':
                self._memory_low_samples = self._memory_low_samples + 1 if critical else 0
                critical = self._memory_low_samples >= 2
            if not critical or self._active[kind]:
                continue
            self._active[kind] = True
            self._generation[kind] += 1
            if kind == 'battery':
                text = f'Battery charge is {value:g}% and it is not charging.'
            elif kind == 'disk':
                text = f'Storage is nearly full: {value:g}% remains free.'
            else:
                text = f'Memory is running low: {value:g}% is available.'
            alerts.append({'key': f'system:{kind}:{self._generation[kind]}',
                           'kind': kind, 'text': text, 'value_percent': value,
                           'observed_at': float(now)})
        return alerts
