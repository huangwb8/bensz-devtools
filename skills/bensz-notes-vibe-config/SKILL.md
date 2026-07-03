---
name: bensz-notes-vibe-config
category: normal
description: "bensz-notes DevTools 远程管理桥梁：当用户要求通过 bensz-notes 的 DevTools/API Token 管理笔记、目录、标签、同步、设置、成员、token、审计或平台治理入口时使用。"
metadata:
  author: Bensz Conan
  short-description: bensz-notes DevTools Agent API 桥梁
  keywords:
    - bensz-notes-vibe-config
    - bensz-notes
    - devtools
    - Agent API Token
    - 笔记管理
    - 同步
    - workspace
---

# bensz-notes-vibe-config

## 目标与边界

把人类管理意图翻译为 `bensz-notes` DevTools Agent API 请求；只操作远程数据，不修改 `/Volumes/2T01/Github/bensz-notes` 源码。设计缺陷先用 `bensz-collect-bugs` 记录，除非用户明确要求公开上报，否则不要上传 bug。

覆盖：认证诊断、笔记 CRUD/版本/回收站、目录、标签、本地同步、设置、workspace 成员、Agent token、审计，以及 super_admin 平台治理只读入口。`raw` 仅作为受限补充：只访问配置的 API base；非 GET 必须 `--confirm-write`。

## 强制安全规则

- 只调用 `{BENSZ_NOTES_URL}{BENSZ_NOTES_API_PREFIX}/*`；默认值见 `config.yaml`。
- 不输出完整 token；日志最多显示脱敏前缀。
- 真实站点测试优先只读：`health`、`doctor`、`notes list`、`folders list`、`tags list`、`sync manifest`。
- 写操作先 `--dry-run`；不得为验证链路创建、发布、删除或重试真实站点已有内容。
- 客户端自动加确定性 `Idempotency-Key` 后才允许保守重试。
- `status=published` 必须显式 `--allow-publish`。
- 删除笔记、同步路径、成员、token 必须显式 `--confirm-delete`。
- 笔记更新/移动和同步删除必须尊重 `baseRevision` / `baseContentHash`；无字段更新、无目标移动、缺少同步删除基线都必须拒绝。
- 遇到 `409 REVISION_CONFLICT` / `SYNC_CONFLICT`：重新读取 note 或 manifest，比较 revision/hash 后再决定。

## 环境变量

- `BENSZ_NOTES_URL`：站点 Web 根地址或 API 地址。
- `BENSZ_NOTES_KEY`：DevTools 创建的 `bnt_...` Agent API Token，或 scoped JWT。
- `BENSZ_NOTES_API_PREFIX`：API 前缀；直连 API 服务时传 `-` 或空值。
- 兼容别名见 `config.yaml`；脚本支持 `--env /path/to/remote.env`。

## 标准工作流

```bash
python3 scripts/env_check.py --env /path/to/remote.env
python3 scripts/client.py --env /path/to/remote.env health
python3 scripts/client.py --env /path/to/remote.env doctor
python3 scripts/client.py --env /path/to/remote.env notes list --limit 5
```

修改前读取现状与 revision：

```bash
python3 scripts/client.py notes show --id <note-id>
python3 scripts/client.py notes versions --id <note-id> --take 5
```

写操作先 dry-run，再带基线执行：

```bash
python3 scripts/client.py --dry-run notes update --id <note-id> --base-revision 3 --title "新标题"
python3 scripts/client.py notes update --id <note-id> --base-revision 3 --title "新标题"
```

## 常见任务

- 身份：`python3 scripts/client.py me`
- 笔记：`notes list/show/create/update/append/move/delete/trash-restore/versions/version/restore-version`
- 发布：`python3 scripts/client.py notes update --id <id> --base-revision <n> --status published --allow-publish`
- 目录/标签：`python3 scripts/client.py folders list`、`python3 scripts/client.py tags list`
- 同步：`python3 scripts/client.py sync manifest`
- 同步写入：`python3 scripts/client.py sync upsert --path folder/note.md --markdown '# Note' --create-folders`
- 同步删除：`python3 scripts/client.py sync delete --path folder/note.md --base-revision 3 --base-content-hash sha256:... --confirm-delete`
- 设置/成员/token/审计：`settings get`、`members list`、`tokens list`、`audit --limit 20`
- 平台治理只读：`admin users/workspaces/notes/note/tokens/audit`

## API 速查

Base：`{BENSZ_NOTES_URL}{BENSZ_NOTES_API_PREFIX}`。认证头：`Authorization: Bearer <BENSZ_NOTES_KEY>`。细节见 `docs/api-contract.md`。

- 无鉴权：`GET /health`、`GET /settings/public`、`GET /settings/console-gate/{suffix}`
- 认证：`GET /auth/me`
- 笔记：`/notes`、`/notes/{id}`、`/notes/{id}/append`、`/notes/{id}/move`、`/notes/{id}/versions`、`/notes/{id}/restore`、`/trash/{id}/restore`
- 同步：`/sync/manifest`、`/sync/notes/by-path/{path}`
- 分类：`/folders`、`/tags`
- 设置/成员/token/审计：`/settings`、`/workspace/members`、`/api-tokens`、`/audit-logs`
- 平台治理：`/admin/users`、`/admin/workspaces`、`/admin/notes`、`/admin/api-tokens`、`/admin/audit-logs`

## 失败处理

- `401/403`：检查 token、scope、workspace 状态。
- `404`：确认 token 所属 workspace；普通 API 不跨 workspace。
- `5xx/503`：不要重复写操作；等待后用只读命令回查。
