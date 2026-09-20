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

    def find_resources_by_tag(self, resource_type, tag):
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


if __name__ == "__main__":
    unittest.main()
