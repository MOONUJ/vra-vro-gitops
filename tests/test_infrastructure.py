import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "tooling" / "vcf"))

from infrastructure import InfrastructureError, InfrastructureService  # noqa: E402
from cli import build_parser  # noqa: E402


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class InvalidJsonResponse(FakeResponse):
    def json(self):
        raise ValueError("invalid json")


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if not self.responses:
            raise AssertionError(f"예상하지 않은 요청: {method} {path}")
        return self.responses.pop(0)


class InfrastructureServiceTest(unittest.TestCase):
    def test_invalid_json_response_is_reported_as_infrastructure_error(self):
        service = InfrastructureService(FakeClient([InvalidJsonResponse(200)]), "infrastructure")
        with self.assertRaisesRegex(InfrastructureError, "유효한 JSON"):
            service.discover_kind("Project")

    def test_adopt_requires_explicit_resource_or_all(self):
        parser = build_parser()
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["adopt"])
        args = parser.parse_args(["adopt", "--all", "--kind", "Project", "--dry-run"])
        self.assertTrue(args.all)
        self.assertEqual(args.kind, ["Project"])
        self.assertTrue(args.dry_run)

    def test_discovery_uses_all_pages(self):
        client = FakeClient(
            [
                FakeResponse(200, {"content": [{"id": "1", "name": "one"}, {"id": "2", "name": "two"}], "totalElements": 3}),
                FakeResponse(200, {"content": [{"id": "3", "name": "three"}], "totalElements": 3}),
            ]
        )
        service = InfrastructureService(client, "infrastructure")
        result = service.discover_kind("Project", page_size=2)
        self.assertEqual([item["id"] for item in result], ["1", "2", "3"])
        self.assertEqual(client.calls[1][2]["params"]["page"], 1)

    def test_discovery_fails_closed_on_forbidden(self):
        service = InfrastructureService(FakeClient([FakeResponse(403)]), "infrastructure")
        with self.assertRaises(InfrastructureError):
            service.discover_kind("CloudZone")

    def test_adopt_writes_remote_identity_and_status_is_in_sync(self):
        remote = {
            "id": "zone-1",
            "name": "Production Zone",
            "description": "Production",
            "regionId": "region-1",
            "placementPolicy": "DEFAULT",
            "updatedAt": "volatile",
        }
        client = FakeClient([FakeResponse(200, remote), FakeResponse(200, remote)])
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "infrastructure"
            service = InfrastructureService(client, root)
            path = service.adopt("CloudZone", "zone-1")
            manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["metadata"]["name"], "production-zone")
            self.assertEqual(manifest["metadata"]["remoteId"], "zone-1")
            self.assertNotIn("updatedAt", manifest["spec"])
            self.assertEqual(service.status()[0]["state"], "IN_SYNC")

    def test_status_marks_manifest_without_remote_id_as_create_pending(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "infrastructure"
            path = root / "projects" / "application-team.yaml"
            path.parent.mkdir(parents=True)
            path.write_text(
                yaml.safe_dump(
                    {
                        "apiVersion": "gitops.vcf.example/v1alpha1",
                        "kind": "Project",
                        "metadata": {"name": "application-team"},
                        "spec": {"name": "Application Team"},
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            result = InfrastructureService(FakeClient([]), root).status()
            self.assertEqual(result[0]["state"], "CREATE_PENDING")

    def test_adopt_refuses_duplicate_remote_identity(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "infrastructure" / "projects"
            root.mkdir(parents=True)
            (root / "existing.yaml").write_text(
                yaml.safe_dump(
                    {
                        "apiVersion": "gitops.vcf.example/v1alpha1",
                        "kind": "Project",
                        "metadata": {"name": "existing", "remoteId": "project-1"},
                        "spec": {"name": "Existing"},
                    }
                ),
                encoding="utf-8",
            )
            service = InfrastructureService(FakeClient([]), root.parent)
            with self.assertRaises(InfrastructureError):
                service.adopt("Project", "project-1")

    def test_validate_rejects_duplicate_remote_identity(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "infrastructure" / "projects"
            root.mkdir(parents=True)
            manifest = {
                "apiVersion": "gitops.vcf.example/v1alpha1",
                "kind": "Project",
                "metadata": {"name": "one", "remoteId": "project-1"},
                "spec": {"name": "One"},
            }
            (root / "one.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
            manifest["metadata"]["name"] = "two"
            (root / "two.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
            errors = InfrastructureService(FakeClient([]), root.parent).validate()
            self.assertTrue(any("중복" in error for error in errors))

    def test_bulk_adopt_plan_does_not_write_until_applied(self):
        project = {"id": "project-1", "name": "Application Team", "description": "Team project"}
        client = FakeClient(
            [
                FakeResponse(200, {"content": [project], "totalElements": 1}),
                FakeResponse(200, project),
            ]
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "infrastructure"
            service = InfrastructureService(client, root)
            selectors = service.discover_selectors(["Project"])
            plan = service.plan_adopt(selectors)
            self.assertEqual(plan[0]["action"], "CREATE")
            self.assertFalse(plan[0]["path"].exists())
            created = service.apply_adopt_plan(plan)
            self.assertEqual(created, [root / "projects" / "application-team.yaml"])
            self.assertTrue(created[0].exists())

    def test_bulk_adopt_skips_existing_remote_identity(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "infrastructure" / "projects"
            root.mkdir(parents=True)
            (root / "existing.yaml").write_text(
                yaml.safe_dump(
                    {
                        "apiVersion": "gitops.vcf.example/v1alpha1",
                        "kind": "Project",
                        "metadata": {"name": "existing", "remoteId": "project-1"},
                        "spec": {"name": "Existing"},
                    }
                ),
                encoding="utf-8",
            )
            service = InfrastructureService(FakeClient([]), root.parent)
            plan = service.plan_adopt([("Project", "project-1")])
            self.assertEqual(plan[0]["action"], "SKIP")
            self.assertEqual(service.apply_adopt_plan(plan), [])

    def test_bulk_adopt_conflict_blocks_all_writes(self):
        first = {"id": "project-1", "name": "Same Name"}
        second = {"id": "project-2", "name": "Same Name"}
        client = FakeClient([FakeResponse(200, first), FakeResponse(200, second)])
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "infrastructure"
            service = InfrastructureService(client, root)
            plan = service.plan_adopt([("Project", "project-1"), ("Project", "project-2")])
            self.assertEqual([item["action"] for item in plan], ["CREATE", "CONFLICT"])
            with self.assertRaises(InfrastructureError):
                service.apply_adopt_plan(plan)
            self.assertFalse((root / "projects" / "same-name.yaml").exists())

    def test_bulk_discovery_without_id_fails_closed(self):
        client = FakeClient([FakeResponse(200, {"content": [{"name": "Missing ID"}], "totalElements": 1})])
        service = InfrastructureService(client, "infrastructure")
        with self.assertRaises(InfrastructureError):
            service.discover_selectors(["Project"])

    def test_adopt_detail_without_name_fails_before_write(self):
        client = FakeClient([FakeResponse(200, {"id": "project-1"})])
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "infrastructure"
            service = InfrastructureService(client, root)
            with self.assertRaises(InfrastructureError):
                service.plan_adopt([("Project", "project-1")])
            self.assertFalse((root / "projects").exists())

    def test_invalid_manifest_blocks_adopt_preflight(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "infrastructure" / "projects"
            root.mkdir(parents=True)
            (root / "invalid.yaml").write_text("- not\n- an\n- object\n", encoding="utf-8")
            service = InfrastructureService(FakeClient([]), root.parent)
            with self.assertRaises(InfrastructureError):
                service.plan_adopt([("Project", "project-1")])


if __name__ == "__main__":
    unittest.main()
