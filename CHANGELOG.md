# Changelog

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本遵循语义化版本。

## [Unreleased]

### Changed

- 对齐全部 bridge skill 的中间文件约定：`SKILL.md`、README 与聚合索引统一使用本轮唯一的 `./.bensz-api/task-{yyyymmdd-hhmm}-{简短描述}/shared|{skill名}/input|output|log`，并明确凭据、正式交付物和同一逻辑任务目录复用边界。
- 调整 `bensz-notes-vibe-config` 的 `sync_workspace.py`：不再默认向用户笔记目录写入 `.bensz-notes/sync-state.json`；需要改名识别基线时，调用方必须显式用 `--state-file` 指向当前 `.bensz-api` 任务目录。
- 更新 `README.md`、`skills/README.md` 与 `.gitignore`：登记 `bensz-notes-vibe-config` 的本地优先工作区上传/镜像同步能力，并将其新增回归测试纳入版本控制。
- 调整 `.gitignore`：新增 `.bensz-api/` 与 `skills/*/.bensz-api/` 忽略规则，隔离 auto-test/compact 等本地执行产物
- 基于 2026-04-19 对 `/Volumes/2T01/winE/Starup/dudu` 最新 `Vibe Agent` 源码再次审计，更新 `skills/dudu-vibe-config` 的契约口径：补充风格市场/可见性、最后一个订阅删除时的 orphan 清理闭环、Vibe 仍未开放 `searchMode`、以及 `rss_opml` 模板在当前 Vibe 路由下仍要求非空 `query` 等边界
- 同步更新仓库级入口文档：`AGENTS.md`、`README.md`、`skills/README.md` 统一反映 `dudu-vibe-config` 的最新范围与 `bensz-channel-vibe-config` 的标签能力
- 调整 `.gitignore`：为 `skills/dudu-vibe-config/plans/2026-04-19-vibe-contract-audit-and-hardening.md` 增加精确例外，保留本轮计划沉淀，同时继续忽略其它历史批次产物
- 使用 `compact-bensz-skills` 收紧 `skills/dudu-vibe-config` 与 `skills/bensz-channel-vibe-config` 的工作型 Markdown，保留触发语义、关键命令、安全边界与默认路径，同时降低上下文体积
- 基于 2026-04-13 对 `dudu` 最新 `/vibe/agent/*` 源码审计，同步更新仓库入口文档：`dudu-vibe-config` 的能力范围扩展为“模板、报道风格、订阅、报道、域名规则”
- 将 `skills/bensz-channel-devtools` 重命名为 `skills/bensz-channel-vibe-config`
- 同步更新仓库入口文档、skill 元数据、脚本中的默认 skill 名称与命令示例
- 将 `bensz-channel-vibe-config` 的能力说明更新为“频道、标签、文章、评论、用户”，并同步来源仓库路径到 `/Volumes/2T01/winE/Starup/bensz-channel`
- 基于当前仓库实际维护边界，统一文档中的上游业务仓库路径：`dudu` 对齐为 `/Volumes/2T01/winE/Starup/dudu`，`bensz-channel` 对齐为 `/Volumes/2T01/winE/Starup/bensz-channel`
- 统一仓库结构口径：`SKILL.md`、`README.md`、`config.yaml`、`scripts/` 为核心资产，`docs/`、`plans/`、`tests/` 为推荐且可追踪的沉淀目录
- 调整 `.gitignore`：取消忽略整个 `skills/*/plans/` 与 `skills/*/tests/`，只保留缓存/临时产物忽略规则，确保每个 skill 的计划与测试沉淀都能被版本控制追踪
- 为 `skills/dudu-vibe-config/tests/test_client_defaults.py` 增加 `.gitignore` 精确例外，确保本次新增回归测试可被版本控制追踪，同时不放出其他历史批次产物
- 保持 `skills/*/tests/` 持续走 Git 忽略；`bensz-channel-vibe-config` 的核心 CLI 回归脚本改放到 `skills/bensz-channel-vibe-config/scripts/test_client_cli.py`
- 调整 `.gitignore`：新增 `skills/*/.compact-bensz-skills/`，隔离技能压缩产生的隐藏工作区与统计产物

### Added

- `dudu-vibe-config` 新增 `sourceType=hybrid` 订阅创建透传、18 个高质量访谈/观点节目公开 RSS 的 OPML 配置，以及 RSS 优先、搜索补充的订阅说明。

- 新增 `skills/bensz-notes-vibe-config`：基于 `/Volumes/2T01/Github/bensz-notes` 的 API 文档与控制器源码，提供 DevTools Agent API Token 客户端、环境检查、笔记/目录/标签/同步/设置/成员/token/审计/平台治理入口与单元测试
- 为 `skills/dudu-vibe-config` 新增 2026-04-19 契约审计计划沉淀，并补充最新 Vibe 边界回归测试
- 为 `skills/bensz-channel-vibe-config` 新增 tags 管理能力、文章标签关联/筛选/清空能力，以及自动化 CLI 回归测试

## [1.0.0] - 2026-03-12

### Added

- 初始化聚合仓库级文档：`AGENTS.md`、`CLAUDE.md`、`README.md`、`.gitignore`
- 从 `dudu-devtools` 迁入 `skills/dudu-vibe-config`
- 从 `bensz-channel` 迁入 `skills/bensz-channel-vibe-config`
- 新增迁移计划文档 `docs/plans/2026-03-12-vibe-skill-migration.md`
- 新增 `skills/README.md` 作为聚合技能索引

### Changed

- 将仓库定位从通用“文档项目”修正为“vibe / devtools 远程桥梁 skill 聚合仓库”
- 为当前以 Python 脚本为主的 skill 目录补充缓存与环境文件忽略规则

### Fixed

- 清理迁移过程中的系统垃圾与缓存文件，不把 `.DS_Store`、`__pycache__/`、`*.pyc` 带入仓库
