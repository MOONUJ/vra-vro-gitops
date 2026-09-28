import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tooling" / "vcf"))

from vcf_sync import pull_all


class FakeVroClient:
    def __init__(self, package=None):
        self.package = package
        self.exported = []
        self.mutations = []
        self.package_discovery = []

    def find_resources_by_tag(self, resource_type, tag):
        return []

    def find_resources_by_package(self, resource_type, package_name):
        self.package_discovery.append((resource_type, package_name))
        return []

    def get_package(self, name):
        return self.package

    def export_package(self, name, path):
        self.exported.append((name, path))

    def create_or_update_package(self, *args, **kwargs):
        self.mutations.append((args, kwargs))
        raise AssertionError("pull에서 package mutation을 호출하면 안 됩니다.")


class PullReadOnlyTest(unittest.TestCase):
    def test_missing_package_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            client = FakeVroClient(package=None)
            pull_all(
                client,
                {"gitops_tag": "dev", "package": {"name": "example", "local_path": "content/example.package"}},
                directory,
            )
            self.assertEqual([], client.mutations)
            self.assertEqual([], client.exported)

    def test_existing_package_is_only_exported(self):
        with tempfile.TemporaryDirectory() as directory:
            client = FakeVroClient(package={"name": "example"})
            pull_all(
                client,
                {"gitops_tag": "dev", "package": {"name": "example", "local_path": "content/example.package"}},
                directory,
            )
            self.assertEqual([], client.mutations)
            self.assertEqual(1, len(client.exported))

    def test_package_discovery_is_used_for_every_resource_type(self):
        with tempfile.TemporaryDirectory() as directory:
            client = FakeVroClient(package={"name": "example"})
            pull_all(
                client,
                {
                    "gitops_tag": "dev",
                    "vro_discovery_mode": "package",
                    "package": {"name": "example", "local_path": "content/example.package"},
                },
                directory,
            )
            self.assertEqual(
                [
                    ("Workflow", "example"),
                    ("Action", "example"),
                    ("ConfigurationElement", "example"),
                    ("ResourceElement", "example"),
                ],
                client.package_discovery,
            )


if __name__ == "__main__":
    unittest.main()
