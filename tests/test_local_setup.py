import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "tooling" / "template"))

import setup as local_setup  # noqa: E402
from setup import SetupError, _prompt, main, write_refresh_token  # noqa: E402


class LocalSetupTest(unittest.TestCase):
    def test_refresh_token_is_written_with_private_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "secrets.json"
            self.assertTrue(write_refresh_token(path, "secret-value"))
            value = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual("secret-value", value["automation"]["refresh_token"])
            self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))

    def test_existing_real_token_is_not_overwritten_without_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "secrets.json"
            write_refresh_token(path, "existing")
            self.assertFalse(write_refresh_token(path, "replacement"))
            value = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual("existing", value["automation"]["refresh_token"])
            self.assertTrue(write_refresh_token(path, "replacement", overwrite=True))

    def test_non_interactive_mode_requires_explicit_values(self):
        with self.assertRaisesRegex(SetupError, "값이 필요"):
            _prompt(None, "Automation endpoint", non_interactive=True)
        self.assertEqual("default", _prompt(None, "Organization", default="default", non_interactive=True))

    def test_non_interactive_main_fails_before_writing_when_values_are_missing(self):
        self.assertEqual(1, main(["--non-interactive"]))

    def test_non_interactive_setup_does_not_forward_token_to_commands(self):
        commands = []
        environment = {"VCF_AUTOMATION_REFRESH_TOKEN": "secret-value"}
        arguments = [
            "--non-interactive",
            "--name", "automation-lab",
            "--endpoint", "https://automation.example.com",
            "--package-name", "com.example.automation.lab",
            "--project", "project-a",
            "--orchestrator-deployment", "embedded",
        ]
        with patch.dict(local_setup.os.environ, environment, clear=True), patch.object(
            local_setup, "run", side_effect=lambda command: commands.append([str(item) for item in command])
        ), patch.object(local_setup, "write_refresh_token", return_value=True):
            self.assertEqual(0, main(arguments))
            self.assertNotIn("VCF_AUTOMATION_REFRESH_TOKEN", local_setup.os.environ)

        self.assertGreaterEqual(len(commands), 4)
        self.assertTrue(all("secret-value" not in item for command in commands for item in command))


if __name__ == "__main__":
    unittest.main()
