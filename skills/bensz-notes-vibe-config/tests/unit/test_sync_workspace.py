from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

SKILL_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import sync_workspace as sync  # noqa: E402


class WorkspaceSyncTests(unittest.TestCase):
    def test_scan_excludes_legacy_internal_state_and_hashes_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "note.md").write_text("# 测试", encoding="utf-8")
            (root / ".bensz-notes").mkdir()
            (root / ".bensz-notes" / "ignored.md").write_text("ignored", encoding="utf-8")
            files = sync.scan_workspace(root, ["**/*.md", "*.md"], [])
        self.assertEqual([item.path for item in files], ["note.md"])
        self.assertTrue(files[0].content_hash.startswith("sha256:"))

    def test_state_is_written_only_to_explicit_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / ".bensz-api" / "task-test" / "bensz-notes-vibe-config" / "output" / "sync-state.json"
            state = {"note.md": {"id": "n1", "revision": 1, "contentHash": "sha256:test"}}
            sync.write_state(state_path, state)
            self.assertEqual(sync.read_state(state_path), state)
            self.assertFalse((root / ".bensz-notes").exists())

    def test_omitted_state_path_is_a_noop(self) -> None:
        self.assertEqual(sync.read_state(None), {})
        sync.write_state(None, {"note.md": {"id": "n1"}})

    def test_unchanged_directory_rename_is_detected(self) -> None:
        file = sync.LocalFile("new/name.md", "# Same", sync._hash("# Same"))
        remote = {"old/name.md": sync.RemoteNote("n1", "old/name.md", 2, file.content_hash)}
        state = {"old/name.md": {"id": "n1", "revision": 2, "contentHash": file.content_hash}}
        actions = sync.plan_sync([file], remote, state, delete_missing=True)
        self.assertIn({"action": "rename", "path": "new/name.md", "from": "old/name.md"}, actions)
        self.assertIn({"action": "delete", "path": "old/name.md"}, actions)

    def test_changed_remote_path_is_updated_with_local_authority(self) -> None:
        file = sync.LocalFile("note.md", "# Local", sync._hash("# Local"))
        remote = {"note.md": sync.RemoteNote("n1", "note.md", 7, sync._hash("# Cloud"))}
        actions = sync.plan_sync([file], remote, {}, delete_missing=False)
        self.assertEqual(actions, [{"action": "update", "path": "note.md"}])

    def test_missing_remote_path_is_previewed_without_delete_confirmation(self) -> None:
        remote = {"old.md": sync.RemoteNote("n1", "old.md", 1, sync._hash("# old"))}
        actions = sync.plan_sync([], remote, {}, delete_missing=False)
        self.assertEqual(actions, [{"action": "delete-preview", "path": "old.md"}])


if __name__ == "__main__":
    unittest.main()
