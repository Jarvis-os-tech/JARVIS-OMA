"""Central model policy; provider billing remains outside the CLI supervisor."""
import os


def apply_model_policy(assignments, profile='budget', environ=None):
    if profile not in ('budget', 'configured'):
        raise ValueError('cost_profile must be budget or configured')
    env = os.environ if environ is None else environ
    defaults = {'codex': 'gpt-5.6-luna', 'claude': 'haiku'}
    result = []
    for assignment in assignments:
        item = dict(assignment)
        agent = item['agent']
        if profile == 'budget':
            model = env.get(f'JARVIS_BUDGET_MODEL_{agent.upper()}', defaults.get(agent, ''))
            if not isinstance(model, str) or not model.strip():
                raise ValueError(
                    f'Set JARVIS_BUDGET_MODEL_{agent.upper()} to a supported budget model '
                    'before starting budget work; no expensive fallback will be selected.')
            model = model.strip()
            if model.startswith('-') or len(model) > 200 or any(ord(c) < 32 for c in model):
                raise ValueError(f'Invalid budget model for {agent}')
            item['model'] = model
            # OpenCode's native TUI deliberately uses its configured model.
            # Budget work requires an explicit per-task model, so select the
            # finite batch route that supports --model before any stage starts.
            if agent == 'opencode':
                item['batch'] = True
        result.append(item)
    return result
