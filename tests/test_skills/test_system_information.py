import asyncio
import json
from pathlib import Path
import sys

import pytest

from skills.system_information import SystemInformation, _command


def write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def reader(tmp_path):
    return SystemInformation(proc_root=tmp_path / 'proc', sys_root=tmp_path / 'sys', root=tmp_path)


@pytest.mark.asyncio
async def test_memory_reports_available_and_never_substitutes_zeros(reader):
    write(reader.proc, 'meminfo', 'MemTotal: 1000 kB\nMemAvailable: 250 kB\nSwapTotal: 0 kB\nSwapFree: 0 kB')
    result = await reader.get_system_information('memory')
    assert result['status'] == 'ok'
    assert result['data']['used_bytes'] == 750 * 1024
    assert result['data']['used_percent'] == 75
    assert result['observed_at'].endswith('+00:00')
    write(reader.proc, 'meminfo', 'MemTotal: 1000 kB')
    # Missing required counters are unavailable, never fabricated.
    result = await reader.get_system_information('memory')
    assert result['status'] == 'unavailable'
    assert result['data'] is None


@pytest.mark.asyncio
async def test_cpu_is_sampled_utilization_not_load_average(reader):
    write(reader.proc, 'stat', 'cpu  100 0 50 850 0 0 0 0 0 0')
    write(reader.proc, 'loadavg', '12.00 8.00 4.00 1/20 500')

    async def advance():
        await asyncio.sleep(.03)
        write(reader.proc, 'stat', 'cpu  120 0 60 920 0 0 0 0 0 0')
    changer = asyncio.create_task(advance())
    result = await reader.get_system_information('cpu')
    await changer
    assert result['status'] == 'ok'
    assert result['data']['utilization_percent'] == 30
    assert result['data']['load_average_1_5_15_minutes'] == [12, 8, 4]
    assert result['data']['measurement']['sample_seconds'] >= .1


@pytest.mark.asyncio
async def test_cpu_nonadvancing_counters_are_unavailable(reader):
    write(reader.proc, 'stat', 'cpu  100 0 50 850 0 0 0 0')
    result = await reader.get_system_information('cpu')
    assert result['status'] == 'unavailable'
    assert result['data'] is None


@pytest.mark.asyncio
@pytest.mark.parametrize('section,detail,limit', [('invalid', None, 10), ('os', None, True),
                                                 ('os', None, 51), ('services', 'a;shutdown', 10),
                                                 ('services', '--all', 10), ('audio', 'microphone', 10)])
async def test_rejects_invalid_inputs(reader, section, detail, limit):
    result = await reader.get_system_information(section, detail, limit)
    assert result['status'] in ('error', 'unavailable')
    assert result['data'] is None


@pytest.mark.asyncio
async def test_no_battery_is_unknown_not_zero(reader):
    result = await reader.get_system_information('battery')
    assert result['status'] == 'unavailable'
    assert result['data'] is None
    write(reader.sys, 'class/power_supply/BAT0/type', 'Battery')
    write(reader.sys, 'class/power_supply/BAT0/capacity', '73')
    write(reader.sys, 'class/power_supply/BAT0/status', 'Discharging')
    result = await reader.get_system_information('battery')
    assert result['data']['batteries'][0]['capacity'] == 73
    assert result['data']['batteries'][0]['power_now'] is None


@pytest.mark.asyncio
async def test_external_commands_fixed_filtered_and_bounded():
    calls = []
    async def run(argv):
        calls.append(argv)
        return json.dumps([{'ifname': 'eth0', 'operstate': 'UP', 'secret': 'not returned',
                            'addr_info': [{'family': 'inet', 'local': '192.0.2.1', 'prefixlen': 24}]}])
    result = await SystemInformation(command_runner=run).get_system_information('network', 'eth', 1)
    assert calls == [['ip', '-j', 'address', 'show']]
    assert result['data']['interfaces'][0]['addresses'][0]['address'] == '192.0.2.1'
    assert 'secret' not in json.dumps(result)
    assert result['data']['internet_reachability_tested'] is False


@pytest.mark.asyncio
async def test_external_failure_and_invalid_json_never_success():
    async def run(argv):
        raise RuntimeError('desktop connection refused')
    result = await SystemInformation(command_runner=run).get_system_information('displays')
    assert result['status'] == 'unavailable'
    async def malformed(argv):
        return '{broken'
    result = await SystemInformation(command_runner=malformed).get_system_information('network')
    assert result['status'] == 'unavailable'


@pytest.mark.asyncio
async def test_processes_exclude_command_lines_and_label_lifetime_cpu(reader):
    fields = ['S'] + ['0'] * 21
    fields[11], fields[12], fields[21] = '100', '100', '2'
    write(reader.proc, '42/stat', '42 (name with spaces) ' + ' '.join(fields))
    write(reader.proc, '42/cmdline', 'password=secret')
    result = await reader.get_system_information('processes')
    assert result['status'] == 'ok'
    process = result['data']['processes'][0]
    assert process['name'] == 'name with spaces'
    assert process['resident_bytes'] > 0
    assert 'lifetime' in result['data']['cpu_measurement']
    assert 'secret' not in json.dumps(result)


@pytest.mark.asyncio
async def test_oversized_files_fail_explicitly(reader):
    write(reader.proc, 'meminfo', 'x' * 300000)
    assert (await reader.get_system_information('memory'))['status'] == 'unavailable'


@pytest.mark.asyncio
async def test_empty_cpu_hardware_is_unknown(reader):
    write(reader.proc, 'cpuinfo', '')
    result = await reader.get_system_information('hardware')
    assert result['status'] == 'unavailable'
    assert result['data'] is None


@pytest.mark.asyncio
async def test_service_properties_required_and_not_found_preserved():
    async def empty(argv):
        return ''
    result = await SystemInformation(command_runner=empty).get_system_information('services', 'missing.service')
    assert result['status'] == 'unavailable'
    async def notfound(argv):
        return 'Id=missing.service\nLoadState=not-found\nActiveState=inactive\nSubState=dead\nMainPID=0'
    result = await SystemInformation(command_runner=notfound).get_system_information('services', 'missing.service')
    assert result['status'] == 'ok'
    assert result['data']['service']['LoadState'] == 'not-found'


@pytest.mark.asyncio
async def test_command_output_limit_kills_and_reaps():
    with pytest.raises(RuntimeError, match='exceeded'):
        await _command([sys.executable, '-c', "import sys,time;sys.stdout.write('x'*1100000);sys.stdout.flush();time.sleep(20)"])


@pytest.mark.asyncio
async def test_command_cancellation_reaps_child(tmp_path):
    pid_file = tmp_path / 'pid'
    task = asyncio.create_task(_command([sys.executable, '-c',
        'import os,time,pathlib;pathlib.Path(__import__("sys").argv[1]).write_text(str(os.getpid()));time.sleep(20)', str(pid_file)]))
    for _ in range(50):
        if pid_file.exists():
            break
        await asyncio.sleep(.01)
    assert pid_file.exists()
    pid = int(pid_file.read_text())
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not Path(f'/proc/{pid}').exists()
