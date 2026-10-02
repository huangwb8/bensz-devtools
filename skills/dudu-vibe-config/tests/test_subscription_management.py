from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import client
import _subscriptions
from _subscriptions import LocalSubscriptionReader, SubscriptionError
from _vibe_env import VibeEnv

FIRST = "11111111-1111-4111-8111-111111111111"
SECOND = "22222222-2222-4222-8222-222222222222"
VIBE = VibeEnv(url="http://localhost:3001", key="test_key_long_enough_123456", url_source=None, key_source=None)


def subscription(topic_id=FIRST):
    return {"topicId": topic_id, "name": "示例订阅", "frequency": "daily",
            "ai": {"sdk": "codex_cli", "model": "old-model", "reasoningEffort": "medium", "thinkingMode": "off"},
            "generationAi": {"sdk": "claude_code", "model": "old-generation"},
            "sourceType": "search", "tier": "standard", "style": "deep_research", "groupId": None,
            "searchMode": "searxng", "preservedDigest": "unchanged"}


class MemoryReader:
    def __init__(self):
        self.rows = [subscription(FIRST), subscription(SECOND)]

    def read(self, **kwargs):
        rows = copy.deepcopy(self.rows)
        if kwargs.get("topic_ids") is not None:
            rows = [row for row in rows if row["topicId"] in kwargs["topic_ids"]]
        return rows


class SubscriptionManagementTests(unittest.TestCase):
    def setUp(self):
        self.reader = MemoryReader()
        self.calls = []
        self.fail_topic = None
        self.failure_status = 500
        self.mismatch = False
        self.terminate = False
        self.timeout = False

    def http(self, method, url, *, headers, json_body=None, timeout_seconds, retries):
        self.calls.append((method, url, copy.deepcopy(json_body), dict(headers), retries))
        if url.endswith("/connect"):
            data, status = {"connectionId": "33333333-3333-4333-8333-333333333333"}, 200
        elif url.endswith("/disconnect"):
            data, status = {"ok": True}, 200
        elif url.endswith("/reports/generate"):
            data, status = {"attemptId": FIRST, "queued": True}, 202
        elif url.endswith("/parse-prompt"):
            topic_id = url.rsplit("/", 2)[-2]
            row = next(row for row in self.reader.rows if row["topicId"] == topic_id)
            if "ai" in json_body:
                row["ai"] = copy.deepcopy(json_body["ai"])
                row["generationAi"] = copy.deepcopy(json_body["ai"])
            data, status = {"success": True, "derivedRefreshStatus": "updated"}, 200
        else:
            topic_id = url.rsplit("/", 1)[-1]
            if topic_id == self.fail_topic:
                if self.timeout:
                    raise RuntimeError("timed out")
                if self.terminate:
                    return client.HttpResult(409, {"x-dudu-vibe-terminate": "1"}, "", {"error": "terminate_requested"})
                return client.HttpResult(self.failure_status, {}, "", {"error": "test failure"})
            row = next(row for row in self.reader.rows if row["topicId"] == topic_id)
            if "ai" in json_body:
                row["ai"] = copy.deepcopy(json_body["ai"])
                row["generationAi"] = copy.deepcopy(json_body["ai"])
            for field in ("name", "frequency", "prompt", "derivedQuery", "derivedPlan"):
                if field in json_body:
                    row[field] = copy.deepcopy(json_body[field])
            if self.mismatch:
                row["generationAi"] = {"model": "wrong-model"}
            data, status = {"success": True, "topicId": topic_id, "derivedRefreshStatus": "skipped"}, 200
        return client.HttpResult(status, {}, "", data)

    def run_cli(self, arguments):
        output = io.StringIO()
        with patch.object(client, "resolve_vibe_env", return_value=VIBE), patch.object(client, "request_json", side_effect=self.http), patch.object(client, "LocalSubscriptionReader", return_value=self.reader), contextlib.redirect_stdout(output):
            code = client.main(arguments)
        # Dry-run prints a stream of requests and a final aggregate.
        decoder, objects, raw, position = json.JSONDecoder(), [], output.getvalue(), 0
        while raw[position:].strip():
            position += len(raw[position:]) - len(raw[position:].lstrip())
            item, position = decoder.raw_decode(raw, position)
            objects.append(item)
        return code, objects

    def patches(self):
        return [call for call in self.calls if call[0] == "PATCH"]

    def test_missing_list_capability_never_reads_database_or_network(self):
        with patch.object(_subscriptions.subprocess, "run") as run:
            code, objects = self.run_cli(["subscriptions", "list"])
        self.assertEqual(code, 2)
        self.assertEqual(objects[-1]["error"], "unsupported_server_capability")
        run.assert_not_called()
        self.assertEqual(self.calls, [])

    def test_list_and_show_hide_internal_digest(self):
        code, objects = self.run_cli(["subscriptions", "list", "--local-db-readonly"])
        self.assertEqual(code, 0)
        self.assertEqual(objects[-1]["count"], 2)
        self.assertNotIn("preservedDigest", objects[-1]["subscriptions"][0])
        code, objects = self.run_cli(["subscriptions", "show", "--topic-id", SECOND, "--local-db-readonly"])
        self.assertEqual(objects[-1]["subscription"]["topicId"], SECOND)
        self.assertEqual(self.calls, [])

    def test_ai_partial_update_preserves_sdk_model_and_thinking(self):
        code, objects = self.run_cli(["subscriptions", "update", "--topic-id", FIRST, "--reasoning-effort", "high", "--local-db-readonly"])
        self.assertEqual(code, 0)
        self.assertTrue(objects[-1]["verified"])
        body = self.patches()[0][2]
        self.assertEqual(body["ai"], {"sdk": "codex_cli", "model": "old-model", "reasoningEffort": "high", "thinkingMode": "off"})
        self.assertFalse(body["refreshDerived"])
        self.assertNotIn("prompt", body)
        self.assertEqual(self.calls[-1][1].rsplit("/", 1)[-1], "disconnect")

    def test_partial_ai_without_reader_fails_before_connect(self):
        code, objects = self.run_cli(["subscriptions", "update", "--topic-id", FIRST, "--model", "new-model"])
        self.assertEqual(code, 2)
        self.assertEqual(objects[-1]["error"], "current_ai_unavailable")
        self.assertEqual(self.calls, [])

    def test_remote_explicit_replacement_is_supported_without_claiming_verification(self):
        code, objects = self.run_cli(["subscriptions", "update", "--topic-id", FIRST, "--replace-ai", "--sdk", "codex_cli", "--model", "gpt-6-luna", "--reasoning-effort", "high"])
        self.assertEqual(code, 0)
        self.assertFalse(objects[-1]["verified"])
        self.assertEqual(objects[-1]["status"], 200)
        self.assertEqual(self.patches()[0][2]["ai"]["model"], "gpt-6-luna")

    def test_replacement_requires_sdk_and_model(self):
        code, objects = self.run_cli(["subscriptions", "update", "--topic-id", FIRST, "--replace-ai", "--model", "new-model"])
        self.assertEqual(code, 2)
        self.assertEqual(self.calls, [])

    def test_name_and_frequency_update_does_not_require_ai_read(self):
        code, objects = self.run_cli(["subscriptions", "update", "--topic-id", FIRST, "--name", "新名字", "--frequency", "weekly"])
        self.assertEqual(code, 0)
        self.assertEqual(self.patches()[0][2], {"name": "新名字", "frequency": "weekly"})

    def test_batch_all_merges_and_verifies_each_subscription(self):
        code, objects = self.run_cli(["subscriptions", "update-many", "--all", "--model", "gpt-6-luna", "--reasoning-effort", "high", "--local-db-readonly"])
        self.assertEqual(code, 0)
        self.assertEqual(objects[-1]["updated_count"], 2)
        self.assertTrue(objects[-1]["verified"])
        self.assertEqual(sum(url.endswith("/connect") for _, url, *_ in self.calls), 1)
        self.assertTrue(all(call[4] == 0 for call in self.calls))
        self.assertTrue(all(row["ai"] == row["generationAi"] for row in self.reader.rows))

    def test_batch_deduplicates_targets(self):
        code, objects = self.run_cli(["subscriptions", "update-many", "--topic-id", FIRST, "--topic-id", FIRST, "--model", "new", "--local-db-readonly"])
        self.assertEqual(code, 0)
        self.assertEqual(len(self.patches()), 1)

    def test_batch_frequency_update_verifies_and_preserves_ai(self):
        initial = copy.deepcopy(self.reader.rows)
        code, objects = self.run_cli(["subscriptions", "update-many", "--all", "--frequency", "weekly", "--local-db-readonly"])
        self.assertEqual(code, 0)
        self.assertTrue(objects[-1]["verified"])
        for before, after in zip(initial, self.reader.rows):
            self.assertEqual(after["frequency"], "weekly")
            self.assertEqual(after["ai"], before["ai"])
            self.assertEqual(after["generationAi"], before["generationAi"])

    def test_second_invalid_ai_fails_entire_batch_before_connect(self):
        self.reader.rows[1]["ai"] = None
        code, objects = self.run_cli(["subscriptions", "update-many", "--all", "--model", "new", "--local-db-readonly"])
        self.assertEqual(code, 2)
        self.assertEqual(self.calls, [])

    def test_explicit_refresh_overrides_ai_only_default(self):
        code, objects = self.run_cli(["subscriptions", "update", "--topic-id", FIRST, "--model", "new", "--refresh-derived", "--local-db-readonly"])
        self.assertEqual(code, 0)
        self.assertTrue(self.patches()[0][2]["refreshDerived"])

    def test_parse_prompt_ai_is_merged_or_requires_explicit_replacement(self):
        code, objects = self.run_cli(["subscriptions", "parse-prompt", "--topic-id", FIRST, "--reasoning-effort", "high", "--local-db-readonly"])
        self.assertEqual(code, 0)
        self.assertEqual(self.reader.rows[0]["ai"]["model"], "old-model")
        self.assertEqual(self.reader.rows[0]["ai"]["sdk"], "codex_cli")
        self.calls.clear()
        code, objects = self.run_cli(["subscriptions", "parse-prompt", "--topic-id", FIRST, "--reasoning-effort", "high"])
        self.assertEqual(code, 2)
        self.assertEqual(self.calls, [])

    def test_canonical_derived_plan_is_verified_after_server_normalization(self):
        before = subscription()
        after = copy.deepcopy(before)
        after.update(prompt="prompt", derivedQuery="canonical query", derivedPlan={"version": "topic-search-plan-v2", "derivedQuery": "canonical query", "promptHash": hashlib.sha256(b"prompt").hexdigest()})
        payload = {"derivedPlan": {"version": "old-version", "derivedQuery": "canonical query"}}
        response = {"derivedRefreshStatus": "updated", "derivedQuery": "canonical query"}
        self.assertTrue(_subscriptions.verify_update(before, after, payload, response))
        after["derivedPlan"]["promptHash"] = "stale-hash"
        self.assertFalse(_subscriptions.verify_update(before, after, payload, response))

    def test_preflight_unknown_owner_and_sdk_change_fail_without_writes(self):
        unknown = "44444444-4444-4444-8444-444444444444"
        for arguments, error in [
            (["--topic-id", FIRST, "--topic-id", unknown, "--model", "new"], "subscription_not_found"),
            (["--all", "--sdk", "claude_code"], "sdk_change_requires_model"),
        ]:
            code, objects = self.run_cli(["subscriptions", "update-many", *arguments, "--local-db-readonly"])
            self.assertEqual(code, 2)
            self.assertEqual(objects[-1]["error"], error)
            self.assertEqual(self.calls, [])

    def test_batch_stops_on_first_http_failure_and_reports_completed(self):
        self.fail_topic = SECOND
        code, objects = self.run_cli(["subscriptions", "update-many", "--all", "--model", "new", "--local-db-readonly"])
        self.assertEqual(code, 1)
        self.assertEqual(objects[-1]["updated_count"], 1)
        self.assertEqual(objects[-1]["failed_topic_id"], SECOND)
        self.assertEqual(len(self.patches()), 2)
        self.assertEqual(self.calls[-1][1].rsplit("/", 1)[-1], "disconnect")

    def test_batch_stops_on_verification_mismatch(self):
        self.mismatch = True
        code, objects = self.run_cli(["subscriptions", "update-many", "--all", "--model", "new", "--local-db-readonly"])
        self.assertEqual(code, 1)
        self.assertEqual(objects[-1]["error"], "subscription_verification_failed")
        self.assertEqual(len(self.patches()), 1)
        self.assertFalse(objects[-1]["results"][0]["verified"])

    def test_user_termination_disconnects_and_keeps_partial_receipts(self):
        self.fail_topic, self.terminate = SECOND, True
        code, objects = self.run_cli(["subscriptions", "update-many", "--all", "--model", "new", "--local-db-readonly"])
        self.assertEqual(code, 0)
        self.assertTrue(objects[-1]["terminate_requested"])
        self.assertEqual(objects[-1]["updated_count"], 1)
        self.assertEqual(self.calls[-1][1].rsplit("/", 1)[-1], "disconnect")

    def test_timeout_never_retries_and_returns_completed_count(self):
        self.fail_topic, self.timeout = SECOND, True
        code, objects = self.run_cli(["subscriptions", "update-many", "--all", "--model", "new", "--local-db-readonly"])
        self.assertEqual(code, 1)
        self.assertEqual(objects[-1]["error"], "transport_error")
        self.assertEqual(objects[-1]["updated_count"], 1)
        self.assertEqual(len(self.patches()), 2)

    def test_patch_not_supported_uses_put_once_then_stops(self):
        self.fail_topic, self.failure_status = FIRST, 404
        code, objects = self.run_cli(["subscriptions", "update-many", "--all", "--model", "new", "--local-db-readonly"])
        self.assertEqual(code, 2)
        self.assertEqual([call[0] for call in self.calls], ["POST", "PATCH", "PUT", "POST"])
        self.assertEqual(objects[-1]["updated_count"], 0)

    def test_all_requires_explicit_reader(self):
        code, objects = self.run_cli(["subscriptions", "update-many", "--all", "--model", "new"])
        self.assertEqual(code, 2)
        self.assertEqual(self.calls, [])

    def test_local_and_offline_dry_run_never_issue_http_requests(self):
        code, objects = self.run_cli(["--dry-run", "subscriptions", "update-many", "--all", "--model", "new", "--local-db-readonly"])
        self.assertEqual(code, 0)
        self.assertEqual(objects[-1]["updated_count"], 0)
        self.assertEqual(objects[-1]["target_count"], 2)
        self.assertFalse(objects[-1]["verified"])
        self.assertEqual(self.calls, [])
        code, objects = self.run_cli(["--dry-run", "subscriptions", "update", "--topic-id", FIRST, "--model", "new"])
        self.assertTrue(objects[-1]["unresolved_ai_fields"])
        self.assertEqual(self.calls, [])

    def test_idempotency_header_and_current_ai_choices(self):
        code, objects = self.run_cli(["reports", "generate", "--topic-id", FIRST, "--sdk", "kimi", "--reasoning-effort", "max", "--idempotency-key", "report-request-123"])
        self.assertEqual(code, 0)
        request = next(call for call in self.calls if call[1].endswith("/reports/generate"))
        self.assertEqual(request[3]["idempotency-key"], "report-request-123")
        self.assertEqual(request[2]["ai"], {"sdk": "kimi", "reasoningEffort": "max"})
        self.assertEqual(request[4], 0)


class LocalDatabaseTests(unittest.TestCase):
    def reader(self, vibe=VIBE):
        return LocalSubscriptionReader(vibe, container="dudu-postgres", database="dudu", user="dudu", timeout=15)

    def test_fixed_sql_is_read_only_scoped_and_never_passes_raw_key(self):
        result = SimpleNamespace(returncode=0, stdout=json.dumps({"ownerCount": 1, "subscriptions": [subscription()]}))
        with patch.object(_subscriptions.subprocess, "run", return_value=result) as run:
            rows = self.reader().read()
        command, sql = run.call_args.args[0], run.call_args.kwargs["input"]
        self.assertEqual(rows[0]["topicId"], FIRST)
        self.assertIn("BEGIN READ ONLY;", sql)
        self.assertIn("ROLLBACK;", sql)
        self.assertIn("s.user_id IN (SELECT user_id FROM owner)", sql)
        self.assertIn("k.revoked_at IS NULL AND u.status = 'active'", sql)
        self.assertIn(hashlib.sha256(VIBE.key.encode()).hexdigest(), sql)
        self.assertNotIn(VIBE.key, sql)
        self.assertNotIn(VIBE.key, " ".join(command))
        self.assertNotIn('t.prompt, t.derived_query AS', sql)

    def test_remote_url_and_option_injection_rejected_before_query(self):
        remote = VibeEnv(url="https://remote.example", key=VIBE.key, url_source=None, key_source=None)
        with self.assertRaises(SubscriptionError):
            self.reader(remote)
        with self.assertRaises(SubscriptionError):
            LocalSubscriptionReader(VIBE, container="--privileged", database="dudu", user="dudu", timeout=15)

    def test_invalid_owner_stops_without_returning_other_user_data(self):
        for count in (0, 2):
            result = SimpleNamespace(returncode=0, stdout=json.dumps({"ownerCount": count, "subscriptions": [subscription()]}))
            with patch.object(_subscriptions.subprocess, "run", return_value=result), self.assertRaises(SubscriptionError) as error:
                self.reader().read()
            self.assertEqual(error.exception.code, "invalid_vibe_key_owner")

    def test_single_target_read_filters_sql_and_rejects_invalid_ids(self):
        result = SimpleNamespace(returncode=0, stdout=json.dumps({"ownerCount": 1, "subscriptions": [subscription()]}))
        with patch.object(_subscriptions.subprocess, "run", return_value=result) as run:
            self.reader().read(topic_ids=[FIRST], include_content=True)
        sql = run.call_args.kwargs["input"]
        self.assertIn("AND t.id IN ('" + FIRST + "')", sql)
        self.assertIn('t.prompt, t.derived_query AS', sql)
        with patch.object(_subscriptions.subprocess, "run") as run, self.assertRaises(SubscriptionError):
            self.reader().read(topic_ids=["';DROP TABLE topics;--"])
        run.assert_not_called()

    def test_subprocess_failure_and_timeout_do_not_echo_stderr_or_sql(self):
        result = SimpleNamespace(returncode=1, stderr="SECRET-SQL", stdout="")
        with patch.object(_subscriptions.subprocess, "run", return_value=result), self.assertRaises(SubscriptionError) as error:
            self.reader().read()
        self.assertNotIn("SECRET-SQL", str(error.exception))
        with patch.object(_subscriptions.subprocess, "run", side_effect=subprocess.TimeoutExpired("SECRET-SQL", 15)), self.assertRaises(SubscriptionError) as error:
            self.reader().read()
        self.assertNotIn("SECRET-SQL", str(error.exception))


if __name__ == "__main__":
    unittest.main()
