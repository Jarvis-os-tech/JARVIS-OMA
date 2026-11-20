import pytest
from unittest.mock import Mock
from jarvis_control.tools import Executor, Result
from jarvis_control.config import Config


@pytest.mark.parametrize("name", ["Antigravity", "ANTIGRAVITY", "antigravity.desktop"])
def test_launch_resolves_display_case_without_selecting_other_app(monkeypatch, name):
    monkeypatch.setattr('jarvis_control.tools._desktop_entry_exists', lambda name: name in {'antigravity', 'antigravity-ide'})
    monkeypatch.setattr('jarvis_control.discovery.applications', lambda: [('antigravity', 'Antigravity'), ('antigravity-ide', 'Antigravity IDE')])
    monkeypatch.setattr('jarvis_control.tools.shutil.which', lambda name: '/usr/bin/gtk-launch')
    executor = Executor(Config())
    executor._shell = Mock(return_value=Result(False, 'test launch stopped'))
    executor._tool_launch_app(name)
    assert executor._shell.call_args.args[0] == ['/usr/bin/gtk-launch', 'antigravity.desktop']


def test_catalog_respects_hidden_override_and_nested_entries(tmp_path, monkeypatch):
    from skills.skills import DesktopSkills
    user = tmp_path / 'user'
    system = tmp_path / 'system'
    for root in (user, system):
        (root / 'applications').mkdir(parents=True)
    (system / 'applications/old.desktop').write_text('[Desktop Entry]\nType=Application\nName=Old\nExec=old\n')
    (user / 'applications/old.desktop').write_text('[Desktop Entry]\nHidden=true\n')
    nested = user / 'applications/vendor'
    nested.mkdir()
    (nested / 'editor.desktop').write_text('[Desktop Entry]\nType=Application\nName=Editor\nExec=editor\n')
    monkeypatch.setenv('XDG_DATA_HOME', str(user))
    monkeypatch.setenv('XDG_DATA_DIRS', str(system))
    skills = DesktopSkills.__new__(DesktopSkills)
    assert skills._applications() == {'vendor-editor.desktop': 'Editor'}
