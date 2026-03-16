# dudu-vibe-config

`dudu-vibe-config` 是一个 **“桥梁”Skill**：让你在 Claude Code / OpenAI Codex 等 Vibe Coding 工具里，通过 `dudu` 的 **Vibe Agent API**（`/vibe/agent/*`）远程优化“氛围配置”（模板/订阅/报道/域名规则）。

## 适用场景

- 批量维护域名规则（allowlist/blocklist/keywords）
- 创建/删除模板（Templates）
- 创建/更新/退订订阅（Subscriptions），并可显式指定主题 AI 与按用户存储的生成偏好
- 触发生成报道、删除报道（Reports），并可在生成时临时覆盖 AI 配置

## 依赖与约束

- Python 3（仅使用标准库；不依赖 `requests` / `PyYAML`）
- 需要一个有效的 `Vibe URL + Vibe Key`
- **安全边界**：只调用 `dudu` 的 `/vibe/agent/*` 受限接口；不做越权访问
- **禁止事项**：严禁修改 dudu 软件源代码（本 skill 仅用于配置侧变更）

## 配置（URL + KEY）

优先从环境变量读取：

- `DUDU_VIBE_URL`（默认 `http://localhost:3001`）
- `DUDU_VIBE_KEY`

兼容别名：

- URL：`dudu_vibe_url`
- KEY：`dudu_vibe_key`、`dudu_vibe_api`

`.env` 搜索顺序（脚本自动查找）：

1. 当前工作目录的 `.env` / `.env.local`
2. `~/.dudu-vibe.env`
3. `~/.config/dudu/vibe.env`

也可以显式指定：

```bash
python3 scripts/env_check.py --env-file /path/to/.env
```

## 快速开始（本机 + Docker）

1) 启动 dudu（Docker）

```bash
cd /Volumes/2T01/winE/Starup/dudu/docker
docker compose up -d --build
```

2) 检查环境并 ping

```bash
python3 scripts/env_check.py
python3 scripts/client.py ping
python3 scripts/client.py doctor
# 可选：保持连接并持续心跳（便于在 Web 端观察连接并随时终止）
python3 scripts/client.py doctor --watch-seconds 120
```

## 常用命令

说明：`doctor`/`doctor --watch-seconds` 输出为 JSON（或多条 JSON），便于在工具调用中稳定解析；若 Web 端触发终止，会输出 `terminate_requested=true` 并以退出码 0 结束。若你的订阅走 `claude_code` / `codex_cli`，宿主环境仍需在 dudu 主项目侧启用对应 CLI provider / MCP 能力，否则服务端会按主项目当前策略回退。

兼容性提醒：`subscriptions update` 的字段模型已按 `dudu` 最新 `topics/:id` + `topics/:id/subscribe` 语义对齐，但当前最新 `dudu` 源码里的 `/vibe/agent/*` 仍未提供订阅更新路由。为避免“删除重建订阅”导致 topic/report 历史丢失，本 skill 遇到旧服务时会返回结构化 `unsupported_server_capability`，而不会做破坏性兜底。

```bash
# 域名规则（读取）
python3 scripts/client.py domains get

# 域名规则（更新；会自动 connect/disconnect）
python3 scripts/client.py domains set --allowlist example.com --blocklist bad.com --keywords "某关键词"

# 域名规则（重置为你提供的列表；危险操作）
python3 scripts/client.py domains set --reset --allowlist example.com

# dry-run：只打印将要发出的请求（不打印 key）
python3 scripts/client.py --dry-run domains set --reset --allowlist example.com

# 模板
python3 scripts/client.py templates add --title "模板标题" --query "检索词/提示词" --frequency daily
python3 scripts/client.py templates delete --id <template-id>

# 订阅
python3 scripts/client.py subscriptions create --name "订阅名" --prompt "订阅提示词" --frequency daily
python3 scripts/client.py subscriptions create --name "开发工具追踪" --prompt "跟踪 Claude Code / Codex CLI / MCP 更新" --frequency daily --sdk claude_code --reasoning-effort medium --thinking-mode thinking
python3 scripts/client.py subscriptions update --topic-id <topic-uuid> --sdk codex_cli --model "" --reasoning-effort high
python3 scripts/client.py subscriptions update --topic-id <topic-uuid> --tier premium --style deep_research --generation-sdk claude --generation-thinking-mode thinking
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
- 订阅偏好字段：`--tier`、`--style`、`--group-id`
- 手动“生成报道”默认 AI：`--generation-sdk`、`--generation-model`、`--generation-reasoning-effort`、`--generation-thinking-mode`
- 清空生成偏好：`--clear-generation-ai`

说明：
- `--model ""` 仍表示“使用 provider / CLI 默认模型”。
- `--group-id default` 或 `--group-id null` 会清空分组，回到默认组。
- `--frequency` 同时支持 `hourly|daily|weekly` 和 `{"type":"custom","interval_seconds":...}`。

## 安全建议

- 不要在日志/截图/issue 中暴露完整 `DUDU_VIBE_KEY`（本 skill 默认只展示前缀）
- 建议在 dudu Web 的“氛围配置”页面按需创建/吊销 Key
