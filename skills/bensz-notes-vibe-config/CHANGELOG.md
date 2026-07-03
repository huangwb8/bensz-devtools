# Changelog

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [0.1.0] - 2026-07-03

### Added

- 初始化 `bensz-notes-vibe-config` bridge skill。
- 新增零依赖 Python 客户端，支持环境检查、健康检查、身份读取、笔记/目录/标签/同步/设置/成员/token/审计/平台治理只读入口。
- 增加发布、删除、幂等键和同步路径校验保护，避免真实站点联调误污染数据。
- 增加无字段更新、无目标移动、空设置 PATCH、同步删除缺少基线等防误操作保护。
- 删除未使用的 `write_retry_count` 配置，统一由幂等键策略控制写操作重试。
- 新增 CLI 单元测试覆盖环境解析、dry-run、发布保护、删除确认和同步路径校验。
