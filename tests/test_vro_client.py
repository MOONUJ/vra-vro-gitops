import sys
import types
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "tooling" / "vcf"))
try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    sys.modules["requests"] = types.SimpleNamespace()

from vro_client import from_runtime_config  # noqa: E402


class VroClientConfigurationTest(unittest.TestCase):
    def test_external_endpoint_reuses_automation_oauth_credential(self):
        client = from_runtime_config(
            {
                "vcf_url": "https://automation.example.com",
                "refresh_token": "automation-token",
                "org": "example",
                "verify_ssl": True,
                "vro_url": "https://vro.example.com",
                "vro_verify_ssl": True,
            }
        )

        self.assertEqual("https://vro.example.com/vco", client.vco_url)
        self.assertEqual("automation-token", client.refresh_token)

    def test_package_membership_is_normalized_for_discovery(self):
        client = from_runtime_config(
            {
                "vcf_url": "https://automation.example.com",
                "refresh_token": "token",
                "vro_url": "https://vro.example.com",
            }
        )
        client.get_package = lambda name: {
            "workflows": [
                {
                    "href": "https://vro.example.com/vco/api/workflows/workflow-1",
                    "attribute": [
                        {"name": "name", "value": "Resize VM"},
                        {"name": "version", "value": "1.2.0"},
                    ],
                }
            ]
        }

        resources = client.find_resources_by_package("Workflow", "com.example.gitops")

        self.assertEqual("workflow-1", resources[0]["id"])
        self.assertEqual("Resize VM", resources[0]["name"])
        self.assertEqual("1.2.0", resources[0]["version"])


if __name__ == "__main__":
    unittest.main()
