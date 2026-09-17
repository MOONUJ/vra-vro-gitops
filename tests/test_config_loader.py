import json
import sys
import tempfile
import unittest
from pathlib import Path

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

    def test_split_config_supports_terraform(self):
        variables = build_terraform_variables(self.config)
        self.assertEqual(variables["cloud_zone_name"], "example-cloud-zone")
        self.assertFalse(variables["vra_insecure"])

    def test_legacy_runtime_config_remains_supported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "vcf_url": "https://legacy.example.com",
                        "refresh_token": "token",
                        "package": {"local_path": "vro/packages/legacy.package"},
                    }
                ),
                encoding="utf-8",
            )
            legacy = load_source_config(legacy_config_path=config_path)
            runtime = normalize_runtime_config(legacy)
            self.assertEqual(runtime["vcf_url"], legacy["vcf_url"])
            self.assertEqual(runtime["package"]["local_path"], "content/orchestrator/packages/legacy.package")
            with self.assertRaises(ConfigError):
                build_terraform_variables(legacy)


if __name__ == "__main__":
    unittest.main()
