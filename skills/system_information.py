"""Fresh, bounded, read-only Linux observations. No model-derived system facts."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from itertools import islice
import os
from pathlib import Path
import re
import shutil
from typing import Any


SECTIONS = ('overview', 'cpu', 'memory', 'disks', 'battery', 'temperatures',
            'hardware', 'os', 'network', 'displays', 'audio', 'services',
            'processes', 'packages')


async def _command(argv: list[str]) -> str:
    """Bound both pipes and lifetime; reap children on timeout and cancellation."""
    process = await asyncio.create_subprocess_exec(
        *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

    async def read(stream):
        result = bytearray()
        while chunk := await stream.read(16384):
            result.extend(chunk)
            if len(result) > 1024 * 1024:
                raise RuntimeError('command output exceeded 1 MiB')
        return result.decode('utf-8', errors='replace').strip()

    tasks = [asyncio.create_task(read(process.stdout)), asyncio.create_task(read(process.stderr))]
    try:
        async with asyncio.timeout(4):
            output, error = await asyncio.gather(*tasks)
            code = await process.wait()
        if code:
            raise RuntimeError(f'{argv[0]} exited {code}: {error[:240]}')
        return output
    finally:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        await process.wait()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


class SystemInformation:
    def __init__(self, *, proc_root=Path('/proc'), sys_root=Path('/sys'), root=Path('/'),
                 command_runner=None, sample_seconds=.15):
        self.proc = Path(proc_root)
        self.sys = Path(sys_root)
        self.root = Path(root)
        self.command_runner = command_runner or _command
        self.sample_seconds = max(.05, min(float(sample_seconds), 1))

    @staticmethod
    def _read(path: Path, maximum=262144) -> str:
        with path.open('rb') as handle:
            raw = handle.read(maximum + 1)
        if len(raw) > maximum:
            raise ValueError(f'{path.name}: source exceeds observation limit')
        return raw.decode('utf-8', errors='replace').strip()

    async def _run(self, *argv):
        return await self.command_runner(list(argv))

    async def get_system_information(self, section='overview', detail=None, limit=10):
        stamp = lambda: datetime.now(timezone.utc).isoformat()
        result = dict(section=section, observed_at=stamp(), status='error', sources=[], data=None, errors=[])
        if not isinstance(section, str) or section not in SECTIONS:
            result['errors'] = ['Unsupported section. Choose: ' + ', '.join(SECTIONS)]
            return result
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
            result['errors'] = ['limit must be an integer from 1 to 50']
            return result
        if detail is not None and (not isinstance(detail, str) or len(detail) > 128
                                   or not re.fullmatch(r'[\w .@:/+\-]+', detail)):
            result['errors'] = ['detail must be a plain filter of at most 128 characters']
            return result
        if detail is not None and section not in ('disks', 'network', 'displays', 'services', 'processes', 'packages'):
            result['errors'] = [f'{section} does not support detail filters']
            return result
        try:
            if section == 'overview':
                children = await asyncio.gather(*(self.get_system_information(name, limit=limit)
                                                  for name in ('os', 'cpu', 'memory', 'disks', 'battery')))
                result['data'] = {child['section']: child for child in children}
                result['status'] = 'ok' if all(c['status'] == 'ok' for c in children) else 'partial'
                result['sources'] = sorted({s for c in children for s in c['sources']})
            elif section == 'cpu':
                def counters():
                    fields = self._read(self.proc / 'stat').splitlines()[0].split()
                    if fields[0] != 'cpu' or len(fields) < 5:
                        raise ValueError('invalid aggregate CPU counters')
                    values = [int(v) for v in fields[1:9]]  # guest counters already included in user/nice
                    return sum(values), values[3] + (values[4] if len(values) > 4 else 0)
                before = await asyncio.to_thread(counters)
                started = asyncio.get_running_loop().time()
                await asyncio.sleep(self.sample_seconds)
                after = await asyncio.to_thread(counters)
                elapsed = asyncio.get_running_loop().time() - started
                total, idle = after[0] - before[0], after[1] - before[1]
                if total <= 0 or idle < 0 or idle > total:
                    raise ValueError('CPU counters did not advance consistently; utilization unavailable')
                load = await asyncio.to_thread(self._read, self.proc / 'loadavg')
                result.update(data={'utilization_percent': round(100 * (total - idle) / total, 2),
                                    'load_average_1_5_15_minutes': [float(v) for v in load.split()[:3]],
                                    'measurement': {'method': 'aggregate /proc/stat delta; iowait counted idle',
                                                    'sample_seconds': round(elapsed, 3)}}, sources=['/proc/stat', '/proc/loadavg'])
                result['status'] = 'ok'
            elif section in ('network', 'displays', 'audio', 'services', 'packages'):
                data, source = await self._external(section, detail, limit)
                result.update(data=data, sources=[source], status='ok')
            else:
                data, sources = await asyncio.to_thread(self._local, section, detail, limit)
                result.update(data=data, sources=sources, status='ok')
                if section == 'battery' and any(b.get('unavailable_fields') for b in data['batteries']):
                    result['status'] = 'partial'
        except (OSError, ValueError, RuntimeError, KeyError, IndexError, TypeError,
                ZeroDivisionError, asyncio.TimeoutError) as error:
            result['status'] = 'unavailable'
            result['errors'] = [str(error)[:400]]
        result['observed_at'] = stamp()
        return result

    def _local(self, section, detail, limit):
        if section == 'os':
            release = {}
            for line in self._read(self.root / 'etc/os-release').splitlines():
                if '=' in line:
                    key, value = line.split('=', 1)
                    if key in ('PRETTY_NAME', 'NAME', 'ID', 'VERSION_ID', 'VERSION'):
                        release[key.lower()] = value.strip('"')
            release['kernel'] = self._read(self.proc / 'sys/kernel/osrelease')
            release['uptime_seconds'] = float(self._read(self.proc / 'uptime').split()[0])
            return release, ['/etc/os-release', '/proc/sys/kernel/osrelease', '/proc/uptime']
        if section == 'memory':
            values = {}
            for line in self._read(self.proc / 'meminfo').splitlines():
                key, value = line.split(':', 1)
                parts = value.split()
                values[key] = int(parts[0]) * (1024 if len(parts) > 1 and parts[1] == 'kB' else 1)
            total, available = values['MemTotal'], values['MemAvailable']
            if total <= 0 or not 0 <= available <= total:
                raise ValueError('invalid memory counters')
            return {'total_bytes': total, 'available_bytes': available, 'used_bytes': total - available,
                    'used_percent': round(100 * (total - available) / total, 2),
                    'swap_total_bytes': values.get('SwapTotal'), 'swap_free_bytes': values.get('SwapFree')}, ['/proc/meminfo']
        if section == 'disks':
            path = detail or '/'
            if not path.startswith('/'):
                raise ValueError('disk detail must be an absolute path')
            usage = shutil.disk_usage(self.root / path.lstrip('/'))
            return {'path': path, 'total_bytes': usage.total, 'used_bytes': usage.used,
                    'free_bytes': usage.free, 'used_percent': round(100 * usage.used / usage.total, 2)}, ['statvfs:' + path]
        if section == 'battery':
            batteries = []
            for device in sorted((self.sys / 'class/power_supply').glob('*'))[:100]:
                try:
                    kind = self._read(device / 'type')
                except OSError:
                    continue
                if kind != 'Battery':
                    continue
                item = {'name': device.name}
                unavailable = []
                for field in ('status', 'capacity', 'energy_now', 'energy_full', 'power_now', 'voltage_now'):
                    try:
                        value = self._read(device / field)
                        item[field] = value if field == 'status' else int(value)
                    except (OSError, ValueError) as error:
                        item[field] = None
                        unavailable.append({'field': field, 'reason': str(error)[:160]})
                item['unavailable_fields'] = unavailable
                item['units'] = {'capacity': 'percent', 'energy_now': 'microWh', 'energy_full': 'microWh',
                                 'power_now': 'microW', 'voltage_now': 'microV'}
                batteries.append(item)
            if not batteries:
                raise ValueError('No readable battery device reported by sysfs')
            return {'batteries': batteries[:limit]}, ['/sys/class/power_supply']
        if section == 'temperatures':
            items = []
            for zone in sorted((self.sys / 'class/thermal').glob('thermal_zone*'))[:100]:
                try:
                    items.append({'sensor': self._read(zone / 'type'),
                                  'celsius': int(self._read(zone / 'temp')) / 1000})
                except (OSError, ValueError):
                    continue
            if not items:
                raise ValueError('No readable thermal-zone sensors')
            return {'sensors': items[:limit], 'truncated': len(items) > limit}, ['/sys/class/thermal']
        if section == 'hardware':
            cpu = self._read(self.proc / 'cpuinfo')
            models = sorted({line.split(':', 1)[1].strip() for line in cpu.splitlines()
                             if line.split(':', 1)[0].strip() in ('model name', 'Hardware')})
            count = sum(line.startswith('processor') for line in cpu.splitlines())
            if count == 0:
                raise ValueError('No recognized logical processors in /proc/cpuinfo')
            gpu = []
            for card in sorted((self.sys / 'class/drm').glob('card[0-9]*'))[:50]:
                if not re.fullmatch(r'card\d+', card.name):
                    continue
                try:
                    gpu.append({'card': card.name, 'pci_vendor_id': self._read(card / 'device/vendor'),
                                'pci_device_id': self._read(card / 'device/device')})
                except OSError:
                    continue
            return {'cpu_models': models, 'logical_cpu_count': count,
                    'gpu_pci_devices': gpu[:limit], 'gpu_names_available': False}, ['/proc/cpuinfo', '/sys/class/drm']
        if section == 'processes':
            items = []
            failures = 0
            for path in islice(self.proc.iterdir(), 16384):
                if not path.name.isdecimal():
                    continue
                try:
                    raw = self._read(path / 'stat', 16384)
                    start, end = raw.index('('), raw.rindex(')')
                    name = raw[start + 1:end]
                    if detail and detail.casefold() not in name.casefold():
                        continue
                    fields = raw[end + 2:].split()
                    items.append({'pid': int(path.name), 'name': name, 'state': fields[0],
                                  'cpu_lifetime_seconds': (int(fields[11]) + int(fields[12])) / os.sysconf('SC_CLK_TCK'),
                                  'resident_bytes': int(fields[21]) * os.sysconf('SC_PAGE_SIZE')})
                except (OSError, ValueError, IndexError):
                    failures += 1
            items.sort(key=lambda item: item['resident_bytes'], reverse=True)
            return {'processes': items[:limit], 'truncated': len(items) > limit,
                    'unreadable_or_exited_count': failures,
                    'cpu_measurement': 'lifetime user+system CPU seconds; not instantaneous utilization'}, ['/proc/<pid>/stat']
        raise ValueError('Unsupported local section')

    async def _external(self, section, detail, limit):
        if section == 'network':
            raw = json.loads(await self._run('ip', '-j', 'address', 'show'))
            if not isinstance(raw, list) or any(not isinstance(n, dict) for n in raw):
                raise ValueError('Invalid network response')
            if any(not isinstance(n.get('addr_info', []), list) or
                   any(not isinstance(a, dict) for a in n.get('addr_info', [])) or
                   not isinstance(n.get('ifname', ''), str) for n in raw):
                raise ValueError('Invalid network interface fields')
            items = [{'name': n.get('ifname'), 'state': n.get('operstate'),
                      'addresses': [{'family': a.get('family'), 'address': a.get('local'), 'prefix_length': a.get('prefixlen')}
                                    for a in n.get('addr_info', [])[:20]]} for n in raw
                     if not detail or detail.casefold() in n.get('ifname', '').casefold()]
            return {'interfaces': items[:limit], 'truncated': len(items) > limit,
                    'internet_reachability_tested': False}, 'ip -j address show'
        if section == 'displays':
            raw = json.loads(await self._run('hyprctl', 'monitors', '-j'))
            if not isinstance(raw, list) or any(not isinstance(n, dict) for n in raw):
                raise ValueError('Invalid monitor response')
            if any(not isinstance(n.get('name', ''), str) for n in raw):
                raise ValueError('Invalid monitor name')
            keys = ('name', 'description', 'width', 'height', 'refreshRate', 'scale', 'x', 'y', 'focused', 'disabled')
            items = [{k: n[k] for k in keys if k in n} for n in raw
                     if not detail or detail.casefold() in n.get('name', '').casefold()]
            return {'displays': items[:limit], 'truncated': len(items) > limit}, 'hyprctl monitors -j'
        if section == 'audio':
            output = await self._run('wpctl', 'get-volume', '@DEFAULT_AUDIO_SINK@')
            match = re.fullmatch(r'Volume:\s*([0-9.]+)(\s+\[MUTED\])?', output)
            if not match:
                raise ValueError('Unrecognized audio volume response')
            return {'default_output_volume_percent': round(float(match[1]) * 100, 2),
                    'default_output_muted': bool(match[2])}, 'wpctl get-volume @DEFAULT_AUDIO_SINK@'
        if section == 'services':
            if detail:
                if not re.fullmatch(r'[\w@.\-]+', detail) or detail.startswith('-'):
                    raise ValueError('service detail must be a unit name')
                output = await self._run('systemctl', '--user', 'show', '--no-pager',
                                         '--property=Id,LoadState,ActiveState,SubState,MainPID', '--', detail)
                data = dict(line.split('=', 1) for line in output.splitlines() if '=' in line)
                if not all(data.get(key) for key in ('Id', 'LoadState', 'ActiveState')):
                    raise ValueError('Missing required service state properties')
                return {'scope': 'user', 'service': data}, 'systemctl --user show (selected state properties)'
            output = await self._run('systemctl', '--user', 'list-units', '--type=service', '--all',
                                     '--no-pager', '--plain', '--no-legend')
            items = []
            for line in output.splitlines():
                parts = line.split(None, 4)
                if len(parts) >= 4:
                    items.append(dict(zip(('unit', 'load', 'active', 'sub'), parts[:4])))
            return {'scope': 'user', 'services': items[:limit], 'truncated': len(items) > limit}, 'systemctl --user list-units'
        output = await self._run('pacman', '-Q')
        items = []
        for line in output.splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2 and (not detail or detail.casefold() in parts[0].casefold()):
                items.append({'name': parts[0], 'version': parts[1]})
        return {'packages': items[:limit], 'matching_count': len(items), 'truncated': len(items) > limit}, 'pacman -Q'


async def get_system_information(section='overview', detail=None, limit=10):
    return await SystemInformation().get_system_information(section, detail, limit)
