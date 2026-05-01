---
name: dudu-vibe-config
description: dudu 氛围配置“桥梁”Skill：通过 Vibe Agent API（/vibe/agent/*）在受限范围内管理模板/报道风格/订阅/报道/域名规则，适用于 Claude Code/Codex 远程优化配置。
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
    - styles
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
- 报道风格：列出 / 创建 / 更新 / 删除
- 订阅：创建 / 更新 / 解析 prompt / 删除
- 报道：生成 / 删除
- 域名规则：读取 / 更新

## 当前能力边界

- 最近一次基于上游源码的审计时间与变更说明，统一记录在 `CHANGELOG.md` 与 `plans/2026-04-19-vibe-contract-audit-and-hardening.md`；本节只保留当前仍然生效的能力与限制。

- 当前 `/vibe/agent/*` 已覆盖模板 `add/delete`、报道风格 `list/create/update/delete`、订阅 `create/update/parse-prompt/delete`、报道 `generate/delete`、域名规则 `get/set`，以及 `ping/connect/heartbeat/disconnect`。
- `templates add` 已对齐 `sourceType=search|rss_opml` 与可选 `opml`；其中 `search` 模板会由服务端在创建时自动预生成并持久化模板级 `derivedQuery / derivedPlan`，当前 CLI 仍不支持手工传入模板级 `derived_*`。
- 当前 Vibe 模板路由仍要求 `query` 为非空字符串；也就是说即使主站 `templates` API 已允许 `rss_opml` 模板持久化空 query，bridge skill 走 `/vibe/agent/templates` 时仍必须显式提供 `--query`。
- 默认 derived 路径是“AI 宿主型本地生成”：先在当前对话里生成 `derivedQuery / derivedPlan`，再显式写回 dudu。
- 可选“脚本自驱型本地生成”：用 `python3 scripts/local_derive.py ...` 预览，或在 `subscriptions create/update` 里加 `--local-derived-script`，先调用本地 `codex` / `claude` CLI 生成，再写回 dudu。
- `subscriptions create/update` 支持 `derivedQuery` / `derivedPlan`；需要服务端重算时，用 `subscriptions parse-prompt` 或更新时的 `--refresh-derived/--no-refresh-derived`。
- `subscriptions update` 只接受 `name/prompt/frequency/ai/derivedQuery/derivedPlan/refreshDerived`；旧字段 `groupId`、`generationAi`、`tier`、`style` 会在本地直接拒绝。
- dudu 主项目当前已存在订阅级 `search_mode` 等主站字段，但 `/vibe/agent/subscriptions*` 仍未开放这些字段；本 skill 不会假装支持，也不会越权改走 `/topics/*`。
- `subscriptions update` 与 `subscriptions parse-prompt --ai ...` 会由服务端顺带同步 `topic_subscriptions.generation_ai_config`，以保持手动“生成报道”和订阅默认 AI 的口径一致；但 bridge skill 仍不接受显式 `--generation-*`，避免和当前 Vibe 契约漂移。
- `styles list` 当前走的是 `available` 视图：会返回“内置风格 + 当前用户私有风格 + 市场可见风格”；bridge skill 不额外暴露 `mine/market/builtin` 过滤参数。
- `styles create/update` 已可透传 `visibility=private|market` 与 `baseStyle`，可用于私有风格和市场风格发布/继承。
- 删除最后一个订阅时，当前服务端会同时清理 orphan topic 的运行工件、报道工件、notes/system events 等残留；bridge skill 已按这个最新闭环理解返回结果，不再把它当作“仅删一条订阅关系”。
- 所有写请求默认不自动重试；新增订阅默认 AI 为 `sdk=codex_cli`、`model=""`、`reasoningEffort=medium`，显式参数优先。
- 模板接口仍不保存模板级 AI 配置；若需要影响模板预生成的 derived 结果，应先在本地优化 `query/prompt`，再调用服务端创建。

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
- 自动发现优先级：进程环境变量 > 显式 `--env-file` > 当前工作目录 `.env/.env.local/remote.env` > 从 skill 目录向上查找项目级 `remote.env` > fallback 文件

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
- 报道风格：先 `styles list` 看当前“Vibe 可见风格目录”（内置 + 自己的私有 + 市场可见），再按需 `styles create/update/delete`
- 域名规则：先 `domains get`，再 `domains set`；默认安全合并，只有“完全替换”才用 `--reset`
- 订阅 prompt / `derived_*`：默认先本地产生 `derivedQuery / derivedPlan` 再显式写回；只有用户明确要求服务端重算，或本地生成不可用时，才用 `subscriptions parse-prompt`
- 订阅字段边界：当前 Vibe 仍只允许修改 `name/prompt/frequency/ai/derivedQuery/derivedPlan/refreshDerived`；若用户想调 `searchMode`、`groupId`、`generationAi` 等主站字段，应明确告知“当前 bridge skill 不覆盖”
- 宿主 AI 想把本地生成下沉到脚本时，用 `python3 scripts/local_derive.py ...` 或 `subscriptions create/update --local-derived-script`
- 模板 / 报道按需执行；所有写操作默认自动 `connect → disconnect`

4. 不确定时先 `--dry-run`；纯本地预览不要求预先配置 key

```bash
python3 scripts/client.py --dry-run domains set --reset --allowlist example.com
```

## 常见任务映射（意图 → 命令）

- 白名单 / 黑名单 / 关键词：`domains set --allowlist ...`、`--blocklist ...`、`--keywords ...`
- 报道风格：`styles list`、`styles create --payload-file ...`、`styles update --id ... --payload-json ...`、`styles delete --id ...`
- 新增订阅：`subscriptions create --frequency daily`
- 本地生成后写回：`subscriptions update --topic-id ... --prompt ... --derived-query ... --derived-plan-file ...`
- 命令行本地生成并写回：`subscriptions update --topic-id ... --prompt ... --local-derived-script`
- 让服务端重算 derived：`subscriptions parse-prompt --topic-id ...`
- 切到 `codex_cli` 高推理：`subscriptions update --topic-id ... --sdk codex_cli --reasoning-effort high --local-derived-script`
- 创建 RSS 模板：`templates add --query "RSS 导入模板" --source-type rss_opml --opml '<opml ...>' ...`
- 创建市场风格：`styles create --payload-file ./style-market.json`
- 触发报道生成：`reports generate --topic-id ...`
- 临时覆盖本次生成 AI：`reports generate --topic-id ... --sdk codex_cli --reasoning-effort high`

## 订阅更新兼容策略

- `subscriptions update` 现在直接对齐 `PATCH /vibe/agent/subscriptions/:topicId`
- 客户端会优先尝试 `PATCH /vibe/agent/subscriptions/:topicId`，再回退尝试 `PUT /vibe/agent/subscriptions/:topicId`
- 若当前 dudu 服务未暴露该能力，客户端会输出结构化 `unsupported_server_capability`
- 若用户传入当前 Vibe 契约不支持的旧字段（`groupId` / `generationAi` / `tier` / `style`），客户端会在本地直接给出结构化拒绝
- 当前 dudu 主项目虽已支持订阅级 `search_mode`，但 Vibe 路由仍未开放；本 skill 也不会私自绕过到主站 API
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
