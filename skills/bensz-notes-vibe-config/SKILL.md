---
name: bensz-notes-vibe-config
description: "bensz-notes DevTools 远程管理桥梁：当用户要求通过 bensz-notes 的 DevTools/API Token 管理笔记、目录、标签，或把本地 Markdown 笔记上传、更新、镜像同步到云端（包括目录/文件改名或移动）时使用；也覆盖设置、成员、token、审计和平台治理入口。"
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

## 任务工作区与中间文件

- 调用本 skill 前，先向用户说明 `bensz-notes-vibe-config` 将完成的具体工作；不需要落盘时明确说明不创建目录。
- 需要保存输入引用、预览结果、临时 Markdown、脚本输出或验证日志时，只使用本轮唯一的 `./.bensz-api/task-{yyyymmdd-hhmm}-{简短描述}/`。任务共享材料放 `shared/input|output|log`，本 skill 的材料放 `bensz-notes-vibe-config/input|output|log`。
- `remote.env`、Token 和原始敏感笔记不得复制进任务目录。正式笔记、用户指定导出文件和项目文档仍保存到用户指定或项目约定位置，而不是 `.bensz-api`。
- 连续调用、恢复会话或追加步骤必须复用首次声明的任务目录；不得为同一逻辑任务新建第二个目录。

## 强制安全规则

- 只调用 `{BENSZ_NOTES_URL}{BENSZ_NOTES_API_PREFIX}/*`；默认值见 `config.yaml`。
- 不输出完整 token；日志最多显示脱敏前缀。
- 真实站点测试优先只读：`health`、`doctor`、`notes list`、`folders list`、`tags list`、`sync manifest`。
- 写操作先 `--dry-run`；不得为验证链路创建、发布、删除或重试真实站点已有内容。
- 客户端自动加确定性 `Idempotency-Key` 后才允许保守重试。
- `status=published` 必须显式 `--allow-publish`。
- 删除笔记、同步路径、成员、token 必须显式 `--confirm-delete`。
- 笔记更新/移动和同步删除必须尊重 `baseRevision` / `baseContentHash`；无字段更新、无目标移动、缺少同步删除基线都必须拒绝。
- 工作区上传以本地 Markdown 为权威源。默认只创建/更新本地存在的文件；要让云端严格镜像本地，必须同时传 `--delete-missing --confirm-delete`，将远端缺失路径移入回收站。
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

## 本地优先工作区上传（首选）

当用户说“把本地笔记上传到云端”“更新云端笔记”“让云端与本地对齐”或提到本地目录/文件改名时，优先使用 `scripts/sync_workspace.py`，不要逐文件手工调用 `sync upsert`。它只依赖 Python 标准库，会先读取一次 manifest、跳过内容未变的文件、自动创建目录链。需要保留成功基线以识别后续改名时，显式传入当前任务目录内的 `--state-file`；脚本不会再向用户笔记目录写入隐藏状态。

先预览，再执行本地到云端的增量上传：

```bash
python3 scripts/sync_workspace.py /absolute/path/to/notes --env /path/to/remote.env --dry-run
python3 scripts/sync_workspace.py /absolute/path/to/notes --env /path/to/remote.env \
  --state-file ./.bensz-api/task-{yyyymmdd-hhmm}-{简短描述}/bensz-notes-vibe-config/output/sync-state.json
```

需要“云端绝对等于本地”时，显式确认软删除云端多出的路径：

```bash
python3 scripts/sync_workspace.py /absolute/path/to/notes --env /path/to/remote.env --dry-run --delete-missing --confirm-delete
python3 scripts/sync_workspace.py /absolute/path/to/notes --env /path/to/remote.env --delete-missing --confirm-delete \
  --state-file ./.bensz-api/task-{yyyymmdd-hhmm}-{简短描述}/bensz-notes-vibe-config/output/sync-state.json
```

目录或文件改名后，内容未变的文件会在计划中标为 `rename`，执行时先上传新路径、再软删除旧路径；这适用于整目录重命名。若同一次既改名又改正文，协议无法可靠识别其为同一笔记，仍可用镜像模式完成“新建路径 + 删除旧路径”。所有更新都携带刚读取的远端 revision/hash；若执行期间云端再次变化，脚本停止并报告 `SYNC_CONFLICT`，不得静默覆盖竞态写入。

## Markdown 表格约定

创建或更新含表格的笔记时，优先写标准 GFM Markdown 表格；`bensz-notes` 会在安全渲染时为表格自动添加 `AI-Based-TB` 类并应用默认表格风格。只有迁移旧 blognas 文章或用户明确要求保留原 HTML 时，才保留 `<table class="AI-Based-TB">` 形式；不要为表格写内联样式或脚本。

## 常见任务

- 身份：`python3 scripts/client.py me`
- 笔记：`notes list/show/create/update/append/move/delete/trash-restore/versions/version/restore-version`
- 发布：`python3 scripts/client.py notes update --id <id> --base-revision <n> --status published --allow-publish`
- 目录/标签：`python3 scripts/client.py folders list`、`python3 scripts/client.py tags list`
- 工作区上传：`python3 scripts/sync_workspace.py <本地目录> --env <remote.env> [--dry-run] [--state-file <task-dir>/bensz-notes-vibe-config/output/sync-state.json]`
- 严格镜像：追加 `--delete-missing --confirm-delete`
- 单文件同步 API：`python3 scripts/client.py sync manifest`、`sync upsert`、`sync delete`
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
