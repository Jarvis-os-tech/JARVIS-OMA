import subprocess
from pathlib import Path
import pytest
from orchestration.goal_workspaces import project_workspace


def git(root,*args):
    return subprocess.run(['git','-C',str(root),*args],check=True,capture_output=True)


def test_project_snapshot_preserves_working_edits_and_original_checkout(tmp_path):
    source=tmp_path/'project';source.mkdir()
    git(source,'init','--quiet');(source/'app.py').write_text('value=1\n')
    git(source,'add','app.py');git(source,'-c','user.name=Test','-c','user.email=test@localhost','-c','commit.gpgsign=false','commit','-qm','Base')
    (source/'app.py').write_text('value=2\n')
    (source/'input.txt').write_text('Requested input')
    workspace,rev=project_workspace(tmp_path/'tasks/isolated',source,['input.txt'])
    path=Path(workspace)
    assert (path/'.git').is_file() and len(rev)==40
    assert (path/'app.py').read_text()=='value=2\n'
    assert (path/'input.txt').read_text()=='Requested input'
    (path/'app.py').write_text('value=3\n')
    assert (source/'app.py').read_text()=='value=2\n'


def test_credential_inputs_are_rejected_before_worker_launch(tmp_path):
    source=tmp_path/'project';source.mkdir();git(source,'init','--quiet')
    git(source,'-c','user.name=Test','-c','user.email=test@localhost','-c','commit.gpgsign=false','commit','--allow-empty','-qm','Base')
    (source/'.env').write_text('PRIVATE=example')
    with pytest.raises(ValueError,match='Credential'):
        project_workspace(tmp_path/'tasks/isolated',source,['.env'])
