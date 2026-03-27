from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HttpResult:
    status: int
    headers: dict[str, str]
    body_text: str
    json: Any | None


def _read_response_body(res: Any) -> str:
    raw = res.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: Any | None = None,
    timeout_seconds: int = 15,
    retries: int = 0,
    backoff_seconds: float = 0.6,
) -> HttpResult:
    hdrs = {"accept": "application/json"}
    if headers:
        hdrs.update(headers)

    data = None
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        hdrs.setdefault("content-type", "application/json")

    method_upper = method.upper().strip()
    has_idempotency_key = any(
        key.lower() == "x-idempotency-key" and str(value).strip() != ""
        for key, value in hdrs.items()
    )
    # Safety guard: never blind-retry non-idempotent writes unless caller explicitly provides idempotency key.
    effective_retries = retries
    if method_upper in {"POST", "PUT", "PATCH", "DELETE"} and not has_idempotency_key:
        effective_retries = 0

    last_err: Exception | None = None
    for attempt in range(effective_retries + 1):
        if attempt > 0:
            time.sleep(backoff_seconds * (2 ** (attempt - 1)))
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs, method=method.upper())
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            # Reliability: avoid accidentally sending localhost traffic through corporate proxies.
            bypass_proxy = host in {"localhost", "127.0.0.1", "0.0.0.0", "::1", "host.docker.internal"}
            opener = (
                urllib.request.build_opener(urllib.request.ProxyHandler({}))
                if bypass_proxy
                else urllib.request.build_opener()
            )
            with opener.open(req, timeout=timeout_seconds) as res:
                body = _read_response_body(res)
                header_map = {k.lower(): v for k, v in dict(res.headers).items()}
                parsed_json = None
                try:
                    parsed_json = json.loads(body) if body.strip() else None
                except json.JSONDecodeError:
                    parsed_json = None
                return HttpResult(status=int(res.status), headers=header_map, body_text=body, json=parsed_json)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = _read_response_body(e)
            except Exception:
                body = ""
            header_map = {k.lower(): v for k, v in dict(getattr(e, "headers", {}) or {}).items()}
            parsed_json = None
            try:
                parsed_json = json.loads(body) if body.strip() else None
            except json.JSONDecodeError:
                parsed_json = None
            status = int(e.code)
            retryable = status in {408, 429} or 500 <= status <= 599
            if retryable and attempt < effective_retries:
                last_err = e
                continue
            return HttpResult(status=status, headers=header_map, body_text=body, json=parsed_json)
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"request failed after {effective_retries + 1} attempts: {last_err!r}")
