#!/usr/bin/env python3
"""Push a local Markdown workspace to bensz-notes with local-authoritative semantics.

The remote API identifies notes by path.  This tool records the last successful
manifest locally, uploads changed files in one pass, and can delete paths absent
from the local workspace when explicitly confirmed.  A rename is implemented as
an upsert at the new path followed by a soft-delete at the old path.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from _bn_env import BnEnv, resolve_bn_env
from _http_json import HttpResult, request_json


SKILL_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ".bensz-notes"
STATE_FILE = "sync-state.json"
DEFAULT_EXCLUDED_DIRS = {".git", ".bensz-notes", "node_modules", "__pycache__"}


@dataclass(frozen=True)
class RemoteNote:
    id: str
    path: str
    revision: int
    content_hash: str
    deleted_at: str | None = None


@dataclass(frozen=True)
class LocalFile:
    path: str
    markdown: str
    content_hash: str


def _api_url(env: BnEnv, path: str) -> str:
    return f"{env.url.rstrip('/')}{env.api_prefix}{path if path.startswith('/') else '/' + path}"


def _headers(env: BnEnv, key: str | None = None) -> dict[str, str]:
    headers = {"authorization": f"Bearer {env.key}", "user-agent": "bensz-notes-vibe-config/workspace-sync"}
    if key:
        headers["idempotency-key"] = key
    return headers


def _hash(markdown: str) -> str:
    return "sha256:" + hashlib.sha256(markdown.encode("utf-8")).hexdigest()


def _state_path(root: Path) -> Path:
    return root / STATE_DIR / STATE_FILE


def read_state(root: Path) -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(_state_path(root).read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def write_state(root: Path, state: dict[str, dict[str, Any]]) -> None:
    target = _state_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(target)


def _matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def scan_workspace(root: Path, includes: list[str], excludes: list[str]) -> list[LocalFile]:
    files: list[LocalFile] = []
    for current, directories, names in os.walk(root):
        directories[:] = sorted(name for name in directories if name not in DEFAULT_EXCLUDED_DIRS)
        for name in sorted(names):
            if not name.lower().endswith(".md"):
                continue
            absolute = Path(current) / name
            relative = absolute.relative_to(root).as_posix()
            if not _matches(relative, includes) or _matches(relative, excludes):
                continue
            markdown = absolute.read_text(encoding="utf-8")
            files.append(LocalFile(relative, markdown, _hash(markdown)))
    return sorted(files, key=lambda item: item.path)


def parse_manifest(payload: Any) -> dict[str, RemoteNote]:
    if not isinstance(payload, dict) or not isinstance(payload.get("notes"), list):
        raise RuntimeError("Invalid /sync/manifest response: expected {notes: [...]}")
    notes: dict[str, RemoteNote] = {}
    for raw in payload["notes"]:
        if not isinstance(raw, dict) or raw.get("deletedAt"):
            continue
        try:
            note = RemoteNote(
                id=str(raw["id"]), path=str(raw["path"]), revision=int(raw["revision"]),
                content_hash=str(raw["contentHash"]), deleted_at=raw.get("deletedAt"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("Invalid note in /sync/manifest response") from exc
        notes[note.path] = note
    return notes


def detect_renames(files: list[LocalFile], state: dict[str, dict[str, Any]], remote: dict[str, RemoteNote]) -> dict[str, str]:
    """Return new-path -> old-path for unchanged files moved since the last push.

    A changed file that is moved cannot be identified safely by the path-only
    protocol, so it remains a create plus (optional) delete operation.
    """
    local_paths = {file.path for file in files}
    candidates: dict[str, list[str]] = {}
    for old_path, saved in state.items():
        if old_path in local_paths or old_path not in remote:
            continue
        content_hash = saved.get("contentHash")
        if isinstance(content_hash, str):
            candidates.setdefault(content_hash, []).append(old_path)
    renames: dict[str, str] = {}
    for file in files:
        old_paths = candidates.get(file.content_hash, [])
        if file.path not in remote and len(old_paths) == 1:
            renames[file.path] = old_paths[0]
    return renames


def plan_sync(files: list[LocalFile], remote: dict[str, RemoteNote], state: dict[str, dict[str, Any]], *, delete_missing: bool) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    local_paths = {file.path for file in files}
    renames = detect_renames(files, state, remote)
    for file in files:
        current = remote.get(file.path)
        if current and current.content_hash == file.content_hash:
            actions.append({"action": "skip", "path": file.path})
        elif current:
            actions.append({"action": "update", "path": file.path})
        elif file.path in renames:
            actions.append({"action": "rename", "path": file.path, "from": renames[file.path]})
        else:
            actions.append({"action": "create", "path": file.path})
    for old_path in sorted(set(remote) - local_paths):
        actions.append({"action": "delete" if delete_missing else "delete-preview", "path": old_path})
    return actions


def _request(env: BnEnv, method: str, path: str, *, body: Any | None = None, idempotency_key: str | None = None) -> HttpResult:
    return request_json(method, _api_url(env, path), headers=_headers(env, idempotency_key), json_body=body, timeout_seconds=20, retries=2)


def fetch_manifest(env: BnEnv) -> dict[str, RemoteNote]:
    result = _request(env, "GET", "/sync/manifest")
    if result.status != 200:
        raise RuntimeError(f"manifest request failed with HTTP {result.status}")
    return parse_manifest(result.json)


def _encoded_path(path: str) -> str:
    return "/".join(quote(part, safe="") for part in path.split("/"))


def upsert(env: BnEnv, file: LocalFile, remote: RemoteNote | None, status: str | None) -> RemoteNote:
    body: dict[str, Any] = {"markdown": file.markdown, "createFolders": True}
    if remote:
        body.update({"baseRevision": remote.revision, "baseContentHash": remote.content_hash})
    if status:
        body["status"] = status
    result = _request(env, "PUT", f"/sync/notes/by-path/{_encoded_path(file.path)}", body=body, idempotency_key=f"sync:{_encoded_path(file.path)}:{file.content_hash}")
    if result.status == 409:
        raise RuntimeError(f"SYNC_CONFLICT: {file.path}; re-run to read the latest manifest before deciding how to proceed")
    if result.status not in {200, 201} or not isinstance(result.json, dict) or not isinstance(result.json.get("note"), dict):
        raise RuntimeError(f"upsert failed for {file.path} with HTTP {result.status}")
    note = result.json["note"]
    return RemoteNote(str(note["id"]), file.path, int(note["revision"]), str(note.get("contentHash") or file.content_hash))


def delete_remote(env: BnEnv, remote: RemoteNote) -> None:
    result = _request(env, "DELETE", f"/sync/notes/by-path/{_encoded_path(remote.path)}", body={"baseRevision": remote.revision, "baseContentHash": remote.content_hash}, idempotency_key=f"sync-delete:{_encoded_path(remote.path)}:{remote.revision}")
    if result.status not in {200, 204, 404}:
        raise RuntimeError(f"delete failed for {remote.path} with HTTP {result.status}")


def _state_entry(note: RemoteNote) -> dict[str, Any]:
    return {"id": note.id, "revision": note.revision, "contentHash": note.content_hash, "syncedAt": datetime.now(timezone.utc).isoformat()}


def run(args: argparse.Namespace) -> int:
    root = Path(args.workspace).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"Workspace does not exist or is not a directory: {root}")
    if args.delete_missing and not args.confirm_delete:
        raise SystemExit("--delete-missing requires --confirm-delete.")
    if args.status == "published" and not args.allow_publish:
        raise SystemExit("--status published requires --allow-publish.")
    env = resolve_bn_env(skill_root=SKILL_ROOT, env_file=Path(args.env).expanduser() if args.env else None)
    if not env.key or len(env.key) < 20:
        raise SystemExit("Missing or invalid BENSZ_NOTES_KEY.")
    files = scan_workspace(root, args.include or ["**/*.md", "*.md"], args.exclude or [])
    remote = fetch_manifest(env)
    state = read_state(root)
    actions = plan_sync(files, remote, state, delete_missing=args.delete_missing)
    print(json.dumps({"workspace": str(root), "dryRun": args.dry_run, "actions": actions}, ensure_ascii=False, indent=2))
    if args.dry_run:
        return 0
    local_by_path = {file.path: file for file in files}
    for action in actions:
        kind, path = action["action"], action["path"]
        if kind == "skip":
            state[path] = _state_entry(remote[path])
        elif kind in {"create", "update", "rename"}:
            state[path] = _state_entry(upsert(env, local_by_path[path], remote.get(path), args.status))
        if kind == "delete":
            delete_remote(env, remote[path])
            state.pop(path, None)
    write_state(root, state)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="将本地 Markdown 工作区本地优先地推送到 bensz-notes")
    parser.add_argument("workspace", help="本地 Markdown 工作区根目录")
    parser.add_argument("--env", help="remote.env 路径")
    parser.add_argument("--dry-run", action="store_true", help="仅读 manifest 并输出计划，不写入远端或状态文件")
    parser.add_argument("--delete-missing", action="store_true", help="软删除云端存在但本地缺失的路径，以实现镜像")
    parser.add_argument("--confirm-delete", action="store_true", help="确认 --delete-missing 的软删除")
    parser.add_argument("--include", action="append", default=[], help="包含 glob；可重复，默认所有 Markdown")
    parser.add_argument("--exclude", action="append", default=[], help="排除 glob；可重复")
    parser.add_argument("--status", choices=["draft", "private", "published"], help="创建/更新时指定状态；默认保留远端状态")
    parser.add_argument("--allow-publish", action="store_true", help="确认设置 published 状态")
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
