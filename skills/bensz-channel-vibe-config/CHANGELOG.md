# Changelog

All notable changes to `bensz-channel-vibe-config` will be documented in this file.

The format is based on Keep a Changelog.

## [Unreleased]

### Changed（变更）
- 将 skill 名称从 `bensz-channel-devtools` 调整为 `bensz-channel-vibe-config`。
- 同步更新目录名、文档标题、配置元数据、CLI 默认标识与命令示例。

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
