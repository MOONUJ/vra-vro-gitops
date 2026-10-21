import tempfile
import unittest
from pathlib import Path

import yaml


import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tooling" / "vcf"))

from template_update import TemplateUpdateError, apply_update, plan_update


class TemplateUpdateTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.source = root / "source"
        self.destination = root / "destination"
        self.source.mkdir()
        self.destination.mkdir()
        (self.source / ".template-version").write_text("2.0.0\n", encoding="utf-8")
        (self.source / ".vcf-gitops-version").write_text("0.2.0\n", encoding="utf-8")
        (self.source / "tooling" / "vcf").mkdir(parents=True)
        (self.source / "tooling" / "vcf" / "cli.py").write_text("new\n", encoding="utf-8")
        (self.source / "docs").mkdir()
        (self.source / "docs" / "TEMPLATE.md").write_text("new docs\n", encoding="utf-8")
        (self.source / "content").mkdir()
        (self.source / "content" / "desired.yaml").write_text("source\n", encoding="utf-8")
        (self.destination / "tooling" / "vcf").mkdir(parents=True)
        (self.destination / "tooling" / "vcf" / "cli.py").write_text("old\n", encoding="utf-8")
        (self.destination / "instance.yaml").write_text(
            yaml.safe_dump(
                {
                    "spec": {
                        "management": {"infrastructure": "native"},
                        "orchestrator": {
                            "deployment": "embedded",
                            "discovery": {"mode": "tag", "requireNonEmpty": False},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        (self.destination / "content").mkdir()
        (self.destination / "content" / "desired.yaml").write_text("owned\n", encoding="utf-8")

    def tearDown(self):
        self.tempdir.cleanup()

    def test_preview_does_not_write_and_excludes_desired_state(self):
        preview = plan_update(self.source, self.destination)
        paths = {item["path"] for item in preview["spec"]["changes"]}
        self.assertIn("tooling/vcf/cli.py", paths)
        self.assertIn("docs/TEMPLATE.md", paths)
        self.assertNotIn("content/desired.yaml", paths)
        self.assertEqual("old\n", (self.destination / "tooling" / "vcf" / "cli.py").read_text())

    def test_apply_requires_exact_version_and_preserves_state(self):
        preview = plan_update(self.source, self.destination)
        with self.assertRaises(TemplateUpdateError):
            apply_update(preview, "1.0.0")
        applied = apply_update(preview, "2.0.0")
        self.assertIn("tooling/vcf/cli.py", applied)
        self.assertEqual("new docs\n", (self.destination / "docs" / "TEMPLATE.md").read_text())
        self.assertEqual("new\n", (self.destination / "tooling" / "vcf" / "cli.py").read_text())
        self.assertEqual("embedded", yaml.safe_load((self.destination / "instance.yaml").read_text())["spec"]["orchestrator"]["deployment"])
        self.assertEqual("owned\n", (self.destination / "content" / "desired.yaml").read_text())

    def test_source_tamper_after_preview_is_rejected(self):
        preview = plan_update(self.source, self.destination)
        (self.source / "tooling" / "vcf" / "cli.py").write_text("tampered\n", encoding="utf-8")
        with self.assertRaises(TemplateUpdateError):
            apply_update(preview, "2.0.0")

    def test_preview_reports_protected_instance_migration_and_blocks_apply(self):
        (self.destination / "instance.yaml").write_text(
            yaml.safe_dump({"spec": {"orchestrator": {"package": {"name": "example"}}}}),
            encoding="utf-8",
        )
        preview = plan_update(self.source, self.destination)
        migration = preview["spec"]["migrations"][0]
        self.assertEqual("0.3.0-orchestrator-connection", migration["id"])
        self.assertTrue(migration["required"])
        with self.assertRaisesRegex(TemplateUpdateError, "migration"):
            apply_update(preview, "2.0.0")
        self.assertNotIn("deployment", yaml.safe_load((self.destination / "instance.yaml").read_text())["spec"]["orchestrator"])

    def test_preview_blocks_legacy_terraform_ownership(self):
        instance = yaml.safe_load((self.destination / "instance.yaml").read_text(encoding="utf-8"))
        instance["spec"]["management"]["infrastructure"] = "terraform"
        (self.destination / "instance.yaml").write_text(yaml.safe_dump(instance), encoding="utf-8")
        legacy_root = self.destination / "foundation" / "automation" / "terraform"
        legacy_root.mkdir(parents=True)
        (legacy_root / "providers.tf").write_text("terraform {}\n", encoding="utf-8")

        preview = plan_update(self.source, self.destination)
        migration = next(item for item in preview["spec"]["migrations"] if item["id"] == "0.4.0-native-infrastructure-only")
        self.assertTrue(migration["required"])
        self.assertEqual(2, len(migration["requiredChanges"]))
        with self.assertRaisesRegex(TemplateUpdateError, "migration"):
            apply_update(preview, "2.0.0")


if __name__ == "__main__":
    unittest.main()
