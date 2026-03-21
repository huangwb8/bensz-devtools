from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from _dotenv import EnvSource, expand_user_paths, load_dotenv_file
from _flat_yaml import load_flat_yaml
from _redact import redact_secret


@dataclass(frozen=True)
class VibeEnv:
    url: str
    key: str
    url_source: EnvSource
    key_source: EnvSource

    def key_prefix(self) -> str:
        return redact_secret(self.key, keep=10)


def _first_present(env: dict[str, str], keys: list[str]) -> tuple[str | None, str | None]:
    for k in keys:
        v = env.get(k)
        if v is not None and str(v).strip():
            return k, str(v).strip()
    return None, None


def _normalize_base_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return u
    if "://" in u and not (u.startswith("http://") or u.startswith("https://")):
        raise SystemExit(f"Invalid vibe URL scheme (http/https only): {url!r}")
    if not (u.startswith("http://") or u.startswith("https://")):
        # 默认按 http 处理（本机 docker/内网常见）；避免 silent failure
        u = "http://" + u
    return u.rstrip("/")


def resolve_vibe_env(*, skill_root: Path, env_file: Path | None = None) -> VibeEnv:
    config_path = skill_root / "config.yaml"
    config = load_flat_yaml(config_path)

    url_keys = config.lists.get("env_url_keys", ["DUDU_VIBE_URL", "dudu_vibe_url"])
    key_keys = config.lists.get("env_key_keys", ["DUDU_VIBE_KEY", "dudu_vibe_key", "dudu_vibe_api"])

    default_url = config.scalars.get("default_vibe_url", "http://localhost:3001").strip()
    default_url = _normalize_base_url(default_url)

    url_source = EnvSource(kind="default", detail=str(config_path))
    key_source = EnvSource(kind="missing", detail="not found")

    # Priority (high -> low):
    #   1) OS env
    #   2) explicit --env-file (optional)
    #   3) cwd .env candidates
    #   4) fallback env files (home-level)
    sources: list[tuple[EnvSource, dict[str, str]]] = []

    os_env = {k: v for k, v in os.environ.items() if isinstance(v, str)}
    sources.append((EnvSource(kind="os_env", detail="process"), os_env))

    if env_file is not None:
        sources.append((EnvSource(kind="env_file", detail=str(env_file)), load_dotenv_file(env_file)))

    candidates = config.lists.get("env_file_candidates", [".env", ".env.local"])
    for name in candidates:
        p = (Path.cwd() / name).resolve()
        sources.append((EnvSource(kind="cwd_env", detail=str(p)), load_dotenv_file(p)))

    for p in expand_user_paths(config.lists.get("fallback_env_files", [])):
        sources.append((EnvSource(kind="fallback_env", detail=str(p)), load_dotenv_file(p)))

    url_value: str | None = None
    key_value: str | None = None

    for src, env in sources:
        if url_value is None:
            k, v = _first_present(env, url_keys)
            if v is not None:
                url_value = v
                if src.kind in {"env_file", "cwd_env", "fallback_env"}:
                    url_source = EnvSource(kind=src.kind, detail=f"{k or '?'} ({src.detail})")
                else:
                    url_source = EnvSource(kind=src.kind, detail=k or src.detail)
        if key_value is None:
            k, v = _first_present(env, key_keys)
            if v is not None:
                key_value = v
                if src.kind in {"env_file", "cwd_env", "fallback_env"}:
                    key_source = EnvSource(kind=src.kind, detail=f"{k or '?'} ({src.detail})")
                else:
                    key_source = EnvSource(kind=src.kind, detail=k or src.detail)
        if url_value is not None and key_value is not None:
            break

    url = _normalize_base_url(url_value or default_url)
    key = (key_value or "").strip()

    return VibeEnv(url=url, key=key, url_source=url_source, key_source=key_source)
