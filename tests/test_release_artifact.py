import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "tooling" / "vcf"))

from release_artifact import ReleaseArtifactError, build_local_release, validate_version, verify_release
from vcf_release import export_legacy, export_release, logger


class ReleaseArtifactTest(unittest.TestCase):
    def test_local_release_is_immutable_and_verifiable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = root / "content" / "automation"
            content.mkdir(parents=True)
            (content / "item.json").write_text('{"name": "item"}\n', encoding="utf-8")
            releases = root / "releases"

            release_path, manifest = build_local_release(
                root,
                releases,
                "1.2.3",
                {"name": "dev"},
                "test",
                "commit-a",
            )

            self.assertEqual(verify_release(release_path), manifest)
            self.assertEqual(manifest["spec"]["gitCommit"], "commit-a")
            self.assertTrue(manifest["spec"]["artifacts"][0]["sha256"])
            with self.assertRaisesRegex(ReleaseArtifactError, "덮어쓰지"):
                build_local_release(root, releases, "1.2.3", {"name": "dev"}, "test", "commit-a")

    def test_release_tamper_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = root / "content"
            content.mkdir()
            (content / "item.txt").write_text("value\n", encoding="utf-8")
            release_path, manifest = build_local_release(root, root / "releases", "1.0.0", {}, "test", "commit")
            artifact = release_path / manifest["spec"]["artifacts"][0]["path"]
            artifact.write_bytes(b"tampered")

            with self.assertRaisesRegex(ReleaseArtifactError, "무결성"):
                verify_release(release_path)

    def test_version_must_be_semver(self):
        for value in ("../outside", "/tmp/outside", "latest", "1.0"):
            with self.assertRaises(ReleaseArtifactError):
                validate_version(value)
        self.assertEqual(validate_version("1.0.0-rc.1"), "1.0.0-rc.1")

    def test_remote_export_is_finalized_with_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            releases = Path(directory) / "releases"

            def fake_export(vra_client, vro_client, config, version, output_dir):
                target = Path(output_dir) / version
                target.mkdir()
                (target / "remote.zip").write_bytes(b"remote")
                (target / "manifest.json").write_text(
                    json.dumps({"components": {"vra_artifacts_zip": "remote.zip"}}),
                    encoding="utf-8",
                )

            with patch("vcf_release.export_legacy", side_effect=fake_export):
                release_path, manifest = export_release(
                    object(), object(), {"gitops_tag": "dev", "projects": []}, "2.0.0", releases,
                    {"name": "dev"}, "test", "commit-a"
                )

            self.assertEqual(manifest["spec"]["source"], "remote-export")
            self.assertEqual(verify_release(release_path), manifest)

    def test_export_implementation_has_no_update_or_package_mutation(self):
        source = inspect.getsource(export_legacy)
        self.assertNotIn("update_workflow", source)
        self.assertNotIn("update_action", source)
        self.assertNotIn("update_configuration", source)
        self.assertNotIn("update_resource_metadata", source)
        self.assertNotIn("create_or_update_package", source)

    def test_export_warning_prevents_final_release(self):
        with tempfile.TemporaryDirectory() as directory:
            releases = Path(directory) / "releases"

            def incomplete_export(vra_client, vro_client, config, version, output_dir):
                target = Path(output_dir) / version
                target.mkdir()
                (target / "partial.zip").write_bytes(b"partial")
                logger.warning("partial export")

            with patch("vcf_release.export_legacy", side_effect=incomplete_export):
                with self.assertRaisesRegex(ReleaseArtifactError, "완전하지"):
                    export_release(object(), object(), {}, "3.0.0", releases, {}, "test", "commit")
            self.assertFalse((releases / "3.0.0").exists())


if __name__ == "__main__":
    unittest.main()
