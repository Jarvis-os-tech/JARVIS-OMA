import shlex
import subprocess

import pytest

from jarvis_control.phone_control import PhoneController, save_link, launcher_components
from jarvis_control.tools import Executor, tools_for
from jarvis_control.config import Config


def test_launcher_discovery_accepts_real_android_indented_output():
    output = '''2 activities found:
  Activity #0:
    priority=0 preferredOrder=0 match=0x108000 specificIndex=-1 isDefault=true
    com.android.chrome/com.google.android.apps.chrome.Main
  Activity #1:
    priority=0 preferredOrder=0 match=0x108000 specificIndex=-1 isDefault=true
    com.vivo.calculator/.Calculator
'''
    assert launcher_components(output) == ['com.android.chrome/com.google.android.apps.chrome.Main', 'com.vivo.calculator/.Calculator']
    assert launcher_components('    com.example.app/.Main$Nested\n') == ['com.example.app/.Main$Nested']


def test_launcher_query_returns_packages_to_the_voice_model(tmp_path):
    path = tmp_path / 'link.json'
    save_link('10.0.0.2:5555', 'serial', 'Phone', path)
    def runner(command, **kwargs):
        output = b'serial' if command[-1] == 'getprop ro.serialno' else b'1 activities found:\n  Activity #0:\n    com.vivo.calculator/.Calculator\n'
        return subprocess.CompletedProcess(command, 0, output, b'')
    result = PhoneController(path, runner).execute('list_apps')
    assert result['packages'] == ['com.vivo.calculator']


def test_wireless_adapter_quotes_remote_text_and_never_uses_implicit_usb(tmp_path):
    path = tmp_path / 'link.json'
    save_link('10.0.0.2:5555', 'phone-serial', 'Test Phone', path)
    commands = []
    def runner(command, **kwargs):
        commands.append(command)
        output = b'phone-serial\n' if command[-1] == 'getprop ro.serialno' else b''
        return subprocess.CompletedProcess(command, 0, output, b'')
    controller = PhoneController(path, runner)
    text = 'hello; $(touch /tmp/not-real) `echo test` "quotes"'
    controller.execute('type_text', text=text)
    assert all(command[:3] == ['adb', '-s', '10.0.0.2:5555'] for command in commands)
    assert shlex.split(commands[-1][-1]) == ['input', 'text', text.replace(' ', '%s')]
    assert path.stat().st_mode & 0o777 == 0o600


def test_rejects_changed_phone_identity_before_any_action(tmp_path):
    path = tmp_path / 'link.json'
    save_link('10.0.0.2:5555', 'expected', 'Phone', path)
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, b'other-phone', b'')
    with pytest.raises(ValueError, match='identity changed'):
        PhoneController(path, runner).execute('press_key', key='HOME')
    assert len(calls) == 1


@pytest.mark.parametrize('action,args', [
    ('shell', {'command': 'anything'}), ('open_app', {'package_name': 'x.y;reboot'}),
    ('open_url', {'url': 'file:///data'}), ('open_url', {'url': 'https://user:secret@example.com'}),
    ('press_key', {'key': 'CALL'}), ('tap', {'x': True, 'y': 100}),
    ('swipe', {'x': 1, 'y': 2, 'end_x': 3, 'end_y': 4, 'duration_ms': 100000}),
    ('status', {'command': 'ignored shell command'}),
])
def test_rejects_unapproved_actions_and_bad_arguments(action, args):
    with pytest.raises(ValueError):
        PhoneController.validate(action, **args)


def test_phone_actions_use_existing_executor_policy_and_dry_run():
    executor = Executor(Config(dry_run=True))
    result = executor.call('phone_control', {'action': 'press_key', 'key': 'HOME'})
    assert result.ok and '[dry-run]' in result.output
    assert not executor.call('phone_control', {'action': 'press_key', 'key': 'CALL'}).ok
    assert any(tool['name'] == 'phone_control' for tool in tools_for(Config()))
    assert 'private text' not in executor.describe('phone_control', {'action': 'type_text', 'text': 'private text'})


def test_explicit_mobile_call_reuses_signed_native_phone_adapter(tmp_path):
    import base64
    import hashlib
    import hmac
    import json
    path = tmp_path / 'phone_link.json'
    save_link('10.0.0.2:5555', 'serial', 'Phone', path)
    token = 'x' * 64
    (tmp_path / 'pairing_credentials.json').write_text(json.dumps({'auth_token': token}))
    observed = []
    def runner(command, **kwargs):
        if command[-1] == 'getprop ro.serialno':
            return subprocess.CompletedProcess(command, 0, b'serial', b'')
        words = shlex.split(command[-1])
        values = {words[index + 1]: words[index + 2] for index in range(len(words) - 2) if words[index] == '--es'}
        body = json.loads(base64.urlsafe_b64decode(values['payload']))
        assert values['signature'] == hmac.new(token.encode(), values['payload'].encode(), hashlib.sha256).hexdigest()
        observed.append(body)
        reply = base64.urlsafe_b64encode(json.dumps({'device': 'phone', 'status': 'call_requested'}).encode()).decode()
        return subprocess.CompletedProcess(command, 0, f'Broadcast completed: result=0, data="{reply}"'.encode(), b'')
    result = PhoneController(path, runner).execute('call_contact', recipient='Test Person')
    assert result['status'] == 'call_requested'
    assert observed[0]['tool'] == 'phone_call_contact'
    assert observed[0]['args'] == {'recipient': 'Test Person'}
