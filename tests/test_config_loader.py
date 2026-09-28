import sys
import tempfile
import unittest
import json
from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "tooling" / "vcf"))

from config_loader import ConfigError, build_terraform_variables, load_source_config, normalize_runtime_config  # noqa: E402


class ConfigLoaderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_source_config(REPOSITORY_ROOT / "instance.example.yaml", REPOSITORY_ROOT / "secrets.example.json")

    def test_split_config_supports_runtime_tools(self):
        runtime = normalize_runtime_config(self.config)
        self.assertEqual(runtime["vcf_url"], "https://automation.example.com")
        self.assertEqual(runtime["projects"], ["example-project"])

    def test_native_config_does_not_generate_terraform_input(self):
        with self.assertRaises(ConfigError):
            build_terraform_variables(self.config)

    def test_native_management_mode_is_loaded(self):
        self.assertEqual(self.config["automation"]["management"]["infrastructure"], "native")

    def test_missing_split_config_does_not_fallback(self):
        with self.assertRaises(ConfigError):
            load_source_config(REPOSITORY_ROOT / "missing-instance.yaml", REPOSITORY_ROOT / "missing-secrets.json")

    def test_real_instance_rejects_example_package_placeholder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            instance = root / "instance.yaml"
            secrets = root / "secrets.json"
            instance.write_bytes((REPOSITORY_ROOT / "instance.example.yaml").read_bytes())
            secrets.write_bytes((REPOSITORY_ROOT / "secrets.example.json").read_bytes())
            with self.assertRaisesRegex(ConfigError, "placeholder"):
                load_source_config(instance, secrets)

    def test_external_orchestrator_reuses_automation_oauth_for_independent_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            instance = yaml.safe_load((REPOSITORY_ROOT / "instance.example.yaml").read_text(encoding="utf-8"))
            instance["spec"]["orchestrator"].update(
                {
                    "deployment": "external",
                    "endpoint": "https://vro.example.com",
                    "verifySsl": True,
                    "discovery": {"mode": "package", "requireNonEmpty": True},
                }
            )
            instance_path = root / "external.yaml"
            secrets_path = root / "secrets.json"
            instance_path.write_text(yaml.safe_dump(instance), encoding="utf-8")
            secrets_path.write_text(
                json.dumps(
                    {"automation": {"refresh_token": "automation-token"}}
                ),
                encoding="utf-8",
            )

            runtime = normalize_runtime_config(load_source_config(instance_path, secrets_path))

            self.assertEqual("https://vro.example.com", runtime["vro_url"])
            self.assertEqual("automation-token", runtime["vro_refresh_token"])
            self.assertEqual("package", runtime["vro_discovery_mode"])
            self.assertTrue(runtime["vro_require_non_empty"])

    def test_external_orchestrator_requires_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            instance = yaml.safe_load((REPOSITORY_ROOT / "instance.example.yaml").read_text(encoding="utf-8"))
            instance["spec"]["orchestrator"]["deployment"] = "external"
            instance_path = root / "external.yaml"
            secrets_path = root / "secrets.json"
            instance_path.write_text(yaml.safe_dump(instance), encoding="utf-8")
            secrets_path.write_text(json.dumps({"automation": {"refresh_token": "token"}}), encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "endpoint"):
                load_source_config(instance_path, secrets_path)

if __name__ == "__main__":
    unittest.main()
