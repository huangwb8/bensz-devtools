from __future__ import annotations

import argparse
import json
import platform
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from _flat_yaml import load_flat_yaml
from _http_json import HttpResult, request_json
from _redact import redact_secret
from _vibe_env import VibeEnv, resolve_vibe_env


DRY_RUN = False


class TerminateRequested(Exception):
    def __init__(self, *, reason: str, res: HttpResult):
        super().__init__(reason)
        self.reason = reason
        self.res = res


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _config() -> dict[str, Any]:
    cfg = load_flat_yaml(_skill_root() / "config.yaml")
    return {
        "name": cfg.scalars.get("skill_name", "dudu-vibe-config"),
        "version": cfg.scalars.get("skill_version", "0.0.0"),
        "timeout": int(cfg.scalars.get("request_timeout_seconds", "15")),
        "heartbeat": int(cfg.scalars.get("heartbeat_interval_seconds", "30")),
    }


def _headers(vibe: VibeEnv, *, connection_id: str | None = None) -> dict[str, str]:
    cfg = _config()
    headers = {
        "user-agent": f"{cfg['name']}/{cfg['version']} ({platform.system()} {platform.release()})",
        "x-dudu-vibe-key": vibe.key,
    }
    if connection_id:
        headers["x-dudu-vibe-connection"] = connection_id
    return headers


def _url(vibe: VibeEnv, path: str) -> str:
    base = vibe.url.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return base + path


def _normalize_base_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return u
    if "://" in u and not (u.startswith("http://") or u.startswith("https://")):
        raise SystemExit(f"Invalid --url scheme (http/https only): {url!r}")
    if not (u.startswith("http://") or u.startswith("https://")):
        u = "http://" + u
    return u.rstrip("/")


def _require_uuid(value: str, *, name: str) -> str:
    raw = (value or "").strip()
    try:
        uuid.UUID(raw)
    except Exception:
        raise SystemExit(f"Invalid {name}: expected UUID, got {value!r}")
    return raw


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
        _print_json(
            {
                "dry_run": True,
                "method": method.upper(),
                "url": url,
                "json_body": json_body,
                "note": "headers not printed (to avoid leaking x-dudu-vibe-key)",
            }
        )
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
        payload["body"] = res.body_text[:300]
    return payload


def _ensure_key(vibe: VibeEnv) -> None:
    if not vibe.key:
        raise SystemExit("Missing DUDU_VIBE_KEY (or dudu_vibe_key / dudu_vibe_api).")
    if len(vibe.key) < 16:
        raise SystemExit("Invalid vibe key (length < 16).")


def _terminate_guard(res: HttpResult) -> None:
    if res.headers.get("x-dudu-vibe-terminate") == "1":
        raise TerminateRequested(reason="x-dudu-vibe-terminate: 1", res=res)
    if res.status == 409 and isinstance(res.json, dict):
        code = (res.json.get("code") or res.json.get("error") or res.json.get("name") or "").strip()
        if code == "terminate_requested":
            raise TerminateRequested(reason="HTTP 409 terminate_requested", res=res)
    if isinstance(res.json, dict) and res.json.get("terminate") is True:
        raise TerminateRequested(reason="terminate=true", res=res)


@contextmanager
def _auto_connection(vibe: VibeEnv, *, enable: bool, timeout_seconds: int) -> Iterator[str | None]:
    if not enable:
        yield None
        return
    if DRY_RUN:
        connect_body = {
            "clientName": "dudu-vibe-config",
            "clientVersion": _config()["version"],
            "machine": platform.node(),
            "workdir": str(Path.cwd()),
        }
        _call(
            "POST",
            _url(vibe, "/vibe/agent/connect"),
            headers=_headers(vibe),
            json_body=connect_body,
            timeout_seconds=timeout_seconds,
            retries=0,
        )
        fake_conn = "00000000-0000-0000-0000-000000000000"
        try:
            yield fake_conn
        finally:
            _call(
                "POST",
                _url(vibe, "/vibe/agent/disconnect"),
                headers=_headers(vibe, connection_id=fake_conn),
                json_body={"connectionId": fake_conn},
                timeout_seconds=timeout_seconds,
                retries=0,
            )
        return

    res = _call(
        "POST",
        _url(vibe, "/vibe/agent/connect"),
        headers=_headers(vibe),
        json_body={
            "clientName": "dudu-vibe-config",
            "clientVersion": _config()["version"],
            "machine": platform.node(),
            "workdir": str(Path.cwd()),
        },
        timeout_seconds=timeout_seconds,
        retries=2,
    )
    if res.status != 200:
        raise SystemExit(f"connect failed: HTTP {res.status} {res.body_text[:200]}")
    _terminate_guard(res)
    conn_id = str((res.json or {}).get("connectionId") or "").strip()
    if not conn_id:
        raise SystemExit("connect failed: missing connectionId")
    try:
        yield conn_id
    finally:
        try:
            _call(
                "POST",
                _url(vibe, "/vibe/agent/disconnect"),
                headers=_headers(vibe, connection_id=conn_id),
                json_body={"connectionId": conn_id},
                timeout_seconds=timeout_seconds,
                retries=0,
            )
        except Exception:
            pass


def cmd_ping(vibe: VibeEnv, timeout_seconds: int) -> int:
    if DRY_RUN:
        _call("GET", _url(vibe, "/vibe/agent/ping"), headers=_headers(vibe), timeout_seconds=timeout_seconds, retries=0)
        return 0
    res = _call("GET", _url(vibe, "/vibe/agent/ping"), headers=_headers(vibe), timeout_seconds=timeout_seconds, retries=2)
    _terminate_guard(res)
    _print_json(_result_payload(res))
    return 0 if res.status == 200 else 1


def cmd_doctor(vibe: VibeEnv, timeout_seconds: int) -> int:
    if DRY_RUN:
        cmd_ping(vibe, timeout_seconds)
        with _auto_connection(vibe, enable=True, timeout_seconds=timeout_seconds) as conn_id:
            hb = _call(
                "POST",
                _url(vibe, "/vibe/agent/heartbeat"),
                headers=_headers(vibe, connection_id=conn_id),
                json_body={"connectionId": conn_id},
                timeout_seconds=timeout_seconds,
                retries=0,
            )
            _print_json({"doctor": {"url": vibe.url, "key_prefix": redact_secret(vibe.key, keep=10)}, "heartbeat": _result_payload(hb)})
        return 0

    ping = _call("GET", _url(vibe, "/vibe/agent/ping"), headers=_headers(vibe), timeout_seconds=timeout_seconds, retries=2)
    _terminate_guard(ping)
    if ping.status != 200:
        _print_json({"doctor": {"url": vibe.url, "key_prefix": redact_secret(vibe.key, keep=10)}, "ping": _result_payload(ping)})
        return 1

    with _auto_connection(vibe, enable=True, timeout_seconds=timeout_seconds) as conn_id:
        hb = _call(
            "POST",
            _url(vibe, "/vibe/agent/heartbeat"),
            headers=_headers(vibe, connection_id=conn_id),
            json_body={"connectionId": conn_id},
            timeout_seconds=timeout_seconds,
            retries=0,
        )
        _terminate_guard(hb)
        _print_json(
            {
                "doctor": {"url": vibe.url, "key_prefix": redact_secret(vibe.key, keep=10)},
                "ping": _result_payload(ping),
                "heartbeat": _result_payload(hb),
            }
        )
    return 0


def cmd_domains_get(vibe: VibeEnv, timeout_seconds: int) -> int:
    if DRY_RUN:
        _call("GET", _url(vibe, "/vibe/agent/domains/rules"), headers=_headers(vibe), timeout_seconds=timeout_seconds, retries=0)
        return 0
    res = _call("GET", _url(vibe, "/vibe/agent/domains/rules"), headers=_headers(vibe), timeout_seconds=timeout_seconds, retries=2)
    _terminate_guard(res)
    _print_json({"status": res.status, "rules": res.json, **({"body": res.body_text[:300]} if res.status >= 400 and res.json is None else {})})
    return 0 if res.status == 200 else 1


def _coerce_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    out: list[str] = []
    for v in values:
        s = str(v).strip()
        if s:
            out.append(s)
    return out


def _build_ai_payload(
    *,
    sdk: str | None,
    model: str | None,
    reasoning_effort: str | None,
    thinking_mode: str | None,
) -> dict[str, Any] | None:
    payload: dict[str, Any] = {}
    if sdk is not None:
        payload["sdk"] = sdk
    if model is not None:
        payload["model"] = model
    if reasoning_effort is not None:
        payload["reasoningEffort"] = reasoning_effort
    if thinking_mode is not None:
        payload["thinkingMode"] = thinking_mode
    return payload or None


def _unique_merge(existing: list[str], incoming: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in existing + incoming:
        s = str(item).strip()
        if not s:
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def cmd_domains_set(
    vibe: VibeEnv,
    timeout_seconds: int,
    allowlist: list[str],
    blocklist: list[str],
    keywords: list[str],
    *,
    reset: bool,
) -> int:
    incoming_allow = _coerce_list(allowlist)
    incoming_block = _coerce_list(blocklist)
    incoming_keywords = _coerce_list(keywords)

    if reset:
        body = {"allowlist": incoming_allow, "blocklist": incoming_block, "keywords": incoming_keywords}
    else:
        if DRY_RUN:
            _print_json(
                {
                    "dry_run": True,
                    "error": "domains_set_merge_requires_network",
                    "hint": "Use --reset for dry-run, or run without --dry-run to allow fetching existing rules for safe merge.",
                }
            )
            return 2
        # Safety: default to "merge" to avoid accidentally wiping existing rules.
        existing_res = _call(
            "GET",
            _url(vibe, "/vibe/agent/domains/rules"),
            headers=_headers(vibe),
            timeout_seconds=timeout_seconds,
            retries=2,
        )
        _terminate_guard(existing_res)
        if existing_res.status != 200 or not isinstance(existing_res.json, dict):
            _print_json({"error": "failed_to_fetch_existing_rules", **_result_payload(existing_res)})
            return 1
        existing_json = existing_res.json
        existing_allow = list(existing_json.get("allowlist") or [])
        existing_block = list(existing_json.get("blocklist") or [])
        existing_keywords = list(existing_json.get("keywords") or [])

        if not (incoming_allow or incoming_block or incoming_keywords):
            _print_json({"status": 200, "rules": existing_json, "note": "no changes (no incoming values); skipped PUT"})
            return 0

        body = {
            "allowlist": _unique_merge(existing_allow, incoming_allow) if incoming_allow else existing_allow,
            "blocklist": _unique_merge(existing_block, incoming_block) if incoming_block else existing_block,
            "keywords": _unique_merge(existing_keywords, incoming_keywords) if incoming_keywords else existing_keywords,
        }
        if body["allowlist"] == existing_allow and body["blocklist"] == existing_block and body["keywords"] == existing_keywords:
            _print_json({"status": 200, "rules": body, "note": "no changes (merged result equals existing); skipped PUT"})
            return 0
    with _auto_connection(vibe, enable=True, timeout_seconds=timeout_seconds) as conn_id:
        res = _call(
            "PUT",
            _url(vibe, "/vibe/agent/domains/rules"),
            headers=_headers(vibe, connection_id=conn_id),
            json_body=body,
            timeout_seconds=timeout_seconds,
            retries=2,
        )
        _terminate_guard(res)
        _print_json({"status": res.status, "rules": res.json, **({"body": res.body_text[:300]} if res.status >= 400 and res.json is None else {})})
        return 0 if (DRY_RUN or res.status == 200) else 1


def cmd_templates_add(vibe: VibeEnv, timeout_seconds: int, title: str, query: str, frequency: str, price: int, source_type: str, description: str | None, opml: str | None) -> int:
    payload: dict[str, Any] = {
        "title": title,
        "query": query,
        "frequency": frequency,
        "price": int(price),
        "sourceType": source_type,
    }
    if description is not None:
        payload["description"] = description
    if opml is not None:
        payload["opml"] = opml
    with _auto_connection(vibe, enable=True, timeout_seconds=timeout_seconds) as conn_id:
        res = _call(
            "POST",
            _url(vibe, "/vibe/agent/templates"),
            headers=_headers(vibe, connection_id=conn_id),
            json_body=payload,
            timeout_seconds=timeout_seconds,
            retries=2,
        )
        _terminate_guard(res)
        _print_json(_result_payload(res))
        return 0 if (DRY_RUN or res.status == 200) else 1


def cmd_templates_delete(vibe: VibeEnv, timeout_seconds: int, template_id: str) -> int:
    template_id = _require_uuid(template_id, name="template id")
    with _auto_connection(vibe, enable=True, timeout_seconds=timeout_seconds) as conn_id:
        res = _call(
            "DELETE",
            _url(vibe, f"/vibe/agent/templates/{template_id}"),
            headers=_headers(vibe, connection_id=conn_id),
            timeout_seconds=timeout_seconds,
            retries=2,
        )
        _terminate_guard(res)
        _print_json(_result_payload(res))
        return 0 if (DRY_RUN or res.status in (200, 204)) else 1


def cmd_subscriptions_create(
    vibe: VibeEnv,
    timeout_seconds: int,
    name: str,
    prompt: str,
    frequency: str,
    tier: str | None,
    style: str | None,
    sdk: str | None,
    model: str | None,
    reasoning_effort: str | None,
    thinking_mode: str | None,
) -> int:
    freq: Any = frequency
    if isinstance(frequency, str):
        trimmed = frequency.strip()
        if trimmed.startswith("{") and trimmed.endswith("}"):
            try:
                freq = json.loads(trimmed)
            except json.JSONDecodeError:
                freq = frequency
    payload: dict[str, Any] = {"name": name, "prompt": prompt, "frequency": freq}
    if tier is not None:
        payload["tier"] = tier
    if style is not None:
        payload["style"] = style
    ai_payload = _build_ai_payload(
        sdk=sdk,
        model=model,
        reasoning_effort=reasoning_effort,
        thinking_mode=thinking_mode,
    )
    if ai_payload is not None:
        payload["ai"] = ai_payload
    with _auto_connection(vibe, enable=True, timeout_seconds=timeout_seconds) as conn_id:
        res = _call(
            "POST",
            _url(vibe, "/vibe/agent/subscriptions"),
            headers=_headers(vibe, connection_id=conn_id),
            json_body=payload,
            timeout_seconds=timeout_seconds,
            retries=2,
        )
        _terminate_guard(res)
        _print_json(_result_payload(res))
        return 0 if (DRY_RUN or res.status == 200) else 1


def cmd_subscriptions_delete(vibe: VibeEnv, timeout_seconds: int, topic_id: str) -> int:
    topic_id = _require_uuid(topic_id, name="topic id")
    with _auto_connection(vibe, enable=True, timeout_seconds=timeout_seconds) as conn_id:
        res = _call(
            "DELETE",
            _url(vibe, f"/vibe/agent/subscriptions/{topic_id}"),
            headers=_headers(vibe, connection_id=conn_id),
            timeout_seconds=timeout_seconds,
            retries=2,
        )
        _terminate_guard(res)
        _print_json(_result_payload(res))
        return 0 if (DRY_RUN or res.status == 200) else 1


def cmd_reports_generate_with_ai(
    vibe: VibeEnv,
    timeout_seconds: int,
    topic_id: str,
    sdk: str | None,
    model: str | None,
    reasoning_effort: str | None,
    thinking_mode: str | None,
) -> int:
    topic_id = _require_uuid(topic_id, name="topic id")
    body: dict[str, Any] = {}
    ai_payload = _build_ai_payload(
        sdk=sdk,
        model=model,
        reasoning_effort=reasoning_effort,
        thinking_mode=thinking_mode,
    )
    if ai_payload is not None:
        body["ai"] = ai_payload
    with _auto_connection(vibe, enable=True, timeout_seconds=timeout_seconds) as conn_id:
        res = _call(
            "POST",
            _url(vibe, f"/vibe/agent/subscriptions/{topic_id}/reports/generate"),
            headers=_headers(vibe, connection_id=conn_id),
            json_body=body,
            timeout_seconds=timeout_seconds,
            retries=2,
        )
        _terminate_guard(res)
        _print_json(_result_payload(res))
        return 0 if (DRY_RUN or res.status in (200, 202)) else 1


def cmd_reports_delete(vibe: VibeEnv, timeout_seconds: int, topic_id: str, report_id: str) -> int:
    topic_id = _require_uuid(topic_id, name="topic id")
    report_id = _require_uuid(report_id, name="report id")
    with _auto_connection(vibe, enable=True, timeout_seconds=timeout_seconds) as conn_id:
        res = _call(
            "DELETE",
            _url(vibe, f"/vibe/agent/subscriptions/{topic_id}/reports/{report_id}"),
            headers=_headers(vibe, connection_id=conn_id),
            timeout_seconds=timeout_seconds,
            retries=2,
        )
        _terminate_guard(res)
        _print_json(_result_payload(res))
        return 0 if (DRY_RUN or res.status == 200) else 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="client.py", description="Minimal client for dudu Vibe Agent API (/vibe/agent/*).")
    parser.add_argument("--env-file", type=str, default=None, help="Optional path to .env file.")
    parser.add_argument("--url", type=str, default=None, help="Override base URL (e.g., http://localhost:3001).")
    parser.add_argument("--key", type=str, default=None, help="Override key (WARNING: may leak via shell history).")
    parser.add_argument("--timeout", type=int, default=None, help="Request timeout seconds.")
    parser.add_argument("--dry-run", action="store_true", help="不发请求：只打印将要调用的 HTTP 请求（不打印 key）。")

    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ping")
    doctor = sub.add_parser("doctor")
    doctor.add_argument(
        "--watch-seconds",
        type=int,
        default=0,
        help="可选：保持连接并按 config.yaml 的 heartbeat_interval_seconds 循环心跳指定秒数，便于 Web 端观察/终止连接。",
    )

    domains = sub.add_parser("domains")
    domains_sub = domains.add_subparsers(dest="domains_cmd", required=True)
    domains_sub.add_parser("get")
    ds = domains_sub.add_parser("set")
    ds.add_argument("--allowlist", action="append", default=[], help="Repeatable. Example: --allowlist example.com")
    ds.add_argument("--blocklist", action="append", default=[], help="Repeatable.")
    ds.add_argument("--keywords", action="append", default=[], help="Repeatable.")
    ds.add_argument(
        "--reset",
        action="store_true",
        help="危险：将 allowlist/blocklist/keywords 直接重置为你提供的列表（未提供的字段将清空）。默认行为为安全合并（merge）。",
    )

    templates = sub.add_parser("templates")
    templates_sub = templates.add_subparsers(dest="templates_cmd", required=True)
    ta = templates_sub.add_parser("add")
    ta.add_argument("--title", required=True)
    ta.add_argument("--query", required=True)
    ta.add_argument("--frequency", required=True, choices=["hourly", "daily", "weekly"])
    ta.add_argument("--price", type=int, default=0)
    ta.add_argument("--source-type", default="search", choices=["search", "rss_opml"])
    ta.add_argument("--description", default=None)
    ta.add_argument("--opml", default=None)
    td = templates_sub.add_parser("delete")
    td.add_argument("--id", required=True)

    subs = sub.add_parser("subscriptions")
    subs_sub = subs.add_subparsers(dest="subs_cmd", required=True)
    sc = subs_sub.add_parser("create")
    sc.add_argument("--name", required=True)
    sc.add_argument("--prompt", required=True)
    sc.add_argument("--frequency", required=True, help="hourly|daily|weekly or JSON for custom frequency")
    sc.add_argument("--tier", default=None, choices=["basic", "standard", "premium"])
    sc.add_argument("--style", default=None, help="Report style (e.g., deep_research)")
    sc.add_argument("--sdk", default=None, choices=["codex", "codex_cli", "claude", "claude_code", "zhipu", "ark", "qwen", "deepseek"])
    sc.add_argument("--model", default=None, help="Model override; for CLI providers, empty string means use CLI default model.")
    sc.add_argument("--reasoning-effort", default=None, choices=["none", "low", "medium", "high", "xhigh"])
    sc.add_argument("--thinking-mode", default=None, choices=["off", "thinking"])
    sd = subs_sub.add_parser("delete")
    sd.add_argument("--topic-id", required=True)

    reports = sub.add_parser("reports")
    reports_sub = reports.add_subparsers(dest="reports_cmd", required=True)
    rg = reports_sub.add_parser("generate")
    rg.add_argument("--topic-id", required=True)
    rg.add_argument("--sdk", default=None, choices=["codex", "codex_cli", "claude", "claude_code", "zhipu", "ark", "qwen", "deepseek"])
    rg.add_argument("--model", default=None, help="Model override; for CLI providers, empty string means use CLI default model.")
    rg.add_argument("--reasoning-effort", default=None, choices=["none", "low", "medium", "high", "xhigh"])
    rg.add_argument("--thinking-mode", default=None, choices=["off", "thinking"])
    rr = reports_sub.add_parser("delete")
    rr.add_argument("--topic-id", required=True)
    rr.add_argument("--report-id", required=True)

    args = parser.parse_args(argv)
    global DRY_RUN
    DRY_RUN = bool(args.dry_run)

    vibe = resolve_vibe_env(skill_root=_skill_root(), env_file=Path(args.env_file).expanduser() if args.env_file else None)
    if args.url:
        vibe = VibeEnv(url=_normalize_base_url(args.url), key=vibe.key, url_source=vibe.url_source, key_source=vibe.key_source)
    if args.key:
        vibe = VibeEnv(url=vibe.url, key=args.key.strip(), url_source=vibe.url_source, key_source=vibe.key_source)

    _ensure_key(vibe)

    timeout_seconds = int(args.timeout or _config()["timeout"])

    try:
        if args.cmd == "ping":
            return cmd_ping(vibe, timeout_seconds)
        if args.cmd == "doctor":
            if int(getattr(args, "watch_seconds", 0) or 0) <= 0:
                return cmd_doctor(vibe, timeout_seconds)
            watch_seconds = int(args.watch_seconds)
            if DRY_RUN:
                return cmd_doctor(vibe, timeout_seconds)
            cfg = _config()
            interval = max(5, int(cfg["heartbeat"]))

            ping = _call("GET", _url(vibe, "/vibe/agent/ping"), headers=_headers(vibe), timeout_seconds=timeout_seconds, retries=2)
            _terminate_guard(ping)
            if ping.status != 200:
                _print_json({"watch": {"url": vibe.url, "key_prefix": redact_secret(vibe.key, keep=10)}, "ping": _result_payload(ping)})
                return 1

            _print_json(
                {
                    "watch": {
                        "url": vibe.url,
                        "key_prefix": redact_secret(vibe.key, keep=10),
                        "watch_seconds": watch_seconds,
                        "heartbeat_interval_seconds": interval,
                    },
                    "ping": _result_payload(ping),
                }
            )
            end_at = time.time() + watch_seconds
            with _auto_connection(vibe, enable=True, timeout_seconds=timeout_seconds) as conn_id:
                while time.time() < end_at:
                    hb = _call(
                        "POST",
                        _url(vibe, "/vibe/agent/heartbeat"),
                        headers=_headers(vibe, connection_id=conn_id),
                        json_body={"connectionId": conn_id},
                        timeout_seconds=timeout_seconds,
                        retries=0,
                    )
                    _terminate_guard(hb)
                    _print_json({"heartbeat": _result_payload(hb)})
                    sleep_for = min(interval, max(0.0, end_at - time.time()))
                    if sleep_for <= 0:
                        break
                    time.sleep(sleep_for)
            return 0
        if args.cmd == "domains":
            if args.domains_cmd == "get":
                return cmd_domains_get(vibe, timeout_seconds)
            if args.domains_cmd == "set":
                return cmd_domains_set(vibe, timeout_seconds, args.allowlist, args.blocklist, args.keywords, reset=bool(args.reset))
        if args.cmd == "templates":
            if args.templates_cmd == "add":
                return cmd_templates_add(
                    vibe,
                    timeout_seconds,
                    title=args.title,
                    query=args.query,
                    frequency=args.frequency,
                    price=args.price,
                    source_type=args.source_type,
                    description=args.description,
                    opml=args.opml,
                )
            if args.templates_cmd == "delete":
                return cmd_templates_delete(vibe, timeout_seconds, args.id)
        if args.cmd == "subscriptions":
            if args.subs_cmd == "create":
                return cmd_subscriptions_create(
                    vibe,
                    timeout_seconds,
                    args.name,
                    args.prompt,
                    args.frequency,
                    args.tier,
                    args.style,
                    args.sdk,
                    args.model,
                    args.reasoning_effort,
                    args.thinking_mode,
                )
            if args.subs_cmd == "delete":
                return cmd_subscriptions_delete(vibe, timeout_seconds, args.topic_id)
        if args.cmd == "reports":
            if args.reports_cmd == "generate":
                return cmd_reports_generate_with_ai(
                    vibe,
                    timeout_seconds,
                    args.topic_id,
                    args.sdk,
                    args.model,
                    args.reasoning_effort,
                    args.thinking_mode,
                )
            if args.reports_cmd == "delete":
                return cmd_reports_delete(vibe, timeout_seconds, args.topic_id, args.report_id)
    except TerminateRequested as e:
        _print_json({"terminate_requested": True, "reason": e.reason, **_result_payload(e.res)})
        return 0

    raise SystemExit("unknown command")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
