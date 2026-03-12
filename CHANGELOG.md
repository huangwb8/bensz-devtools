# Changelog

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本遵循语义化版本。

## [Unreleased]

### Changed

- 将 `skills/bensz-channel-devtools` 重命名为 `skills/bensz-channel-vibe-config`
- 同步更新仓库入口文档、skill 元数据、脚本中的默认 skill 名称与命令示例

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
