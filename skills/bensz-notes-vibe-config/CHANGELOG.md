# Changelog

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [Unreleased]

### Changed

- 补充 Markdown 表格写作约定：优先使用 GFM 表格，由 bensz-notes 渲染层自动应用 `AI-Based-TB` 默认风格。
- 移除 `SKILL.md` frontmatter 中的非标准 `category` 字段，兼容 Codex skill 校验器。
- 将本地 Markdown 工作区上传设为本地优先的标准同步路径，并在 SKILL/README 中明确其触发场景与镜像删除确认流程。

### Added

- 新增 `scripts/sync_workspace.py`：一次读取远端 manifest 后批量创建、更新或跳过本地 Markdown，使用内容 hash、确定性幂等键与 revision/hash 基线保证快速、可重试的安全上传。
- 新增工作区级 `.bensz-notes/sync-state.json` 状态管理，以及对未改正文的文件/目录改名的自动识别；镜像模式按“上传新路径、软删除旧路径”收敛云端状态。
- 新增工作区同步单元测试，覆盖扫描排除、哈希、目录改名、本地优先更新和删除预览。

## [0.1.0] - 2026-07-03

### Added

- 初始化 `bensz-notes-vibe-config` bridge skill。
- 新增零依赖 Python 客户端，支持环境检查、健康检查、身份读取、笔记/目录/标签/同步/设置/成员/token/审计/平台治理只读入口。
- 增加发布、删除、幂等键和同步路径校验保护，避免真实站点联调误污染数据。
- 增加无字段更新、无目标移动、空设置 PATCH、同步删除缺少基线等防误操作保护。
- 删除未使用的 `write_retry_count` 配置，统一由幂等键策略控制写操作重试。
- 新增 CLI 单元测试覆盖环境解析、dry-run、发布保护、删除确认和同步路径校验。
