"""Legacy adjustment adapters must share the production control path under mocks."""
import unittest
from unittest.mock import AsyncMock, patch

from skills import DesktopSkills, SkillError
from skills import system_control


class AdjustmentRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_volume_routes_consistently_even_with_mock_runner(self):
        skills = DesktopSkills()
        skills._run = AsyncMock()
        for action, expected in [('raise', 'raise'), ('lower', 'lower'), ('mute_toggle', 'toggle')]:
            with self.subTest(action=action), patch.object(system_control, 'set_volume', new_callable=AsyncMock,
                    return_value={'status': 'success'}) as control:
                await skills._adapter_adjust_volume(action, amount=5)
                control.assert_awaited_once_with(percent=None, action=expected, amount=5)
        skills._run.assert_not_awaited()

    async def test_brightness_routes_consistently_even_with_mock_runner(self):
        skills = DesktopSkills()
        skills._run = AsyncMock()
        with patch.object(system_control, 'set_brightness', new_callable=AsyncMock,
                return_value={'status': 'success'}) as control:
            await skills._adapter_adjust_brightness('raise', amount=5)
        control.assert_awaited_once_with(percent=None, direction='raise', amount=5)
        skills._run.assert_not_awaited()

    async def test_adjustment_errors_reach_callers(self):
        skills = DesktopSkills()
        skills._run = AsyncMock()
        for name, call in [('set_volume', lambda: skills._adapter_adjust_volume('raise')),
                           ('set_brightness', lambda: skills._adapter_adjust_brightness('lower'))]:
            with self.subTest(name=name), patch.object(system_control, name, new_callable=AsyncMock,
                    return_value={'status': 'error', 'message': 'synthetic failure'}):
                with self.assertRaisesRegex(SkillError, 'synthetic failure'):
                    await call()
