import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class PackageMetadataTest(unittest.TestCase):
    def test_version_contract_is_consistent(self):
        pyproject = (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        package = (REPOSITORY_ROOT / "tooling" / "vcf" / "__init__.py").read_text(encoding="utf-8")
        project_version = re.search(r'^version = "([^"]+)"$', pyproject, re.MULTILINE).group(1)
        package_version = re.search(r'^__version__ = "([^"]+)"$', package, re.MULTILINE).group(1)
        pinned_versions = {
            (REPOSITORY_ROOT / ".template-version").read_text(encoding="utf-8").strip(),
            (REPOSITORY_ROOT / ".vcf-gitops-version").read_text(encoding="utf-8").strip(),
            project_version,
            package_version,
        }
        self.assertEqual({project_version}, pinned_versions)


if __name__ == "__main__":
    unittest.main()
