import unittest
from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class RepositoryStructureTest(unittest.TestCase):
    def test_lifecycle_manifest_paths_exist(self):
        for manifest_path in sorted((REPOSITORY_ROOT / "lifecycle").glob("day*.yaml")):
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            for resource in manifest["spec"]["resources"]:
                target = REPOSITORY_ROOT / resource["path"]
                if resource["path"] == "instance.yaml" and not target.exists():
                    target = REPOSITORY_ROOT / "instance.example.yaml"
                self.assertTrue(target.exists(), f"{manifest_path}: 존재하지 않는 경로 {resource['path']}")

    def test_required_repository_boundaries_exist(self):
        required_paths = [
            ".template-version",
            "instance.example.yaml",
            "foundation/automation/terraform",
            "content/automation",
            "content/orchestrator",
            "tooling/vcf/vcf_sync.py",
            "tooling/vcf/vcf_release.py",
            "releases",
            "automation/loops",
            "tooling/template/bootstrap.py",
        ]
        for relative_path in required_paths:
            self.assertTrue((REPOSITORY_ROOT / relative_path).exists(), relative_path)

    def test_legacy_gitops_directory_is_absent(self):
        self.assertFalse((REPOSITORY_ROOT / "gitops").exists())


if __name__ == "__main__":
    unittest.main()
