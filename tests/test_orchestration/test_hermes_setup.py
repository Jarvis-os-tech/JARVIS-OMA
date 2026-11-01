from pathlib import Path
import os

import pytest

from orchestration.hermes_setup import configured, assert_offline, atomic_text


def test_fresh_configuration_keeps_credentials_model_and_skills_untouched(tmp_path):
    original = {'model':{'provider':'example','default':'existing-model'},
                'memory':{'provider':'cognee'},
                'mcp_servers':{'cognee':{'url':'http://local'}, 'context7':{'command':'docs'}},
                'approvals':{'mode':'smart'}, 'custom_setting':'keep'}
    updated, disconnected = configured(original, tmp_path, tmp_path / 'python')
    assert updated['memory']['provider'] == 'builtin'
    assert original['memory']['provider'] == 'cognee'
    assert updated['model'] == original['model']
    assert updated['approvals'] == original['approvals']
    assert updated['custom_setting'] == 'keep'
    assert updated['mcp_servers']['cognee']['enabled'] is False
    assert updated['mcp_servers']['context7'] == original['mcp_servers']['context7']
    assert disconnected == ['cognee']
    assert updated['mcp_servers']['jarvis_orchestrator']['args'][0] == '-I'
    assert updated['delegation']['subagent_auto_approve'] is False


def test_reset_refuses_running_gateway_and_atomic_text_is_private(tmp_path):
    (tmp_path / 'gateway.pid').write_text(str(os.getpid()))
    with pytest.raises(ValueError, match='Stop the Hermes gateway'):
        assert_offline(tmp_path)
    atomic_text(tmp_path / 'new-memory', '')
    assert (tmp_path / 'new-memory').stat().st_mode & 0o777 == 0o600
