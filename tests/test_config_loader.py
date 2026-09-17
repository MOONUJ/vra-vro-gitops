import sys
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

    def test_native_config_does_not_generate_terraform_input(self):
        with self.assertRaises(ConfigError):
            build_terraform_variables(self.config)

    def test_native_management_mode_is_loaded(self):
        self.assertEqual(self.config["automation"]["management"]["infrastructure"], "native")

    def test_missing_split_config_does_not_fallback(self):
        with self.assertRaises(ConfigError):
            load_source_config(REPOSITORY_ROOT / "missing-instance.yaml", REPOSITORY_ROOT / "missing-secrets.json")

if __name__ == "__main__":
    unittest.main()
