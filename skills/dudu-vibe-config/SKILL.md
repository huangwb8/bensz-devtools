---
name: dudu-vibe-config
description: 管理 dudu 的已有订阅参数、批量 AI 配置、报道风格、报道和域名规则；写入通过 Vibe Agent API，本机订阅查询须获只读授权。
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
- 模板：保留历史 CLI 入口；当前用户级 Vibe API 禁止模板写入
- 报道风格：列出 / 创建 / 更新 / 删除
- 订阅：查询 / 创建 / 更新 / 批量更新 / 解析 prompt / 删除
- 报道：生成 / 删除
- 域名规则：读取 / 更新

## 任务工作区与中间文件

- 调用本 skill 前，先向用户说明 `dudu-vibe-config` 将完成的具体工作；仅文本答复时明确说明不创建目录。
- 需要落盘时，只使用本轮唯一的 `./.bensz-api/task-{yyyymmdd-hhmm}-{简短描述}/`。任务共享材料放 `shared/input|output|log`，derived 草案、临时 JSON payload、脱敏命令输出和验证日志放 `dudu-vibe-config/input|output|log`。
- 不归档 Vibe Key、`.env`/`remote.env`、完整私有订阅内容或其它敏感数据；正式报道、用户指定文件和项目文档仍保存到用户指定或项目约定位置。
- 同一逻辑任务的后续调用必须复用首次声明的任务目录，不能因工具续写或步骤变化创建第二个目录。

## 当前能力边界

- 当前契约以 2026-10-02 上游审计为准，详见 `docs/subscription-management.md` 与 `CHANGELOG.md`；历史计划保留。

- 当前 `/vibe/agent/*` 已覆盖报道风格 `list/create/update/delete`、订阅 `create/update/parse-prompt/delete`、报道 `generate/delete`、域名规则 `get/set`，以及 `ping/connect/heartbeat/disconnect`。
- 全局模板写入已由管理员 API 管理；用户级 Vibe 的模板创建/删除均返回 403。保留旧 CLI 入口便于旧服务器兼容，不改走管理员 API。
- 上游尚无订阅列表/详情读取接口，`ping` 不返回订阅。`subscriptions list/show` 通过显式 `--local-db-readonly` 读取本机数据库；未授权时不访问数据库，远程场景须提供订阅 ID。
- `subscriptions update-many --all` 维护当前 Vibe Key 用户的全部订阅；也可重复 `--topic-id` 维护指定集合。列表来源、AI 合并及逐项核验见 `docs/subscription-management.md`。
- 默认 derived 路径是“AI 宿主型本地生成”：先在当前对话里生成 `derivedQuery / derivedPlan`，再显式写回 dudu。
- 可选“脚本自驱型本地生成”：用 `python3 scripts/local_derive.py ...` 预览，或在 `subscriptions create/update` 里加 `--local-derived-script`，先调用本地 `codex` / `claude` CLI 生成，再写回 dudu。
- `subscriptions create/update` 支持 `derivedQuery` / `derivedPlan`；需要服务端重算时，用 `subscriptions parse-prompt` 或更新时的 `--refresh-derived/--no-refresh-derived`。
- `subscriptions update` 只接受 `name/prompt/frequency/ai/derivedQuery/derivedPlan/refreshDerived`；旧字段 `groupId`、`generationAi`、`tier`、`style` 会在本地直接拒绝。
- 仅改 AI 且未传 prompt 时，默认 `refreshDerived=false`，保留检索计划。读取当前配置后仅合并用户指定的 AI 字段；切换 SDK 必须指定模型。没有读取能力时，用 `--replace-ai --sdk ... --model ...` 显式替换，未指定字段取服务端默认值。
- SDK 已对齐 `kimi`，推理强度已对齐 `max`；不把某次操作的模型选择改成新增订阅的永久默认值。
- dudu 主项目当前已存在订阅级 `search_mode` 等主站字段，但 `/vibe/agent/subscriptions*` 仍未开放这些字段；本 skill 不会假装支持，也不会越权改走 `/topics/*`。订阅创建已开放 `sourceType=search|rss_opml|hybrid` 与 `opml`，其中 `hybrid` 会先采集 RSS、再用 prompt 的搜索计划补充召回。
- `subscriptions update` 与 `subscriptions parse-prompt --ai ...` 会由服务端顺带同步 `topic_subscriptions.generation_ai_config`，以保持手动“生成报道”和订阅默认 AI 的口径一致；但 bridge skill 仍不接受显式 `--generation-*`，避免和当前 Vibe 契约漂移。
- `styles list` 当前走的是 `available` 视图：会返回“内置风格 + 当前用户私有风格 + 市场可见风格”；bridge skill 不额外暴露 `mine/market/builtin` 过滤参数。
- `styles create/update` 已可透传 `visibility=private|market` 与 `baseStyle`，可用于私有风格和市场风格发布/继承。
- 删除最后一个订阅时，当前服务端会同时清理 orphan topic 的运行工件、报道工件、notes/system events 等残留；bridge skill 已按这个最新闭环理解返回结果，不再把它当作“仅删一条订阅关系”。
- 所有写请求默认不自动重试；新增订阅默认 AI 为 `sdk=codex_cli`、`model=""`、`reasoningEffort=medium`，显式参数优先。
- `reports generate --idempotency-key ...` 支持服务端幂等请求头；返回 `attemptId`，重复请求可返回 `idempotentReplay`。默认不重试生成请求。

## 安全边界（强制）

- 只允许调用：`{DUDU_VIBE_URL}/vibe/agent/*`
- 本机只读例外：用户明确授权后可用 `--local-db-readonly`，仅限回环 URL；查询以有效 Vibe Key 所属用户为范围，SQL 使用 `BEGIN READ ONLY`，不读取原始 Key、不执行数据库写入。既有授权可复用，无须重复询问。
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
- 已有订阅：授权范围内先 `subscriptions list/show --local-db-readonly` 确认 ID 与参数；AI 修改用 `update`，全部订阅用 `update-many --all`，带同一只读选项合并并核验。用户已授权修改时直接执行，批量首个失败即停止并报告完成清单。
- 报道风格：先 `styles list` 看当前“Vibe 可见风格目录”（内置 + 自己的私有 + 市场可见），再按需 `styles create/update/delete`
- 域名规则：先 `domains get`，再 `domains set`；默认安全合并，只有“完全替换”才用 `--reset`
- 订阅 prompt / `derived_*`：默认先本地产生 `derivedQuery / derivedPlan` 再显式写回；只有用户明确要求服务端重算，或本地生成不可用时，才用 `subscriptions parse-prompt`
- 订阅字段边界：创建支持 `name/prompt/frequency/ai/derivedQuery/derivedPlan/sourceType/opml`；更新仍只允许 `name/prompt/frequency/ai/derivedQuery/derivedPlan/refreshDerived`。若用户想调 `searchMode`、`groupId`、`generationAi` 等主站字段，应明确告知“当前 bridge skill 不覆盖”。
- 宿主 AI 想把本地生成下沉到脚本时，用 `python3 scripts/local_derive.py ...` 或 `subscriptions create/update --local-derived-script`
- 报道按需执行；所有写操作默认自动 `connect → disconnect`

4. 不确定时先 `--dry-run`；纯本地预览不要求预先配置 key

```bash
python3 scripts/client.py --dry-run domains set --reset --allowlist example.com
```

## 常见任务映射（意图 → 命令）

- 白名单 / 黑名单 / 关键词：`domains set --allowlist ...`、`--blocklist ...`、`--keywords ...`
- 报道风格：`styles list`、`styles create --payload-file ...`、`styles update --id ... --payload-json ...`、`styles delete --id ...`
- 新增订阅：`subscriptions create --frequency daily`
- 创建 RSS + 搜索混合订阅：`subscriptions create --source-type hybrid --opml @feeds.opml --frequency daily`
- 本地生成后写回：`subscriptions update --topic-id ... --prompt ... --derived-query ... --derived-plan-file ...`
- 命令行本地生成并写回：`subscriptions update --topic-id ... --prompt ... --local-derived-script`
- 让服务端重算 derived：`subscriptions parse-prompt --topic-id ...`
- 已有订阅改模型/推理：`subscriptions update --topic-id ... --model gpt-6-luna --reasoning-effort high --local-db-readonly`
- 所有现有订阅改模型/推理：`subscriptions update-many --all --model gpt-6-luna --reasoning-effort high --local-db-readonly`
- 远程已知 ID 显式替换 AI：`subscriptions update --topic-id ... --replace-ai --sdk codex_cli --model gpt-6-luna --reasoning-effort high`
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
- 本机读取/合并失败：结构化错误并停止，预检不通过不发写请求；批量请求失败、终止或核验失败返回 `updated_count/results`，不自动回滚或重试，先回读确认实际状态。

## 输出约定（用于工具调用）

- `scripts/client.py` 的 `doctor` 与 `doctor --watch-seconds` 仅输出 JSON（便于工具稳定解析）
- 遇到终止请求（`terminate_requested`）时：输出 `{"terminate_requested": true, ...}` 并以退出码 `0` 结束（视为用户主动终止）
