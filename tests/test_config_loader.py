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

if __name__ == "__main__":
    unittest.main()
