import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "tooling" / "vcf"))

from content_identity import content_hash, identity_preview, normalize_content, validate_identities


class ContentIdentityTest(unittest.TestCase):
    def _write_identity(self, path, name, target, remote_id=None):
        metadata = {"name": name}
        if remote_id:
            metadata["remoteId"] = remote_id
        value = {
            "apiVersion": "gitops.vcf.example/v1alpha1",
            "kind": "ContentIdentity",
            "metadata": metadata,
            "spec": {
                "product": "automation",
                "type": "Blueprint",
                "path": target,
                "scope": {"project": "project-a"},
                "usages": ["provisioning"],
            },
        }
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def test_normalization_drops_volatile_fields_and_redacts_secure_values(self):
        first = {
            "updatedAt": "now",
            "attributes": [
                {"name": "password", "type": "SecureString", "value": {"secure-string": {"value": "secret"}}},
                {"name": "region", "type": "string", "value": "seoul\r\n"},
            ],
        }
        second = {
            "attributes": [
                {"value": "seoul\n", "type": "string", "name": "region"},
                {"value": {"secure-string": {"value": "different"}}, "type": "SecureString", "name": "password"},
            ],
            "updatedAt": "later",
        }

        normalized = normalize_content(first)
        self.assertNotIn("secret", json.dumps(normalized))
        self.assertEqual(content_hash(first), content_hash(second))

    def test_catalog_import_runtime_fields_do_not_change_hash(self):
        first = {
            "name": "source",
            "configuration": {"sourceType": "CATALOG"},
            "lastImportStartedAt": "2026-09-18T00:00:00Z",
            "lastImportCompletedAt": "2026-09-18T00:01:00Z",
            "itemsFound": 10,
            "itemsImported": 10,
            "lastImportErrors": [],
        }
        second = {
            **first,
            "lastImportStartedAt": "2026-09-21T00:00:00Z",
            "lastImportCompletedAt": "2026-09-21T00:02:00Z",
            "itemsFound": 11,
            "itemsImported": 11,
        }
        self.assertEqual(content_hash(first), content_hash(second))

    def test_identity_preview_is_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            blueprint = root / "content" / "automation" / "blueprints" / "hello"
            blueprint.mkdir(parents=True)
            (blueprint / "blueprint.json").write_text("{}\n", encoding="utf-8")

            preview = identity_preview(root)

            self.assertEqual(len(preview), 1)
            self.assertEqual(preview[0]["action"], "CREATE")
            self.assertEqual(preview[0]["manifest"]["spec"]["type"], "Blueprint")
            self.assertFalse((blueprint / ".gitops.yaml").exists())

    def test_validate_accepts_sidecar_and_rejects_duplicate_remote_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "content" / "automation" / "blueprints" / "first"
            second = root / "content" / "automation" / "blueprints" / "second"
            first.mkdir(parents=True)
            second.mkdir(parents=True)
            (first / "blueprint.json").write_text("{}\n", encoding="utf-8")
            (second / "blueprint.json").write_text("{}\n", encoding="utf-8")
            self._write_identity(
                first / ".gitops.yaml",
                "first",
                "content/automation/blueprints/first",
                "remote-1",
            )
            self.assertEqual(validate_identities(root), [])

            self._write_identity(
                second / ".gitops.yaml",
                "second",
                "content/automation/blueprints/second",
                "remote-1",
            )
            errors = validate_identities(root)
            self.assertTrue(any("remote identity" in error for error in errors))

    def test_validate_rejects_path_outside_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            blueprint = root / "content" / "automation" / "blueprints" / "hello"
            blueprint.mkdir(parents=True)
            (blueprint / "blueprint.json").write_text("{}\n", encoding="utf-8")
            self._write_identity(blueprint / ".gitops.yaml", "hello", "../outside", "remote-1")

            errors = validate_identities(root)

            self.assertTrue(any("content/ 아래" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
