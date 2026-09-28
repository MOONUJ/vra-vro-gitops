import json
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "tooling" / "vcf"))

from content_observation import ContentObservationError, complete_observation, incomplete_observation
from vcf_sync import get_vra_status, get_vro_status


EMPTY_VRO = {
    "Workflow": {"IN_SYNC": [], "MODIFIED": [], "LOCAL_ONLY": [], "SERVER_ONLY": []},
    "Action": {"IN_SYNC": [], "MODIFIED": [], "LOCAL_ONLY": [], "SERVER_ONLY": []},
}
EMPTY_VRA = {
    "Blueprint": {"IN_SYNC": [], "MODIFIED": [], "LOCAL_ONLY": [], "SERVER_ONLY": []},
}


class FailingVroClient:
    def find_resources_by_tag(self, resource_type, tag):
        raise PermissionError("forbidden")


class EmptyVroClient:
    def find_resources_by_tag(self, resource_type, tag):
        return []


class PackageScopedVroClient:
    def find_resources_by_package(self, resource_type, package_name):
        if resource_type == "Workflow":
            return [{"id": "workflow-1", "name": "Resize VM", "version": "1.0.0"}]
        return []

    def find_resources_by_tag(self, resource_type, tag):
        raise AssertionError("package discovery must not use tag search")


class FailingVraClient:
    def get_projects(self):
        raise PermissionError("forbidden")


class PolicyDetailVraClient:
    def get_projects(self):
        return []

    def list_blueprints(self):
        return []

    def list_abx_actions(self):
        return []

    def list_custom_resources(self):
        return []

    def list_resource_actions(self):
        return []

    def list_catalog_sources(self):
        return []

    def list_policies(self):
        return [{"id": "policy-1", "name": "Default"}]

    def get_policy(self, policy_id):
        return {"id": policy_id, "name": "Default", "type": "CATALOG_SOURCE_ENTITLEMENT", "properties": {}}

    def list_subscriptions(self):
        return []

    def list_catalog_items(self):
        return []


class ContentObservationTest(unittest.TestCase):
    def test_complete_observation_is_deterministic_and_renames_remote_state(self):
        target = {
            "endpoint": "https://automation.example.com",
            "organization": "default",
            "gitopsTag": "example",
            "projects": ["project-a"],
        }
        vro = dict(EMPTY_VRO)
        vro["Workflow"] = {
            "IN_SYNC": [("wf-b", "id-b")],
            "MODIFIED": [],
            "LOCAL_ONLY": [],
            "SERVER_ONLY": [("wf-a", "id-a")],
        }

        first = complete_observation(target, vro, EMPTY_VRA)
        second = complete_observation(target, vro, EMPTY_VRA)

        self.assertEqual(first, second)
        resources = first["spec"]["products"]["orchestrator"]["resources"]
        self.assertEqual([item["identity"] for item in resources], ["wf-a", "wf-b"])
        self.assertEqual(resources[0]["state"], "REMOTE_ONLY")
        self.assertNotIn("SERVER_ONLY", json.dumps(first))

    def test_incomplete_observation_contains_no_partial_drift(self):
        result = incomplete_observation({"endpoint": "https://example.com"}, "automation", PermissionError("forbidden"))

        self.assertFalse(result["metadata"]["complete"])
        self.assertEqual(result["spec"]["products"]["automation"]["state"], "INCOMPLETE")
        self.assertNotIn("resources", result["spec"]["products"]["automation"])

    def test_vro_discovery_failure_is_not_treated_as_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ContentObservationError, "discovery 실패"):
                get_vro_status(FailingVroClient(), {"gitops_tag": "example"}, directory)

    def test_required_non_empty_vro_discovery_rejects_false_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ContentObservationError, "0건"):
                get_vro_status(
                    EmptyVroClient(),
                    {"gitops_tag": "example", "vro_require_non_empty": True},
                    directory,
                )

    def test_package_membership_can_scope_vro_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            result = get_vro_status(
                PackageScopedVroClient(),
                {
                    "gitops_tag": "unused",
                    "package": {"name": "com.example.gitops"},
                    "vro_discovery_mode": "package",
                    "vro_require_non_empty": True,
                },
                directory,
            )
            self.assertEqual([("workflow-1", "Resize VM")], result["Workflow"]["SERVER_ONLY"])

    def test_vra_project_failure_is_not_treated_as_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ContentObservationError, "Project discovery 실패"):
                get_vra_status(
                    FailingVraClient(),
                    {"gitops_tag": "example", "projects": ["project-a"]},
                    directory,
                )

    def test_observation_rejects_malformed_status_item(self):
        malformed = {
            "Workflow": {"IN_SYNC": [()], "MODIFIED": [], "LOCAL_ONLY": [], "SERVER_ONLY": []},
        }
        with self.assertRaises(ContentObservationError):
            complete_observation({}, malformed, EMPTY_VRA)

    def test_policy_comparison_uses_full_detail_like_pull(self):
        with tempfile.TemporaryDirectory() as directory:
            policy_root = Path(directory) / "content" / "automation" / "policies"
            policy_root.mkdir(parents=True)
            (policy_root / "Default.json").write_text(
                json.dumps({"id": "policy-1", "name": "Default", "type": "CATALOG_SOURCE_ENTITLEMENT", "properties": {}}),
                encoding="utf-8",
            )
            result = get_vra_status(
                PolicyDetailVraClient(),
                {"gitops_tag": "example", "projects": []},
                directory,
            )
            self.assertEqual([("Default", "Matching")], result["Catalog Policy"]["IN_SYNC"])


if __name__ == "__main__":
    unittest.main()
