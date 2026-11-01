"""Registry-to-readback acceptance fixtures, without live desktop input/audio."""
import copy
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from core.config import Config
from skills import DesktopSkills, ground_truth, system_control
from skills.gui_control import GuiControl, GuiControlError
import filesystem.filesystem as files


@pytest_asyncio.fixture
async def desktop(monkeypatch, tmp_path):
    config = Config()
    config.memory.enabled = False
    skills = DesktopSkills(config=config)
    skills._command = lambda name: '/fixture/' + name
    monkeypatch.setattr(system_control.shutil, 'which', lambda name: '/fixture/' + name)
    window = {'address': '0x123', 'pid': 42, 'class': 'editor', 'title': 'Project notes',
              'workspace': {'id': 1}, 'fullscreen': 0, 'floating': False}
    state = {'before': window, 'after': copy.deepcopy(window), 'workspace': 1, 'target_workspace': 2,
             'dispatched': False, 'clients': None}

    async def observe(_binary, query):
        if query == 'activewindow':
            value = state['before']
        elif query == 'clients':
            value = state['clients'] if state['clients'] is not None else [state['after']]
        elif query == 'workspaces':
            value = [{'id': n} for n in (1, 2, 3)]
        elif query == 'activeworkspace':
            value = {'id': state['target_workspace'] if state['dispatched'] else state['workspace']}
        else:
            raise AssertionError(query)
        return {'status': 'success', 'data': copy.deepcopy(value), 'source': 'fixture ' + query, 'observed_at': 'fresh'}

    async def dispatch(*_args, **_kwargs):
        state['dispatched'] = True
        return {'status': 'executed'}

    monkeypatch.setattr(system_control, '_desktop_observe', observe)
    monkeypatch.setattr(system_control, '_desktop_dispatch', AsyncMock(side_effect=dispatch))
    monkeypatch.setattr(system_control, '_query_open_windows', AsyncMock(return_value=[window]))
    monkeypatch.setattr(system_control, '_query_active_window', AsyncMock(return_value=window))
    monkeypatch.setattr(system_control, '_run_command', AsyncMock(return_value=(0, '', '')))
    monkeypatch.setattr(skills, '_launch', AsyncMock())
    monkeypatch.setattr(skills, '_applications', lambda: {'editor.desktop': 'Editor'})
    gui = GuiControl('/fixture/driver')
    gui._browser_tabs['browser'] = {'tab'}
    gui._call = AsyncMock(return_value={'tab_id': 'tab', 'url': 'https://example.com/'})
    monkeypatch.setattr(skills, '_gui_control', lambda: gui)
    try:
        yield skills, state, gui, tmp_path
    finally:
        await skills.close_agent_jobs()


CASES = ['focus_address', 'focus_class', 'focus_title', 'open_application',
         'switch_workspace', 'next_workspace', 'previous_workspace', 'move_window',
         'move_unchanged', 'fullscreen', 'maximize', 'float', 'make_directory',
         'write_file', 'append_file', 'edit_file', 'copy_file', 'move_file',
         'browser_https', 'browser_blank']


@pytest.mark.asyncio
@pytest.mark.parametrize('trial', range(3))
@pytest.mark.parametrize('case', CASES)
async def test_twenty_workflows_across_three_fixture_trials(desktop, case, trial):
    skills, state, gui, root = desktop
    path = root / f'notes-{trial}.txt'
    expected = f'Independent trial {trial}: café\nsecond line'
    state['before']['pid'] += trial
    state['after']['pid'] += trial
    if case.startswith('focus_'):
        query = {'focus_address': '0x123', 'focus_class': 'editor', 'focus_title': 'Project notes'}[case]
        result = await skills.execute('focus_window', {'query': query})
        assert ground_truth.same_window(result['window'], state['before'])
    elif case == 'open_application':
        result = await skills.execute('open_application', {'name': 'Editor'})
        skills._launch.assert_awaited_once()
    elif case in ('switch_workspace', 'next_workspace', 'previous_workspace'):
        target = {'switch_workspace': 2, 'next_workspace': 'next', 'previous_workspace': 'previous'}[case]
        state['target_workspace'] = 3 if case == 'previous_workspace' else 2
        result = await skills.execute('switch_workspace', {'workspace': target})
        assert result['target_workspace'] == state['target_workspace']
    elif case in ('move_window', 'move_unchanged'):
        target = 1 if case == 'move_unchanged' else 2 + trial
        state['after']['workspace']['id'] = target
        result = await skills.execute('move_window_to_workspace', {'workspace': target})
        assert result['workspace'] == target
        assert result['executed'] is (case != 'move_unchanged')
    elif case in ('fullscreen', 'maximize', 'float'):
        state['after'].update({'floating': True} if case == 'float' else
                              {'fullscreen': 2 if case == 'fullscreen' else 1})
        result = await skills.execute('manage_window', {'action': case})
        assert result['post_action_verified']
    elif case == 'make_directory':
        result = await skills.execute('make_directory', {'path': str(root / 'new-directory')})
        assert (root / 'new-directory').is_dir()
    elif case in ('write_file', 'append_file', 'edit_file'):
        if case != 'write_file':
            path.write_text('prefix' if case == 'append_file' else 'old content')
        args = {'path': str(path), **({'old': 'old content', 'new': expected} if case == 'edit_file'
                                     else {'content': expected})}
        result = await skills.execute(case, args)
        assert path.read_text() == ('prefix' if case == 'append_file' else '') + expected
    elif case in ('copy_file', 'move_file'):
        path.write_text(expected)
        destination = root / f'new-{trial}.txt'
        result = await skills.execute('copy_path' if case == 'copy_file' else 'move_path',
            {'source': str(path), 'destination': str(destination)})
        assert destination.read_text() == expected
        assert path.exists() is (case == 'copy_file')
    else:
        url = 'https://example.com/' if case == 'browser_https' else 'about:blank'
        gui._call.return_value = {'tab_id': 'tab', 'url': url}
        result = await skills.execute('gui_browser_navigate', {'target_id': 'browser', 'tab_id': 'tab', 'url': url})
        assert result['evidence']['observed_url'] == url
    assert result['verified'] is True, result
    assert result['evidence']['source'] and result['evidence']['observed_at']


@pytest.mark.asyncio
async def test_ambiguous_focus_sends_no_command(desktop, monkeypatch):
    skills, state, _, _ = desktop
    windows = [state['before'], {**state['before'], 'address': '0x456', 'pid': 99}]
    monkeypatch.setattr(system_control, '_query_open_windows', AsyncMock(return_value=windows))
    result = await skills.execute('focus_window', {'query': 'editor'})
    assert not result['verified'] and 'ambiguous' in result['reason']
    system_control._run_command.assert_not_awaited()


@pytest.mark.asyncio
async def test_wrong_active_identity_is_never_focused(desktop, monkeypatch):
    skills, state, _, _ = desktop
    from skills import modal_healing
    monkeypatch.setattr(system_control, '_query_active_window', AsyncMock(return_value={**state['before'], 'pid': 99}))
    monkeypatch.setattr(modal_healing, 'heal_window_focus', AsyncMock(return_value={'recovered': False}))
    result = await skills.execute('focus_window', {'query': 'editor'})
    assert result['status'] == 'unverified' and not result['verified']


@pytest.mark.asyncio
@pytest.mark.parametrize('clients', [[], [{'address': '0x123', 'pid': 99, 'workspace': {'id': 2}}],
                                   [{'address': '0x123', 'workspace': {'id': 2}}],
                                   [{'address': '0x123', 'pid': 42, 'workspace': {'id': 3}}]])
async def test_move_requires_exact_window_and_workspace(desktop, clients):
    skills, state, _, _ = desktop
    state['clients'] = clients
    result = await skills.execute('move_window_to_workspace', {'workspace': 2})
    assert result['status'] == 'unverified' and not result['verified']
    system_control._desktop_dispatch.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('clients', [[], [{'address': '0x777', 'pid': 11, 'class': 'terminal', 'title': 'editor'}]])
async def test_process_or_title_cannot_prove_application_window(desktop, clients):
    skills, state, _, _ = desktop
    state['clients'] = clients
    result = await skills.execute('open_application', {'name': 'Editor'})
    assert result['status'] == 'unverified' and not result['verified']
    skills._launch.assert_awaited_once()


@pytest.mark.asyncio
async def test_cold_application_can_appear_after_initial_readback_window(desktop, monkeypatch):
    skills, state, _, _ = desktop
    observe = AsyncMock(side_effect=[
        *[{'status': 'success', 'data': [], 'source': 'fixture clients', 'observed_at': 'early'} for _ in range(8)],
        {'status': 'success', 'data': [state['after']], 'source': 'fixture clients', 'observed_at': 'ready'},
    ])
    monkeypatch.setattr(system_control, '_desktop_observe', observe)
    result = await skills.execute('open_application', {'name': 'Editor'})
    assert result['verified'] and result['evidence']['observed_at'] == 'ready'
    skills._launch.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('snapshot', [
    {'tabs': [{'tab_id': 'other', 'url': 'https://example.com/'}]},
    {'tab_id': 'tab', 'url': 'https://example.com/login'},
    {'target_id': 'other-browser', 'tab_id': 'tab', 'url': 'https://example.com/'},
    {'tabs': None},
])
async def test_navigation_requires_bound_tab_url(desktop, snapshot):
    skills, _, gui, _ = desktop
    gui._call.return_value = snapshot
    result = await skills.execute('gui_browser_navigate', {'target_id': 'browser', 'tab_id': 'tab', 'url': 'https://example.com/'})
    assert not result['verified'] and result['status'] == 'dispatched_unverified'
    assert sum(call.args[0] == 'browser_navigate' for call in gui._call.await_args_list) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('url', ['https://example.com:bad/', 'https:///missing-host', 'https://user:pass@example.com/'])
async def test_invalid_navigation_never_dispatches(desktop, url):
    _, _, gui, _ = desktop
    with pytest.raises(GuiControlError):
        await gui.browser_navigate('browser', 'tab', url)
    gui._call.assert_not_awaited()


@pytest.mark.asyncio
async def test_website_launcher_is_not_page_verification(desktop):
    skills, _, _, _ = desktop
    result = await skills.execute('open_website', {'url': 'https://example.com/'})
    assert result['status'] == 'dispatched_unverified' and not result['verified']


@pytest.mark.asyncio
async def test_delayed_page_readback_never_repeats_navigation(desktop):
    skills, _, gui, _ = desktop
    gui._call.side_effect = [
        {'effect': 'accepted'}, {'tab_id': 'tab', 'url': 'about:blank'},
        {'tab_id': 'tab', 'url': 'https://example.com/'},
    ]
    result = await skills.execute('gui_browser_navigate', {
        'target_id': 'browser', 'tab_id': 'tab', 'url': 'https://example.com/'})
    assert result['verified'] and result['evidence']['observed_url'] == 'https://example.com/'
    assert sum(call.args[0] == 'browser_navigate' for call in gui._call.await_args_list) == 1


@pytest.mark.asyncio
async def test_application_identity_uses_desktop_startup_class(tmp_path, monkeypatch):
    directory = tmp_path / 'applications'
    directory.mkdir()
    (directory / 'org.example.Editor.desktop').write_text(
        '[Desktop Entry]\nType=Application\nName=Example Editor\nExec=example-editor\nStartupWMClass=ExampleEditorClass\n')
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path))
    monkeypatch.setenv('XDG_DATA_DIRS', str(tmp_path / 'empty'))
    config = Config()
    config.memory.enabled = False
    skills = DesktopSkills(config=config)
    skills._command = lambda name: '/fixture/' + name
    skills._launch = AsyncMock()
    monkeypatch.setattr(system_control.shutil, 'which', lambda name: '/fixture/' + name)
    monkeypatch.setattr(system_control, '_desktop_observe', AsyncMock(return_value={
        'status': 'success', 'source': 'fixture clients', 'observed_at': 'fresh',
        'data': [{'address': '0x123', 'pid': 42, 'class': 'ExampleEditorClass'}],
    }))
    try:
        result = await skills.execute('open_application', {'name': 'Example Editor'})
        assert result['verified'] and result['window']['pid'] == 42
    finally:
        await skills.close_agent_jobs()


@pytest.mark.parametrize('operation', ['copy', 'move'])
def test_noop_filesystem_command_cannot_prove_success(tmp_path, monkeypatch, operation):
    source, destination = tmp_path / 'original', tmp_path / 'destination'
    source.write_text('expected')
    monkeypatch.setattr(files.shutil, 'copy2' if operation == 'copy' else 'move', lambda *_args: None)
    result = (files.copy_path if operation == 'copy' else files.move_path)(str(source), str(destination))
    assert result['status'] == 'unverified' and not result['verified']


def test_noop_atomic_write_does_not_prove_content(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'replace', lambda *_args: None)
    result = files.write_text(str(tmp_path / 'missing'), 'expected')
    assert result['status'] == 'unverified' and not result['verified']


def test_large_file_copy_is_not_falsely_certified(tmp_path, monkeypatch):
    monkeypatch.setattr(files, 'VERIFY_MAX_BYTES', 4)
    source, destination = tmp_path / 'source', tmp_path / 'destination'
    source.write_bytes(b'larger than verification limit')
    result = files.copy_path(str(source), str(destination))
    assert destination.read_bytes() == source.read_bytes()
    assert not result['verified'] and result['status'] == 'unverified'


@pytest.mark.asyncio
async def test_task_stops_after_unverified_file_effect(tmp_path):
    import asyncio
    import json
    from filesystem.task_runner import TaskRunner
    execute = AsyncMock(return_value={'status': 'unverified', 'verified': False})
    runner = TaskRunner(execute, lambda *_args: True)
    try:
        task = runner.start('verified task', json.dumps([
            {'tool': 'write_file', 'args': {'path': str(tmp_path / 'first'), 'content': 'one'}},
            {'tool': 'write_file', 'args': {'path': str(tmp_path / 'second'), 'content': 'two'}},
        ]))
        await asyncio.gather(*list(runner._workers.values()))
        status = runner.status(task['id'])
        assert status['status'] == 'failed' and status['completed_steps'] == 0
        assert status['steps'][0]['result']['verified'] is False
        execute.assert_awaited_once()
    finally:
        await runner.close()
