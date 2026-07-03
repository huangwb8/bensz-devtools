from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from _dotenv import EnvSource, expand_user_paths, load_dotenv_file
from _flat_yaml import load_flat_yaml
from _redact import redact_secret


@dataclass(frozen=True)
class BnEnv:
    url: str
    api_prefix: str
    key: str
    url_source: EnvSource
    key_source: EnvSource
    api_prefix_source: EnvSource
    env_file_path: Path | None

    def key_prefix(self) -> str:
        return redact_secret(self.key, keep=12)


def _first_present(env: dict[str, str], keys: list[str]) -> tuple[str | None, str | None]:
    for key in keys:
        value = env.get(key)
        if value is not None and str(value).strip():
            return key, str(value).strip()
    return None, None


def normalize_base_url(url: str) -> str:
    value = (url or "").strip()
    if not value:
        return value
    if "://" in value and not (value.startswith("http://") or value.startswith("https://")):
        raise SystemExit(f"Invalid URL scheme (http/https only): {url!r}")
    if not (value.startswith("http://") or value.startswith("https://")):
        value = "http://" + value
    return value.rstrip("/")


def normalize_api_prefix(prefix: str | None) -> str:
    value = (prefix or "").strip()
    if value in {"", "/", "none", "None", "NONE", "-"}:
        return ""
    if not value.startswith("/"):
        value = "/" + value
    return value.rstrip("/")


def _find_env_files_upward(start_dir: Path, filenames: list[str], max_depth: int) -> list[Path]:
    found: list[Path] = []
    seen: set[Path] = set()
    current = start_dir.resolve()
    for _ in range(max_depth):
        for name in filenames:
            candidate = (current / name).resolve()
            if candidate.is_file() and candidate not in seen:
                found.append(candidate)
                seen.add(candidate)
        parent = current.parent
        if parent == current:
            break
        current = parent
    return found


def resolve_bn_env(*, skill_root: Path, env_file: Path | None = None) -> BnEnv:
    config_path = skill_root / "config.yaml"
    config = load_flat_yaml(config_path)

    url_keys = config.lists.get("env_url_keys", ["BENSZ_NOTES_URL", "bn_url"])
    key_keys = config.lists.get("env_key_keys", ["BENSZ_NOTES_KEY", "bn_key"])
    prefix_keys = config.lists.get("env_api_prefix_keys", ["BENSZ_NOTES_API_PREFIX", "bn_api_prefix"])

    default_url = normalize_base_url(config.scalars.get("default_url", "http://localhost:3000"))
    default_prefix = normalize_api_prefix(config.scalars.get("default_api_prefix", "/api/backend"))

    url_source = EnvSource(kind="default", detail=str(config_path))
    key_source = EnvSource(kind="missing", detail="not found")
    prefix_source = EnvSource(kind="default", detail=str(config_path))
    used_env_file: Path | None = None

    sources: list[tuple[EnvSource, dict[str, str], Path | None]] = []
    sources.append((EnvSource(kind="os_env", detail="process"), dict(os.environ), None))

    if env_file is not None:
        sources.append((EnvSource(kind="env_file", detail=str(env_file)), load_dotenv_file(env_file), env_file))

    candidates = config.lists.get("env_file_candidates", [".env", ".env.local", "remote.env"])
    max_depth = int(config.scalars.get("env_search_max_depth", "5"))
    for path in _find_env_files_upward(Path.cwd(), candidates, max_depth=max_depth):
        sources.append((EnvSource(kind="cwd_env", detail=str(path)), load_dotenv_file(path), path))

    for path in expand_user_paths(config.lists.get("fallback_env_files", [])):
        sources.append((EnvSource(kind="fallback_env", detail=str(path)), load_dotenv_file(path), path))

    url_value: str | None = None
    key_value: str | None = None
    prefix_value: str | None = None

    for source, env, file_path in sources:
        if url_value is None:
            key, value = _first_present(env, url_keys)
            if value is not None:
                url_value = value
                url_source = EnvSource(source.kind, f"{key or '?'} ({source.detail})" if file_path else key or source.detail)
                used_env_file = used_env_file or file_path
        if key_value is None:
            key, value = _first_present(env, key_keys)
            if value is not None:
                key_value = value
                key_source = EnvSource(source.kind, f"{key or '?'} ({source.detail})" if file_path else key or source.detail)
                used_env_file = used_env_file or file_path
        if prefix_value is None:
            key, value = _first_present(env, prefix_keys)
            if value is not None:
                prefix_value = value
                prefix_source = EnvSource(source.kind, f"{key or '?'} ({source.detail})" if file_path else key or source.detail)
                used_env_file = used_env_file or file_path
        if url_value is not None and key_value is not None and prefix_value is not None:
            break

    url = normalize_base_url(url_value or default_url)
    api_prefix = normalize_api_prefix(prefix_value if prefix_value is not None else default_prefix)
    if url.endswith("/api/backend"):
        url = url[: -len("/api/backend")]
        api_prefix = "/api/backend" if prefix_value is None else api_prefix

    return BnEnv(
        url=url,
        api_prefix=api_prefix,
        key=(key_value or "").strip(),
        url_source=url_source,
        key_source=key_source,
        api_prefix_source=prefix_source,
        env_file_path=used_env_file,
    )
