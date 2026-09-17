import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "tooling" / "vcf"))

from repository import (  # noqa: E402
    RepositoryContext,
    RepositoryContextError,
    RepositoryMode,
    detect_repository_context,
    require_instance_mode,
    validate_infrastructure_paths,
)


class RepositoryContextTest(unittest.TestCase):
    def _git(self, root, *args):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)

    def test_detects_template_ambiguous_and_instance_modes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._git(root, "init")
            self.assertEqual(detect_repository_context(root).mode, RepositoryMode.TEMPLATE)

            (root / "instance.yaml").write_text("kind: AutomationInstance\n", encoding="utf-8")
            self.assertEqual(detect_repository_context(root).mode, RepositoryMode.AMBIGUOUS)

            self._git(root, "add", "instance.yaml")
            self.assertEqual(detect_repository_context(root).mode, RepositoryMode.INSTANCE)

    def test_non_git_directory_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(RepositoryContextError):
                detect_repository_context(temporary_directory)

    def test_template_remote_commands_require_local_paths(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            context = RepositoryContext(root=root, mode=RepositoryMode.TEMPLATE)
            validate_infrastructure_paths(
                context,
                "adopt",
                root / "instance.local.yaml",
                root / "secrets.local.json",
                root / ".gitops" / "infrastructure-test",
            )
            with self.assertRaises(RepositoryContextError):
                validate_infrastructure_paths(
                    context,
                    "adopt",
                    root / "instance.local.yaml",
                    root / "secrets.local.json",
                    root / "infrastructure",
                )

    def test_instance_mode_accepts_default_paths(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            context = RepositoryContext(root=root, mode=RepositoryMode.INSTANCE)
            validate_infrastructure_paths(
                context,
                "status",
                root / "instance.yaml",
                root / "secrets.json",
                root / "infrastructure",
            )

    def test_template_plan_requires_all_outputs_under_gitops(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            context = RepositoryContext(root=root, mode=RepositoryMode.TEMPLATE)
            with self.assertRaises(RepositoryContextError):
                validate_infrastructure_paths(
                    context,
                    "plan",
                    root / "instance.local.yaml",
                    root / "secrets.local.json",
                    root / "infrastructure",
                    root / "plans",
                    root / "results",
                )

    def test_remote_mutation_requires_instance_mode(self):
        context = RepositoryContext(root=Path("/tmp"), mode=RepositoryMode.TEMPLATE)
        with self.assertRaises(RepositoryContextError):
            require_instance_mode(context, "apply")


if __name__ == "__main__":
    unittest.main()
