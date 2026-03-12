from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from _dotenv import EnvSource, expand_user_paths, load_dotenv_file
from _flat_yaml import load_flat_yaml
from _redact import redact_secret


@dataclass(frozen=True)
class BdcEnv:
    url: str
    key: str
    url_source: EnvSource
    key_source: EnvSource
    env_file_path: Path | None  # 实际使用的 .env 文件路径（如果有）

    def key_prefix(self) -> str:
        return redact_secret(self.key, keep=12)


def _first_present(env: dict[str, str], keys: list[str]) -> tuple[str | None, str | None]:
    for k in keys:
        v = env.get(k)
        if v is not None and str(v).strip():
            return k, str(v).strip()
    return None, None


def normalize_base_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return u
    if not (u.startswith("http://") or u.startswith("https://")):
        u = "http://" + u
    return u.rstrip("/")


def _find_env_files_upward(start_dir: Path, filenames: list[str], max_depth: int = 5) -> list[Path]:
    """向上递归查找 .env 文件（类似 git 查找 .git 目录）"""
    found: list[Path] = []
    current = start_dir.resolve()

    for _ in range(max_depth):
        for name in filenames:
            candidate = current / name
            if candidate.is_file():
                found.append(candidate)

        parent = current.parent
        if parent == current:  # 到达根目录
            break
        current = parent

    return found


def resolve_bdc_env(*, skill_root: Path, env_file: Path | None = None) -> BdcEnv:
    config_path = skill_root / "config.yaml"
    config = load_flat_yaml(config_path)

    url_keys = config.lists.get("env_url_keys", ["BENSZ_CHANNEL_URL", "bensz_channel_url", "bdc_url"])
    key_keys = config.lists.get("env_key_keys", ["BENSZ_CHANNEL_KEY", "bensz_channel_key", "bdc_key"])

    default_url = config.scalars.get("default_url", "http://localhost:6542").strip()
    default_url = normalize_base_url(default_url)

    url_source = EnvSource(kind="default", detail=str(config_path))
    key_source = EnvSource(kind="missing", detail="not found")
    used_env_file: Path | None = None  # 记录实际使用的 .env 文件路径

    sources: list[tuple[EnvSource, dict[str, str], Path | None]] = []
    search_max_depth = int(config.scalars.get("env_search_max_depth", "5"))

    # 1. OS 环境变量（最高优先级）
    os_env = {k: v for k, v in os.environ.items() if isinstance(v, str)}
    sources.append((EnvSource(kind="os_env", detail="process"), os_env, None))

    # 2. 用户指定的 env 文件
    if env_file is not None:
        sources.append((EnvSource(kind="env_file", detail=str(env_file)), load_dotenv_file(env_file), env_file))

    # 3. 当前工作目录及向上递归查找 .env 文件
    candidates = config.lists.get("env_file_candidates", [".env", ".env.local"])
    found_env_files = _find_env_files_upward(Path.cwd(), candidates, max_depth=search_max_depth)
    for p in found_env_files:
        sources.append((EnvSource(kind="cwd_env", detail=str(p)), load_dotenv_file(p), p))

    # 4. Fallback 配置文件（用户主目录等）
    for p in expand_user_paths(config.lists.get("fallback_env_files", [])):
        sources.append((EnvSource(kind="fallback_env", detail=str(p)), load_dotenv_file(p), p))

    url_value: str | None = None
    key_value: str | None = None

    for src, env, file_path in sources:
        if url_value is None:
            k, v = _first_present(env, url_keys)
            if v is not None:
                url_value = v
                if src.kind in {"env_file", "cwd_env", "fallback_env"}:
                    url_source = EnvSource(kind=src.kind, detail=f"{k or '?'} ({src.detail})")
                    if used_env_file is None and file_path is not None:
                        used_env_file = file_path
                else:
                    url_source = EnvSource(kind=src.kind, detail=k or src.detail)
        if key_value is None:
            k, v = _first_present(env, key_keys)
            if v is not None:
                key_value = v
                if src.kind in {"env_file", "cwd_env", "fallback_env"}:
                    key_source = EnvSource(kind=src.kind, detail=f"{k or '?'} ({src.detail})")
                    if used_env_file is None and file_path is not None:
                        used_env_file = file_path
                else:
                    key_source = EnvSource(kind=src.kind, detail=k or src.detail)
        if url_value is not None and key_value is not None:
            break

    url = normalize_base_url(url_value or default_url)
    key = (key_value or "").strip()

    return BdcEnv(url=url, key=key, url_source=url_source, key_source=key_source, env_file_path=used_env_file)
