import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "tooling" / "vcf"))

from repository import (  # noqa: E402
    OPERATION_REGISTRY,
    OperationClass,
    RepositoryContext,
    RepositoryContextError,
    RepositoryMode,
    classify_operation,
    detect_repository_context,
    is_worktree_clean,
    require_instance_mode,
    require_operation_allowed,
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

    def test_remote_mutation_registry_covers_existing_commands(self):
        self.assertEqual(classify_operation("status"), OperationClass.READ_ONLY)
        self.assertEqual(classify_operation("pull"), OperationClass.LOCAL_WRITE)
        for operation in ("apply", "push", "push-all", "content-apply", "restore", "restore-apply"):
            self.assertEqual(OPERATION_REGISTRY[operation], OperationClass.REMOTE_MUTATION)
        for operation in ("status", "export", "backup", "verify"):
            self.assertEqual(OPERATION_REGISTRY[operation], OperationClass.READ_ONLY)
        with self.assertRaisesRegex(RepositoryContextError, "등록되지 않은"):
            classify_operation("unknown-mutation")

    def test_operation_guard_blocks_template_mutation(self):
        context = RepositoryContext(root=Path("/tmp"), mode=RepositoryMode.TEMPLATE)
        with self.assertRaises(RepositoryContextError):
            require_operation_allowed(context, "push", require_clean=False)
        require_operation_allowed(context, "status")

    def test_operation_guard_requires_clean_tracked_state(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self._git(root, "init")
            self._git(root, "config", "user.email", "test@example.com")
            self._git(root, "config", "user.name", "Test")
            (root / "instance.yaml").write_text("kind: AutomationInstance\n", encoding="utf-8")
            self._git(root, "add", "instance.yaml")
            self._git(root, "commit", "-m", "baseline")
            context = detect_repository_context(root)

            self.assertTrue(is_worktree_clean(context))
            require_operation_allowed(context, "apply")

            (root / "instance.yaml").write_text("kind: Changed\n", encoding="utf-8")
            self.assertFalse(is_worktree_clean(context))
            with self.assertRaisesRegex(RepositoryContextError, "추적 파일 변경"):
                require_operation_allowed(context, "apply")


if __name__ == "__main__":
    unittest.main()
