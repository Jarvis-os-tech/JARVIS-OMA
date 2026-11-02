"""Approved project snapshots for Hermes; native worktrees remain real Git worktrees."""
from pathlib import Path
import os
import subprocess

from core.secret_env import sanitized_subprocess_env
from jarvis_control.workspace_files import open_file


def project_workspace(target, source, inputs=()):
    target, source = Path(target), Path(source).resolve(strict=True)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    env = {k:v for k,v in sanitized_subprocess_env().items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null', GIT_TERMINAL_PROMPT='0')
    def git(root, *args, data=None):
        result = subprocess.run(['/usr/bin/git','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false',
                                 '-C',str(root),*args],input=data,capture_output=True,timeout=30,env=env,check=True)
        return result.stdout
    revision = git(source, 'rev-parse','HEAD').decode().strip()
    git(source,'worktree','add','--detach',str(target),revision)
    patch = git(source,'diff','--binary','--no-ext-diff','--no-textconv',revision,'--')
    if len(patch) > 8*1024*1024:
        raise ValueError('Project patch exceeds input budget; choose narrower inputs')
    if patch:
        git(target,'apply','--binary','-',data=patch)
    total=0
    for relative in inputs:
        path=Path(relative)
        if path.name.startswith('.env') or path.suffix.lower() in {'.pem','.key'} or any(p in {'.git','.ssh','.aws','.secrets'} for p in path.parts):
            raise ValueError('Credential or runtime metadata files are not task inputs')
        with open_file(source,relative) as stream:
            raw=stream.read(16*1024*1024+1)
        total+=len(raw)
        if len(raw)>16*1024*1024 or total>32*1024*1024:
            raise ValueError('Project inputs exceed their byte budget')
        destination=(target/relative).resolve()
        if not destination.is_relative_to(target.resolve()):
            raise ValueError('Input destination leaves task workspace')
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(raw)
    target.chmod(0o700)
    return str(target), revision
