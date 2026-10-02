"""User-scoped, explicitly enabled local reads; subscription writes stay in client.py."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import uuid
from typing import Any
from urllib.parse import urlparse

AI_FIELDS = {"sdk", "model", "reasoningEffort", "thinkingMode"}


class SubscriptionError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class LocalSubscriptionReader:
    def __init__(self, vibe: Any, *, container: str, database: str, user: str, timeout: int):
        if urlparse(vibe.url).hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise SubscriptionError("local_database_requires_local_url", "本机数据库查询仅用于回环地址上的 dudu，不能与远程 URL 混用。")
        for value in (container, database, user):
            if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", value):
                raise SubscriptionError("invalid_database_option", "容器、数据库及用户名只能包含字母、数字、下划线、点和连字符。")
        if len(vibe.key) < 16:
            raise SubscriptionError("missing_vibe_key", "本机只读查询也需要有效 Vibe Key，以限定用户范围。")
        if timeout <= 0:
            raise SubscriptionError("invalid_timeout", "查询超时必须大于零。")
        self.key_hash = hashlib.sha256(vibe.key.encode()).hexdigest()
        self.command = ["docker", "exec", "-i", container, "psql", "-X", "-qAt", "-U", user, "-d", database, "-v", "ON_ERROR_STOP=1"]
        self.timeout = timeout

    def read(self, *, topic_ids: list[str] | None = None, include_content: bool = False) -> list[dict[str, Any]]:
        # Only a computed SHA-256 hex value and a validated integer are interpolated.
        # SQL is fixed, writes are forbidden by the database transaction itself.
        content = ', t.prompt, t.derived_query AS "derivedQuery", t.derived_plan AS "derivedPlan"' if include_content else ''
        topic_filter = ''
        if topic_ids is not None:
            try:
                safe_ids = [str(uuid.UUID(value)) for value in topic_ids]
            except (ValueError, TypeError, AttributeError):
                raise SubscriptionError("invalid_topic_id", "订阅 ID 必须为 UUID。") from None
            topic_filter = " AND t.id IN (" + ','.join("'" + value + "'" for value in safe_ids) + ")" if safe_ids else " AND false"
        sql = f"""BEGIN READ ONLY;
SET LOCAL statement_timeout = '{self.timeout * 1000}ms';
WITH owner AS (
  SELECT k.user_id FROM vibe_api_keys k JOIN users u ON u.id = k.user_id
  WHERE k.key_hash = '{self.key_hash}' AND k.revoked_at IS NULL AND u.status = 'active'
), subscriptions AS (
  SELECT t.id AS "topicId", t.name, t.frequency, t.ai_config AS ai,
         s.generation_ai_config AS "generationAi", t.source_type AS "sourceType",
         s.preferred_tier AS tier, s.preferred_style AS style,
         s.group_id AS "groupId", s.search_mode AS "searchMode",
         md5(jsonb_build_array(t.prompt,t.derived_query,t.derived_at,t.derived_prompt_hash,t.derived_plan)::text) AS "preservedDigest"{content}
  FROM topic_subscriptions s JOIN topics t ON t.id = s.topic_id
  WHERE s.user_id IN (SELECT user_id FROM owner){topic_filter} ORDER BY t.id
)
SELECT json_build_object('ownerCount',(SELECT count(*) FROM owner),
  'subscriptions',COALESCE((SELECT json_agg(subscriptions) FROM subscriptions),'[]'::json));
ROLLBACK;
"""
        try:
            result = subprocess.run(self.command, input=sql, text=True, capture_output=True, timeout=self.timeout + 5)
        except (OSError, subprocess.TimeoutExpired):
            raise SubscriptionError("local_database_read_failed", "无法执行本机只读查询；请检查 Docker、数据库容器和超时配置。") from None
        # Never echo psql stderr: it may contain the SQL and key hash.
        if result.returncode:
            raise SubscriptionError("local_database_read_failed", "本机只读查询失败；请检查数据库名称、用户权限和上游表结构。")
        try:
            data = json.loads(result.stdout)
            if data["ownerCount"] != 1:
                raise SubscriptionError("invalid_vibe_key_owner", "未找到唯一的有效 Vibe Key 用户；停止查询和更新。")
            rows = data["subscriptions"]
            if not isinstance(rows, list) or any(not isinstance(row, dict) or not row.get("topicId") for row in rows):
                raise ValueError()
            return rows
        except (ValueError, KeyError, TypeError):
            raise SubscriptionError("invalid_database_response", "本机查询结果格式不符合当前订阅契约。") from None


def merge_ai(current: dict[str, Any] | None, override: dict[str, Any], *, replace: bool) -> dict[str, Any]:
    if replace:
        if not override.get("sdk") or "model" not in override:
            raise SubscriptionError("replacement_ai_requires_sdk_and_model", "--replace-ai 必须显式提供 --sdk 和 --model；未指定的 AI 字段使用服务端默认值。")
        return dict(override)
    if not isinstance(current, dict) or not current.get("sdk"):
        raise SubscriptionError("current_ai_unavailable", "无法保留当前 AI 配置；请启用已获授权的 --local-db-readonly，或用 --replace-ai 显式替换配置。")
    if override.get("sdk", current["sdk"]) != current["sdk"]:
        if "model" not in override:
            raise SubscriptionError("sdk_change_requires_model", "切换 SDK 时必须指定 --model（可为空），避免沿用不兼容的旧模型。")
        # A different provider gets its own defaults rather than the old provider's thinking settings.
        return dict(override)
    return {**{key: value for key, value in current.items() if key in AI_FIELDS}, **override}


def public_subscription(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key != "preservedDigest"}


def verify_update(before: dict[str, Any], after: dict[str, Any] | None, payload: dict[str, Any], response: dict[str, Any] | None = None) -> bool:
    if after is None:
        return False
    for field in ("name", "frequency"):
        if after.get(field) != payload.get(field, before.get(field)):
            return False
    for field in ("tier", "style", "groupId", "searchMode", "sourceType"):
        if after.get(field) != before.get(field):
            return False
    if "prompt" in payload and after.get("prompt") != payload["prompt"]:
        return False
    if "derivedQuery" in payload or "derivedPlan" in payload:
        # Upstream rebuilds/normalizes the supplied plan, including version/hash.
        # Verify its canonical return value and stored consistency, not raw JSON equality.
        canonical_query = (response or {}).get("derivedQuery")
        plan = after.get("derivedPlan")
        if (response or {}).get("derivedRefreshStatus") != "updated" or not canonical_query:
            return False
        if after.get("derivedQuery") != canonical_query or not isinstance(plan, dict) or plan.get("derivedQuery") != canonical_query:
            return False
        if not isinstance(after.get("prompt"), str) or plan.get("promptHash") != hashlib.sha256(after["prompt"].encode()).hexdigest():
            return False
    if "ai" in payload:
        for key, value in payload["ai"].items():
            if any((after.get(field) or {}).get(key) != value for field in ("ai", "generationAi")):
                return False
    elif any(after.get(field) != before.get(field) for field in ("ai", "generationAi")):
        return False
    if not any(key in payload for key in ("prompt", "derivedQuery", "derivedPlan")) and payload.get("refreshDerived") is not True:
        if after.get("preservedDigest") != before.get("preservedDigest"):
            return False
    return True
