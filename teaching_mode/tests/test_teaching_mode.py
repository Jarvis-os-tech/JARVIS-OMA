"""Tests for Universal Visual Learning & Interactive Teaching Mode."""
import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

import sys
from pathlib import Path

# Add local domain directory to path for standalone execution
domain_dir = Path(__file__).resolve().parent.parent / "domain"
manifest_path = Path(__file__).resolve().parent.parent / "manifest" / "teaching.json"
if str(domain_dir) not in sys.path:
    sys.path.insert(0, str(domain_dir))

from teaching import TeachingDomain, ADAPTERS as TEACHING_ADAPTERS, RESTRICTED_TEACHING_TOOLS
from skills import DesktopSkills, SkillError


class StandaloneTeachingSkills(DesktopSkills, TeachingDomain):
    ADAPTERS = {**DesktopSkills.ADAPTERS, **TEACHING_ADAPTERS}

    async def execute(self, name: str, arguments: dict):
        if self.is_teaching_mode_active() and name in RESTRICTED_TEACHING_TOOLS:
            raise SkillError(
                f"Autonomous actuation tool '{name}' is restricted while in Teaching Mode. "
                "JARVIS is acting as a tutor."
            )
        return await super().execute(name, arguments)


class TeachingModeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.skills = StandaloneTeachingSkills()
        # Load local teaching manifest into declarations
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
        for skill in manifest_data.get("skills", []):
            self.skills._skills[skill["name"]] = skill

        # Mock external shell presentations to avoid calling omarchy-shell in test environment
        self.skills._adapter_show_widget = AsyncMock(return_value={"status": "ok"})
        self.skills._adapter_manage_widget = AsyncMock(return_value={"status": "ok"})
        self.skills._adapter_control_vision_mode = AsyncMock(return_value={"status": "ok", "mode": "screen"})

    async def test_teaching_skills_registered_in_manifest(self):
        declared = {s["name"] for s in self.skills.declarations}
        for skill_name in (
            "activate_teaching_mode",
            "update_teaching_lesson",
            "exit_teaching_mode",
            "teaching_status",
        ):
            self.assertIn(skill_name, declared, f"{skill_name} must be declared in skills registry")

    async def test_activate_teaching_mode_transitions_state(self):
        self.assertFalse(self.skills.is_teaching_mode_active())

        result = await self.skills.execute(
            "activate_teaching_mode",
            {"topic": "Bubble Sort Algorithm"},
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["mode"], "teaching_active")
        self.assertEqual(result["topic"], "Bubble Sort Algorithm")
        self.assertTrue(result["actuation_locked"])
        self.assertTrue(self.skills.is_teaching_mode_active())

        # Verify initial HUD widget was presented
        self.skills._adapter_show_widget.assert_awaited()
        call_kwargs = self.skills._adapter_show_widget.await_args.kwargs
        self.assertEqual(call_kwargs["widget_id"], "teaching_hud")
        self.assertEqual(call_kwargs["presentation"], "floating")
        self.assertEqual(call_kwargs["expires_seconds"], 0)

    async def test_activate_teaching_mode_is_idempotent(self):
        await self.skills.execute("activate_teaching_mode", {"topic": "Asyncio"})
        repeat = await self.skills.execute("activate_teaching_mode", {"topic": "Asyncio"})
        self.assertEqual(repeat["status"], "already_active")
        self.assertTrue(self.skills.is_teaching_mode_active())

    async def test_update_teaching_lesson_updates_hud(self):
        await self.skills.execute("activate_teaching_mode", {"topic": "Binary Search"})

        update_result = await self.skills.execute(
            "update_teaching_lesson",
            {
                "step_number": 1,
                "step_title": "Divide Array",
                "explanation_markdown": "Calculate mid point = (low + high) // 2.",
                "code_snippet": "mid = (low + high) // 2\nif arr[mid] == target: return mid",
                "code_language": "python",
                "suggested_actions": ["Next Step", "Show Example"],
            },
        )

        self.assertEqual(update_result["status"], "ok")
        self.assertEqual(update_result["step"], 1)
        self.assertEqual(update_result["title"], "Divide Array")

        # Verify widget payload contains code snippet and explanation
        call_kwargs = self.skills._adapter_show_widget.await_args.kwargs
        payload = json.loads(call_kwargs["data_json"])
        self.assertIn("layout", payload)
        self.assertEqual(call_kwargs["widget_id"], "teaching_hud")

    async def test_graphviz_dot_diagram_compilation(self):
        await self.skills.execute("activate_teaching_mode", {"topic": "State Machines"})

        dot_source = "digraph G { Idle -> Active [label=\"start\"]; Active -> Idle [label=\"stop\"]; }"
        update_result = await self.skills.execute(
            "update_teaching_lesson",
            {
                "step_number": 2,
                "step_title": "State Flow",
                "explanation_markdown": "Here is the state transition diagram.",
                "diagram_dot": dot_source,
            },
        )

        self.assertEqual(update_result["status"], "ok")
        self.assertTrue(update_result["diagram_rendered"])

        # Should present as kind="image"
        call_kwargs = self.skills._adapter_show_widget.await_args.kwargs
        self.assertEqual(call_kwargs["kind"], "image")
        image_data = json.loads(call_kwargs["data_json"])
        self.assertTrue(image_data["path"].endswith(".png"))

    async def test_pedagogical_guard_intercepts_mutating_actuation(self):
        await self.skills.execute("activate_teaching_mode", {"topic": "Python Functions"})
        self.assertTrue(self.skills.is_teaching_mode_active())

        # Mutating input/actuation tools must be blocked
        with self.assertRaisesRegex(SkillError, "restricted while in Teaching Mode"):
            await self.skills.execute("type_text", {"text": "print('hello')"})

        with self.assertRaisesRegex(SkillError, "restricted while in Teaching Mode"):
            await self.skills.execute("press_key", {"key": "Return"})

        # Perception and read-only tools must remain permitted
        status_res = await self.skills.execute("teaching_status", {})
        self.assertEqual(status_res["status"], "ok")
        self.assertTrue(status_res["active"])
        self.assertEqual(status_res["topic"], "Python Functions")

    async def test_exit_teaching_mode_restores_standard_autonomy(self):
        await self.skills.execute("activate_teaching_mode", {"topic": "Memory Layout"})
        self.assertTrue(self.skills.is_teaching_mode_active())

        # Exit mode
        exit_result = await self.skills.execute("exit_teaching_mode", {"summary": "Great session."})
        self.assertEqual(exit_result["status"], "ok")
        self.assertEqual(exit_result["mode"], "idle")
        self.assertFalse(exit_result["actuation_locked"])
        self.assertFalse(self.skills.is_teaching_mode_active())

        # Verify widget was dismissed
        self.skills._adapter_manage_widget.assert_awaited_with("dismiss", widget_id="teaching_hud")

        # Actuation tools are now unlocked (not blocked by PedagogicalGuard)
        with patch.object(self.skills, "_adapter_type_text", AsyncMock(return_value={"status": "ok"})):
            try:
                await self.skills.execute("type_text", {"text": "hello"})
            except SkillError as e:
                self.assertNotIn("restricted while in Teaching Mode", str(e))

    async def test_visual_mode_detection_and_overlay_calls(self):
        # 1. Bubble Sort auto-detection
        res_sort = await self.skills.execute("activate_teaching_mode", {"topic": "Learn Bubble Sort"})
        self.assertEqual(res_sort["visual_mode"], "bubble_sort")
        await self.skills.execute("exit_teaching_mode", {})

        # 2. Quadcopter auto-detection
        res_drone = await self.skills.execute("activate_teaching_mode", {"topic": "Quadcopter flight control and rotors"})
        self.assertEqual(res_drone["visual_mode"], "quadcopter")
        await self.skills.execute("exit_teaching_mode", {})

        # 3. Arbitrary topic falls back to whiteboard
        res_wb = await self.skills.execute("activate_teaching_mode", {"topic": "Understanding OAuth2 PKCE"})
        self.assertEqual(res_wb["visual_mode"], "whiteboard")
        await self.skills.execute("exit_teaching_mode", {})

    async def test_update_teaching_lesson_visual_action_and_inference(self):
        await self.skills.execute("activate_teaching_mode", {"topic": "Bubble Sort Visualization"})

        # Explicit visual action & data
        res1 = await self.skills.execute(
            "update_teaching_lesson",
            {
                "step_number": 1,
                "step_title": "Compare Adjacent Elements",
                "explanation_markdown": "Compare elements at index 0 and 1.",
                "visual_action": "compare",
                "visual_data": {"indices": [0, 1]},
            },
        )
        self.assertEqual(res1["visual_action"], "compare")

        # Inferred visual action (swap detected from text)
        res2 = await self.skills.execute(
            "update_teaching_lesson",
            {
                "step_number": 2,
                "step_title": "Swap Values",
                "explanation_markdown": "Since left > right, swap them now.",
            },
        )
        self.assertEqual(res2["visual_action"], "swap")

        await self.skills.execute("exit_teaching_mode", {})


if __name__ == "__main__":
    unittest.main()
