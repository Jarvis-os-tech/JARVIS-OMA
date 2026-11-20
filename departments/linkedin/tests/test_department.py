"""Tests for the LinkedIn Department in JARVIS OS."""

import json
from pathlib import Path
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from departments.linkedin.config import LinkedInConfig
from departments.linkedin.agents import AGENT_REGISTRY
from departments.linkedin.department import LinkedInDepartment


class TestLinkedInDepartment(unittest.TestCase):

    def setUp(self):
        self.dept = LinkedInDepartment()

    def test_configuration_and_paths(self):
        self.assertIsNotNone(self.dept.cfg.state_dir)
        self.assertTrue(self.dept.cfg.state_dir.exists())
        self.assertTrue(self.dept.cfg.references_dir.exists())
        self.assertTrue(self.dept.cfg.review_queue_dir.exists())

    def test_agent_registry(self):
        self.assertEqual(len(AGENT_REGISTRY), 12)
        for i in range(1, 13):
            key = f"A{i}"
            self.assertIn(key, AGENT_REGISTRY)

    def test_approved_image_publishes_through_scheduler_once(self):
        from departments.linkedin.tools import LinkedInTools

        with TemporaryDirectory() as folder:
            root = Path(folder)
            image = root / "certificate.png"
            image.touch()
            tools = LinkedInTools()
            tools._author_urn = "urn:li:person:fixture"
            dept = LinkedInDepartment(LinkedInConfig(base_dir=root), tools=tools)
            draft = dept.a12_scheduler.execute({"post_draft": "Approved text", "formula_code": "F7"})
            post_id = draft.output["post_id"]
            uploaded = {"name": image.name, "mimetype": "image/png", "s3key": "fixture-key"}
            with patch("connectors.composio.get_client"), patch(
                "composio.core.models._files.FileUploadable.from_path",
                return_value=Mock(model_dump=Mock(return_value=uploaded)),
            ) as upload, patch("connectors.composio.execute_tool", return_value={
                "success": True, "data": {"x_restli_id": "urn:li:share:fixture"},
            }) as execute:
                result = dept.publish_post(post_id, image_path=str(image))
                self.assertEqual(result["status"], "PUBLISHED_LIVE")
                self.assertFalse(dept.publish_post(post_id, image_path=str(image))["success"])
                upload.assert_called_once()
                execute.assert_called_once_with("LINKEDIN_CREATE_LINKED_IN_POST", {
                    "author": tools._author_urn, "commentary": "Approved text",
                    "visibility": "PUBLIC", "images": [uploaded],
                })

    def test_custom_client_config_and_auth_failure_stop_fallback(self):
        cfg = LinkedInConfig(api_key="test-key", max_retries=3)
        client = LinkedInDepartment(cfg).a3_writer.client
        self.assertIs(client.cfg, cfg)
        with patch("departments.linkedin.nim_client.requests.post",
                   return_value=Mock(status_code=401)) as post:
            result = client.generate([{"role": "user", "content": "test"}])
        self.assertFalse(result.success)
        self.assertIn("401", result.error)
        post.assert_called_once()

    def test_tools_integration_and_author_urn(self):
        self.assertIsNotNone(self.dept.tools)
        # Should have a valid author urn resolver
        author = self.dept.tools.resolve_author_urn()
        self.assertIsNotNone(author)
        self.assertTrue(author.startswith("urn:li:person:"))

    def test_stager_and_approval_flow(self):
        # Test A12 Staging directly with synthetic post
        test_post = "We spent 3 months rebuilding our multi-agent orchestrator.\nHere is what broke and what we learned."
        res = self.dept.a12_scheduler.execute({
            "post_draft": test_post,
            "scheduled_date": "2026-11-10 09:00",
            "pillar": "Authority & Build Logs",
            "formula_code": "F7",
            "humanizer_metadata": {"authenticity_pass": True, "flagged_markers": []},
            "media_prompt": "System diagram",
        })

        self.assertTrue(res.success)
        post_id = res.metadata["post_id"]

        # Verify staged in review queue
        json_file = self.dept.cfg.review_queue_dir / f"{post_id}.json"
        md_file = self.dept.cfg.review_queue_dir / f"{post_id}.md"

        self.assertTrue(json_file.exists())
        self.assertTrue(md_file.exists())

        # Check pending reviews list
        pending = self.dept.get_pending_reviews()
        found = any(p["post_id"] == post_id for p in pending)
        self.assertTrue(found)

        # Check approval action
        approved = self.dept.approve_post(post_id)
        self.assertTrue(approved)

        data = json.loads(json_file.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "APPROVED_READY_TO_PUBLISH")

        # Cleanup test files
        json_file.unlink(missing_ok=True)
        md_file.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
