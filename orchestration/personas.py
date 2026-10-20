"""User-defined system-agent responsibilities and autonomous workflow."""

PERSONAS = {
    'hermes': {'role': 'Researcher and planner', 'core': True},
    'codex': {'role': 'Development engineer', 'core': True},
    'claude': {'role': 'Developer, reviewer and final tester', 'core': True},
    'antigravity': {'role': 'Development engineer', 'core': True},
    'opencode': {'role': 'Independent test engineer', 'core': True},
    'gemini': {'role': 'Optional research specialist', 'core': False},
    'omp': {'role': 'Optional coordination specialist', 'core': False},
    'pi': {'role': 'Optional development assistant', 'core': False},
    'crush': {'role': 'Optional development assistant', 'core': False},
}


def software_assignments(executables):
    """Require the core gates; select an installed development executor."""
    # Codex is temporarily excluded at the user's request.
    developer = 'claude' if executables.get('claude') else None
    missing = [name for name in ('hermes', 'opencode', 'claude') if not executables.get(name)]
    if missing or developer is None:
        raise ValueError('Autonomous workflow requires installed agents: ' + ', '.join(missing or ['claude']))
    return [
        {'agent': 'hermes', 'visible': True, 'batch': False, 'yolo': True, 'prompt':
         'Research the goal and inspect the project. Produce a concrete implementation plan, '
         'acceptance criteria and test strategy. Do not change application source.'},
        {'agent': developer, 'visible': True, 'batch': False, 'yolo': True, 'prompt':
         'Implement the goal using the preceding research and plan. Preserve unrelated edits. '
         'Run relevant checks and report changed files and limitations.'},
        {'agent': 'opencode', 'visible': True, 'batch': False, 'yolo': True, 'prompt':
         'Independently test the implementation against the goal and acceptance criteria. '
         'Run relevant tests, investigate failures and add regression tests where needed. '
         'Report exact evidence and remaining defects; do not claim success without checks.'},
        {'agent': 'claude', 'visible': True, 'batch': False, 'yolo': True, 'prompt':
         'Review implementation and independent QA evidence. Fix remaining defects within scope, '
         'rerun affected tests and perform final verification. Report unresolved issues explicitly. '
         'Do not publish, deploy or merge changes unless the original user request authorizes it.'},
    ]
