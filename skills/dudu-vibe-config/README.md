# dudu-vibe-config

`dudu-vibe-config` 是一个 **“桥梁”Skill**：让你在 Claude Code / OpenAI Codex 等 Vibe Coding 工具里，通过 `dudu` 的 **Vibe Agent API**（`/vibe/agent/*`）远程优化“氛围配置”（模板/报道风格/订阅/报道/域名规则）。

## 适用场景

- 批量维护域名规则（allowlist/blocklist/keywords）
- 创建/删除模板（Templates）
- 管理报道风格（Report Styles）：列出、创建、更新、删除
- 创建/更新/退订订阅（Subscriptions），并可显式指定主题 AI 与检索式构建结果
- 主动刷新订阅的 `derivedQuery / derivedPlan`
- 触发生成报道、删除报道（Reports），并可在生成时临时覆盖 AI 配置

## 当前能力边界

- 最近一次基于上游源码的审计时间与变更说明，统一记录在 `CHANGELOG.md` 与 `plans/2026-04-19-vibe-contract-audit-and-hardening.md`；本节只保留当前仍然生效的能力与限制。

- 当前 `dudu` 最新 `/vibe/agent/*` 实际开放的能力：模板 `add/delete`、报道风格 `list/create/update/delete`、订阅 `create/update/parse-prompt/delete`、报道 `generate/delete`、域名规则 `get/set`，以及 `ping/connect/heartbeat/disconnect`。
- 模板创建已支持 `sourceType=search|rss_opml` 与可选 `opml`；对于 `search` 模板，服务端会在创建时自动预生成并持久化模板级 `derivedQuery / derivedPlan`，当前 skill 不支持手工传入模板级 `derived_*`。
- 当前 `/vibe/agent/templates` 仍要求 `query` 为非空字符串；因此即使主站 `templates` API 已允许 `rss_opml` 模板空 query，bridge skill 走 Vibe 路由时也必须继续传 `--query`。
- 当前 skill 的默认策略已切到 **AI 宿主型本地生成**：当你在 Codex / Claude Code 里直接使用本 skill 调整 subscription prompt / derived_* 时，推荐先在当前本地对话里生成 `derivedQuery / derivedPlan`，再显式写回 dudu，而不是把这一步默认交给 dudu 服务端。
- 当前 skill 也新增了 **脚本自驱型本地生成**：`scripts/local_derive.py` 可直接调用本地 `codex` / `claude` CLI 生成 derived；`scripts/client.py subscriptions create|update --local-derived-script` 则可把“本地生成 + 写回 dudu”合成一条命令。
- `subscriptions create/update` 现已支持显式写入 `derivedQuery` / `derivedPlan`；若不显式提供，服务端会按当时可用 AI 环境尝试刷新，并在返回体中带回 `derivedRefreshStatus`、`derivedQuery`、`derivedAt`。
- `subscriptions update` 当前只对齐 **Vibe 专用契约**：`name/prompt/frequency/ai/derivedQuery/derivedPlan/refreshDerived`。
- `groupId`、`generationAi`、`tier`、`style` 属于主站 `/topics` / `/topics/:id/subscribe` 语义，不是当前 Vibe PATCH 契约；本 skill 现会在本地明确拒绝这些旧参数，避免继续把请求打成 400。
- dudu 主项目当前已有订阅级 `search_mode`，但 `/vibe/agent/subscriptions*` 仍未暴露 `searchMode`；本 skill 不会假装支持，也不会越权改走 `/topics/*`。
- `subscriptions update` 与 `subscriptions parse-prompt --ai ...` 在服务端会顺带同步 `topic_subscriptions.generation_ai_config`，让“订阅默认 AI”与手动“生成报道”保持一致；bridge skill 仍不接受显式 `--generation-*`，避免越过当前 Vibe 契约。
- `styles list` 当前返回的是 `available` 目录：内置风格、当前用户私有风格、以及市场可见风格会一起出现；当前 Vibe 路由未暴露 `mine/market/builtin` 过滤参数。
- `styles create/update` 已支持直接透传 `visibility=private|market` 与 `baseStyle`，可用于私有风格和风格市场发布。
- 删除最后一个订阅时，当前服务端会一起清理 orphan topic 的运行工件、报道工件和 system events 等残留；bridge skill 以此为最新删除语义。
- 所有写请求默认**不自动重试**，避免在超时或瞬时 5xx 后重复创建连接、模板或订阅。
- 新增订阅时，如未显式指定 AI 配置，CLI 默认会发送 `codex_cli + CLI/provider 默认模型 + medium`；也就是 `sdk=codex_cli`、`model=""`、`reasoningEffort=medium`。若你明确传入 `--sdk/--model/--reasoning-effort`，则以显式参数为准。
- 新增模板接口当前只保存模板元数据，不保存 AI 配置；因此“默认 SDK”只会作用在后续基于该模板创建订阅时，不会额外写入不存在的模板字段。
- 当前 `/vibe/agent/templates` 仍不支持显式写入模板级 `derivedQuery / derivedPlan`；因此模板场景下的本地生成主要用于先把 query/prompt 打磨好，再交由 dudu 服务端自动持久化模板 derived 结果。

## 依赖与约束

- Python 3（仅使用标准库；不依赖 `requests` / `PyYAML`）
- 除纯本地 `--dry-run` 外，需要一个有效的 `Vibe URL + Vibe Key`
- **安全边界**：只调用 `dudu` 的 `/vibe/agent/*` 受限接口；不做越权访问
- **禁止事项**：严禁修改 dudu 软件源代码（本 skill 仅用于配置侧变更）
- **可靠性约束**：变更类请求默认不自动重试，优先避免重复写入

## 配置（URL + KEY）

优先从环境变量读取：

- `DUDU_VIBE_URL`（默认 `http://localhost:3001`）
- `DUDU_VIBE_KEY`

兼容别名：

- URL：`dudu_vibe_url`、`dudu_base_url`
- KEY：`dudu_vibe_key`、`dudu_vibe_api`

`.env` 搜索顺序（脚本自动查找）：

1. 当前工作目录的 `.env` / `.env.local` / `remote.env`
2. 从 skill 目录向上查找项目级 `remote.env`（默认最多 5 层，适配本仓库根目录凭证）
3. `~/.dudu-vibe.env`
4. `~/.config/dudu/vibe.env`

也可以显式指定：

```bash
python3 scripts/env_check.py --env-file /path/to/.env
```

优先级始终是：进程环境变量 > 显式 `--env-file` > 当前工作目录候选文件 > 项目级 `remote.env` > fallback 文件。

## 快速开始（本机 + Docker）

1) 启动 dudu（Docker）

```bash
cd ../dudu/docker
docker compose up -d --build
```

如果你的本地目录布局不是“`bensz-devtools` 与 `dudu` 同级”，请把 `../dudu/docker` 改成你自己的 `dudu/docker` 路径。

2) 检查环境并 ping

```bash
python3 scripts/env_check.py
python3 scripts/client.py ping
python3 scripts/client.py doctor
# 可选：保持连接并持续心跳（便于在 Web 端观察连接并随时终止）
python3 scripts/client.py doctor --watch-seconds 120
```

## 本地 Derived 策略

- 默认模式：`AI 宿主型本地生成`
  - 当你直接在 Codex / Claude Code 里使用本 skill 调整 subscription prompt 时，优先让宿主 AI 先在当前对话里生成 `derivedQuery / derivedPlan`。
  - 然后再调用 `scripts/client.py subscriptions create|update ... --derived-query ... --derived-plan-file|--derived-plan-json ...` 显式写回 dudu。
- 可选模式：`脚本自驱型本地生成`
  - 若你想把这一步完全下沉到命令行，可使用 `python3 scripts/local_derive.py ...` 预览。
  - 也可以直接用 `scripts/client.py subscriptions create|update --local-derived-script`，让脚本先调用本地 `codex` / `claude` CLI 生成 derived，再自动写回 dudu。
- 服务端重算：`subscriptions parse-prompt`
  - 只在你明确想复用 dudu 主项目的 AI 环境，或本地生成不可用时使用。

更多说明见 [local-derived-workflow.md](docs/local-derived-workflow.md)。

## 常用命令

说明：`doctor`/`doctor --watch-seconds` 输出为 JSON（或多条 JSON），便于在工具调用中稳定解析；若 Web 端触发终止，会输出 `terminate_requested=true` 并以退出码 0 结束。`--local-derived-script` 走的是你当前机器上的 `codex` / `claude` CLI，不依赖 dudu 主项目是否配置好了 provider；但若你改用 `subscriptions parse-prompt`，那仍依赖 dudu 服务端自己的 AI 环境。

兼容性提醒：`subscriptions update` 现在是真正落到最新 `/vibe/agent/subscriptions/:topicId` 的，而不是旧的“前向兼容包装”。如果你传入当前 Vibe 契约不支持的旧字段（如 `--group-id`、`--generation-*`、`--tier`、`--style`），CLI 会在本地输出结构化 `unsupported_server_capability`，避免把请求直接打坏。当前 dudu 主项目虽已有订阅级 `searchMode`，但 `/vibe/agent/subscriptions*` 仍未开放，bridge skill 也不会绕过到 `/topics/*`。

```bash
# 域名规则（读取）
python3 scripts/client.py domains get

# 域名规则（更新；会自动 connect/disconnect）
python3 scripts/client.py domains set --allowlist example.com --blocklist bad.com --keywords "某关键词"

# 域名规则（重置为你提供的列表；危险操作）
python3 scripts/client.py domains set --reset --allowlist example.com

# dry-run：只打印将要发出的请求（不打印 key）；纯本地预览时不要求先配置 key
python3 scripts/client.py --dry-run domains set --reset --allowlist example.com

# 模板
python3 scripts/client.py templates add --title "模板标题" --query "检索词/提示词" --frequency daily
python3 scripts/client.py templates add --title "RSS 模板" --query "RSS 导入模板" --frequency daily --source-type rss_opml --opml '<opml version="2.0">...</opml>'
python3 scripts/client.py templates delete --id <template-id>
# 当前模板 derived 由 dudu 服务端在创建 search 模板时自动生成并持久化；CLI 不支持手工传模板 derived
# 注意：当前 Vibe 路由下 rss_opml 仍要求非空 --query

# 报道风格
python3 scripts/client.py styles list
python3 scripts/client.py styles create --payload-file /path/to/style.json
python3 scripts/client.py styles create --payload-json '{"name":"市场风格示例","category":"professional","description":"示例","sectionStrategy":"style","citationStyle":"default","articleStructure":["导语","主体","结论"],"tone":"专业","targetAudience":"研究者","examples":["Example"],"roleDefault":"资深编辑","extraRules":"注意引用","writingGuide":"先证据后判断","visibility":"market","baseStyle":"deep_research"}'
python3 scripts/client.py styles update --id custom_style --payload-json '{"description":"更新后的说明"}'
python3 scripts/client.py styles delete --id custom_style
# styles list 当前展示 Vibe 可见目录：内置 + 你的私有风格 + 市场可见风格

# 订阅
# 未传 AI 参数时，默认创建为 codex_cli + CLI/provider 默认模型 + medium
python3 scripts/client.py subscriptions create --name "订阅名" --prompt "订阅提示词" --frequency daily
python3 scripts/client.py subscriptions create --name "开发工具追踪" --prompt "跟踪 Claude Code / Codex CLI / MCP 更新" --frequency daily --sdk claude_code --reasoning-effort medium --thinking-mode thinking
# 用脚本自驱方式先在本地生成 derived_* 再创建订阅
python3 scripts/client.py subscriptions create --name "AI 安全" --prompt '"AI safety" OR alignment' --frequency daily --local-derived-script
# 创建时显式写入检索式 / 检索计划
python3 scripts/client.py subscriptions create --name "AI 安全" --prompt '"AI safety" OR alignment' --frequency daily --derived-query '"AI safety" OR alignment OR "model safety"' --derived-plan-file /path/to/derived-plan.json
# 预览脚本自驱生成的本地 derived 结果
python3 scripts/local_derive.py --prompt '"agentic coding" OR codex OR "claude code"' --topic-name "开发工具追踪"
# 更新订阅，并由脚本先在本地生成 derived_* 再写回 dudu
python3 scripts/client.py subscriptions update --topic-id <topic-uuid> --prompt '"agentic coding" OR codex OR "claude code"' --local-derived-script
# 直接写入手工检索计划，不依赖当下 AI 刷新
python3 scripts/client.py subscriptions update --topic-id <topic-uuid> --derived-query '"agentic coding" OR codex' --derived-plan-json '{"source":"ai","version":"2026-03-25","promptHash":"...","derivedQuery":"\"agentic coding\" OR codex"}'
# 主动让 dudu 服务端重新解析 prompt，可附带临时 AI 配置
python3 scripts/client.py subscriptions parse-prompt --topic-id <topic-uuid> --sdk claude --model claude-sonnet-4-5 --thinking-mode thinking
# 旧的 metadata/generation 参数不属于当前 Vibe PATCH 契约，会被本地拒绝
python3 scripts/client.py subscriptions update --topic-id <topic-uuid> --generation-sdk claude
python3 scripts/client.py --dry-run subscriptions update --topic-id <topic-uuid> --prompt '"agentic coding" OR codex OR "claude code"' --frequency '{"type":"custom","interval_seconds":21600}'
python3 scripts/client.py subscriptions delete --topic-id <topic-uuid>

# 报道
python3 scripts/client.py reports generate --topic-id <topic-uuid>
python3 scripts/client.py reports generate --topic-id <topic-uuid> --sdk codex_cli --model "" --reasoning-effort high
python3 scripts/client.py reports delete --topic-id <topic-uuid> --report-id <report-uuid>
```

## WHICHMODEL

- **复杂配置编排/多步变更**：选择支持强工具调用与长上下文的“高可靠推理模型”（能在多轮 API 操作中保持一致性与安全边界）。
- **单条命令执行/核对结果**：选择更快的“工具型模型”即可（关键是严格按 `scripts/client.py` 输出做决定）。

## 订阅更新字段说明

- 主题级字段：`--name`、`--prompt`、`--frequency`、`--sdk`、`--model`、`--reasoning-effort`、`--thinking-mode`
- 检索式字段：`--derived-query`、`--derived-plan-json`、`--derived-plan-file`、`--local-derived-script`
- 刷新控制：`--refresh-derived`、`--no-refresh-derived`
- 主动刷新命令：`subscriptions parse-prompt`

说明：
- `--model ""` 仍表示“使用 provider / CLI 默认模型”。
- `--frequency` 同时支持 `hourly|daily|weekly` 和 `{"type":"custom","interval_seconds":...}`。
- `derivedPlan` 推荐通过 `--derived-plan-file` 传入完整 JSON，适合包含 `booleanLines`、`queryVariants.mcp`、`keywords`、`coreQuestions` 等较长结构。
- 默认优先本地生成：若你正在宿主 AI 中直接操作 skill，先让宿主 AI 本地生成 derived；若你更偏向纯命令行闭环，则使用 `--local-derived-script`。
- `--local-derived-script` 不要和 `--derived-query` / `--derived-plan-*` 混用；前者是“本地 CLI 自动生成”，后者是“显式手工写入”。
- 若你只是想“明确让 dudu 服务端按它自己的 AI 环境重新生成一版检索计划”，才使用 `subscriptions parse-prompt`。
- `--tier`、`--style`、`--group-id`、`--generation-*`、`--clear-generation-ai` 不属于当前 Vibe PATCH 契约；CLI 会显式拒绝它们，而不是继续向服务端发送无效 payload。

## 新增订阅默认 AI

- 默认 SDK：`codex_cli`（Codex CLI，不是 OpenAI Responses API 的 `codex`）
- 默认模型：留空（`""`），交由服务端/provider/CLI 默认值补齐
- 默认 `reasoningEffort`：`medium`

说明：
- 仅在 `subscriptions create` 且用户未显式指定对应字段时自动补齐。
- 若你显式传入 `--sdk claude_code`、`--model ""` 或其他覆盖值，CLI 不会强行改写你的选择。
- 模板 API 当前没有 `ai` 字段，所以 `templates add` 不会持久化上述默认 AI 配置。

## 报道风格 JSON

- `styles create` / `styles update` 走的是与上游 `/vibe/agent/styles` 一致的 JSON 契约。
- 为了减少桥梁层参数漂移，CLI 当前使用 `--payload-json` / `--payload-file` 直接透传对象，而不是再造一层大量命令行 flags。
- `styles create` 的完整字段可参考：`name`、`category`、`description`、`sectionStrategy`、`citationStyle`、`articleStructure`、`tone`、`targetAudience`、`examples`、`roleDefault`、`roleByTier`、`extraRules`、`writingGuide`、`visibility`、`baseStyle`。
- `styles update` 只需要传你要改的字段子集；`--id` 使用现有 `style id`（内置或自定义）。
- `visibility` 目前支持 `private` 和 `market`；`baseStyle` 可用于从现有风格衍生。
- `styles list` 当前不提供额外 scope 过滤，只返回当前 Vibe 可见目录。

## 安全建议

- 不要在日志/截图/issue 中暴露完整 `DUDU_VIBE_KEY`（本 skill 默认只展示前缀）
- 建议在 dudu Web 的“氛围配置”页面按需创建/吊销 Key

## 常见状态码

- `200`：请求已完成。
- `202`：请求已入队，当前主要出现在 `reports generate`。
- `400`：参数或请求体不符合服务端校验规则；也包括缺失 `x-dudu-vibe-connection` 的写请求。
- `401`：`x-dudu-vibe-key` 无效，或 `x-dudu-vibe-connection` 无效/失效。
- `404`：资源不存在。
- `409`：Web 端已经终止当前连接，返回 `terminate_requested`。
- `5xx` / 超时：服务端或网络异常；本 skill 对写请求不会自动重试，避免重复写入。
- 非 HTTP 网络失败：CLI 会输出结构化 `transport_error` JSON，而不是 Python traceback。
