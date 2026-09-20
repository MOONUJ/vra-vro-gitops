import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tooling" / "vcf"))

from observe_loop import LoopError, ObserveLoopRunner, RetryableObservationError, validate_loop_target


def observation(drift=False):
    summary = {"IN_SYNC": 1, "MODIFIED": int(drift), "LOCAL_ONLY": 0, "REMOTE_ONLY": 0}
    return {
        "apiVersion": "gitops.vcf.example/v1alpha1",
        "kind": "ContentObservation",
        "metadata": {"complete": True},
        "spec": {"target": {"name": "dev"}, "products": {"automation": {"state": "COMPLETE", "summary": summary, "resources": []}}},
    }


def loop_document(name="observer"):
    return {
        "apiVersion": "gitops.vcf.example/v1alpha1",
        "kind": "ReconciliationLoop",
        "metadata": {"name": name},
        "spec": {
            "enabled": True,
            "repositoryMode": "instance",
            "instanceRef": "dev",
            "lifecycle": "day2",
            "products": ["automation"],
            "interval": "15m",
            "mode": "observe",
            "retry": {"maxAttempts": 3, "maxElapsedSeconds": 30, "backoffSeconds": 0},
            "repeatDriftThreshold": 2,
            "approval": {"requiredFor": ["content-apply"]},
        },
    }


class ObserveLoopRunnerTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_retryable_error_is_retried_and_secret_is_not_journaled(self):
        calls = []

        def observe():
            calls.append(1)
            if len(calls) == 1:
                raise RetryableObservationError("temporary token-secret")
            return observation()

        path, journal = ObserveLoopRunner(self.root, "0.2.0", sleep=lambda _: None).run(
            loop_document(), observe, ["token-secret"]
        )
        self.assertEqual(2, journal["spec"]["attempts"])
        self.assertIn("observationHash", journal["status"])
        self.assertNotIn("token-secret", path.read_text(encoding="utf-8"))

    def test_non_retryable_error_is_not_retried_and_is_redacted(self):
        calls = []

        def observe():
            calls.append(1)
            raise ValueError("bad token-secret")

        path, journal = ObserveLoopRunner(self.root, sleep=lambda _: None).run(loop_document(), observe, ["token-secret"])
        self.assertEqual(1, len(calls))
        self.assertEqual("FAILED", journal["status"]["state"])
        self.assertIn("[REDACTED]", path.read_text(encoding="utf-8"))

    def test_same_in_sync_observation_is_quiet(self):
        runner = ObserveLoopRunner(self.root)
        _, first = runner.run(loop_document(), lambda: observation())
        _, second = runner.run(loop_document(), lambda: observation())
        self.assertFalse(first["status"]["notify"])
        self.assertFalse(second["status"]["notify"])
        self.assertFalse(second["status"]["changed"])

    def test_repeated_drift_escalates(self):
        runner = ObserveLoopRunner(self.root)
        _, first = runner.run(loop_document(), lambda: observation(True))
        _, second = runner.run(loop_document(), lambda: observation(True))
        self.assertFalse(first["status"]["escalation"])
        self.assertTrue(second["status"]["escalation"])
        self.assertTrue(first["status"]["notify"])
        self.assertTrue(second["status"]["notify"])

    def test_repeated_drift_is_quiet_until_escalation_threshold(self):
        loop = loop_document("quiet-drift")
        loop["spec"]["repeatDriftThreshold"] = 3
        runner = ObserveLoopRunner(self.root)
        _, first = runner.run(loop, lambda: observation(True))
        _, second = runner.run(loop, lambda: observation(True))
        _, third = runner.run(loop, lambda: observation(True))
        self.assertTrue(first["status"]["notify"])
        self.assertFalse(second["status"]["notify"])
        self.assertTrue(third["status"]["notify"])

    def test_existing_lock_blocks_duplicate_run(self):
        lock = self.root / ".gitops" / "locks" / "dev.observe.lock"
        lock.parent.mkdir(parents=True)
        lock.write_text("other", encoding="utf-8")
        with self.assertRaises(LoopError):
            ObserveLoopRunner(self.root).run(loop_document(), lambda: observation())


class ObserveLoopTargetTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / "schemas").mkdir()
        source_schema = Path(__file__).resolve().parents[1] / "schemas" / "reconciliation-loop-v1alpha1.schema.json"
        (self.root / "schemas" / source_schema.name).write_bytes(source_schema.read_bytes())
        instance = {
            "apiVersion": "gitops.vcf.example/v1alpha2", "kind": "AutomationInstance", "metadata": {"name": "dev"},
            "spec": {"environmentTag": "dev", "endpoint": "https://example.invalid", "organization": "default", "verifySsl": True,
                     "gitops": {"tag": "dev", "projects": ["dev"]}, "management": {"infrastructure": "native", "deletionPolicy": "require-explicit-approval"},
                     "orchestrator": {"package": {"name": "example", "localPath": "content/example.package"}}},
        }
        (self.root / "instance.yaml").write_text(yaml.safe_dump(instance), encoding="utf-8")
        (self.root / "secrets.json").write_text(json.dumps({"automation": {"refresh_token": "secret"}}), encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "instance.yaml"], check=True)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_example_loop_is_rejected(self):
        path = self.root / "observer.example.yaml"
        path.write_text(yaml.safe_dump(loop_document()), encoding="utf-8")
        with self.assertRaises(LoopError):
            validate_loop_target(self.root, path)

    def test_active_tracked_instance_loop_is_accepted(self):
        path = self.root / "observer.yaml"
        path.write_text(yaml.safe_dump(loop_document()), encoding="utf-8")
        loop, source = validate_loop_target(self.root, path)
        self.assertEqual("observer", loop["metadata"]["name"])
        self.assertEqual("dev", source["environment"]["name"])


if __name__ == "__main__":
    unittest.main()
