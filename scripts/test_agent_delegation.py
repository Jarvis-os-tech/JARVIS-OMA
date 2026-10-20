"""Live delegation smoke test.

This is intentionally not collected by the normal offline pytest suite. It uses
installed agent accounts and temporary repositories, and should be run only as
an explicit smoke test.
"""
import argparse
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skills import DesktopSkills
from agent_orchestrator import AGENTS


async def main(timeout, agents):
    root = Path(tempfile.mkdtemp(prefix='jarvis-agent-smoke-'))
    print(json.dumps({'test_directory': str(root)}), flush=True)
    skills = DesktopSkills()
    gate = asyncio.Semaphore(3)
    reports = []

    async def test(name):
        async with gate:
            workspace = root / name
            workspace.mkdir()
            subprocess.run(['git', 'init', '-q', str(workspace)], check=True)
            expected = f'JARVIS_DELEGATION_OK:{name}\n'
            prompt = (f'This is a minimal delegation smoke test. Create ONLY the file delegation-ok.txt '
                      f'in the current directory containing exactly {expected.strip()} followed by a newline. '
                      'Use your file-writing tool. Do not inspect other directories, run tests, install anything, '
                      'change configuration, or ask questions. Then reply briefly that the file was created.')
            started = await skills.execute('delegate_agent', {
                'agent': name, 'prompt': prompt, 'workspace': str(workspace),
                'timeout_seconds': timeout})
            key = started['job']['id']
            print(json.dumps({'agent': name, 'job_id': key, 'state': 'started'}), flush=True)
            worker = skills._agent_orchestrator.workers[key]
            await worker
            job = (await skills.execute('check_agent_job', {'job_id': key, 'max_chars': 20000}))['job']
            marker = workspace / 'delegation-ok.txt'
            content = marker.read_text(encoding='utf-8') if marker.is_file() else None
            verified = content is not None and content.rstrip('\n') == expected.rstrip('\n')
            (workspace / 'agent-output.log').write_text(job['output'], encoding='utf-8')
            report = {'agent': name, 'job_id': key, 'state': job['state'],
                      'exit_code': job['exit_code'], 'file_verified': verified,
                      'exact_content': content == expected,
                      'log': str(workspace / 'agent-output.log')}
            reports.append(report)
            print(json.dumps(report), flush=True)

    try:
        await asyncio.gather(*(test(name) for name in agents))
    finally:
        await skills.close_agent_jobs()
    (root / 'report.json').write_text(json.dumps(reports, indent=2), encoding='utf-8')
    print(json.dumps({'passed': sum(item['file_verified'] and item['state'] == 'completed'
                                    for item in reports), 'total': len(reports),
                      'report': str(root / 'report.json')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=int, default=90)
    parser.add_argument('--agents', nargs='+', choices=AGENTS, default=list(AGENTS))
    args = parser.parse_args()
    asyncio.run(main(args.timeout, args.agents))
