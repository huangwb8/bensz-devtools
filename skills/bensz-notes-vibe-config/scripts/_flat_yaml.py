from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FlatYaml:
    scalars: dict[str, str]
    lists: dict[str, list[str]]


def load_flat_yaml(path: Path) -> FlatYaml:
    """
    极简 YAML 解析器（仅支持 top-level `key: value` 与 `key:` + `- item` 列表）。
    设计目标：0 依赖、可预测、足够覆盖本 skill 的 config.yaml。
    """
    scalars: dict[str, str] = {}
    lists: dict[str, list[str]] = {}

    current_list_key: str | None = None

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return FlatYaml(scalars=scalars, lists=lists)

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("- "):
            if current_list_key is None:
                continue
            item = stripped[2:].strip()
            if (item.startswith('"') and item.endswith('"')) or (item.startswith("'") and item.endswith("'")):
                item = item[1:-1]
            lists.setdefault(current_list_key, []).append(item)
            continue

        current_list_key = None
        if ":" not in stripped:
            continue
        key, rest = stripped.split(":", 1)
        key = key.strip()
        value = rest.strip()
        if not key:
            continue
        if value == "":
            current_list_key = key
            lists.setdefault(key, [])
            continue
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        scalars[key] = value

    return FlatYaml(scalars=scalars, lists=lists)

