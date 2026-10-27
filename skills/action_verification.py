"""Mandatory verification boundary around the registry's GUI mutations."""
from functools import wraps

from skills import ground_truth


VERIFIED_ADAPTERS = frozenset({
    'input.type', 'input.key', 'gui.click_desktop', 'gui.scroll_desktop',
    'gui.click_element', 'gui.type_at', 'gui.key_at', 'window.manage',
})


def verified_desktop_action(owner, adapter, arguments):
    def decorate(dispatch):
        @wraps(dispatch)
        async def guarded():
            gui = owner._gui_control() if adapter.startswith('gui.') else None
            before = await ground_truth.prepare_action_target(arguments, gui)
            if not before.get('verified'):
                return {'status': 'blocked', 'verified': False, 'dispatched': False,
                        'reason': before.get('reason'), 'fallback': 'use_accessibility_or_cli'}
            token = ground_truth.ACTION_TARGET.set(before)
            try:
                result = await dispatch()
            finally:
                ground_truth.ACTION_TARGET.reset(token)
            result = dict(result) if isinstance(result, dict) else {'output': result}
            result['pre_action_verified'] = True
            result['focus_healed'] = before.get('healed', False)
            if result.get('status') in ('error', 'blocked'):
                return result
            if adapter == 'window.manage':
                # manage_window verifies the exact target's requested state,
                # including disappearance on close and scratchpad on minimize.
                result['post_action_verified'] = result.get('verified') is True
                if result.get('verified') is not True:
                    result.update(status='unverified_effect', fallback='use_accessibility_or_cli')
                return result
            from skills import system_control
            after = await system_control._query_active_window()
            target_preserved = ground_truth.same_window(before['window'], after)
            result['post_action_focus_verified'] = target_preserved
            result['verified'] = False  # Focus/surface change alone is not semantic success.
            if not target_preserved or result.get('status') != 'effect_observed':
                result.update(status='unverified_effect', fallback='use_accessibility_or_cli')
                result.setdefault('reason', 'input delivery or requested effect could not be proven')
            return result
        return guarded
    return decorate


async def verify_adapter_action(owner, adapter, arguments, dispatch):
    if adapter not in VERIFIED_ADAPTERS:
        return await dispatch()
    return await verified_desktop_action(owner, adapter, arguments)(dispatch)()
