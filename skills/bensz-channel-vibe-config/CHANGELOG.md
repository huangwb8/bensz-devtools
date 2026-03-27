# Changelog

All notable changes to `bensz-channel-vibe-config` will be documented in this file.

The format is based on Keep a Changelog.

## [Unreleased]

### Changed（变更）
- 将 skill 名称从 `bensz-channel-devtools` 调整为 `bensz-channel-vibe-config`。
- 同步更新目录名、文档标题、配置元数据、CLI 默认标识与命令示例。
- 新增 `articles create-draft` 安全命令：用于验证文章创建、标签关联、封面参数或幂等键链路时，强制创建草稿，避免误触发 RSS 与邮件推送。
- 更新 `scripts/client.py` 的文章创建帮助文案，明确 `articles create` 默认创建草稿，只有显式传入 `--published` 才会正式发布。
- 更新 `SKILL.md` 与 `README.md`：把“验证链路必须使用草稿”写成硬规则，并提供 `articles create-draft` 的推荐命令路径。
- 在 `SKILL.md` 与 `README.md` 中新增“发布安全红线 / 高风险发布规则”：
  对 `articles create/update/delete` 等可能触发 RSS、邮件订阅的真实内容操作，结果不确定时禁止重试、禁止额外测试、禁止通过更换 `slug` 或轻微改标题重复发文，只允许暂停等待并使用只读命令回查。
- 客户端新增“保守重试”默认策略：非幂等写操作（POST/PUT/PATCH/DELETE）默认不自动重试；仅 `articles create` 在携带幂等键时允许自动重试。
- `articles create` 现默认自动附带确定性 `X-Idempotency-Key`，并支持 `--idempotency-key` 手动覆盖，用于降低网络抖动或重复执行命令导致的重复发文风险。
- `config.yaml` 新增 `write_retry_count`、`article_create_idempotency_enabled`、`article_create_retry_with_idempotency` 与 `article_create_idempotency_prefix` 配置项，并将版本提升到 `1.5.0`。

### Fixed（修复）
- 修复 skill 工作流设计缺陷：此前未把“发布类操作不可用来测试链路，终端返回不稳定时应等待并回查”写成硬规则，可能导致重复文章被推送到订阅流。
- 修复 CLI 行为与安全规则不一致问题：此前代码层面对写操作仍存在自动重试，和“发布结果不确定时不要重试”的策略冲突。
- 修复“为了验证可用性而临时创建文章”缺少安全入口的问题；现在可显式走草稿验证路径，不必冒险使用正式发布做联调。

## [1.3.0] - 2026-03-24

### Added（新增）
- 新增 `tags ensure` 命令：先读取现有标签，若 `slug` / `public_id` / `name` 精确命中则直接复用，否则再创建新标签。
- 新增针对 `tags ensure` 的 CLI 回归测试，锁定“优先复用已有标签、必要时再创建”的行为。

### Changed（变更）
- 更新 `SKILL.md` 与 `README.md`，明确 AI 生成文章标签时必须优先沿用已有标签，并补充标签 RSS、public_id 外链和当前 SEO 能力边界说明。
- 更新 `config.yaml` 版本号到 `1.3.0`，并把 skill 描述同步到“优先复用既有标签”的最新工作流。

## [1.2.0] - 2026-03-18

### Added（新增）
- 新增 `tags list/create/update/delete` CLI，完整对齐上游 `GET/POST/PUT/DELETE /api/vibe/tags`。
- 新增文章标签能力：`articles list` 支持 `--tag-id` 过滤，`articles create/update` 支持重复传入 `--tag-id` 写入 `tag_ids`。
- 新增文章标签清空能力：`articles update --clear-tags` 可显式发送空数组，移除已有标签关联。
- 新增自动化 CLI 回归测试 `scripts/test_client_cli.py`，覆盖 tags 子命令、文章标签过滤/关联/清空以及既有关键能力。

### Changed（变更）
- 更新 `SKILL.md` 与 `README.md`，补齐标签管理、文章标签关联、标签筛选和标识规则说明。
- 更新 `config.yaml` 版本号到 `1.2.0`，并把 skill 描述扩展到“频道、标签、文章、评论和用户”。

### Fixed（修复）
- 修复聚合 skill 与上游 `bensz-channel` 2026-03-18 版 Vibe API 的能力漂移问题，避免出现“服务端已支持标签，但 CLI 无法调用”的错位。

## [1.1.0] - 2026-03-10

### Added（新增）
- 新增频道顶栏显隐参数支持：`channels create/update` 现可通过 `--show-in-top-nav true|false` 对齐最新频道管理能力。
- 新增文章运营参数支持：`articles list` 现支持 `--pinned` / `--featured` 过滤，`articles create/update` 现支持 `slug`、`published_at`、`is_pinned`、`is_featured` 与切换主频道。
- 新增用户管理能力：`users update` 现支持 `--avatar-url`，并新增 `users delete` 命令以对齐现有 API。
- 新增仓库内推荐用法说明：明确在本仓库内优先使用 `--env ./self/remote.env`，同时保持只读使用 `./self`。
- 新增 DevTools skill 回归脚本：通过 `scripts/test/test_bensz_channel_devtools.py` 覆盖新增 CLI 能力与诊断返回码。

### Changed（变更）
- 更新 `SKILL.md` 与 `README.md`：补齐标识规则、服务端约束、最新命令示例与 Docker 重部署后的审查用法。
- 更新 `config.yaml` 版本号到 `1.1.0`，保持 skill 元信息与本次能力对齐同步。

### Fixed（修复）
- 修复 `doctor` 在 heartbeat 返回非 200 时仍报告成功的问题，现会正确返回失败并保留 disconnect 闭环。
- 修复 skill 文档与当前服务端能力漂移的问题，避免遗漏用户删除、文章置顶/精华、频道顶栏显隐等最新操作。

## [1.0.1] - 2026-03-08

### Fixed（修复）
- 修复 `scripts/client.py` 中 `ping` 命令错误要求 `BENSZ_CHANNEL_KEY` 的问题，使首次连通性检查与 `/api/vibe/ping` 的“无需鉴权”约定一致。
- 修复列表查询通过字符串拼接构造 URL 的问题，改为统一 URL 编码，避免搜索词包含空格、`&` 等字符时请求被截断或污染。
- 修复 `doctor` 对 heartbeat `terminate: true` 信号未及时终止的问题，确保在服务端要求中止时立即退出并由连接上下文完成 disconnect。
- 修复 `--url` 覆盖参数未统一标准化的问题，支持像 `localhost:6542` 这样的裸地址自动补全协议。

### Changed（变更）
- 更新 `config.yaml` 中的 `skill_version` 为 `1.0.1`，保持版本号与本次修复同步。
- 新增 `env_search_max_depth` 配置项，并让 `_bdc_env.py` 与 `env_check.py` 共同读取 `config.yaml` 中的搜索深度和候选文件，减少文档/脚本硬编码漂移。
- 更新 `SKILL.md` 的健康检查说明，明确 `ping` 无需 KEY，而 `doctor` 仍需要 KEY 并执行完整连接闭环。
