import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "tooling" / "vcf"))

from infrastructure import InfrastructureError, InfrastructureService  # noqa: E402
from infrastructure_plan import InfrastructurePlanService  # noqa: E402


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if not self.responses:
            raise AssertionError(f"예상하지 않은 요청: {method} {path}")
        return self.responses.pop(0)


class InfrastructurePlanServiceTest(unittest.TestCase):
    NOW = datetime(2026, 9, 17, 0, 0, tzinfo=timezone.utc)
    INSTANCE = {
        "name": "automation-dev",
        "endpoint": "https://automation.example.com",
        "organization": "default",
        "management": {"infrastructure": "native", "deletionPolicy": "require-explicit-approval"},
    }

    def _write_manifest(self, root, spec, remote_id="project-1", name="application-team"):
        path = root / "projects" / f"{name}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        metadata = {"name": name}
        if remote_id is not None:
            metadata["remoteId"] = remote_id
        path.write_text(
            yaml.safe_dump(
                {
                    "apiVersion": "gitops.vcf.example/v1alpha1",
                    "kind": "Project",
                    "metadata": metadata,
                    "spec": spec,
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        return path

    def _service(self, root, client):
        infrastructure = InfrastructureService(client, root / "infrastructure")
        return InfrastructurePlanService(
            infrastructure,
            root / ".gitops" / "plans",
            root / ".gitops" / "apply-results",
            self.INSTANCE,
            "test",
            now=lambda: self.NOW,
        )

    def test_identical_observation_reuses_immutable_plan(self):
        remote = {"id": "project-1", "name": "Application Team", "description": "Remote"}
        desired = {"name": "Application Team", "description": "Desired"}
        client = FakeClient([FakeResponse(200, remote), FakeResponse(200, remote)])
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._write_manifest(root / "infrastructure", desired)
            service = self._service(root, client)

            first_path, first, first_reused = service.create_plan()
            second_path, second, second_reused = service.create_plan()

            self.assertFalse(first_reused)
            self.assertTrue(second_reused)
            self.assertEqual(first_path, second_path)
            self.assertEqual(first["metadata"]["planHash"], second["metadata"]["planHash"])
            self.assertEqual(first["spec"]["operations"][0]["action"], "UPDATE")

    def test_tampered_plan_is_rejected(self):
        remote = {"id": "project-1", "name": "Application Team", "description": "Remote"}
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._write_manifest(root / "infrastructure", {"name": "Application Team", "description": "Desired"})
            service = self._service(root, FakeClient([FakeResponse(200, remote)]))
            _, artifact, _ = service.create_plan()
            artifact["spec"]["operations"][0]["after"]["description"] = "Tampered"
            with self.assertRaises(InfrastructureError):
                service.validate_artifact(artifact)

    def test_update_requires_hash_and_verifies_remote_again(self):
        before = {"id": "project-1", "name": "Application Team", "description": "Before"}
        after = {"id": "project-1", "name": "Application Team", "description": "After"}
        client = FakeClient(
            [
                FakeResponse(200, before),
                FakeResponse(200, before),
                FakeResponse(200, after),
                FakeResponse(200, after),
            ]
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._write_manifest(root / "infrastructure", {"name": "Application Team", "description": "After"})
            service = self._service(root, client)
            _, artifact, _ = service.create_plan()
            with self.assertRaises(InfrastructureError):
                service.apply(artifact, "wrong-hash")

            result_path, result = service.apply(artifact, artifact["metadata"]["planHash"])
            self.assertTrue(result_path.is_file())
            self.assertEqual(result["spec"]["status"], "VERIFIED")
            self.assertEqual(client.calls[2][0], "PATCH")
            self.assertEqual(client.calls[2][1], "/iaas/api/projects/project-1")

    def test_manifest_change_after_plan_blocks_apply(self):
        remote = {"id": "project-1", "name": "Application Team", "description": "Before"}
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            path = self._write_manifest(
                root / "infrastructure",
                {"name": "Application Team", "description": "After"},
            )
            service = self._service(root, FakeClient([FakeResponse(200, remote)]))
            _, artifact, _ = service.create_plan()
            manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
            manifest["spec"]["description"] = "Changed again"
            path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
            with self.assertRaises(InfrastructureError):
                service.apply(artifact, artifact["metadata"]["planHash"])

    def test_unmodified_managed_resource_drift_blocks_apply(self):
        before_a = {"id": "project-a", "name": "A", "description": "Before"}
        desired_a = {"name": "A", "description": "After"}
        in_sync_b = {"id": "project-b", "name": "B", "description": "Same"}
        drifted_b = {"id": "project-b", "name": "B", "description": "Changed remotely"}
        client = FakeClient(
            [
                FakeResponse(200, before_a),
                FakeResponse(200, in_sync_b),
                FakeResponse(200, before_a),
                FakeResponse(200, drifted_b),
            ]
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._write_manifest(root / "infrastructure", desired_a, remote_id="project-a", name="a")
            self._write_manifest(
                root / "infrastructure",
                {"name": "B", "description": "Same"},
                remote_id="project-b",
                name="b",
            )
            service = self._service(root, client)
            _, artifact, _ = service.create_plan()
            with self.assertRaises(InfrastructureError):
                service.apply(artifact, artifact["metadata"]["planHash"])
            self.assertFalse(any(call[0] == "PATCH" for call in client.calls))

    def test_plan_rejects_read_only_field_change_before_apply(self):
        before = {
            "id": "storage-1",
            "name": "Storage",
            "regionId": "region-1",
            "defaultItem": False,
            "provisioningType": "thin",
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            path = root / "infrastructure" / "storage-profiles" / "storage.yaml"
            path.parent.mkdir(parents=True)
            path.write_text(
                yaml.safe_dump(
                    {
                        "apiVersion": "gitops.vcf.example/v1alpha1",
                        "kind": "StorageProfile",
                        "metadata": {"name": "storage", "remoteId": "storage-1"},
                        "spec": {**before, "provisioningType": "thick"},
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
            manifest["spec"].pop("id")
            path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
            service = self._service(root, FakeClient([FakeResponse(200, before)]))
            with self.assertRaises(InfrastructureError):
                service.create_plan()

    def test_plan_rejects_implicit_field_removal(self):
        before = {"id": "project-1", "name": "Application Team", "description": "Existing"}
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._write_manifest(root / "infrastructure", {"name": "Application Team"})
            service = self._service(root, FakeClient([FakeResponse(200, before)]))
            with self.assertRaises(InfrastructureError):
                service.create_plan()

    def test_profile_update_derives_region_id_from_remote_link(self):
        before = {
            "id": "network-1",
            "name": "Network",
            "description": "Before",
            "externalRegionId": "external-region",
            "_links": {"region": {"href": "/iaas/api/regions/region-1"}},
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            path = root / "infrastructure" / "network-profiles" / "network.yaml"
            path.parent.mkdir(parents=True)
            path.write_text(
                yaml.safe_dump(
                    {
                        "apiVersion": "gitops.vcf.example/v1alpha1",
                        "kind": "NetworkProfile",
                        "metadata": {"name": "network", "remoteId": "network-1"},
                        "spec": {"name": "Network", "description": "After", "externalRegionId": "external-region"},
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            service = self._service(root, FakeClient([FakeResponse(200, before)]))
            _, artifact, _ = service.create_plan()
            payload = artifact["spec"]["operations"][0]["payload"]
            self.assertEqual(payload["regionId"], "region-1")

    def test_create_records_remote_id_and_verifies(self):
        desired = {"name": "Application Team", "description": "New"}
        created = {"id": "project-new", **desired}
        client = FakeClient(
            [
                FakeResponse(200, {"content": [], "totalElements": 0}),
                FakeResponse(201, created),
                FakeResponse(200, created),
            ]
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            path = self._write_manifest(root / "infrastructure", desired, remote_id=None)
            service = self._service(root, client)
            _, artifact, _ = service.create_plan()
            with self.assertRaises(InfrastructureError):
                service.apply(artifact, artifact["metadata"]["planHash"])

            _, result = service.apply(
                artifact,
                artifact["metadata"]["planHash"],
                approved_creations=[("Project", "application-team")],
            )
            manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["metadata"]["remoteId"], "project-new")
            self.assertEqual(result["spec"]["operations"][0]["status"], "VERIFIED")

    def test_delete_requires_exact_separate_approval(self):
        remote = {"id": "project-old", "name": "Old Project"}
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            client = FakeClient([FakeResponse(200, remote)])
            service = self._service(root, client)
            _, artifact, _ = service.create_plan([("Project", "project-old")])
            with self.assertRaises(InfrastructureError):
                service.apply(artifact, artifact["metadata"]["planHash"])

    def test_partial_failure_records_remaining_operations_as_not_run(self):
        before_a = {"id": "project-a", "name": "A", "description": "Before"}
        before_b = {"id": "project-b", "name": "B", "description": "Before"}
        client = FakeClient(
            [
                FakeResponse(200, before_a),
                FakeResponse(200, before_b),
                FakeResponse(200, before_a),
                FakeResponse(200, before_b),
                FakeResponse(500, text="failed"),
            ]
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._write_manifest(
                root / "infrastructure",
                {"name": "A", "description": "After"},
                remote_id="project-a",
                name="a",
            )
            self._write_manifest(
                root / "infrastructure",
                {"name": "B", "description": "After"},
                remote_id="project-b",
                name="b",
            )
            service = self._service(root, client)
            _, artifact, _ = service.create_plan()
            _, result = service.apply(artifact, artifact["metadata"]["planHash"])
            self.assertEqual(result["spec"]["status"], "FAILED")
            self.assertEqual(
                [item["status"] for item in result["spec"]["operations"]],
                ["FAILED", "NOT_RUN"],
            )
            self.assertEqual(sum(call[0] == "PATCH" for call in client.calls), 1)

    def test_plan_json_contains_no_secret(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            service = self._service(root, FakeClient([]))
            path, _, _ = service.create_plan()
            rendered = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("refresh_token", json.dumps(rendered))


if __name__ == "__main__":
    unittest.main()
