import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "tooling" / "template"))

from bootstrap import copy_secrets_example, write_instance  # noqa: E402


class TemplateBootstrapTest(unittest.TestCase):
    def test_writes_instance_and_local_secrets(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            instance_path = temporary_root / "instance.yaml"
            secrets_path = temporary_root / "secrets.json"

            write_instance(
                REPOSITORY_ROOT / "instance.example.yaml",
                instance_path,
                "automation-lab",
                "https://automation.lab.example.com/",
                "default",
                "lab",
            )
            created = copy_secrets_example(REPOSITORY_ROOT / "secrets.example.json", secrets_path)

            instance = yaml.safe_load(instance_path.read_text(encoding="utf-8"))
            secrets = json.loads(secrets_path.read_text(encoding="utf-8"))
            self.assertEqual(instance["metadata"]["name"], "automation-lab")
            self.assertEqual(instance["spec"]["endpoint"], "https://automation.lab.example.com")
            self.assertEqual(instance["spec"]["gitops"]["tag"], "lab")
            self.assertTrue(created)
            self.assertIn("automation", secrets)

    def test_refuses_to_overwrite_instance_by_default(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            instance_path = Path(temporary_directory) / "instance.yaml"
            instance_path.write_text("existing", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                write_instance(
                    REPOSITORY_ROOT / "instance.example.yaml",
                    instance_path,
                    "automation-lab",
                    "https://automation.lab.example.com",
                    "default",
                    "lab",
                )


if __name__ == "__main__":
    unittest.main()
