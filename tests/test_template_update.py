import tempfile
import unittest
from pathlib import Path


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
        (self.source / "content").mkdir()
        (self.source / "content" / "desired.yaml").write_text("source\n", encoding="utf-8")
        (self.destination / "tooling" / "vcf").mkdir(parents=True)
        (self.destination / "tooling" / "vcf" / "cli.py").write_text("old\n", encoding="utf-8")
        (self.destination / "instance.yaml").write_text("instance\n", encoding="utf-8")
        (self.destination / "content").mkdir()
        (self.destination / "content" / "desired.yaml").write_text("owned\n", encoding="utf-8")

    def tearDown(self):
        self.tempdir.cleanup()

    def test_preview_does_not_write_and_excludes_desired_state(self):
        preview = plan_update(self.source, self.destination)
        paths = {item["path"] for item in preview["spec"]["changes"]}
        self.assertIn("tooling/vcf/cli.py", paths)
        self.assertNotIn("content/desired.yaml", paths)
        self.assertEqual("old\n", (self.destination / "tooling" / "vcf" / "cli.py").read_text())

    def test_apply_requires_exact_version_and_preserves_state(self):
        preview = plan_update(self.source, self.destination)
        with self.assertRaises(TemplateUpdateError):
            apply_update(preview, "1.0.0")
        applied = apply_update(preview, "2.0.0")
        self.assertIn("tooling/vcf/cli.py", applied)
        self.assertEqual("new\n", (self.destination / "tooling" / "vcf" / "cli.py").read_text())
        self.assertEqual("instance\n", (self.destination / "instance.yaml").read_text())
        self.assertEqual("owned\n", (self.destination / "content" / "desired.yaml").read_text())

    def test_source_tamper_after_preview_is_rejected(self):
        preview = plan_update(self.source, self.destination)
        (self.source / "tooling" / "vcf" / "cli.py").write_text("tampered\n", encoding="utf-8")
        with self.assertRaises(TemplateUpdateError):
            apply_update(preview, "2.0.0")


if __name__ == "__main__":
    unittest.main()
