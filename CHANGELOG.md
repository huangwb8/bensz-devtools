# Changelog

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本遵循语义化版本。

## [Unreleased]

### Changed

- 将 `skills/bensz-channel-devtools` 重命名为 `skills/bensz-channel-vibe-config`
- 同步更新仓库入口文档、skill 元数据、脚本中的默认 skill 名称与命令示例
- 将 `bensz-channel-vibe-config` 的能力说明更新为“频道、标签、文章、评论、用户”，并同步来源仓库路径到 `/Volumes/2T01/winE/Starup/bensz-channel`
- 基于当前仓库实际维护边界，统一文档中的上游业务仓库路径：`dudu` 对齐为 `/Volumes/2T01/winE/Starup/dudu`，`bensz-channel` 对齐为 `/Volumes/2T01/winE/Starup/bensz-channel`
- 统一仓库结构口径：`SKILL.md`、`README.md`、`config.yaml`、`scripts/` 为核心资产，`docs/`、`plans/`、`tests/` 为推荐且可追踪的沉淀目录
- 调整 `.gitignore`：取消忽略整个 `skills/*/plans/` 与 `skills/*/tests/`，只保留缓存/临时产物忽略规则，确保每个 skill 的计划与测试沉淀都能被版本控制追踪
- 为 `skills/dudu-vibe-config/tests/test_client_defaults.py` 增加 `.gitignore` 精确例外，确保本次新增回归测试可被版本控制追踪，同时不放出其他历史批次产物
- 保持 `skills/*/tests/` 持续走 Git 忽略；`bensz-channel-vibe-config` 的核心 CLI 回归脚本改放到 `skills/bensz-channel-vibe-config/scripts/test_client_cli.py`

### Added

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
