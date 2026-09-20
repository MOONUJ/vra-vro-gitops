import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "tooling" / "vcf"))

from content_plan import ContentPlanError, ContentPlanService


NOW = datetime(2026, 9, 18, 0, 0, tzinfo=timezone.utc)


def observation(state="MODIFIED"):
    empty = {"state": "COMPLETE", "summary": {"IN_SYNC": 0, "MODIFIED": 0, "LOCAL_ONLY": 0, "REMOTE_ONLY": 0}, "resources": []}
    automation = json.loads(json.dumps(empty))
    automation["summary"][state] = 1
    automation["resources"] = [{"type": "Policy", "state": state, "identity": "lease"}]
    return {
        "apiVersion": "gitops.vcf.example/v1alpha1",
        "kind": "ContentObservation",
        "metadata": {"complete": True},
        "spec": {"target": {"name": "dev"}, "products": {"automation": automation, "orchestrator": empty}},
    }


class ContentPlanServiceTest(unittest.TestCase):
    def _service(self, root):
        return ContentPlanService(
            root / "content",
            root / ".gitops" / "plans",
            root / ".gitops" / "results",
            root / ".gitops" / "locks",
            {"name": "dev", "endpoint": "https://example.com"},
            "test",
            "commit-a",
            now=lambda: NOW,
        )

    def _root(self, directory):
        root = Path(directory)
        content = root / "content" / "automation" / "policies"
        content.mkdir(parents=True)
        (content / "lease.json").write_text('{"name": "lease"}\n', encoding="utf-8")
        return root

    def test_plan_binds_target_commit_content_and_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory)
            service = self._service(root)

            path, plan = service.create_plan(observation(), "day2", ["automation"], ["automation:Policy:lease"])

            self.assertTrue(path.exists())
            self.assertEqual(plan["spec"]["gitCommit"], "commit-a")
            self.assertEqual(plan["spec"]["lifecycle"], "day2")
            self.assertEqual(plan["spec"]["operations"][0]["action"], "UPDATE")
            self.assertNotIn("secret", json.dumps(plan))

    def test_create_requires_exact_separate_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory)
            service = self._service(root)
            _, plan = service.create_plan(
                observation("LOCAL_ONLY"), "day1", ["automation"], ["automation:Policy:lease"]
            )

            with self.assertRaisesRegex(ContentPlanError, "생성 승인"):
                service.apply(
                    plan,
                    plan["metadata"]["planHash"],
                    [],
                    observation("LOCAL_ONLY"),
                    "commit-a",
                    lambda operation: None,
                    lambda operation: True,
                )

    def test_apply_executes_exact_operations_and_verifies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory)
            service = self._service(root)
            _, plan = service.create_plan(observation(), "day2", ["automation"], ["automation:Policy:lease"])
            executed = []

            result_path, result = service.apply(
                plan,
                plan["metadata"]["planHash"],
                [],
                observation(),
                "commit-a",
                lambda operation: executed.append(operation["approvalKey"]),
                lambda operation: True,
            )

            self.assertEqual(executed, ["automation:Policy:lease"])
            self.assertEqual(result["spec"]["status"], "VERIFIED")
            self.assertTrue(result_path.exists())
            self.assertFalse((root / ".gitops" / "locks" / "dev.lock").exists())
            with self.assertRaisesRegex(ContentPlanError, "이미 실행 결과"):
                service.apply(plan, plan["metadata"]["planHash"], [], observation(), "commit-a", lambda op: None, lambda op: True)

    def test_content_or_remote_change_invalidates_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory)
            service = self._service(root)
            _, plan = service.create_plan(observation(), "day2", ["automation"], ["automation:Policy:lease"])
            (root / "content" / "automation" / "policies" / "lease.json").write_text("{}\n", encoding="utf-8")

            with self.assertRaisesRegex(ContentPlanError, "local content"):
                service.apply(plan, plan["metadata"]["planHash"], [], observation(), "commit-a", lambda op: None, lambda op: True)

    def test_existing_instance_lock_blocks_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory)
            service = self._service(root)
            _, plan = service.create_plan(observation(), "day2", ["automation"], ["automation:Policy:lease"])
            lock = root / ".gitops" / "locks" / "dev.lock"
            lock.parent.mkdir(parents=True)
            lock.write_text("other\n", encoding="utf-8")

            with self.assertRaisesRegex(ContentPlanError, "실행 중"):
                service.apply(plan, plan["metadata"]["planHash"], [], observation(), "commit-a", lambda op: None, lambda op: True)


if __name__ == "__main__":
    unittest.main()
