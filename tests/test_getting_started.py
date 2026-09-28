import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class GettingStartedSmokeTest(unittest.TestCase):
    def test_bootstrap_edit_and_validate_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            instance_path = root / "instance.yaml"
            secrets_path = root / "secrets.json"

            bootstrap = subprocess.run(
                [
                    sys.executable,
                    str(REPOSITORY_ROOT / "tooling" / "template" / "bootstrap.py"),
                    "--name",
                    "automation-smoke-dev",
                    "--endpoint",
                    "https://automation.smoke.example.com/",
                    "--organization",
                    "default",
                    "--environment-tag",
                    "smoke-dev",
                    "--package-name",
                    "com.example.automation.smoke.dev",
                    "--output",
                    str(instance_path),
                    "--secrets-output",
                    str(secrets_path),
                ],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(0, bootstrap.returncode, bootstrap.stderr)

            instance = yaml.safe_load(instance_path.read_text(encoding="utf-8"))
            instance["spec"]["gitops"]["projects"] = ["smoke-project"]
            instance_path.write_text(
                yaml.safe_dump(instance, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            secrets = json.loads(secrets_path.read_text(encoding="utf-8"))
            secrets["automation"]["refresh_token"] = "local-smoke-token"
            secrets_path.write_text(json.dumps(secrets), encoding="utf-8")

            validation = subprocess.run(
                [
                    sys.executable,
                    str(REPOSITORY_ROOT / "tooling" / "vcf" / "configure.py"),
                    "validate",
                    "--instance",
                    str(instance_path),
                    "--secrets",
                    str(secrets_path),
                ],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(0, validation.returncode, validation.stderr)
            self.assertIn("environment=automation-smoke-dev", validation.stdout)
            self.assertIn("vcf_url=https://automation.smoke.example.com", validation.stdout)
            self.assertIn("vro_discovery=tag", validation.stdout)
            self.assertEqual(["smoke-project"], instance["spec"]["gitops"]["projects"])


if __name__ == "__main__":
    unittest.main()
