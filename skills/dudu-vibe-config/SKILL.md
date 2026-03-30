---
name: dudu-vibe-config
description: dudu 氛围配置“桥梁”Skill：通过 Vibe Agent API（/vibe/agent/*）在受限范围内管理模板/订阅/报道/域名规则，适用于 Claude Code/Codex 远程优化配置。
metadata:
  author: Bensz Conan
  short-description: dudu 氛围配置远程桥梁（Vibe Agent API）
  keywords:
    - dudu-vibe-config
    - dudu
    - vibe
    - 氛围配置
    - 远程配置
    - templates
    - subscriptions
    - domains
    - reports
  category: 运维支持
  platform: Claude Code | OpenAI Codex | Cursor | ChatGPT
---

# dudu-vibe-config（桥梁 Skill）

## 与 bensz-collect-bugs 的协作约定

- 设计缺陷先用 `bensz-collect-bugs` 记录到 `~/.bensz-skills/bugs/`，不要直接改用户本地已安装的 skill。
- 若存在 workaround：先记 bug，再继续完成任务。
- 只有用户明确要求公开上报时，才用 `gh` 上传新增 bug；不要 pull / clone 整个 bug 仓库。

## 目标

把“人类的配置意图”翻译成对 `dudu` `Vibe Agent API` 的受限操作，仅覆盖：
- 模板：创建 / 删除
- 订阅：创建 / 更新 / 解析 prompt / 删除
- 报道：生成 / 删除
- 域名规则：读取 / 更新

## 当前对齐状态（2026-03-26 审计）

- 当前 `/vibe/agent/*` 已覆盖模板 `add/delete`、订阅 `create/update/parse-prompt/delete`、报道 `generate/delete`、域名规则 `get/set`。
- `templates add` 已对齐 `sourceType=search|rss_opml` 与可选 `opml`。
- 默认 derived 路径是“AI 宿主型本地生成”：先在当前对话里生成 `derivedQuery / derivedPlan`，再显式写回 dudu。
- 可选“脚本自驱型本地生成”：用 `python3 scripts/local_derive.py ...` 预览，或在 `subscriptions create/update` 里加 `--local-derived-script`，先调用本地 `codex` / `claude` CLI 生成，再写回 dudu。
- `subscriptions create/update` 支持 `derivedQuery` / `derivedPlan`；需要服务端重算时，用 `subscriptions parse-prompt` 或更新时的 `--refresh-derived/--no-refresh-derived`。
- `subscriptions update` 只接受 `name/prompt/frequency/ai/derivedQuery/derivedPlan/refreshDerived`；旧字段 `groupId`、`generationAi`、`tier`、`style` 会在本地直接拒绝。
- 所有写请求默认不自动重试；新增订阅默认 AI 为 `sdk=codex_cli`、`model=""`、`reasoningEffort=medium`，显式参数优先。
- 模板接口不保存 AI 配置，也不支持模板级 `derived_*`；模板场景最多只能先本地优化 query/prompt，再调用服务端创建。

## 安全边界（强制）

- 只允许调用：`{DUDU_VIBE_URL}/vibe/agent/*`
- 不做越权访问（不调用其它路径；不绕过 KEY/connection 机制）
- 严禁修改 **dudu 软件源代码**（本 skill 仅用于调用受限 API 更新“氛围配置”相关数据）
- 不输出完整 Key；日志中必须脱敏（仅显示前缀）
- 任何 **变更类请求**（POST/PUT/DELETE，除 `heartbeat`/`disconnect` 外）默认使用 `connect → 执行 → disconnect`，并携带 `x-dudu-vibe-connection`
- 若服务端返回 `x-dudu-vibe-terminate: 1` 或 409 `terminate_requested`：立刻停止后续变更操作并 `disconnect`

## 环境变量

- `DUDU_VIBE_URL`：默认 `http://localhost:3001`
- `DUDU_VIBE_KEY`：长度需 ≥ 16
- URL 兼容别名：`dudu_vibe_url`、`dudu_base_url`
- KEY 兼容别名：`dudu_vibe_key`、`dudu_vibe_api`

## 标准工作流（推荐）

1. 环境检查

```bash
python3 scripts/env_check.py
```

2. 连通性闭环

```bash
python3 scripts/client.py ping
python3 scripts/client.py doctor
```

3. 先决定 derived 路径，再做变更
- 域名规则：先 `domains get`，再 `domains set`；默认安全合并，只有“完全替换”才用 `--reset`
- 订阅 prompt / `derived_*`：默认先本地产生 `derivedQuery / derivedPlan` 再显式写回；只有用户明确要求服务端重算，或本地生成不可用时，才用 `subscriptions parse-prompt`
- 宿主 AI 想把本地生成下沉到脚本时，用 `python3 scripts/local_derive.py ...` 或 `subscriptions create/update --local-derived-script`
- 模板 / 报道按需执行；所有写操作默认自动 `connect → disconnect`

4. 不确定时先 `--dry-run`；纯本地预览不要求预先配置 key

```bash
python3 scripts/client.py --dry-run domains set --reset --allowlist example.com
```

## 常见任务映射（意图 → 命令）

- 白名单 / 黑名单 / 关键词：`domains set --allowlist ...`、`--blocklist ...`、`--keywords ...`
- 新增订阅：`subscriptions create --frequency daily`
- 本地生成后写回：`subscriptions update --topic-id ... --prompt ... --derived-query ... --derived-plan-file ...`
- 命令行本地生成并写回：`subscriptions update --topic-id ... --prompt ... --local-derived-script`
- 让服务端重算 derived：`subscriptions parse-prompt --topic-id ...`
- 切到 `codex_cli` 高推理：`subscriptions update --topic-id ... --sdk codex_cli --reasoning-effort high --local-derived-script`
- 创建 RSS 模板：`templates add --source-type rss_opml --opml '<opml ...>' ...`
- 触发报道生成：`reports generate --topic-id ...`
- 临时覆盖本次生成 AI：`reports generate --topic-id ... --sdk codex_cli --reasoning-effort high`

## 订阅更新兼容策略

- `subscriptions update` 现在直接对齐 `PATCH /vibe/agent/subscriptions/:topicId`
- 客户端会优先尝试 `PATCH /vibe/agent/subscriptions/:topicId`，再回退尝试 `PUT /vibe/agent/subscriptions/:topicId`
- 若当前 dudu 服务未暴露该能力，客户端会输出结构化 `unsupported_server_capability`
- 若用户传入当前 Vibe 契约不支持的旧字段（`groupId` / `generationAi` / `tier` / `style`），客户端会在本地直接给出结构化拒绝
- **不会** 自动走“删除旧订阅 + 新建订阅”的危险兜底，因为那会改变 topic id，并可能丢失历史报道/进度/引用关系

## 订阅提示词策略

`--prompt` 不必写成自然语言。默认搜索后端是 `SearXNG`，它会把查询串原样透传给后端引擎；自身只原生处理 `!engine` 和 `:lang`。建议：
- 优先写关键词组合而不是描述性句子
- 用 `"phrase"` 锁定短语，用 `-term` 排除噪音
- `OR` 和简单括号可用，但避免复杂嵌套，减少后端差异
- 需要稳定复现时，优先把结果沉淀到 `--derived-query` / `--derived-plan-file`

例：

```bash
python3 scripts/client.py subscriptions create \
  --name "AI 安全周报" \
  --prompt '"AI safety" OR "AI alignment" OR "model safety" paper OR research OR incident -marketing' \
  --frequency weekly
```

## 失败处理（必须执行）

- 400：参数或请求体不符合服务端校验规则；也包括写请求缺失 `x-dudu-vibe-connection` → 原样输出 JSON 错误并停止
- 401：可能是 Key/URL 错误、Key 被吊销，或 `x-dudu-vibe-connection` 无效/失效 → 停止并检查 Key/连接状态
- 404：资源不存在，或当前服务端确实没有对应路由 → 原样输出并停止
- 409 terminate_requested：用户已在 Web 端终止连接 → 立刻停止并断开
- 202：请求已入队（主要出现在 `reports generate`）→ 视为成功
- 5xx / 超时：GET 类请求最多重试 2 次；写请求不自动重试，避免重复写入
- 非 HTTP 网络失败：输出结构化 `transport_error` JSON，不输出 Python traceback

## 输出约定（用于工具调用）

- `scripts/client.py` 的 `doctor` 与 `doctor --watch-seconds` 仅输出 JSON（便于工具稳定解析）
- 遇到终止请求（`terminate_requested`）时：输出 `{"terminate_requested": true, ...}` 并以退出码 `0` 结束（视为用户主动终止）
