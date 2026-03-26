from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import client  # noqa: E402
from _vibe_env import VibeEnv, resolve_vibe_env  # noqa: E402


def _parse_json_stream(raw: str) -> list[dict]:
    decoder = json.JSONDecoder()
    idx = 0
    payloads: list[dict] = []
    text = raw.strip()
    while idx < len(text):
        while idx < len(text) and text[idx].isspace():
            idx += 1
        if idx >= len(text):
            break
        obj, next_idx = decoder.raw_decode(text, idx)
        payloads.append(obj)
        idx = next_idx
    return payloads


class SubscriptionCreateDefaultsTest(unittest.TestCase):
    def test_create_payload_defaults_to_codex_cli_cli_default_model_medium(self) -> None:
        payload = client._build_subscription_create_payload(
            name="开发工具追踪",
            prompt="跟踪 Codex CLI 更新",
            frequency="daily",
            tier=None,
            style=None,
            sdk=None,
            model=None,
            reasoning_effort=None,
            thinking_mode=None,
            derived_query=None,
            derived_plan=None,
        )

        self.assertEqual(
            payload["ai"],
            {
                "sdk": "codex_cli",
                "model": "",
                "reasoningEffort": "medium",
            },
        )

    def test_create_payload_keeps_explicit_model_override(self) -> None:
        payload = client._build_subscription_create_payload(
            name="开发工具追踪",
            prompt="跟踪 Codex CLI 更新",
            frequency="daily",
            tier=None,
            style=None,
            sdk="codex_cli",
            model="gpt-5.5-preview",
            reasoning_effort=None,
            thinking_mode=None,
            derived_query=None,
            derived_plan=None,
        )

        self.assertEqual(payload["ai"]["sdk"], "codex_cli")
        self.assertEqual(payload["ai"]["model"], "gpt-5.5-preview")
        self.assertEqual(payload["ai"]["reasoningEffort"], "medium")

    def test_create_payload_preserves_explicit_empty_model_for_cli_default(self) -> None:
        payload = client._build_subscription_create_payload(
            name="开发工具追踪",
            prompt="跟踪 Codex CLI 更新",
            frequency="daily",
            tier=None,
            style=None,
            sdk="codex_cli",
            model="",
            reasoning_effort=None,
            thinking_mode=None,
            derived_query=None,
            derived_plan=None,
        )

        self.assertEqual(
            payload["ai"],
            {
                "sdk": "codex_cli",
                "model": "",
                "reasoningEffort": "medium",
            },
        )

    def test_create_payload_does_not_force_codex_cli_defaults_on_other_sdk(self) -> None:
        payload = client._build_subscription_create_payload(
            name="开发工具追踪",
            prompt="跟踪 Claude Code 更新",
            frequency="daily",
            tier=None,
            style=None,
            sdk="claude_code",
            model=None,
            reasoning_effort=None,
            thinking_mode=None,
            derived_query=None,
            derived_plan=None,
        )

        self.assertEqual(payload["ai"], {"sdk": "claude_code"})

    def test_create_payload_supports_manual_derived_query_and_plan(self) -> None:
        payload = client._build_subscription_create_payload(
            name="AI 搜索",
            prompt='"agentic coding" OR codex',
            frequency="daily",
            tier="premium",
            style="deep_research",
            sdk="codex_cli",
            model="",
            reasoning_effort="high",
            thinking_mode=None,
            derived_query='"agentic coding" OR codex OR "claude code"',
            derived_plan={
                "source": "ai",
                "version": "2026-03-25",
                "promptHash": "abc123",
                "derivedQuery": '"agentic coding" OR codex',
                "booleanLines": ['"agentic coding" OR codex'],
                "queryVariants": {
                    "default": '"agentic coding" OR codex',
                    "display": '"agentic coding" OR codex',
                    "searxng": '"agentic coding" OR codex docs',
                    "api": '"agentic coding" OR codex'
                },
            },
        )

        self.assertEqual(payload["derivedQuery"], '"agentic coding" OR codex OR "claude code"')
        self.assertIn("derivedPlan", payload)


class CliReliabilityTests(unittest.TestCase):
    def test_dry_run_ping_does_not_require_key(self) -> None:
        vibe = VibeEnv(url="http://localhost:3001", key="", url_source="default", key_source="missing")
        stdout = io.StringIO()
        with patch.object(client, "resolve_vibe_env", return_value=vibe):
            with contextlib.redirect_stdout(stdout):
                code = client.main(["--dry-run", "ping"])

        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["method"], "GET")
        self.assertEqual(payload["url"], "http://localhost:3001/vibe/agent/ping")

    def test_transport_error_is_reported_as_structured_json(self) -> None:
        vibe = VibeEnv(
            url="http://localhost:3001",
            key="test_key_long_enough_123456",
            url_source="default",
            key_source="os_env",
        )
        stdout = io.StringIO()
        with patch.object(client, "resolve_vibe_env", return_value=vibe), patch.object(
            client, "request_json", side_effect=RuntimeError("transport error after 3 attempts: connection refused")
        ):
            with contextlib.redirect_stdout(stdout):
                code = client.main(["ping"])

        self.assertEqual(code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["error"], "transport_error")
        self.assertIn("connection refused", payload["message"])

    def test_local_derived_script_create_injects_generated_query_and_plan(self) -> None:
        vibe = VibeEnv(url="http://localhost:3001", key="", url_source="default", key_source="missing")
        stdout = io.StringIO()
        with patch.object(client, "resolve_vibe_env", return_value=vibe), patch.object(
            client,
            "derive_locally",
            return_value=type(
                "LocalDeriveResultStub",
                (),
                {
                    "derived_query": '"agentic coding"\nCodex CLI',
                    "derived_plan": {
                        "version": "topic-search-plan-v2",
                        "promptTemplateId": "topic_search_plan",
                        "promptHash": "abc123",
                        "source": "ai",
                        "derivedQuery": '"agentic coding"\nCodex CLI',
                        "booleanLines": ['"agentic coding"', "Codex CLI"],
                        "queryVariants": {
                            "default": '("agentic coding") AND (Codex CLI)',
                            "display": '"agentic coding"\nCodex CLI',
                            "searxng": '"agentic coding" Codex CLI',
                            "api": '"agentic coding"\nCodex CLI',
                            "mcp": {
                                "default": '("agentic coding") AND (Codex CLI)',
                                "search_query": '("agentic coding") AND (Codex CLI)',
                                "tavily": '"agentic coding" Codex CLI',
                                "serper": '"agentic coding" Codex CLI',
                                "duckduckgo": '"agentic coding" Codex CLI',
                                "brave": '("agentic coding") AND (Codex CLI)',
                                "searxng": '"agentic coding" Codex CLI',
                            },
                        },
                        "keywords": ["agentic coding"],
                        "coreQuestions": ["What changed?"],
                        "qualityIssues": [],
                    },
                },
            )(),
        ):
            with contextlib.redirect_stdout(stdout):
                code = client.main(
                    [
                        "--dry-run",
                        "subscriptions",
                        "create",
                        "--name",
                        "开发工具追踪",
                        "--prompt",
                        "跟踪 Codex CLI 更新",
                        "--frequency",
                        "daily",
                        "--local-derived-script",
                    ]
                )

        self.assertEqual(code, 0)
        payload = next(
            item
            for item in _parse_json_stream(stdout.getvalue())
            if item.get("url") == "http://localhost:3001/vibe/agent/subscriptions"
        )
        self.assertEqual(payload["json_body"]["derivedQuery"], '"agentic coding"\nCodex CLI')
        self.assertIn("derivedPlan", payload["json_body"])

    def test_local_derived_script_update_requires_prompt(self) -> None:
        vibe = VibeEnv(url="http://localhost:3001", key="", url_source="default", key_source="missing")
        with patch.object(client, "resolve_vibe_env", return_value=vibe):
            with self.assertRaises(SystemExit) as ctx:
                client.main(
                    [
                        "--dry-run",
                        "subscriptions",
                        "update",
                        "--topic-id",
                        "11111111-1111-1111-1111-111111111111",
                        "--local-derived-script",
                    ]
                )

        self.assertIn("requires --prompt", str(ctx.exception))


class EnvCompatibilityTests(unittest.TestCase):
    def test_env_file_supports_dudu_base_url_and_dudu_vibe_api_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("dudu_base_url=localhost:3001\ndudu_vibe_api=test_key_long_enough_123456\n", encoding="utf-8")
            vibe = resolve_vibe_env(
                skill_root=Path(__file__).resolve().parents[1],
                env_file=env_file,
            )

        self.assertEqual(vibe.url, "http://localhost:3001")
        self.assertEqual(vibe.key, "test_key_long_enough_123456")
        self.assertEqual(vibe.url_source.kind, "env_file")
        self.assertEqual(vibe.key_source.kind, "env_file")

    def test_invalid_env_url_scheme_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("DUDU_VIBE_URL=ftp://bad.example\nDUDU_VIBE_KEY=test_key_long_enough_123456\n", encoding="utf-8")
            with self.assertRaises(SystemExit) as ctx:
                resolve_vibe_env(
                    skill_root=Path(__file__).resolve().parents[1],
                    env_file=env_file,
                )

        self.assertIn("Invalid vibe URL scheme", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
