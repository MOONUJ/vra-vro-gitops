import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PackageRepositoryRootTest(unittest.TestCase):
    def test_installed_style_import_uses_current_instance_repository(self):
        package_root = Path(__file__).resolve().parents[1] / "tooling" / "vcf"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            (root / "instance.yaml").write_text("kind: AutomationInstance\n", encoding="utf-8")
            command = [
                sys.executable,
                "-c",
                "import config_loader; print(config_loader.REPOSITORY_ROOT)",
            ]
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(package_root)
            result = subprocess.run(command, cwd=root, env=environment, capture_output=True, text=True, check=True)
            self.assertEqual(str(root.resolve()), result.stdout.strip())

    def test_explicit_repository_root_wins(self):
        package_root = Path(__file__).resolve().parents[1] / "tooling" / "vcf"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            environment = dict(os.environ)
            environment["PYTHONPATH"] = str(package_root)
            environment["VCF_GITOPS_REPOSITORY_ROOT"] = str(root)
            result = subprocess.run(
                [sys.executable, "-c", "import config_loader; print(config_loader.REPOSITORY_ROOT)"],
                cwd="/tmp",
                env=environment,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(str(root), result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
