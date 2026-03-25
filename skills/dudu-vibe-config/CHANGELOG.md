# Changelog

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [Unreleased]

## [0.5.0] - 2026-03-25

### Added（新增）

- 新增 `subscriptions parse-prompt` 命令，对齐最新 `POST /vibe/agent/subscriptions/:topicId/parse-prompt`
- 新增检索式构建参数：`subscriptions create/update` 现支持 `--derived-query`、`--derived-plan-json`、`--derived-plan-file`
- 新增 derived 刷新控制：`subscriptions update` 现支持 `--refresh-derived` / `--no-refresh-derived`
- 新增本轮兼容升级计划：`plans/2026-03-25-vibe-search-builder-compat.md`
- 扩充回归测试：覆盖最新 Vibe update 契约、旧 metadata 参数前置拒绝、以及 `parse-prompt` 新路由

### Changed（变更）

- 基于 2026-03-25 对 `/Volumes/2T01/winE/Starup/dudu` 最新 `/vibe/agent/*` 源码审计，更新 skill 口径：`subscriptions update` 已正式开放，不再是假想的前向兼容包装
- `subscriptions update` 现在严格对齐当前 Vibe PATCH 契约：`name/prompt/frequency/ai/derivedQuery/derivedPlan/refreshDerived`
- `README.md` 与 `SKILL.md` 同步更新为最新检索式构建工作流，并补充返回体中的 `derivedRefreshStatus / derivedQuery / derivedAt`

### Fixed（修复）

- 修复旧版 update CLI 会把 `tier/style/groupId/generationAi` 发送到最新服务端而触发 400 的契约漂移问题
- 修复文档错误地宣称 `subscriptions update` 尚未开放的问题
- 修复状态码说明：写请求缺失 `x-dudu-vibe-connection` 现在明确归类为 `400`，而不是笼统写成 `401`

## [0.4.0] - 2026-03-21

### Added（新增）

- 扩充 `tests/test_client_defaults.py`：新增对 `--dry-run` 无 key、本地环境别名、非法 URL scheme 拒绝、以及网络传输失败结构化输出的回归测试

### Changed（变更）

- 基于 2026-03-21 对 `/Volumes/2T01/winE/Starup/dudu` 最新 `/vibe/agent/*` 源码审计，更新文档口径：补充 `rss_opml` 模板能力，并明确 `subscriptions update` 的字段模型已覆盖 `groupId` / `generationAi`
- 新增订阅的默认 AI 调整为：`codex_cli + CLI/provider 默认模型 + medium`，即默认发送 `model=""`，避免把过时的固定模型名写死到 `codex_cli` 订阅中
- `README.md` 与 `SKILL.md` 同步说明：纯本地 `--dry-run` 不要求预先配置 key，网络传输失败会输出结构化 `transport_error`

### Fixed（修复）

- 修复网络层异常直出 Python traceback：`client.py` 现在会把非 HTTP 传输失败收口为结构化 JSON
- 修复环境变量 URL 校验缺口：`DUDU_VIBE_URL` / `dudu_base_url` 现在和 `--url` 一样拒绝非 `http/https` scheme
- 修复 `--dry-run` 仍强制要求 key 的问题，让本地请求预演真正可用

## [0.3.2] - 2026-03-18

### Added（新增）

- 新增契约回归测试：覆盖写请求禁用自动重试、`reports generate` 接受 `202`、以及 `dudu_base_url` / `dudu_vibe_api` 环境变量别名解析
- 新增 `tests/test_client_defaults.py`：覆盖新增订阅时的默认 AI 注入、显式模型覆盖、CLI 空模型透传与非默认 SDK 保持原样

### Changed（变更）

- 基于 2026-03-18 对 `/Volumes/2T01/winE/Starup/dudu` 最新 `/vibe/agent/*` 源码审计，收紧文档口径：明确当前服务端实际开放的是模板/订阅创建删除、报道生成删除、域名规则读写；`subscriptions update` / `generationAi` 更新仍属前向兼容包装
- README 与 SKILL.md 新增常见状态码说明，并明确写请求默认不自动重试
- 新增订阅的默认 AI 从“依赖服务端 topic 默认值”收敛为 skill 侧显式下发：`codex_cli + gpt-5.4 + medium`
- `config.yaml` 新增订阅默认 AI 的单一配置来源，显式传入 `--sdk/--model/--reasoning-effort` 时仍优先尊重用户参数
- 文档同步澄清“新模板默认 SDK”边界：`/vibe/agent/templates` 仅保存模板元数据，不持久化 AI 配置

### Fixed（修复）

- 修复非幂等写请求的重试风险：`POST/PUT/DELETE` 不再自动重试，避免在超时或瞬时 5xx 后重复创建连接、模板或订阅

## [0.3.0] - 2026-03-16

### Added（新增）

- 新增 `subscriptions update` 命令：支持按 `dudu` 最新源码中的 topic/subscription 字段模型更新已有订阅，可修改 `name/prompt/frequency/tier/style/groupId`、主题 AI（`sdk/model/reasoningEffort/thinkingMode`）以及按用户保存的 `generationAi`
- 新增生成偏好控制：`subscriptions update` 现支持 `--generation-sdk`、`--generation-model`、`--generation-reasoning-effort`、`--generation-thinking-mode` 与 `--clear-generation-ai`

### Changed（变更）

- `subscriptions create` 现复用统一的频率解析逻辑，对非法自定义 JSON 频率给出更明确的本地报错
- 更新 `README.md` 与 `SKILL.md`：补充订阅更新示例、字段说明与兼容性策略，明确当前 dudu 服务若尚未提供对应 `/vibe/agent` 路由时会返回结构化 `unsupported_server_capability`，而不会做破坏性重建兜底

## [0.2.1] - 2026-03-11

### Added（新增）

- SKILL.md 新增"订阅提示词策略"章节：推荐使用布尔检索式语法（AND/OR/-/引号/分组）替代自然语言，提供算子速查表、场景对比示例和构造模板

## [0.2.0] - 2026-03-10

### Added（新增）

- 为 `subscriptions create` 新增 AI 配置透传参数：支持 `--sdk`、`--model`、`--reasoning-effort`、`--thinking-mode`，可显式对齐 dudu 主项目近期强化的 `claude_code` / `codex_cli` 搜索代理链路
- 为 `reports generate` 新增同一组 AI 覆盖参数：可在不改订阅默认配置的前提下，临时指定本次报道生成所用 provider/model/reasoning/thinking

### Changed（变更）

- 更新 `README.md` 与 `SKILL.md`：补充面向 CLI provider 的使用示例，并说明 `claude_code` / `codex_cli` 仍依赖主项目侧已启用的 CLI provider / MCP 能力


## [0.1.1] - 2026-03-05

### Fixed（修复）

- 修复连接一致性：`heartbeat`/`disconnect` 也会携带 `x-dudu-vibe-connection`（避免服务端严格校验时失败）
- 修复终止处理：识别 `x-dudu-vibe-terminate: 1`、HTTP 409 `terminate_requested`、`terminate=true` 并输出 `terminate_requested=true`（退出码为 0）

### Changed（变更）

- 改进可解析性：`client.py doctor` 输出合并为单个 JSON；`doctor --watch-seconds` 的启动信息也输出为 JSON
- 改进一致性：`domains set` 在 dry-run 且需要 merge 时，改为输出结构化 JSON 错误（避免混入纯文本）
- 改进健壮性：`connect` 返回后也会执行终止护栏检查

## [0.1.0] - 2026-03-04

### Added（新增）

- 初始化 `dudu-vibe-config`：提供受限的 Vibe Agent API 客户端与环境检查脚本

### Fixed（修复）

- 修复 env 优先级：OS 环境变量不再被 `.env` 意外覆盖
- 修复 HTTP 重试：对 408/429/5xx 的 HTTPError 支持重试，并补齐本机地址绕过代理逻辑
- 修复 `domains set` 安全性：读取现有规则失败时不再继续写入；无输入时跳过 PUT
- 修复 dotenv 解析兼容性：支持 `export KEY=...` 与非引号值的行尾注释

### Changed（变更）

- 强化安全边界：对 template/topic/report id 参数做 UUID 校验，防止路径穿越式 URL 拼接
- 改进可观测性：`client.py doctor --watch-seconds` 支持按配置间隔循环 heartbeat，便于 Web 端终止连接
- 增强可审计性：新增 `client.py --dry-run`，可在不触网的情况下打印将要发出的请求
- 扩展 URL 别名识别：`env_url_keys` 新增 `dudu_base_url`，自动兼容 dudu-devtools `.env` 中的实际 key 名
