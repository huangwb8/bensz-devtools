from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import client  # noqa: E402


class SubscriptionCreateDefaultsTest(unittest.TestCase):
    def test_create_payload_defaults_to_codex_cli_gpt_5_4_medium(self) -> None:
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
        )

        self.assertEqual(
            payload["ai"],
            {
                "sdk": "codex_cli",
                "model": "gpt-5.4",
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
        )

        self.assertEqual(payload["ai"], {"sdk": "claude_code"})


if __name__ == "__main__":
    unittest.main()
