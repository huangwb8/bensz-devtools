from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import sys

SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import client  # noqa: E402
from _bn_env import normalize_api_prefix, resolve_bn_env  # noqa: E402


class BenszNotesClientCliTests(unittest.TestCase):
    def run_cli(self, argv: list[str]) -> tuple[int, str]:
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = client.main(argv)
        return code, stream.getvalue()

    def test_env_resolution_from_explicit_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / "remote.env"
            env_file.write_text(
                "BENSZ_NOTES_URL=https://notes.example.com\n"
                "BENSZ_NOTES_KEY=bnt_12345678901234567890\n",
                encoding="utf-8",
            )
            env = resolve_bn_env(skill_root=SKILL_ROOT, env_file=env_file)
        self.assertEqual(env.url, "https://notes.example.com")
        self.assertEqual(env.api_prefix, "/api/backend")
        self.assertTrue(env.key.startswith("bnt_"))

    def test_api_prefix_can_be_empty(self) -> None:
        self.assertEqual(normalize_api_prefix("-"), "")
        self.assertEqual(normalize_api_prefix("/api/backend/"), "/api/backend")

    def test_dry_run_list_uses_backend_proxy(self) -> None:
        env = {
            "BENSZ_NOTES_URL": "https://notes.example.com",
            "BENSZ_NOTES_KEY": "bnt_12345678901234567890",
        }
        with patch.dict(os.environ, env, clear=True):
            code, output = self.run_cli(["--dry-run", "notes", "list", "--limit", "3"])
        self.assertEqual(code, 0)
        self.assertIn("https://notes.example.com/api/backend/notes?limit=3", output)
        self.assertNotIn("bnt_12345678901234567890", output)

    def test_publish_requires_explicit_allow_flag(self) -> None:
        env = {
            "BENSZ_NOTES_URL": "https://notes.example.com",
            "BENSZ_NOTES_KEY": "bnt_12345678901234567890",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(SystemExit) as raised:
                self.run_cli([
                    "--dry-run",
                    "notes",
                    "create",
                    "--title",
                    "T",
                    "--markdown",
                    "# T",
                    "--status",
                    "published",
                ])
        self.assertIn("--allow-publish", str(raised.exception))

    def test_delete_requires_confirmation(self) -> None:
        env = {
            "BENSZ_NOTES_URL": "https://notes.example.com",
            "BENSZ_NOTES_KEY": "bnt_12345678901234567890",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(SystemExit) as raised:
                self.run_cli(["--dry-run", "notes", "delete", "--id", "note_1"])
        self.assertIn("--confirm-delete", str(raised.exception))

    def test_sync_path_rejects_traversal(self) -> None:
        with self.assertRaises(SystemExit):
            client._path_arg("../bad.md")
        self.assertEqual(client._path_arg("folder/测试.md"), "folder/%E6%B5%8B%E8%AF%95.md")

    def test_update_requires_at_least_one_changed_field(self) -> None:
        env = {
            "BENSZ_NOTES_URL": "https://notes.example.com",
            "BENSZ_NOTES_KEY": "bnt_12345678901234567890",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(SystemExit) as raised:
                self.run_cli(["--dry-run", "notes", "update", "--id", "note_1", "--base-revision", "3"])
        self.assertIn("No note fields", str(raised.exception))

    def test_move_requires_explicit_target(self) -> None:
        env = {
            "BENSZ_NOTES_URL": "https://notes.example.com",
            "BENSZ_NOTES_KEY": "bnt_12345678901234567890",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(SystemExit) as raised:
                self.run_cli(["--dry-run", "notes", "move", "--id", "note_1", "--base-revision", "3"])
        self.assertIn("--folder-id or --root-folder", str(raised.exception))

    def test_sync_upsert_omits_status_by_default(self) -> None:
        env = {
            "BENSZ_NOTES_URL": "https://notes.example.com",
            "BENSZ_NOTES_KEY": "bnt_12345678901234567890",
        }
        with patch.dict(os.environ, env, clear=True):
            code, output = self.run_cli([
                "--dry-run",
                "sync",
                "upsert",
                "--path",
                "folder/note.md",
                "--markdown",
                "# Note",
        ])
        self.assertEqual(code, 0)
        self.assertNotIn('"status": "draft"', output)

    def test_sync_delete_requires_remote_baseline(self) -> None:
        env = {
            "BENSZ_NOTES_URL": "https://notes.example.com",
            "BENSZ_NOTES_KEY": "bnt_12345678901234567890",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(SystemExit) as raised:
                self.run_cli([
                    "--dry-run",
                    "sync",
                    "delete",
                    "--path",
                    "folder/note.md",
                    "--confirm-delete",
                ])
        self.assertIn("--base-revision", str(raised.exception))

    def test_settings_patch_requires_body(self) -> None:
        env = {
            "BENSZ_NOTES_URL": "https://notes.example.com",
            "BENSZ_NOTES_KEY": "bnt_12345678901234567890",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(SystemExit) as raised:
                self.run_cli(["--dry-run", "settings", "patch"])
        self.assertIn("--set", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
