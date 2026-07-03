from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from _bn_env import BnEnv, resolve_bn_env
from _flat_yaml import load_flat_yaml
from _http_json import HttpResult, request_json


DRY_RUN = False


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _config() -> dict[str, Any]:
    cfg = load_flat_yaml(_skill_root() / "config.yaml")
    return {
        "name": cfg.scalars.get("skill_name", "bensz-notes-vibe-config"),
        "version": cfg.scalars.get("skill_version", "0.1.0"),
        "timeout": int(cfg.scalars.get("request_timeout_seconds", "15")),
        "idempotency_enabled": cfg.scalars.get("idempotency_enabled", "true").lower() in {"1", "true", "yes", "on"},
        "idempotency_retry_count": int(cfg.scalars.get("idempotency_retry_count", "2")),
        "idempotency_prefix": cfg.scalars.get("idempotency_prefix", "bn-vibe-config-v1"),
    }


def _headers(env: BnEnv, *, include_auth: bool = True, idempotency_key: str | None = None) -> dict[str, str]:
    cfg = _config()
    headers = {
        "user-agent": f"{cfg['name']}/{cfg['version']} ({platform.system()} {platform.release()})",
        "x-request-id": f"{cfg['name']}-{uuid.uuid4()}",
    }
    if include_auth:
        headers["authorization"] = f"Bearer {env.key}"
    if idempotency_key:
        headers["idempotency-key"] = idempotency_key
    return headers


def _url(env: BnEnv, path: str) -> str:
    clean_path = path if path.startswith("/") else f"/{path}"
    return f"{env.url.rstrip('/')}{env.api_prefix}{clean_path}"


def _url_with_query(env: BnEnv, path: str, params: dict[str, Any]) -> str:
    filtered = [(key, value) for key, value in params.items() if value is not None and value != ""]
    base = _url(env, path)
    return base if not filtered else f"{base}?{urlencode(filtered)}"


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _auto_idempotency_key(method: str, path: str, body: Any) -> str:
    cfg = _config()
    material = {"method": method.upper(), "path": path, "body": body}
    digest = hashlib.sha256(_stable_json(material).encode("utf-8")).hexdigest()
    return f"{cfg['idempotency_prefix']}-{digest[:32]}"


def _json_value(raw: str) -> Any:
    value = raw.strip()
    if value in {"true", "false", "null"}:
        return json.loads(value)
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return raw


def _body_from_args(args: argparse.Namespace, *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {}
    json_text = getattr(args, "json", None)
    json_file = getattr(args, "json_file", None)
    if json_text and json_file:
        raise SystemExit("--json cannot be combined with --json-file.")
    if json_text:
        parsed = json.loads(json_text)
        if not isinstance(parsed, dict):
            raise SystemExit("--json must be a JSON object.")
        body.update(parsed)
    if json_file:
        parsed = json.loads(Path(json_file).expanduser().read_text(encoding="utf-8"))
        if not isinstance(parsed, dict):
            raise SystemExit("--json-file must contain a JSON object.")
        body.update(parsed)
    for item in getattr(args, "set", None) or []:
        if "=" not in item:
            raise SystemExit("--set must use key=value.")
        key, value = item.split("=", 1)
        body[key.strip()] = _json_value(value)
    if extra:
        body.update({key: value for key, value in extra.items() if value is not None})
    return body


def _without_none(body: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in body.items() if value is not None}


def _result_payload(res: HttpResult) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": res.status, "json": res.json}
    if res.status >= 400 and res.json is None and res.body_text.strip():
        payload["body"] = res.body_text[:800]
    return payload


def _call(
    env: BnEnv,
    method: str,
    path: str,
    *,
    json_body: Any | None = None,
    query: dict[str, Any] | None = None,
    auth: bool = True,
    timeout_seconds: int,
    retries: int = 0,
    idempotency_key: str | None = None,
) -> HttpResult:
    url = _url_with_query(env, path, query or {})
    method_upper = method.upper()
    if idempotency_key is None and method_upper in {"POST", "PUT", "PATCH", "DELETE"} and _config()["idempotency_enabled"]:
        idempotency_key = _auto_idempotency_key(method_upper, path, json_body)
        retries = max(retries, int(_config()["idempotency_retry_count"]))

    if DRY_RUN:
        dry_headers: dict[str, str] = {}
        if idempotency_key:
            dry_headers["idempotency-key"] = idempotency_key
        _print_json({
            "dry_run": True,
            "method": method_upper,
            "url": url,
            "json_body": json_body,
            "retries": retries,
            "headers": dry_headers,
            "note": "authorization header hidden",
        })
        return HttpResult(status=0, headers={}, body_text="", json=None)

    return request_json(
        method_upper,
        url,
        headers=_headers(env, include_auth=auth, idempotency_key=idempotency_key),
        json_body=json_body,
        timeout_seconds=timeout_seconds,
        retries=retries,
    )


def _send_and_print(
    env: BnEnv,
    method: str,
    path: str,
    *,
    json_body: Any | None = None,
    query: dict[str, Any] | None = None,
    auth: bool = True,
    timeout_seconds: int,
    ok_statuses: set[int] | None = None,
    retries: int = 0,
    idempotency_key: str | None = None,
) -> int:
    res = _call(
        env,
        method,
        path,
        json_body=json_body,
        query=query,
        auth=auth,
        timeout_seconds=timeout_seconds,
        retries=retries,
        idempotency_key=idempotency_key,
    )
    _print_json(_result_payload(res))
    if DRY_RUN:
        return 0
    return 0 if res.status in (ok_statuses or {200}) else 1


def _ensure_key(env: BnEnv) -> None:
    if not env.key:
        raise SystemExit("Missing BENSZ_NOTES_KEY.")
    if len(env.key) < 20:
        raise SystemExit("Invalid BENSZ_NOTES_KEY (length < 20).")


def _status_guard(status: str | None, allow_publish: bool) -> None:
    if status == "published" and not allow_publish:
        raise SystemExit("Publishing requires --allow-publish.")


def _path_arg(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    if not normalized or normalized.startswith("/") or ".." in normalized.split("/") or not normalized.endswith(".md"):
        raise SystemExit("sync path must be a relative POSIX .md path without '..'.")
    return quote(normalized, safe="/")


def cmd_health(env: BnEnv, timeout_seconds: int) -> int:
    return _send_and_print(env, "GET", "/health", auth=False, timeout_seconds=timeout_seconds, ok_statuses={200}, retries=2)


def cmd_doctor(env: BnEnv, timeout_seconds: int) -> int:
    print(f"url={env.url}")
    print(f"api_prefix={env.api_prefix or '(empty)'}")
    print(f"key={env.key_prefix()}")
    if env.env_file_path:
        print(f"env_file={env.env_file_path}")
    if cmd_health(env, timeout_seconds) != 0:
        return 1
    return _send_and_print(env, "GET", "/auth/me", timeout_seconds=timeout_seconds, ok_statuses={200}, retries=1)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="client.py",
        description="bensz-notes DevTools Agent API 客户端。通过 Bearer Token 管理笔记、目录、标签、同步与治理入口。",
    )
    parser.add_argument("--env", default=None, help="指定 env 文件路径。")
    parser.add_argument("--timeout", type=int, default=None, help="请求超时秒数。")
    parser.add_argument("--dry-run", action="store_true", help="打印请求，不发送。")
    parser.add_argument("--api-prefix", default=None, help="覆盖 API 前缀；直连 API 时传 '-'。")

    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("health", help="检查服务健康（不鉴权）。")
    sub.add_parser("doctor", help="health + auth/me 诊断。")
    sub.add_parser("me", help="读取当前 principal / workspace。")

    notes = sub.add_parser("notes", help="笔记管理")
    notes_sub = notes.add_subparsers(dest="notes_cmd", required=True)
    notes_l = notes_sub.add_parser("list")
    notes_l.add_argument("--q", default=None)
    notes_l.add_argument("--include-deleted", action="store_true")
    notes_l.add_argument("--limit", type=int, default=None)
    notes_l.add_argument("--cursor", default=None)
    notes_s = notes_sub.add_parser("show")
    notes_s.add_argument("--id", required=True)
    notes_c = notes_sub.add_parser("create")
    notes_c.add_argument("--title", required=True)
    notes_c.add_argument("--markdown", required=True)
    notes_c.add_argument("--status", choices=["draft", "private", "published"], default="draft")
    notes_c.add_argument("--folder-id", default=None)
    notes_c.add_argument("--tag-id", action="append", default=None)
    notes_c.add_argument("--allow-publish", action="store_true")
    notes_u = notes_sub.add_parser("update")
    notes_u.add_argument("--id", required=True)
    notes_u.add_argument("--base-revision", type=int, required=True)
    notes_u.add_argument("--title", default=None)
    notes_u.add_argument("--markdown", default=None)
    notes_u.add_argument("--status", choices=["draft", "private", "published"], default=None)
    notes_u.add_argument("--folder-id", default=None)
    notes_u.add_argument("--root-folder", action="store_true")
    notes_u.add_argument("--tag-id", action="append", default=None)
    notes_u.add_argument("--clear-tags", action="store_true")
    notes_u.add_argument("--allow-publish", action="store_true")
    notes_a = notes_sub.add_parser("append")
    notes_a.add_argument("--id", required=True)
    notes_a.add_argument("--markdown", required=True)
    notes_a.add_argument("--base-revision", type=int, default=None)
    notes_m = notes_sub.add_parser("move")
    notes_m.add_argument("--id", required=True)
    notes_m.add_argument("--base-revision", type=int, required=True)
    notes_m.add_argument("--folder-id", default=None)
    notes_m.add_argument("--root-folder", action="store_true")
    notes_d = notes_sub.add_parser("delete")
    notes_d.add_argument("--id", required=True)
    notes_d.add_argument("--confirm-delete", action="store_true")
    notes_tr = notes_sub.add_parser("trash-restore")
    notes_tr.add_argument("--id", required=True)
    notes_v = notes_sub.add_parser("versions")
    notes_v.add_argument("--id", required=True)
    notes_v.add_argument("--take", type=int, default=None)
    notes_vg = notes_sub.add_parser("version")
    notes_vg.add_argument("--id", required=True)
    notes_vg.add_argument("--revision", type=int, required=True)
    notes_r = notes_sub.add_parser("restore-version")
    notes_r.add_argument("--id", required=True)
    notes_r.add_argument("--revision", type=int, required=True)

    folders = sub.add_parser("folders", help="目录管理")
    folders_sub = folders.add_subparsers(dest="folders_cmd", required=True)
    folders_sub.add_parser("list")
    folders_c = folders_sub.add_parser("create")
    folders_c.add_argument("--name", required=True)
    folders_c.add_argument("--parent-id", default=None)

    tags = sub.add_parser("tags", help="标签管理")
    tags_sub = tags.add_subparsers(dest="tags_cmd", required=True)
    tags_sub.add_parser("list")
    tags_c = tags_sub.add_parser("create")
    tags_c.add_argument("--name", required=True)

    sync = sub.add_parser("sync", help="本地同步 API")
    sync_sub = sync.add_subparsers(dest="sync_cmd", required=True)
    sync_m = sync_sub.add_parser("manifest")
    sync_m.add_argument("--include-deleted", action="store_true")
    sync_u = sync_sub.add_parser("upsert")
    sync_u.add_argument("--path", required=True)
    sync_u.add_argument("--markdown", required=True)
    sync_u.add_argument("--base-revision", type=int, default=None)
    sync_u.add_argument("--base-content-hash", default=None)
    sync_u.add_argument("--status", choices=["draft", "private", "published"], default=None)
    sync_u.add_argument("--create-folders", action="store_true")
    sync_u.add_argument("--allow-publish", action="store_true")
    sync_d = sync_sub.add_parser("delete")
    sync_d.add_argument("--path", required=True)
    sync_d.add_argument("--base-revision", type=int, default=None)
    sync_d.add_argument("--base-content-hash", default=None)
    sync_d.add_argument("--confirm-delete", action="store_true")

    settings = sub.add_parser("settings", help="设置与成员")
    settings_sub = settings.add_subparsers(dest="settings_cmd", required=True)
    settings_sub.add_parser("get")
    settings_sub.add_parser("public")
    settings_gate = settings_sub.add_parser("console-gate")
    settings_gate.add_argument("--suffix", required=True)
    settings_p = settings_sub.add_parser("patch")
    settings_p.add_argument("--json", default=None)
    settings_p.add_argument("--json-file", default=None)
    settings_p.add_argument("--set", action="append", default=None)
    settings_sub.add_parser("cdn-logs")

    members = sub.add_parser("members", help="当前 workspace 成员")
    members_sub = members.add_subparsers(dest="members_cmd", required=True)
    members_sub.add_parser("list")
    members_a = members_sub.add_parser("add")
    members_a.add_argument("--email", required=True)
    members_a.add_argument("--role", required=True, choices=["owner", "admin", "editor", "viewer"])
    members_u = members_sub.add_parser("update")
    members_u.add_argument("--id", required=True)
    members_u.add_argument("--role", required=True, choices=["owner", "admin", "editor", "viewer"])
    members_d = members_sub.add_parser("delete")
    members_d.add_argument("--id", required=True)
    members_d.add_argument("--confirm-delete", action="store_true")

    tokens = sub.add_parser("tokens", help="当前 workspace Agent token")
    tokens_sub = tokens.add_subparsers(dest="tokens_cmd", required=True)
    tokens_sub.add_parser("list")
    tokens_c = tokens_sub.add_parser("create")
    tokens_c.add_argument("--name", default=None)
    tokens_c.add_argument("--scope", action="append", choices=["read", "write", "publish", "admin"], default=None)
    tokens_d = tokens_sub.add_parser("revoke")
    tokens_d.add_argument("--id", required=True)
    tokens_d.add_argument("--confirm-delete", action="store_true")

    audit = sub.add_parser("audit", help="当前 workspace 审计日志")
    audit.add_argument("--action", default=None)
    audit.add_argument("--request-id", default=None)
    audit.add_argument("--target-id", default=None)
    audit.add_argument("--limit", type=int, default=None)

    admin = sub.add_parser("admin", help="平台治理入口（需要 super_admin）")
    admin_sub = admin.add_subparsers(dest="admin_cmd", required=True)
    admin_sub.add_parser("users")
    admin_sub.add_parser("workspaces")
    admin_notes = admin_sub.add_parser("notes")
    admin_notes.add_argument("--workspace-id", default=None)
    admin_notes.add_argument("--status", choices=["draft", "private", "published"], default=None)
    admin_notes.add_argument("--include-deleted", action="store_true")
    admin_notes.add_argument("--q", default=None)
    admin_notes.add_argument("--limit", type=int, default=None)
    admin_note = admin_sub.add_parser("note")
    admin_note.add_argument("--id", required=True)
    admin_tokens = admin_sub.add_parser("tokens")
    admin_tokens.add_argument("--workspace-id", default=None)
    admin_tokens.add_argument("--user-id", default=None)
    admin_tokens.add_argument("--include-revoked", action="store_true")
    admin_audit = admin_sub.add_parser("audit")
    admin_audit.add_argument("--workspace-id", default=None)
    admin_audit.add_argument("--actor-user-id", default=None)
    admin_audit.add_argument("--action", default=None)
    admin_audit.add_argument("--request-id", default=None)
    admin_audit.add_argument("--limit", type=int, default=None)

    raw = sub.add_parser("raw", help="受限原始请求；非 GET 必须 --confirm-write。")
    raw.add_argument("method", choices=["GET", "POST", "PUT", "PATCH", "DELETE"])
    raw.add_argument("--path", required=True, help="API 路径，如 /notes。")
    raw.add_argument("--json", default=None)
    raw.add_argument("--json-file", default=None)
    raw.add_argument("--set", action="append", default=None)
    raw.add_argument("--no-auth", action="store_true")
    raw.add_argument("--confirm-write", action="store_true")

    args = parser.parse_args(argv)
    global DRY_RUN
    DRY_RUN = bool(args.dry_run)

    env = resolve_bn_env(skill_root=_skill_root(), env_file=Path(args.env).expanduser() if args.env else None)
    if args.api_prefix is not None:
        from _bn_env import normalize_api_prefix
        env = BnEnv(env.url, normalize_api_prefix(args.api_prefix), env.key, env.url_source, env.key_source, env.api_prefix_source, env.env_file_path)

    if args.cmd not in {"health"} and not (args.cmd == "raw" and args.no_auth):
        _ensure_key(env)
    timeout_seconds = int(args.timeout or _config()["timeout"])

    if args.cmd == "health":
        return cmd_health(env, timeout_seconds)
    if args.cmd == "doctor":
        return cmd_doctor(env, timeout_seconds)
    if args.cmd == "me":
        return _send_and_print(env, "GET", "/auth/me", timeout_seconds=timeout_seconds, retries=1)

    if args.cmd == "notes":
        if args.notes_cmd == "list":
            return _send_and_print(env, "GET", "/notes", query={
                "q": args.q,
                "includeDeleted": "true" if args.include_deleted else None,
                "limit": args.limit,
                "cursor": args.cursor,
            }, timeout_seconds=timeout_seconds, retries=1)
        if args.notes_cmd == "show":
            return _send_and_print(env, "GET", f"/notes/{quote(args.id)}", timeout_seconds=timeout_seconds, retries=1)
        if args.notes_cmd == "create":
            _status_guard(args.status, args.allow_publish)
            body = {"title": args.title, "markdown": args.markdown, "status": args.status}
            if args.folder_id is not None:
                body["folderId"] = args.folder_id
            if args.tag_id is not None:
                body["tagIds"] = args.tag_id
            return _send_and_print(env, "POST", "/notes", json_body=body, timeout_seconds=timeout_seconds, ok_statuses={201, 200})
        if args.notes_cmd == "update":
            _status_guard(args.status, args.allow_publish)
            if args.root_folder and args.folder_id is not None:
                raise SystemExit("--root-folder cannot be combined with --folder-id.")
            if args.clear_tags and args.tag_id:
                raise SystemExit("--clear-tags cannot be combined with --tag-id.")
            body: dict[str, Any] = {"baseRevision": args.base_revision}
            changed = False
            for key, value in (("title", args.title), ("markdown", args.markdown), ("status", args.status)):
                if value is not None:
                    body[key] = value
                    changed = True
            if args.root_folder:
                body["folderId"] = None
                changed = True
            elif args.folder_id is not None:
                body["folderId"] = args.folder_id
                changed = True
            if args.clear_tags:
                body["tagIds"] = []
                changed = True
            elif args.tag_id is not None:
                body["tagIds"] = args.tag_id
                changed = True
            if not changed:
                raise SystemExit("No note fields to update; pass --title/--markdown/--status/--folder-id/--root-folder/--tag-id/--clear-tags.")
            return _send_and_print(env, "PATCH", f"/notes/{quote(args.id)}", json_body=body, timeout_seconds=timeout_seconds)
        if args.notes_cmd == "append":
            return _send_and_print(env, "POST", f"/notes/{quote(args.id)}/append", json_body=_without_none({
                "markdown": args.markdown,
                "baseRevision": args.base_revision,
            }), timeout_seconds=timeout_seconds)
        if args.notes_cmd == "move":
            if args.root_folder and args.folder_id is not None:
                raise SystemExit("--root-folder cannot be combined with --folder-id.")
            if not args.root_folder and args.folder_id is None:
                raise SystemExit("Moving a note requires --folder-id or --root-folder.")
            return _send_and_print(env, "POST", f"/notes/{quote(args.id)}/move", json_body={
                "folderId": None if args.root_folder else args.folder_id,
                "baseRevision": args.base_revision,
            }, timeout_seconds=timeout_seconds)
        if args.notes_cmd == "delete":
            if not args.confirm_delete:
                raise SystemExit("Deleting a note requires --confirm-delete.")
            return _send_and_print(env, "DELETE", f"/notes/{quote(args.id)}", timeout_seconds=timeout_seconds)
        if args.notes_cmd == "trash-restore":
            return _send_and_print(env, "POST", f"/trash/{quote(args.id)}/restore", timeout_seconds=timeout_seconds)
        if args.notes_cmd == "versions":
            return _send_and_print(env, "GET", f"/notes/{quote(args.id)}/versions", query={"take": args.take}, timeout_seconds=timeout_seconds)
        if args.notes_cmd == "version":
            return _send_and_print(env, "GET", f"/notes/{quote(args.id)}/versions/{args.revision}", timeout_seconds=timeout_seconds)
        if args.notes_cmd == "restore-version":
            return _send_and_print(env, "POST", f"/notes/{quote(args.id)}/restore", json_body={"revision": args.revision}, timeout_seconds=timeout_seconds)

    if args.cmd == "folders":
        if args.folders_cmd == "list":
            return _send_and_print(env, "GET", "/folders", timeout_seconds=timeout_seconds)
        if args.folders_cmd == "create":
            return _send_and_print(env, "POST", "/folders", json_body=_without_none({"name": args.name, "parentId": args.parent_id}), timeout_seconds=timeout_seconds)

    if args.cmd == "tags":
        if args.tags_cmd == "list":
            return _send_and_print(env, "GET", "/tags", timeout_seconds=timeout_seconds)
        if args.tags_cmd == "create":
            return _send_and_print(env, "POST", "/tags", json_body={"name": args.name}, timeout_seconds=timeout_seconds)

    if args.cmd == "sync":
        if args.sync_cmd == "manifest":
            return _send_and_print(env, "GET", "/sync/manifest", query={"includeDeleted": "true" if args.include_deleted else None}, timeout_seconds=timeout_seconds)
        if args.sync_cmd == "upsert":
            _status_guard(args.status, args.allow_publish)
            return _send_and_print(env, "PUT", f"/sync/notes/by-path/{_path_arg(args.path)}", json_body=_without_none({
                "markdown": args.markdown,
                "baseRevision": args.base_revision,
                "baseContentHash": args.base_content_hash,
                "status": args.status,
                "createFolders": args.create_folders,
            }), timeout_seconds=timeout_seconds)
        if args.sync_cmd == "delete":
            if not args.confirm_delete:
                raise SystemExit("Deleting a sync path requires --confirm-delete.")
            if args.base_revision is None or not args.base_content_hash:
                raise SystemExit("Deleting a sync path requires --base-revision and --base-content-hash.")
            return _send_and_print(env, "DELETE", f"/sync/notes/by-path/{_path_arg(args.path)}", json_body={
                "baseRevision": args.base_revision,
                "baseContentHash": args.base_content_hash,
            }, timeout_seconds=timeout_seconds)

    if args.cmd == "settings":
        if args.settings_cmd == "get":
            return _send_and_print(env, "GET", "/settings", timeout_seconds=timeout_seconds)
        if args.settings_cmd == "public":
            return _send_and_print(env, "GET", "/settings/public", auth=False, timeout_seconds=timeout_seconds)
        if args.settings_cmd == "console-gate":
            return _send_and_print(env, "GET", f"/settings/console-gate/{quote(args.suffix)}", auth=False, timeout_seconds=timeout_seconds)
        if args.settings_cmd == "patch":
            body = _body_from_args(args)
            if not body:
                raise SystemExit("settings patch requires --json, --json-file, or --set key=value.")
            return _send_and_print(env, "PATCH", "/settings", json_body=body, timeout_seconds=timeout_seconds)
        if args.settings_cmd == "cdn-logs":
            return _send_and_print(env, "GET", "/settings/cdn/logs", timeout_seconds=timeout_seconds)

    if args.cmd == "members":
        if args.members_cmd == "list":
            return _send_and_print(env, "GET", "/workspace/members", timeout_seconds=timeout_seconds)
        if args.members_cmd == "add":
            return _send_and_print(env, "POST", "/workspace/members", json_body={"email": args.email, "role": args.role}, timeout_seconds=timeout_seconds)
        if args.members_cmd == "update":
            return _send_and_print(env, "PATCH", f"/workspace/members/{quote(args.id)}", json_body={"role": args.role}, timeout_seconds=timeout_seconds)
        if args.members_cmd == "delete":
            if not args.confirm_delete:
                raise SystemExit("Removing a member requires --confirm-delete.")
            return _send_and_print(env, "DELETE", f"/workspace/members/{quote(args.id)}", timeout_seconds=timeout_seconds)

    if args.cmd == "tokens":
        if args.tokens_cmd == "list":
            return _send_and_print(env, "GET", "/api-tokens", timeout_seconds=timeout_seconds)
        if args.tokens_cmd == "create":
            return _send_and_print(env, "POST", "/api-tokens", json_body=_without_none({"name": args.name, "scopes": args.scope or []}), timeout_seconds=timeout_seconds)
        if args.tokens_cmd == "revoke":
            if not args.confirm_delete:
                raise SystemExit("Revoking a token requires --confirm-delete.")
            return _send_and_print(env, "DELETE", f"/api-tokens/{quote(args.id)}", timeout_seconds=timeout_seconds)

    if args.cmd == "audit":
        return _send_and_print(env, "GET", "/audit-logs", query={
            "action": args.action,
            "requestId": args.request_id,
            "targetId": args.target_id,
            "limit": args.limit,
        }, timeout_seconds=timeout_seconds)

    if args.cmd == "admin":
        if args.admin_cmd == "users":
            return _send_and_print(env, "GET", "/admin/users", timeout_seconds=timeout_seconds)
        if args.admin_cmd == "workspaces":
            return _send_and_print(env, "GET", "/admin/workspaces", timeout_seconds=timeout_seconds)
        if args.admin_cmd == "notes":
            return _send_and_print(env, "GET", "/admin/notes", query={
                "workspaceId": args.workspace_id,
                "status": args.status,
                "includeDeleted": "true" if args.include_deleted else None,
                "q": args.q,
                "limit": args.limit,
            }, timeout_seconds=timeout_seconds)
        if args.admin_cmd == "note":
            return _send_and_print(env, "GET", f"/admin/notes/{quote(args.id)}", timeout_seconds=timeout_seconds)
        if args.admin_cmd == "tokens":
            return _send_and_print(env, "GET", "/admin/api-tokens", query={
                "workspaceId": args.workspace_id,
                "userId": args.user_id,
                "includeRevoked": "true" if args.include_revoked else None,
            }, timeout_seconds=timeout_seconds)
        if args.admin_cmd == "audit":
            return _send_and_print(env, "GET", "/admin/audit-logs", query={
                "workspaceId": args.workspace_id,
                "actorUserId": args.actor_user_id,
                "action": args.action,
                "requestId": args.request_id,
                "limit": args.limit,
            }, timeout_seconds=timeout_seconds)

    if args.cmd == "raw":
        if args.method != "GET" and not args.confirm_write:
            raise SystemExit("raw non-GET requests require --confirm-write.")
        return _send_and_print(
            env,
            args.method,
            args.path,
            json_body=None if args.method == "GET" else _body_from_args(args),
            auth=not args.no_auth,
            timeout_seconds=timeout_seconds,
            ok_statuses={200, 201, 204},
        )

    raise SystemExit("unknown command")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
