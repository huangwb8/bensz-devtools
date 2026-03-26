from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from _flat_yaml import load_flat_yaml


RUNNER_CHOICES = ["auto", "codex", "claude"]
TOPIC_SEARCH_PLAN_PROMPT_ID = "topic_search_plan"
TOPIC_SEARCH_PLAN_VERSION = "topic-search-plan-v2"
TOPIC_MCP_QUERY_VARIANT_KEYS = [
    "default",
    "search_query",
    "tavily",
    "serper",
    "duckduckgo",
    "brave",
    "searxng",
]
DEFAULT_TOPIC_QUERY_BUDGET = {
    "derivedQueryMaxChars": 1200,
    "booleanLinesMaxCount": 5,
    "booleanLineMaxChars": 240,
    "mcpVariantMaxChars": {
        "default": 1200,
        "search_query": 1200,
        "tavily": 1600,
        "serper": 1200,
        "duckduckgo": 1200,
        "brave": 1200,
        "searxng": 1200,
    },
}

LOCAL_DERIVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "derivedQuery",
        "booleanLines",
        "keywords",
        "coreQuestions",
        "qualityIssues",
        "scenario",
        "scenarioConfidence",
        "scenarioReasoning",
    ],
    "properties": {
        "derivedQuery": {"type": "string", "minLength": 1},
        "booleanLines": {"type": "array", "items": {"type": "string"}},
        "queryVariants": {"type": "object"},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "coreQuestions": {"type": "array", "items": {"type": "string"}},
        "qualityIssues": {"type": "array", "items": {"type": "string"}},
        "scenario": {"type": "string", "enum": ["general", "academic"]},
        "scenarioConfidence": {"type": "number", "minimum": 0, "maximum": 1},
        "scenarioReasoning": {"type": "string", "minLength": 1},
    },
}


@dataclass(frozen=True)
class LocalDeriveResult:
    runner: str
    derived_query: str
    derived_plan: dict[str, Any]
    raw_output: str


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _local_derive_defaults() -> dict[str, Any]:
    cfg = load_flat_yaml(_skill_root() / "config.yaml")
    return {
        "runner": str(cfg.scalars.get("default_local_derived_runner", "auto")).strip() or "auto",
        "timeout": int(cfg.scalars.get("local_derived_timeout_seconds", "180")),
    }


def normalize_topic_prompt_for_derivation(prompt: str) -> str:
    return re.sub(r"\s+", " ", str(prompt or "")).strip()


def compute_topic_prompt_hash(prompt: str) -> str:
    return hashlib.md5(normalize_topic_prompt_for_derivation(prompt).encode("utf-8")).hexdigest()


def _clamp_text(text: str, max_chars: int) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        return ""
    return normalized if len(normalized) <= max_chars else normalized[:max_chars].strip()


def _normalize_boolean_line(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"^[\s•*\-\d.)]+", "", str(value or ""))).strip()


def _normalize_display_query_text(text: str) -> str:
    return "\n".join(line.strip() for line in str(text or "").splitlines() if line.strip()).strip()


def _normalize_query_variant_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _to_clean_string_array(value: Any, max_items: int, max_chars: int) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        normalized = str(item or "").strip()
        if not normalized:
            continue
        normalized = normalized if len(normalized) <= max_chars else normalized[:max_chars].strip()
        out.append(normalized)
        if len(out) >= max_items:
            break
    return out


def _normalize_boolean_lines(value: Any, fallback: str) -> list[str]:
    max_count = int(DEFAULT_TOPIC_QUERY_BUDGET["booleanLinesMaxCount"])
    max_chars = int(DEFAULT_TOPIC_QUERY_BUDGET["booleanLineMaxChars"])

    from_value: list[str] = []
    if isinstance(value, list):
        for item in value:
            normalized = _clamp_text(_normalize_boolean_line(str(item or "")), max_chars)
            if normalized:
                from_value.append(normalized)
    if from_value:
        return list(dict.fromkeys(from_value))[:max_count]

    from_fallback = [
        _clamp_text(_normalize_boolean_line(line), max_chars)
        for line in str(fallback or "").splitlines()
        if _clamp_text(_normalize_boolean_line(line), max_chars)
    ]
    if len(from_fallback) > 1:
        return list(dict.fromkeys(from_fallback))[:max_count]

    single = _clamp_text(_normalize_boolean_line(str(fallback or "")), max_chars)
    return [single] if single else []


def _render_multiline_query(lines: list[str], fallback: str) -> str:
    if len(lines) > 1:
        return "\n".join(lines)
    return str(fallback or "").strip() or (lines[0] if lines else "")


def _render_boolean_single_line(lines: list[str], fallback: str) -> str:
    if len(lines) > 1:
        grouped = [f"({line[1:-1] if line.startswith('(') and line.endswith(')') else line})" for line in lines]
        return " AND ".join(grouped)
    return _normalize_query_variant_text(str(fallback or "")) or (lines[0] if lines else "")


def _render_searxng_query(lines: list[str], fallback: str) -> str:
    if len(lines) > 1:
        return " ".join(lines)
    return _normalize_query_variant_text(str(fallback or "")) or (lines[0] if lines else "")


def _render_tavily_query(lines: list[str], fallback: str) -> str:
    if len(lines) > 1:
        return _normalize_query_variant_text(" ".join(lines))
    return _normalize_query_variant_text(str(fallback or "")) or (lines[0] if lines else "")


def _build_default_mcp_query_variants(lines: list[str], default_query: str) -> dict[str, str]:
    compatibility = _render_boolean_single_line(lines, default_query)
    search_engine_like = _render_searxng_query(lines, default_query)
    semantic_like = _render_tavily_query(lines, default_query)
    normalized_default = _normalize_query_variant_text(default_query)
    return {
        "default": compatibility or normalized_default,
        "search_query": compatibility or normalized_default,
        "tavily": semantic_like or normalized_default,
        "serper": search_engine_like or normalized_default,
        "duckduckgo": search_engine_like or normalized_default,
        "brave": compatibility or normalized_default,
        "searxng": search_engine_like or normalized_default,
    }


def _normalize_query_variants(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}

    out: dict[str, Any] = {}
    for target in ("default", "display", "searxng", "api"):
        value = raw.get(target)
        if not isinstance(value, str):
            continue
        normalized = value.strip() if target == "display" else _normalize_query_variant_text(value)
        if normalized:
            out[target] = normalized

    next_mcp: dict[str, str] = {}
    mcp_raw = raw.get("mcp")
    if isinstance(mcp_raw, dict):
        for target in TOPIC_MCP_QUERY_VARIANT_KEYS:
            value = mcp_raw.get(target)
            if not isinstance(value, str):
                continue
            normalized = _normalize_query_variant_text(value)
            if normalized:
                next_mcp[target] = normalized
    smart_tools_raw = raw.get("smart_tools")
    if isinstance(smart_tools_raw, str):
        normalized = _normalize_query_variant_text(smart_tools_raw)
        if normalized and "default" not in next_mcp:
            next_mcp["default"] = normalized
    if next_mcp:
        out["mcp"] = next_mcp
    return out


def _build_topic_query_variants(derived_query: str, boolean_lines: Any, query_variants: Any) -> dict[str, Any]:
    budget = DEFAULT_TOPIC_QUERY_BUDGET
    base_derived_query = _clamp_text(
        _normalize_display_query_text(str(derived_query or "")),
        int(budget["derivedQueryMaxChars"]),
    )
    normalized_lines = _normalize_boolean_lines(boolean_lines, base_derived_query)
    explicit = _normalize_query_variants(query_variants)
    display = _clamp_text(
        _normalize_display_query_text(explicit.get("display") or _render_multiline_query(normalized_lines, base_derived_query)),
        int(budget["derivedQueryMaxChars"]),
    )
    default_query = _clamp_text(explicit.get("default") or display, int(budget["derivedQueryMaxChars"]))
    searxng = explicit.get("searxng") or _render_searxng_query(normalized_lines, default_query)
    api = explicit.get("api") or _render_multiline_query(normalized_lines, display or base_derived_query)
    default_mcp = _build_default_mcp_query_variants(normalized_lines, default_query or display or base_derived_query)
    explicit_mcp = explicit.get("mcp") if isinstance(explicit.get("mcp"), dict) else {}
    mcp = {**default_mcp, **explicit_mcp, "default": explicit_mcp.get("default", default_mcp["default"])}
    for target in TOPIC_MCP_QUERY_VARIANT_KEYS:
        mcp[target] = _clamp_text(mcp[target], int(budget["mcpVariantMaxChars"][target]))

    return {
        "default": default_query or display or base_derived_query,
        "display": display or base_derived_query,
        "searxng": searxng or _normalize_query_variant_text(default_query or display or base_derived_query),
        "api": api or display or base_derived_query,
        "mcp": mcp,
        "smart_tools": mcp["default"],
    }


def build_topic_derived_plan(*, prompt: str, payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    derived_query = str(payload.get("derivedQuery") or payload.get("derived_query") or "").strip()
    if not derived_query:
        raise SystemExit("Local derived builder returned empty derivedQuery.")

    variants = _build_topic_query_variants(
        derived_query=derived_query,
        boolean_lines=payload.get("booleanLines") or payload.get("boolean_lines"),
        query_variants=payload.get("queryVariants") or payload.get("query_variants"),
    )
    scenario = payload.get("scenario")
    if scenario not in {"general", "academic"}:
        scenario = None
    raw_confidence = payload.get("scenarioConfidence", payload.get("scenario_confidence"))
    scenario_confidence = None
    if isinstance(raw_confidence, (int, float)):
        scenario_confidence = max(0.0, min(1.0, float(raw_confidence)))
    scenario_reasoning = str(payload.get("scenarioReasoning") or payload.get("scenario_reasoning") or "").strip() or None

    plan = {
        "version": TOPIC_SEARCH_PLAN_VERSION,
        "promptTemplateId": TOPIC_SEARCH_PLAN_PROMPT_ID,
        "promptHash": compute_topic_prompt_hash(prompt),
        "source": "ai",
        "derivedQuery": variants["display"],
        "booleanLines": _normalize_boolean_lines(payload.get("booleanLines") or payload.get("boolean_lines"), variants["display"]),
        "queryVariants": variants,
        "keywords": _to_clean_string_array(payload.get("keywords"), 20, 80),
        "coreQuestions": _to_clean_string_array(payload.get("coreQuestions") or payload.get("core_questions"), 10, 160),
        "qualityIssues": _to_clean_string_array(payload.get("qualityIssues") or payload.get("quality_issues"), 10, 80),
    }
    if scenario is not None:
        plan["scenario"] = scenario
    if scenario_confidence is not None:
        plan["scenarioConfidence"] = scenario_confidence
    if scenario_reasoning is not None:
        plan["scenarioReasoning"] = scenario_reasoning
    return variants["display"], plan


def _extract_first_json_object(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        raise SystemExit("Local derived builder returned empty output.")
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    if start < 0:
        raise SystemExit("Local derived builder did not return JSON.")
    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : idx + 1]
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
                break
    raise SystemExit("Failed to extract JSON object from local derived builder output.")


def build_local_derive_prompt(*, prompt: str, topic_name: str | None = None) -> str:
    topic_block = f"\n- 主题名（可选参考）：{topic_name.strip()}" if topic_name and topic_name.strip() else ""
    return textwrap.dedent(
        f"""
        你正在为 dudu 生成本地 search plan。请把用户 prompt 转成稳定、可复用的 derived_query / derived_plan 核心字段。

        约束：
        - 只输出 JSON，不要 Markdown，不要解释。
        - `derivedQuery` 应该是“人类可读、适合展示”的检索表达式；复杂场景优先多行布尔块。
        - `booleanLines` 给出 1-5 条检索行；每条尽量独立、可组合、去噪。
        - 不要把“最新/最近/当下”自动改写成具体年份或时间范围；只有用户明确写了年份、日期、过去 N 天/月/年，才保留时间约束。
        - `keywords` 给 8-12 个英文检索关键词，便于后续多后端搜索复用。
        - `coreQuestions` 给 2-5 个真正要跟踪的问题。
        - `qualityIssues` 只有在你认为 prompt 仍存在明显歧义、范围过大、时间约束缺失、实体冲突等问题时才填写，否则返回空数组。
        - `scenario` 只能是 `general` 或 `academic`。
        - `scenarioConfidence` 用 0-1 小数。
        - `scenarioReasoning` 用一个简短、稳定的标识语句。

        输出 JSON 字段：
        {{
          "derivedQuery": "string",
          "booleanLines": ["string"],
          "keywords": ["string"],
          "coreQuestions": ["string"],
          "qualityIssues": ["string"],
          "scenario": "general|academic",
          "scenarioConfidence": 0.0,
          "scenarioReasoning": "string"
        }}

        用户输入：
        - 原始 prompt：{prompt.strip()!r}{topic_block}
        """
    ).strip()


def _call_codex(*, prompt: str, model: str | None, effort: str | None, timeout_seconds: int) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        schema_path = Path(tmpdir) / "schema.json"
        schema_path.write_text(json.dumps(LOCAL_DERIVE_SCHEMA, ensure_ascii=False), encoding="utf-8")
        cmd = ["codex", "-C", str(Path.cwd()), "-s", "read-only", "-a", "never"]
        if model:
            cmd.extend(["-m", model])
        if effort:
            cmd.extend(["-c", f'reasoning_effort="{effort}"'])
        cmd.extend(["exec", "--skip-git-repo-check", "--output-schema", str(schema_path), "-"])
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=dict(os.environ),
        )
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise SystemExit(f"Local derived builder (codex) failed: {stderr or f'exit {result.returncode}'}")
    return (result.stdout or "").strip()


def _call_claude(*, prompt: str, model: str | None, effort: str | None, timeout_seconds: int) -> str:
    cmd = ["claude", "-p", "--output-format", "text", "--json-schema", json.dumps(LOCAL_DERIVE_SCHEMA, ensure_ascii=False), "--tools", ""]
    if model:
        cmd.extend(["--model", model])
    if effort:
        cmd.extend(["--effort", effort])
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        env=env,
    )
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise SystemExit(f"Local derived builder (claude) failed: {stderr or f'exit {result.returncode}'}")
    return (result.stdout or "").strip()


def resolve_local_derive_runner(runner: str) -> str:
    chosen = str(runner or "auto").strip() or "auto"
    if chosen not in RUNNER_CHOICES:
        raise SystemExit(f"Invalid local derive runner: {chosen!r}")
    if chosen != "auto":
        if shutil.which(chosen) is None:
            raise SystemExit(f"Local derive runner not found in PATH: {chosen}")
        return chosen
    if shutil.which("codex"):
        return "codex"
    if shutil.which("claude"):
        return "claude"
    raise SystemExit("No local derive runner found in PATH. Expected one of: codex, claude.")


def derive_locally(
    *,
    prompt: str,
    topic_name: str | None = None,
    runner: str = "auto",
    model: str | None = None,
    effort: str | None = None,
    timeout_seconds: int = 180,
) -> LocalDeriveResult:
    defaults = _local_derive_defaults()
    normalized_prompt = str(prompt or "").strip()
    if not normalized_prompt:
        raise SystemExit("Local derived builder requires a non-empty prompt.")

    chosen_runner = resolve_local_derive_runner(str(runner or defaults["runner"]))
    runner_prompt = build_local_derive_prompt(prompt=normalized_prompt, topic_name=topic_name)
    if chosen_runner == "codex":
        raw_output = _call_codex(
            prompt=runner_prompt,
            model=model,
            effort=effort,
            timeout_seconds=int(timeout_seconds or defaults["timeout"]),
        )
    else:
        raw_output = _call_claude(
            prompt=runner_prompt,
            model=model,
            effort=effort,
            timeout_seconds=int(timeout_seconds or defaults["timeout"]),
        )
    parsed = _extract_first_json_object(raw_output)
    derived_query, derived_plan = build_topic_derived_plan(prompt=normalized_prompt, payload=parsed)
    return LocalDeriveResult(
        runner=chosen_runner,
        derived_query=derived_query,
        derived_plan=derived_plan,
        raw_output=raw_output,
    )
