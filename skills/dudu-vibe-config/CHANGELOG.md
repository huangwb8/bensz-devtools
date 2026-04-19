# Changelog

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [Unreleased]

## [0.8.0] - 2026-04-19

### Added（新增）

- 新增 `plans/2026-04-19-vibe-contract-audit-and-hardening.md`：沉淀本轮基于 dudu 最新 `Vibe Agent` 源码的审计结论、边界判断与验证计划
- 扩充 CLI 回归测试：覆盖风格市场字段透传，以及最新 Vibe 边界说明

### Changed（变更）

- 基于 2026-04-19 对 `/Volumes/2T01/winE/Starup/dudu` 最新 `/vibe/agent/*` 源码审计，更新 skill 口径：补充 `styles list` 当前实际返回的是 `available` 目录（内置 + 私有 + 市场可见），并明确 `styles create/update` 已可透传 `visibility` / `baseStyle`
- 补充订阅边界说明：当前 dudu 主项目虽已有订阅级 `search_mode`，但 `/vibe/agent/subscriptions*` 仍未开放；同时说明 `subscriptions update` / `parse-prompt --ai` 会在服务端顺带同步 `generation_ai_config`
- 补充删除语义说明：删除最后一个订阅时，当前服务端会一起清理 orphan topic 的运行工件、报道工件与 system events 等残留
- 补充模板边界说明：当前 `/vibe/agent/templates` 即使在 `rss_opml` 场景下也仍要求非空 `query`
- `config.yaml` 升级到 `0.8.0`，与本轮审计后的 README / SKILL / CLI 帮助信息保持一致

### Fixed（修复）

- 修复仓库与 skill 文档对最新 dudu 能力边界的表述滞后问题，避免用户误以为 bridge skill 已支持 `searchMode` 或可绕过 Vibe 路由直接使用主站订阅字段
- 修复 CLI 帮助和示例对 `rss_opml` 模板、风格市场可见性等场景说明不足的问题

## [0.7.0] - 2026-04-13

### Added（新增）

- 新增 `styles list/create/update/delete`：对齐 `dudu` 最新 `/vibe/agent/styles*` 报道风格管理能力
- 新增 CLI 回归测试：覆盖 `styles` dry-run 与 `domains set` 安全合并逻辑

### Changed（变更）

- 基于 2026-04-13 对 `/Volumes/2T01/winE/Starup/dudu` 最新 `/vibe/agent/*` 源码审计，更新 skill 口径：模板创建时 `search` 模板会由服务端自动预生成并持久化模板级 `derivedQuery / derivedPlan`
- `config.yaml` 升级到 `0.7.0`，把新增订阅默认 AI 模型恢复为 `model=""`，与 README、测试和“交由 CLI/provider 默认模型决策”的策略保持一致
- 移除未实际生效的 `default_local_derived_mode` 配置项，避免误导维护者以为它是可切换的运行时开关
- `README.md` 与 `SKILL.md` 同步更新为最新风格管理能力、模板 derived 行为和更通用的本地启动说明

### Fixed（修复）

- 修复 `config.yaml` 与 `tests/test_client_defaults.py` / README 长期不一致，导致默认订阅 AI 行为与文档偏离、测试回归失败的问题

## [0.6.0] - 2026-03-26

### Added（新增）

- 新增 `scripts/_local_derive.py` 与 `scripts/local_derive.py`：可通过本地 `codex` / `claude` CLI 生成 `derivedQuery / derivedPlan`
- 新增 `subscriptions create/update --local-derived-script`：把“本地生成 derived_* + 写回 dudu”合并为一条命令
- 新增 `docs/local-derived-workflow.md`：明确 AI 宿主型本地生成与脚本自驱型本地生成两条工作流
- 新增回归测试：覆盖本地 derived 规范化、runner 选择，以及 `client.py` 中的 `--local-derived-script` 接线

### Changed（变更）

- 将默认策略从“简单场景只传 `--prompt`，服务端自行刷新 derived_*”调整为“优先 AI 宿主型本地生成，再显式写回 dudu”
- `README.md` 与 `SKILL.md` 同步更新为双模式本地 derived 工作流：默认 `host_ai`，可选 `script_local_ai`
- `config.yaml` 升级到 `0.6.0`，新增本地 derived 的默认模式、runner 与 timeout 配置

### Fixed（修复）

- 修复当 dudu 主项目未配置好 AI/provider 时，skill 侧无法稳定生成 subscription `derived_*` 的默认路径依赖问题

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
