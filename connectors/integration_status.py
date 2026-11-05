"""Live bounded checks; installed/configured never imply account authorization."""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from importlib.util import find_spec
import os
from pathlib import Path
import shutil


async def get_status():
    from connectors import api_anything, credentials
    from connectors.api_service import request
    from connectors.agent_reach import AgentReachClient
    broker, retrieval = await asyncio.gather(request('health', {}), AgentReachClient().is_available())
    cli = Path.home() / '.local/share/jarvis-integrations/venv/bin/cli-hub'
    cli_path = str(cli) if cli.is_file() and os.access(cli, os.X_OK) else shutil.which('cli-hub')
    api_installed = api_anything.CLI_SCRIPT.is_file() and shutil.which(api_anything._resolve_bun()) is not None
    key_present = bool(os.environ.get('COMPOSIO_API_KEY') or credentials.get('COMPOSIO_API_KEY'))
    return {'ok': True, 'status': 'complete', 'checked_at': datetime.now(timezone.utc).isoformat(),
            'scope': 'local_service_readiness_not_account_authorization',
            'services': {
                'api_anything': {'installed': api_installed, 'service_ready': bool(broker and broker.get('ok')),
                    'execution_mode': 'supervised_service' if broker and broker.get('ok') else 'bounded_local_process',
                    'domain': 'api_anything'},
                'cli_anything': {'installed': bool(cli_path), 'executable': cli_path,
                    'domain': 'cli_anything', 'individual_harnesses_verified': False},
                'composio': {'sdk_installed': find_spec('composio') is not None,
                    'configured': key_present, 'domain': 'composio',
                    'authorization': 'check_platform_connection_for_each_platform'},
                'agent_reach': {'service_ready': retrieval, 'scope': 'retrieval_only'},
            },
            'execution_policy': {'automatic_write_replay': False,
                'api_writes': 'explicit allow_writes plus stable request_key; verified readback required',
                'routing': 'Composio account actions; discovered API operations; installed CLI application harnesses; observed GUI when required'}}
