import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "tooling" / "vcf"))

from policy import PolicyError, evaluate_plan, load_policy, policy_hash
from schema_validation import validate_document, validate_repository


class SchemaAndPolicyTest(unittest.TestCase):
    def test_repository_manifests_pass_versioned_schemas(self):
        self.assertEqual(validate_repository(REPOSITORY_ROOT), [])

    def test_schema_rejects_unknown_instance_field(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "instance.yaml"
            instance = yaml.safe_load((REPOSITORY_ROOT / "instance.example.yaml").read_text(encoding="utf-8"))
            instance["spec"]["unknown"] = True
            path.write_text(yaml.safe_dump(instance, sort_keys=False), encoding="utf-8")

            errors = validate_document(path, REPOSITORY_ROOT / "schemas")

            self.assertTrue(any("알 수 없는 필드" in error for error in errors))

    def test_policy_hash_is_deterministic(self):
        policy = load_policy(REPOSITORY_ROOT / "governance" / "policy.yaml")
        self.assertEqual(policy_hash(policy), policy_hash(json.loads(json.dumps(policy))))

    def test_policy_limits_operation_count(self):
        policy = load_policy(REPOSITORY_ROOT / "governance" / "policy.yaml")
        policy["spec"]["maxPlanOperations"] = 1
        plan = {
            "spec": {
                "target": {"name": "automation-dev"},
                "operations": [{"action": "UPDATE"}, {"action": "UPDATE"}],
            }
        }
        with self.assertRaisesRegex(PolicyError, "초과"):
            evaluate_plan(plan, policy, "plan")

    def test_policy_blocks_production_apply_but_allows_plan(self):
        policy = load_policy(REPOSITORY_ROOT / "governance" / "policy.yaml")
        plan = {"spec": {"target": {"name": "automation-prod"}, "operations": [{"action": "UPDATE"}]}}

        evaluate_plan(plan, policy, "plan")
        with self.assertRaisesRegex(PolicyError, "production"):
            evaluate_plan(plan, policy, "apply")


if __name__ == "__main__":
    unittest.main()
