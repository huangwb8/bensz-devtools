from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
        return value[1:-1]
    return value


def parse_dotenv(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        raw_value = value.strip()

        if raw_value.startswith(("'", '"')):
            quote = raw_value[0]
            end = raw_value.find(quote, 1)
            if end != -1:
                # Keep only the quoted segment; ignore trailing comment/garbage.
                raw_value = raw_value[: end + 1]
        else:
            # Strip inline comments for unquoted values: `KEY=value # comment`
            if "#" in raw_value:
                hash_index = raw_value.find("#")
                if hash_index > 0 and raw_value[hash_index - 1].isspace():
                    raw_value = raw_value[:hash_index].rstrip()

        value = _strip_quotes(raw_value)
        if not key:
            continue
        result[key] = value
    return result


def load_dotenv_file(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    return parse_dotenv(text)


def expand_user_paths(paths: Iterable[str]) -> list[Path]:
    expanded: list[Path] = []
    for p in paths:
        expanded.append(Path(p).expanduser())
    return expanded


@dataclass(frozen=True)
class EnvSource:
    kind: str
    detail: str
