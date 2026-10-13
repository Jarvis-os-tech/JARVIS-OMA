"""Deterministic and offline tests for the autonomous planner."""
import unittest

from proactive.planner import (
    AGENTS,
    AutonomousPlanner,
    MAX_TASK_CHARS,
    plan_event,
)


class AutonomousPlannerTests(unittest.TestCase):
    def test_accepts_normalized_mapping_and_event_dataclass_shape(self):
        mapping = plan_event({"id": "evt-1", "type": "user_request",
                              "data": {"text": "Fix the failing test"}})
        self.assertEqual(mapping.status, "ready")
        self.assertEqual(mapping.event_type, "task_requested")
        self.assertEqual(mapping.tasks[0].agent, "codex")
        self.assertEqual(mapping.tasks[0].prompt, "Fix the failing test")

        class Event:
            event_type = "task_requested"
            timestamp = 5.0
            data = {"prompt": "Research current API behavior"}

        event_plan = plan_event(Event())
        self.assertEqual(event_plan.tasks[0].agent, "gemini")

    def test_explicit_routes_cover_each_supported_agent(self):
        planner = AutonomousPlanner()
        for index, agent in enumerate(AGENTS):
            with self.subTest(agent=agent):
                result = planner.plan({"event_id": f"route-{index}", "event_type": "task",
                                       "data": {"prompt": "Do this task", "agent": agent}})
                self.assertEqual(result.tasks[0].agent, agent)
                self.assertEqual(result.tasks[0].routing_reason, "explicit agent selection")

    def test_keyword_routes_are_ordered_and_deterministic(self):
        samples = [
            ("Click the desktop window and inspect the screen", "hermes"),
            ("Research and compare sources about this", "gemini"),
            ("Security review of the repository", "claude"),
            ("Coordinate multiple agents", "omp"),
            ("Use OpenCode to build this", "opencode"),
            ("Implement a feature in this repository", "codex"),
        ]
        for index, (prompt, expected) in enumerate(samples):
            with self.subTest(prompt=prompt):
                plan = plan_event({"event_id": f"keyword-{index}", "event_type": "task",
                                   "data": {"prompt": prompt}})
                self.assertEqual(plan.tasks[0].agent, expected)

    def test_bounded_steps_prompt_size_and_depth(self):
        planner = AutonomousPlanner(max_steps=2, max_depth=2)
        many_tasks = [{"prompt": f"task {index}"} for index in range(10)]
        result = planner.plan({"event_id": "bounded", "event_type": "task", "depth": 2,
                               "data": {"tasks": many_tasks}})
        self.assertEqual(len(result.tasks), 2)
        self.assertTrue(all(task.depth == 2 for task in result.tasks))

        deep = planner.plan({"event_id": "too-deep", "event_type": "task", "depth": 3,
                             "data": {"prompt": "Should not be planned"}})
        self.assertEqual(deep.status, "blocked")
        self.assertIn("depth", deep.reason)

        long_plan = plan_event({"event_id": "long", "event_type": "task",
                                "data": {"prompt": "x" * (MAX_TASK_CHARS + 100)}})
        self.assertEqual(len(long_plan.tasks[0].prompt), MAX_TASK_CHARS)

    def test_loop_duplicate_and_explicit_reset(self):
        planner = AutonomousPlanner()
        loop = planner.plan({"event_id": "loop", "event_type": "task", "ancestry": ["loop"],
                             "data": {"prompt": "loop"}})
        self.assertEqual(loop.status, "blocked")

        event = {"event_id": "repeat", "event_type": "task", "data": {"prompt": "Do work"}}
        self.assertEqual(planner.plan(event).status, "ready")
        self.assertEqual(planner.plan(event).status, "ignored")
        planner.clear_seen()
        self.assertEqual(planner.plan(event).status, "ready")

    def test_non_actionable_and_malformed_tasks_are_ignored(self):
        self.assertEqual(plan_event({"id": "system", "type": "heartbeat", "data": {}}).status,
                         "ignored")
        malformed = plan_event({"id": "bad-task", "type": "task",
                                "data": {"tasks": [None, {"prompt": "x", "agent": "unknown"}]}})
        self.assertEqual(malformed.status, "ignored")
        self.assertEqual(malformed.tasks, ())

    def test_plan_is_serializable_and_stable(self):
        event = {"event_id": "stable", "event_type": "task_requested",
                 "data": {"title": "Build", "prompt": "Build a feature"}}
        first = plan_event(event)
        second = plan_event(event)
        self.assertEqual(first.as_dict(), second.as_dict())
        self.assertEqual(first.status, "ready")
        self.assertIsInstance(first.as_dict()["tasks"], list)

    def test_limits_cannot_be_configured_above_safe_ceilings(self):
        for kwargs in ({"max_steps": 9}, {"max_depth": 4}, {"seen_limit": 513},
                       {"max_steps": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                AutonomousPlanner(**kwargs)


if __name__ == "__main__":
    unittest.main()
