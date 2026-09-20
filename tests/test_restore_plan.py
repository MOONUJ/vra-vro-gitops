import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "tooling" / "vcf"))

from release_artifact import finalize_release, prepare_staging
from restore_plan import RestorePlanError, RestorePlanService


NOW = datetime(2026, 9, 18, 0, 0, tzinfo=timezone.utc)


def observation(identity="before"):
    product = {
        "state": "COMPLETE",
        "summary": {"IN_SYNC": 1, "MODIFIED": 0, "LOCAL_ONLY": 0, "REMOTE_ONLY": 0},
        "resources": [{"type": "Policy", "state": "IN_SYNC", "identity": identity}],
    }
    return {
        "apiVersion": "gitops.vcf.example/v1alpha1",
        "kind": "ContentObservation",
        "metadata": {"complete": True},
        "spec": {"target": {"name": "dev"}, "products": {"automation": product, "orchestrator": product}},
    }


class RestorePlanServiceTest(unittest.TestCase):
    def _release(self, root):
        staging, staged, destination = prepare_staging(root / "releases", "1.0.0")
        (staged / "vra.zip").write_bytes(b"archive")
        (staged / "manifest.json").write_text(
            json.dumps({"components": {"vra_artifacts_zip": "vra.zip", "policies": ["lease"]}}),
            encoding="utf-8",
        )
        path, _ = finalize_release(
            staging, staged, destination, "1.0.0", "remote-export", {"name": "source"}, "test", "commit", {}
        )
        return path

    def _service(self, root):
        return RestorePlanService(
            root / ".gitops" / "plans",
            root / ".gitops" / "results",
            root / ".gitops" / "locks",
            {"name": "target", "endpoint": "https://example.com"},
            "test",
            now=lambda: NOW,
        )

    def test_restore_plan_binds_release_target_and_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release = self._release(root)
            service = self._service(root)

            path, plan = service.create_plan(release, observation())

            self.assertTrue(path.exists())
            self.assertEqual(plan["spec"]["releaseVersion"], "1.0.0")
            self.assertEqual(plan["spec"]["target"]["name"], "target")
            self.assertEqual(len(plan["spec"]["requiredApprovals"]), 1)

    def test_restore_requires_exact_artifact_approvals(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = self._service(root)
            _, plan = service.create_plan(self._release(root), observation())

            with self.assertRaisesRegex(RestorePlanError, "artifact 승인"):
                service.apply(plan, plan["metadata"]["planHash"], [], observation(), lambda path: None, lambda release: True)

    def test_restore_apply_records_verified_result_and_blocks_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = self._service(root)
            _, plan = service.create_plan(self._release(root), observation())
            executed = []

            result_path, result = service.apply(
                plan,
                plan["metadata"]["planHash"],
                plan["spec"]["requiredApprovals"],
                observation(),
                lambda path: executed.append(path),
                lambda release: True,
            )

            self.assertEqual(result["spec"]["status"], "VERIFIED")
            self.assertEqual(len(executed), 1)
            self.assertTrue(result_path.exists())
            with self.assertRaisesRegex(RestorePlanError, "이미 실행 결과"):
                service.apply(
                    plan,
                    plan["metadata"]["planHash"],
                    plan["spec"]["requiredApprovals"],
                    observation(),
                    lambda path: None,
                    lambda release: True,
                )

    def test_remote_change_invalidates_restore_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = self._service(root)
            _, plan = service.create_plan(self._release(root), observation())

            with self.assertRaisesRegex(RestorePlanError, "원격 상태"):
                service.apply(
                    plan,
                    plan["metadata"]["planHash"],
                    plan["spec"]["requiredApprovals"],
                    observation("changed"),
                    lambda path: None,
                    lambda release: True,
                )

    def test_failed_verification_is_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = self._service(root)
            _, plan = service.create_plan(self._release(root), observation())

            _, result = service.apply(
                plan,
                plan["metadata"]["planHash"],
                plan["spec"]["requiredApprovals"],
                observation(),
                lambda path: None,
                lambda release: False,
            )

            self.assertEqual(result["spec"]["status"], "FAILED")
            self.assertIn("검증", result["spec"]["operation"]["error"])


if __name__ == "__main__":
    unittest.main()
