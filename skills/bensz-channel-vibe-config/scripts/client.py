from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlencode

from _bdc_env import BdcEnv, normalize_base_url, resolve_bdc_env
from _flat_yaml import load_flat_yaml
from _http_json import HttpResult, request_json
from _redact import redact_secret


DRY_RUN = False


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _config() -> dict[str, Any]:
    cfg = load_flat_yaml(_skill_root() / "config.yaml")
    idempotency_enabled_raw = str(cfg.scalars.get("article_create_idempotency_enabled", "true")).strip().lower()
    return {
        "name": cfg.scalars.get("skill_name", "bensz-channel-vibe-config"),
        "version": cfg.scalars.get("skill_version", "1.0.0"),
        "timeout": int(cfg.scalars.get("request_timeout_seconds", "15")),
        "write_retry_count": int(cfg.scalars.get("write_retry_count", "0")),
        "article_create_idempotency_enabled": idempotency_enabled_raw in {"1", "true", "yes", "on"},
        "article_create_retry_with_idempotency": int(cfg.scalars.get("article_create_retry_with_idempotency", "2")),
        "article_create_idempotency_prefix": str(cfg.scalars.get("article_create_idempotency_prefix", "bdc-article-create-v1")).strip() or "bdc-article-create-v1",
    }


def _headers(
    env: BdcEnv,
    *,
    connection_id: str | None = None,
    include_auth: bool = True,
    idempotency_key: str | None = None,
) -> dict[str, str]:
    cfg = _config()
    headers = {
        "user-agent": f"{cfg['name']}/{cfg['version']} ({platform.system()} {platform.release()})",
    }
    if include_auth:
        headers["x-devtools-key"] = env.key
    if connection_id:
        headers["x-bdc-connection"] = connection_id
    if idempotency_key:
        headers["x-idempotency-key"] = idempotency_key
    return headers


def _url(env: BdcEnv, path: str) -> str:
    base = env.url.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return base + path


def _url_with_query(env: BdcEnv, path: str, params: dict[str, Any]) -> str:
    filtered = [(key, value) for key, value in params.items() if value is not None and value != ""]
    if not filtered:
        return _url(env, path)
    return _url(env, path) + "?" + urlencode(filtered)


def _write_retries() -> int:
    return max(0, int(_config()["write_retry_count"]))


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _build_article_create_idempotency_key(env: BdcEnv, payload: dict[str, Any]) -> str:
    cfg = _config()
    material = {
        "url": normalize_base_url(env.url),
        "path": "/api/vibe/articles",
        "payload": payload,
    }
    digest = hashlib.sha256(_stable_json(material).encode("utf-8")).hexdigest()
    return f"{cfg['article_create_idempotency_prefix']}-{digest[:32]}"


def _call(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    json_body: Any | None = None,
    timeout_seconds: int,
    retries: int,
) -> HttpResult:
    if DRY_RUN:
        dry_run_headers = {}
        for header_name in ("x-bdc-connection", "x-idempotency-key"):
            if header_name in headers:
                dry_run_headers[header_name] = headers[header_name]
        _print_json({
            "dry_run": True,
            "method": method.upper(),
            "url": url,
            "json_body": json_body,
            "retries": retries,
            "headers": dry_run_headers,
            "note": "headers not printed (to avoid leaking x-devtools-key)",
        })
        return HttpResult(status=0, headers={}, body_text="", json=None)
    return request_json(
        method,
        url,
        headers=headers,
        json_body=json_body,
        timeout_seconds=timeout_seconds,
        retries=retries,
    )


def _print_json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))


def _result_payload(res: HttpResult) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": res.status, "json": res.json}
    if res.status >= 400 and (res.json is None) and res.body_text.strip():
        payload["body"] = res.body_text[:400]
    return payload


def _normalize_tag_match_value(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _tags_from_response(res: HttpResult) -> list[dict[str, Any]]:
    payload = res.json if isinstance(res.json, dict) else None
    data = payload.get("data") if payload else None
    if not isinstance(data, list):
        return []
    return [tag for tag in data if isinstance(tag, dict)]


def _find_existing_tag(
    tags: list[dict[str, Any]],
    *,
    name: str,
    slug: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    slug_key = _normalize_tag_match_value(slug)
    name_key = _normalize_tag_match_value(name)

    if slug_key:
        for field in ("slug", "public_id"):
            for tag in tags:
                if _normalize_tag_match_value(tag.get(field)) == slug_key:
                    return tag, field

    if name_key:
        for tag in tags:
            if _normalize_tag_match_value(tag.get("name")) == name_key:
                return tag, "name"

    return None, None


def _ensure_key(env: BdcEnv) -> None:
    if not env.key:
        raise SystemExit("Missing BENSZ_CHANNEL_KEY (or bdc_key).")
    if len(env.key) < 20:
        raise SystemExit("Invalid key (length < 20).")


def _parse_optional_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return value == "true"


def _connect_payload() -> dict[str, str]:
    return {
        "clientName": "bensz-channel-vibe-config",
        "clientVersion": _config()["version"],
        "machine": platform.node(),
        "workdir": str(Path.cwd()),
    }


def _raise_if_terminated(res: HttpResult, *, action: str) -> None:
    payload = res.json if isinstance(res.json, dict) else None
    if not payload or payload.get("terminate") is not True:
        return
    reason = str(payload.get("reason") or payload.get("message") or "server requested terminate").strip()
    raise SystemExit(f"{action}: terminate=true ({reason})")


@contextmanager
def _auto_connection(env: BdcEnv, *, timeout_seconds: int) -> Iterator[str | None]:
    if DRY_RUN:
        _call("POST", _url(env, "/api/vibe/connect"), headers=_headers(env),
              json_body=_connect_payload(),
              timeout_seconds=timeout_seconds, retries=0)
        fake_conn = "00000000-0000-0000-0000-000000000000"
        try:
            yield fake_conn
        finally:
            _call("POST", _url(env, "/api/vibe/disconnect"), headers=_headers(env),
                  json_body={"connectionId": fake_conn}, timeout_seconds=timeout_seconds, retries=0)
        return

    res = _call("POST", _url(env, "/api/vibe/connect"), headers=_headers(env),
                json_body=_connect_payload(),
                timeout_seconds=timeout_seconds, retries=_write_retries())
    if res.status != 200:
        raise SystemExit(f"connect failed: HTTP {res.status} {res.body_text[:200]}")
    conn_id = str((res.json or {}).get("connectionId") or "").strip()
    if not conn_id:
        raise SystemExit("connect failed: missing connectionId")
    try:
        yield conn_id
    finally:
        try:
            _call("POST", _url(env, "/api/vibe/disconnect"), headers=_headers(env),
                  json_body={"connectionId": conn_id}, timeout_seconds=timeout_seconds, retries=0)
        except Exception:
            pass


# ─── Ping / Doctor ───────────────────────────────────────────────────────────

def cmd_ping(env: BdcEnv, timeout_seconds: int) -> int:
    if DRY_RUN:
        _call("GET", _url(env, "/api/vibe/ping"), headers=_headers(env, include_auth=False), timeout_seconds=timeout_seconds, retries=0)
        return 0
    res = _call("GET", _url(env, "/api/vibe/ping"), headers=_headers(env, include_auth=False), timeout_seconds=timeout_seconds, retries=2)
    _print_json(_result_payload(res))
    return 0 if res.status == 200 else 1


def cmd_doctor(env: BdcEnv, timeout_seconds: int) -> int:
    print(f"url={env.url}")
    print(f"key={redact_secret(env.key, keep=12)}")
    if env.env_file_path is not None:
        print(f"env_file={env.env_file_path}")
    if cmd_ping(env, timeout_seconds) != 0:
        return 1
    with _auto_connection(env, timeout_seconds=timeout_seconds) as conn_id:
        hb = _call("POST", _url(env, "/api/vibe/heartbeat"), headers=_headers(env),
                   json_body={"connectionId": conn_id}, timeout_seconds=timeout_seconds, retries=0)
        _print_json({"heartbeat": _result_payload(hb)})
        if hb.status != 200:
            return 1
        _raise_if_terminated(hb, action="heartbeat")
    return 0


# ─── Channels ─────────────────────────────────────────────────────────────────

def cmd_channels_list(env: BdcEnv, timeout_seconds: int) -> int:
    res = _call("GET", _url(env, "/api/vibe/channels"), headers=_headers(env), timeout_seconds=timeout_seconds, retries=2)
    _print_json(_result_payload(res))
    return 0 if (DRY_RUN or res.status == 200) else 1


def cmd_channels_create(env: BdcEnv, timeout_seconds: int, name: str, icon: str, accent_color: str,
                        slug: str | None, description: str | None, sort_order: int | None,
                        show_in_top_nav: bool | None) -> int:
    body: dict[str, Any] = {"name": name, "icon": icon, "accent_color": accent_color}
    if slug:
        body["slug"] = slug
    if description:
        body["description"] = description
    if sort_order is not None:
        body["sort_order"] = sort_order
    if show_in_top_nav is not None:
        body["show_in_top_nav"] = show_in_top_nav
    with _auto_connection(env, timeout_seconds=timeout_seconds) as conn_id:
        res = _call("POST", _url(env, "/api/vibe/channels"), headers=_headers(env, connection_id=conn_id),
                    json_body=body, timeout_seconds=timeout_seconds, retries=_write_retries())
        _print_json(_result_payload(res))
        return 0 if (DRY_RUN or res.status == 201) else 1


def cmd_channels_update(env: BdcEnv, timeout_seconds: int, channel_id: str, **kwargs: Any) -> int:
    body = {k: v for k, v in kwargs.items() if v is not None}
    if not body:
        raise SystemExit("No fields to update.")
    with _auto_connection(env, timeout_seconds=timeout_seconds) as conn_id:
        res = _call("PUT", _url(env, f"/api/vibe/channels/{channel_id}"),
                    headers=_headers(env, connection_id=conn_id),
                    json_body=body, timeout_seconds=timeout_seconds, retries=_write_retries())
        _print_json(_result_payload(res))
        return 0 if (DRY_RUN or res.status == 200) else 1


def cmd_channels_delete(env: BdcEnv, timeout_seconds: int, channel_id: str) -> int:
    with _auto_connection(env, timeout_seconds=timeout_seconds) as conn_id:
        res = _call("DELETE", _url(env, f"/api/vibe/channels/{channel_id}"),
                    headers=_headers(env, connection_id=conn_id),
                    timeout_seconds=timeout_seconds, retries=_write_retries())
        _print_json(_result_payload(res))
        return 0 if (DRY_RUN or res.status == 200) else 1


# ─── Articles ─────────────────────────────────────────────────────────────────

def cmd_articles_list(env: BdcEnv, timeout_seconds: int, channel_id: str | None, published: str | None) -> int:
    return cmd_articles_list_with_filters(env, timeout_seconds, channel_id, published, None, None, None)


def cmd_articles_list_with_filters(
    env: BdcEnv,
    timeout_seconds: int,
    channel_id: str | None,
    published: str | None,
    pinned: str | None,
    featured: str | None,
    tag_id: int | None,
) -> int:
    res = _call("GET", _url_with_query(env, "/api/vibe/articles", {
                    "channel_id": channel_id,
                    "published": published,
                    "pinned": pinned,
                    "featured": featured,
                    "tag_id": tag_id,
                }), headers=_headers(env),
                timeout_seconds=timeout_seconds, retries=2)
    _print_json(_result_payload(res))
    return 0 if (DRY_RUN or res.status == 200) else 1


def cmd_articles_show(env: BdcEnv, timeout_seconds: int, article_id: str) -> int:
    res = _call("GET", _url(env, f"/api/vibe/articles/{article_id}"), headers=_headers(env),
                timeout_seconds=timeout_seconds, retries=2)
    _print_json(_result_payload(res))
    return 0 if (DRY_RUN or res.status == 200) else 1


def cmd_articles_create(env: BdcEnv, timeout_seconds: int, channel_id: str, title: str, body: str,
                        published: bool, excerpt: str | None, cover_gradient: str | None,
                        slug: str | None, published_at: str | None,
                        is_pinned: bool, is_featured: bool, tag_ids: list[int] | None,
                        idempotency_key: str | None = None) -> int:
    payload: dict[str, Any] = {
        "channel_id": int(channel_id),
        "title": title,
        "markdown_body": body,
        "is_published": published,
        "is_pinned": is_pinned,
        "is_featured": is_featured,
    }
    if slug:
        payload["slug"] = slug
    if excerpt:
        payload["excerpt"] = excerpt
    if cover_gradient:
        payload["cover_gradient"] = cover_gradient
    if published_at:
        payload["published_at"] = published_at
    if tag_ids:
        payload["tag_ids"] = [int(tag_id) for tag_id in tag_ids]

    cfg = _config()
    resolved_idempotency_key = (idempotency_key or "").strip() or None
    if resolved_idempotency_key is None and cfg["article_create_idempotency_enabled"]:
        resolved_idempotency_key = _build_article_create_idempotency_key(env, payload)
    write_retries = (
        max(0, int(cfg["article_create_retry_with_idempotency"]))
        if resolved_idempotency_key is not None
        else _write_retries()
    )

    with _auto_connection(env, timeout_seconds=timeout_seconds) as conn_id:
        res = _call("POST", _url(env, "/api/vibe/articles"),
                    headers=_headers(env, connection_id=conn_id, idempotency_key=resolved_idempotency_key),
                    json_body=payload, timeout_seconds=timeout_seconds, retries=write_retries)
        _print_json(_result_payload(res))
        return 0 if (DRY_RUN or res.status == 201) else 1


def cmd_articles_create_draft(env: BdcEnv, timeout_seconds: int, channel_id: str, title: str, body: str,
                              excerpt: str | None, cover_gradient: str | None, slug: str | None,
                              tag_ids: list[int] | None, idempotency_key: str | None = None) -> int:
    return cmd_articles_create(
        env,
        timeout_seconds,
        channel_id,
        title,
        body,
        False,
        excerpt,
        cover_gradient,
        slug,
        None,
        False,
        False,
        tag_ids,
        idempotency_key,
    )


def cmd_articles_update(env: BdcEnv, timeout_seconds: int, article_id: str, **kwargs: Any) -> int:
    body = {k: v for k, v in kwargs.items() if v is not None}
    if "channel_id" in body:
        body["channel_id"] = int(body["channel_id"])
    if "tag_ids" in body:
        body["tag_ids"] = [int(tag_id) for tag_id in body["tag_ids"]]
    if not body:
        raise SystemExit("No fields to update.")
    with _auto_connection(env, timeout_seconds=timeout_seconds) as conn_id:
        res = _call("PUT", _url(env, f"/api/vibe/articles/{article_id}"),
                    headers=_headers(env, connection_id=conn_id),
                    json_body=body, timeout_seconds=timeout_seconds, retries=_write_retries())
        _print_json(_result_payload(res))
        return 0 if (DRY_RUN or res.status == 200) else 1


def cmd_articles_delete(env: BdcEnv, timeout_seconds: int, article_id: str) -> int:
    with _auto_connection(env, timeout_seconds=timeout_seconds) as conn_id:
        res = _call("DELETE", _url(env, f"/api/vibe/articles/{article_id}"),
                    headers=_headers(env, connection_id=conn_id),
                    timeout_seconds=timeout_seconds, retries=_write_retries())
        _print_json(_result_payload(res))
        return 0 if (DRY_RUN or res.status == 200) else 1


# ─── Tags ─────────────────────────────────────────────────────────────────────

def cmd_tags_list(env: BdcEnv, timeout_seconds: int) -> int:
    res = _call("GET", _url(env, "/api/vibe/tags"), headers=_headers(env),
                timeout_seconds=timeout_seconds, retries=2)
    _print_json(_result_payload(res))
    return 0 if (DRY_RUN or res.status == 200) else 1


def _tag_payload(name: str, slug: str | None, description: str | None) -> dict[str, Any]:
    body: dict[str, Any] = {"name": name}
    if slug:
        body["slug"] = slug
    if description:
        body["description"] = description
    return body


def _create_tag_request(env: BdcEnv, timeout_seconds: int, body: dict[str, Any]) -> HttpResult:
    with _auto_connection(env, timeout_seconds=timeout_seconds) as conn_id:
        return _call("POST", _url(env, "/api/vibe/tags"),
                     headers=_headers(env, connection_id=conn_id),
                     json_body=body, timeout_seconds=timeout_seconds, retries=_write_retries())


def cmd_tags_create(
    env: BdcEnv,
    timeout_seconds: int,
    name: str,
    slug: str | None,
    description: str | None,
) -> int:
    body = _tag_payload(name, slug, description)
    res = _create_tag_request(env, timeout_seconds, body)
    _print_json(_result_payload(res))
    return 0 if (DRY_RUN or res.status == 201) else 1


def cmd_tags_ensure(
    env: BdcEnv,
    timeout_seconds: int,
    name: str,
    slug: str | None,
    description: str | None,
) -> int:
    lookup = _call("GET", _url(env, "/api/vibe/tags"), headers=_headers(env),
                   timeout_seconds=timeout_seconds, retries=2)
    if not DRY_RUN and lookup.status != 200:
        _print_json({
            "action": "list_existing_tags",
            **_result_payload(lookup),
        })
        return 1

    matched_tag, matched_by = _find_existing_tag(_tags_from_response(lookup), name=name, slug=slug)
    if matched_tag is not None:
        _print_json({
            "action": "reuse_existing_tag",
            "matched_by": matched_by,
            "tag": matched_tag,
        })
        return 0

    if DRY_RUN:
        _print_json({
            "action": "create_tag_if_needed",
            "description": description,
            "dry_run": True,
            "name": name,
            "note": "tags ensure 会先复用完全匹配的现有标签；仅在找不到 name/slug/public_id 精确匹配时才创建新标签。",
            "slug": slug,
        })
        return 0

    create_res = _create_tag_request(env, timeout_seconds, _tag_payload(name, slug, description))
    if create_res.status == 201:
        _print_json(_result_payload(create_res))
        return 0

    if create_res.status == 422:
        retry_lookup = _call("GET", _url(env, "/api/vibe/tags"), headers=_headers(env),
                             timeout_seconds=timeout_seconds, retries=2)
        if retry_lookup.status == 200:
            matched_tag, matched_by = _find_existing_tag(_tags_from_response(retry_lookup), name=name, slug=slug)
            if matched_tag is not None:
                _print_json({
                    "action": "reuse_existing_tag_after_conflict",
                    "matched_by": matched_by,
                    "tag": matched_tag,
                })
                return 0

    _print_json(_result_payload(create_res))
    return 1


def cmd_tags_update(env: BdcEnv, timeout_seconds: int, tag_id: str, **kwargs: Any) -> int:
    body = {k: v for k, v in kwargs.items() if v is not None}
    if not body:
        raise SystemExit("No fields to update.")
    with _auto_connection(env, timeout_seconds=timeout_seconds) as conn_id:
        res = _call("PUT", _url(env, f"/api/vibe/tags/{tag_id}"),
                    headers=_headers(env, connection_id=conn_id),
                    json_body=body, timeout_seconds=timeout_seconds, retries=_write_retries())
        _print_json(_result_payload(res))
        return 0 if (DRY_RUN or res.status == 200) else 1


def cmd_tags_delete(env: BdcEnv, timeout_seconds: int, tag_id: str) -> int:
    with _auto_connection(env, timeout_seconds=timeout_seconds) as conn_id:
        res = _call("DELETE", _url(env, f"/api/vibe/tags/{tag_id}"),
                    headers=_headers(env, connection_id=conn_id),
                    timeout_seconds=timeout_seconds, retries=_write_retries())
        _print_json(_result_payload(res))
        return 0 if (DRY_RUN or res.status == 200) else 1


# ─── Comments ─────────────────────────────────────────────────────────────────

def cmd_comments_list(env: BdcEnv, timeout_seconds: int, article_id: str | None, visible: str | None) -> int:
    res = _call("GET", _url_with_query(env, "/api/vibe/comments", {
                    "article_id": article_id,
                    "visible": visible,
                }), headers=_headers(env),
                timeout_seconds=timeout_seconds, retries=2)
    _print_json(_result_payload(res))
    return 0 if (DRY_RUN or res.status == 200) else 1


def cmd_comments_update(env: BdcEnv, timeout_seconds: int, comment_id: str, visible: bool) -> int:
    with _auto_connection(env, timeout_seconds=timeout_seconds) as conn_id:
        res = _call("PATCH", _url(env, f"/api/vibe/comments/{comment_id}"),
                    headers=_headers(env, connection_id=conn_id),
                    json_body={"is_visible": visible}, timeout_seconds=timeout_seconds, retries=_write_retries())
        _print_json(_result_payload(res))
        return 0 if (DRY_RUN or res.status == 200) else 1


def cmd_comments_delete(env: BdcEnv, timeout_seconds: int, comment_id: str) -> int:
    with _auto_connection(env, timeout_seconds=timeout_seconds) as conn_id:
        res = _call("DELETE", _url(env, f"/api/vibe/comments/{comment_id}"),
                    headers=_headers(env, connection_id=conn_id),
                    timeout_seconds=timeout_seconds, retries=_write_retries())
        _print_json(_result_payload(res))
        return 0 if (DRY_RUN or res.status == 200) else 1


# ─── Users ────────────────────────────────────────────────────────────────────

def cmd_users_list(env: BdcEnv, timeout_seconds: int, q: str | None, role: str | None) -> int:
    res = _call("GET", _url_with_query(env, "/api/vibe/users", {
                    "q": q,
                    "role": role,
                }), headers=_headers(env),
                timeout_seconds=timeout_seconds, retries=2)
    _print_json(_result_payload(res))
    return 0 if (DRY_RUN or res.status == 200) else 1


def cmd_users_update(env: BdcEnv, timeout_seconds: int, user_id: str, **kwargs: Any) -> int:
    body = {k: v for k, v in kwargs.items() if v is not None}
    if not body:
        raise SystemExit("No fields to update.")
    with _auto_connection(env, timeout_seconds=timeout_seconds) as conn_id:
        res = _call("PUT", _url(env, f"/api/vibe/users/{user_id}"),
                    headers=_headers(env, connection_id=conn_id),
                    json_body=body, timeout_seconds=timeout_seconds, retries=_write_retries())
        _print_json(_result_payload(res))
        return 0 if (DRY_RUN or res.status == 200) else 1


def cmd_users_delete(env: BdcEnv, timeout_seconds: int, user_id: str) -> int:
    with _auto_connection(env, timeout_seconds=timeout_seconds) as conn_id:
        res = _call("DELETE", _url(env, f"/api/vibe/users/{user_id}"),
                    headers=_headers(env, connection_id=conn_id),
                    timeout_seconds=timeout_seconds, retries=_write_retries())
        _print_json(_result_payload(res))
        return 0 if (DRY_RUN or res.status == 200) else 1


# ─── Main ─────────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="client.py",
        description="bensz-channel DevTools 客户端。通过 API 密钥管理频道、标签、文章、评论和用户。"
    )
    parser.add_argument("--env", type=str, default=None, help="指定 .env 配置文件路径。")
    parser.add_argument("--timeout", type=int, default=None, help="请求超时秒数。")
    parser.add_argument("--dry-run", action="store_true", help="只打印将发出的请求，不实际发送。")

    sub = parser.add_subparsers(dest="cmd", required=True)

    # ping / doctor
    sub.add_parser("ping", help="检查服务器连接（无需鉴权）。")
    sub.add_parser("doctor", help="完整诊断：ping + connect + heartbeat + disconnect。")

    # channels
    ch = sub.add_parser("channels", help="频道管理")
    ch_sub = ch.add_subparsers(dest="ch_cmd", required=True)
    ch_sub.add_parser("list", help="列出所有频道")
    ch_c = ch_sub.add_parser("create", help="新建频道")
    ch_c.add_argument("--name", required=True, help="频道名称")
    ch_c.add_argument("--icon", required=True, help="图标（emoji）")
    ch_c.add_argument("--accent-color", required=True, help="强调色（如 #3b82f6）")
    ch_c.add_argument("--slug", default=None)
    ch_c.add_argument("--description", default=None)
    ch_c.add_argument("--sort-order", type=int, default=None)
    ch_c.add_argument("--show-in-top-nav", default=None, choices=["true", "false"], help="是否显示在顶部导航")
    ch_u = ch_sub.add_parser("update", help="更新频道")
    ch_u.add_argument("--id", required=True, help="频道标识（数值 ID / public_id / slug）")
    ch_u.add_argument("--name", default=None)
    ch_u.add_argument("--icon", default=None)
    ch_u.add_argument("--accent-color", default=None)
    ch_u.add_argument("--slug", default=None)
    ch_u.add_argument("--description", default=None)
    ch_u.add_argument("--sort-order", type=int, default=None)
    ch_u.add_argument("--show-in-top-nav", default=None, choices=["true", "false"], help="是否显示在顶部导航")
    ch_d = ch_sub.add_parser("delete", help="删除频道")
    ch_d.add_argument("--id", required=True, help="频道标识（数值 ID / public_id / slug）")

    # articles
    ar = sub.add_parser("articles", help="文章管理")
    ar_sub = ar.add_subparsers(dest="ar_cmd", required=True)
    ar_l = ar_sub.add_parser("list", help="列出文章")
    ar_l.add_argument("--channel-id", default=None)
    ar_l.add_argument("--published", default=None, choices=["true", "false"])
    ar_l.add_argument("--pinned", default=None, choices=["true", "false"])
    ar_l.add_argument("--featured", default=None, choices=["true", "false"])
    ar_l.add_argument("--tag-id", type=int, default=None, help="按标签数值 ID 过滤")
    ar_s = ar_sub.add_parser("show", help="查看单篇文章")
    ar_s.add_argument("--id", required=True, help="文章标识（数值 ID / public_id / slug）")
    ar_c = ar_sub.add_parser("create", help="创建文章（默认草稿；加 --published 才正式发布）")
    ar_c.add_argument("--channel-id", required=True)
    ar_c.add_argument("--title", required=True)
    ar_c.add_argument("--body", required=True, help="Markdown 正文")
    ar_c.add_argument("--published", action="store_true", default=False, help="正式发布；验证链路请改用 create-draft")
    ar_c.add_argument("--slug", default=None)
    ar_c.add_argument("--excerpt", default=None)
    ar_c.add_argument("--cover-gradient", default=None)
    ar_c.add_argument("--published-at", default=None, help="发布时间（ISO 8601）")
    ar_c.add_argument("--pinned", action="store_true", default=False, help="创建后设为置顶")
    ar_c.add_argument("--featured", action="store_true", default=False, help="创建后设为精华")
    ar_c.add_argument("--tag-id", action="append", type=int, default=None, help="关联标签数值 ID；可重复传入")
    ar_c.add_argument("--idempotency-key", default=None, help="自定义幂等键；不传时会按 payload 自动生成确定性键")
    ar_cd = ar_sub.add_parser("create-draft", help="创建验证草稿（强制草稿，不会触发正式发布）")
    ar_cd.add_argument("--channel-id", required=True)
    ar_cd.add_argument("--title", required=True)
    ar_cd.add_argument("--body", required=True, help="Markdown 正文")
    ar_cd.add_argument("--slug", default=None)
    ar_cd.add_argument("--excerpt", default=None)
    ar_cd.add_argument("--cover-gradient", default=None)
    ar_cd.add_argument("--tag-id", action="append", type=int, default=None, help="关联标签数值 ID；可重复传入")
    ar_cd.add_argument("--idempotency-key", default=None, help="自定义幂等键；不传时会按 payload 自动生成确定性键")
    ar_u = ar_sub.add_parser("update", help="更新文章")
    ar_u.add_argument("--id", required=True, help="文章标识（数值 ID / public_id / slug）")
    ar_u.add_argument("--channel-id", default=None)
    ar_u.add_argument("--title", default=None)
    ar_u.add_argument("--slug", default=None)
    ar_u.add_argument("--body", default=None, help="Markdown 正文")
    ar_u.add_argument("--published", default=None, choices=["true", "false"])
    ar_u.add_argument("--published-at", default=None, help="发布时间（ISO 8601）")
    ar_u.add_argument("--pinned", default=None, choices=["true", "false"])
    ar_u.add_argument("--featured", default=None, choices=["true", "false"])
    ar_u.add_argument("--excerpt", default=None)
    ar_u.add_argument("--cover-gradient", default=None)
    ar_u.add_argument("--tag-id", action="append", type=int, default=None, help="覆盖文章标签；可重复传入数值 ID")
    ar_u.add_argument("--clear-tags", action="store_true", default=False, help="清空文章已有标签")
    ar_d = ar_sub.add_parser("delete", help="删除文章")
    ar_d.add_argument("--id", required=True, help="文章标识（数值 ID / public_id / slug）")

    # tags
    tg = sub.add_parser("tags", help="标签管理")
    tg_sub = tg.add_subparsers(dest="tg_cmd", required=True)
    tg_sub.add_parser("list", help="列出所有标签")
    tg_c = tg_sub.add_parser("create", help="新建标签")
    tg_c.add_argument("--name", required=True, help="标签名称")
    tg_c.add_argument("--slug", default=None)
    tg_c.add_argument("--description", default=None)
    tg_e = tg_sub.add_parser("ensure", help="优先复用已有标签；不存在时再创建")
    tg_e.add_argument("--name", required=True, help="期望标签名称")
    tg_e.add_argument("--slug", default=None, help="期望标签 slug；若命中现有 slug/public_id 会直接复用")
    tg_e.add_argument("--description", default=None, help="仅在需要新建标签时使用")
    tg_u = tg_sub.add_parser("update", help="更新标签")
    tg_u.add_argument("--id", required=True, help="标签标识（数值 ID / public_id / slug）")
    tg_u.add_argument("--name", default=None)
    tg_u.add_argument("--slug", default=None)
    tg_u.add_argument("--description", default=None)
    tg_d = tg_sub.add_parser("delete", help="删除标签")
    tg_d.add_argument("--id", required=True, help="标签标识（数值 ID / public_id / slug）")

    # comments
    co = sub.add_parser("comments", help="评论管理")
    co_sub = co.add_subparsers(dest="co_cmd", required=True)
    co_l = co_sub.add_parser("list", help="列出评论")
    co_l.add_argument("--article-id", default=None)
    co_l.add_argument("--visible", default=None, choices=["true", "false"])
    co_u = co_sub.add_parser("update", help="更新评论可见性")
    co_u.add_argument("--id", required=True)
    co_u.add_argument("--visible", required=True, choices=["true", "false"])
    co_d = co_sub.add_parser("delete", help="删除评论")
    co_d.add_argument("--id", required=True)

    # users
    us = sub.add_parser("users", help="用户管理")
    us_sub = us.add_subparsers(dest="us_cmd", required=True)
    us_l = us_sub.add_parser("list", help="列出用户")
    us_l.add_argument("--q", default=None, help="搜索（名称/邮箱/手机）")
    us_l.add_argument("--role", default=None, choices=["admin", "member"])
    us_u = us_sub.add_parser("update", help="更新用户")
    us_u.add_argument("--id", required=True)
    us_u.add_argument("--name", default=None)
    us_u.add_argument("--email", default=None)
    us_u.add_argument("--phone", default=None)
    us_u.add_argument("--role", default=None, choices=["admin", "member"])
    us_u.add_argument("--bio", default=None)
    us_u.add_argument("--avatar-url", default=None)
    us_d = us_sub.add_parser("delete", help="删除普通用户")
    us_d.add_argument("--id", required=True, help="用户数值 ID")

    args = parser.parse_args(argv)
    global DRY_RUN
    DRY_RUN = bool(getattr(args, "dry_run", False))

    env = resolve_bdc_env(skill_root=_skill_root(),
                          env_file=Path(args.env).expanduser() if args.env else None)

    if args.cmd != "ping":
        _ensure_key(env)

    timeout_seconds = int(getattr(args, "timeout", None) or _config()["timeout"])

    if args.cmd == "ping":
        return cmd_ping(env, timeout_seconds)
    if args.cmd == "doctor":
        return cmd_doctor(env, timeout_seconds)

    if args.cmd == "channels":
        if args.ch_cmd == "list":
            return cmd_channels_list(env, timeout_seconds)
        if args.ch_cmd == "create":
            return cmd_channels_create(env, timeout_seconds, args.name, args.icon, args.accent_color,
                                       args.slug, args.description, args.sort_order,
                                       _parse_optional_bool(args.show_in_top_nav))
        if args.ch_cmd == "update":
            return cmd_channels_update(env, timeout_seconds, args.id,
                                       name=args.name, icon=args.icon, accent_color=args.accent_color,
                                       slug=args.slug, description=args.description, sort_order=args.sort_order,
                                       show_in_top_nav=_parse_optional_bool(args.show_in_top_nav))
        if args.ch_cmd == "delete":
            return cmd_channels_delete(env, timeout_seconds, args.id)

    if args.cmd == "articles":
        if args.ar_cmd == "list":
            return cmd_articles_list_with_filters(env, timeout_seconds, args.channel_id, args.published,
                                                  args.pinned, args.featured, args.tag_id)
        if args.ar_cmd == "show":
            return cmd_articles_show(env, timeout_seconds, args.id)
        if args.ar_cmd == "create":
            return cmd_articles_create(env, timeout_seconds, args.channel_id, args.title, args.body,
                                       args.published, args.excerpt, args.cover_gradient,
                                       args.slug, args.published_at, args.pinned, args.featured,
                                       args.tag_id, args.idempotency_key)
        if args.ar_cmd == "create-draft":
            return cmd_articles_create_draft(env, timeout_seconds, args.channel_id, args.title, args.body,
                                             args.excerpt, args.cover_gradient, args.slug,
                                             args.tag_id, args.idempotency_key)
        if args.ar_cmd == "update":
            if args.clear_tags and args.tag_id:
                raise SystemExit("--clear-tags cannot be combined with --tag-id.")
            body_val = args.body if hasattr(args, "body") else None
            pub_val = _parse_optional_bool(args.published)
            pinned_val = _parse_optional_bool(args.pinned)
            featured_val = _parse_optional_bool(args.featured)
            tag_ids = [] if args.clear_tags else args.tag_id
            return cmd_articles_update(env, timeout_seconds, args.id,
                                       channel_id=args.channel_id, title=args.title, slug=args.slug,
                                       markdown_body=body_val, is_published=pub_val,
                                       published_at=args.published_at, is_pinned=pinned_val,
                                       is_featured=featured_val, excerpt=args.excerpt,
                                       cover_gradient=args.cover_gradient, tag_ids=tag_ids)
        if args.ar_cmd == "delete":
            return cmd_articles_delete(env, timeout_seconds, args.id)

    if args.cmd == "tags":
        if args.tg_cmd == "list":
            return cmd_tags_list(env, timeout_seconds)
        if args.tg_cmd == "create":
            return cmd_tags_create(env, timeout_seconds, args.name, args.slug, args.description)
        if args.tg_cmd == "ensure":
            return cmd_tags_ensure(env, timeout_seconds, args.name, args.slug, args.description)
        if args.tg_cmd == "update":
            return cmd_tags_update(env, timeout_seconds, args.id,
                                   name=args.name, slug=args.slug, description=args.description)
        if args.tg_cmd == "delete":
            return cmd_tags_delete(env, timeout_seconds, args.id)

    if args.cmd == "comments":
        if args.co_cmd == "list":
            return cmd_comments_list(env, timeout_seconds, args.article_id, args.visible)
        if args.co_cmd == "update":
            visible_bool = args.visible == "true"
            return cmd_comments_update(env, timeout_seconds, args.id, visible_bool)
        if args.co_cmd == "delete":
            return cmd_comments_delete(env, timeout_seconds, args.id)

    if args.cmd == "users":
        if args.us_cmd == "list":
            return cmd_users_list(env, timeout_seconds, args.q, args.role)
        if args.us_cmd == "update":
            return cmd_users_update(env, timeout_seconds, args.id,
                                    name=args.name, email=args.email, phone=args.phone,
                                    role=args.role, bio=args.bio, avatar_url=args.avatar_url)
        if args.us_cmd == "delete":
            return cmd_users_delete(env, timeout_seconds, args.id)

    raise SystemExit("unknown command")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
