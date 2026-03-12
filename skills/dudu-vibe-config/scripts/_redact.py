from __future__ import annotations


def redact_secret(value: str, *, keep: int = 10) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) <= keep:
        return value[0:1] + "***"
    return value[:keep] + "…"  # avoid revealing full secret

