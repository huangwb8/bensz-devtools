# bensz-notes-vibe-config

`bensz-notes-vibe-config` 是 `bensz-notes` 的 DevTools 远程管理桥梁。它通过 DevTools 页面生成的 Agent API Token 调用后端 API，让 Codex / Claude Code 等 Agent 可以安全地管理笔记、目录、标签、同步清单、设置、成员、token 和审计入口。

## 环境配置

推荐在本仓库根目录的 `remote.env` 中配置：

```bash
BENSZ_NOTES_URL=https://your-notes.example.com
BENSZ_NOTES_KEY=bnt_your_agent_api_token
```

如果直连 API 服务而不是 Web 代理，额外设置：

```bash
BENSZ_NOTES_API_PREFIX=-
```

## 快速验证

```bash
cd skills/bensz-notes-vibe-config
python3 scripts/env_check.py --env ../../remote.env
python3 scripts/client.py --env ../../remote.env health
python3 scripts/client.py --env ../../remote.env doctor
python3 scripts/client.py --env ../../remote.env notes list --limit 5
```

## Agent 中间工作区

需要保存预览、临时 Markdown、命令输出或验证日志时，使用本轮唯一的 `./.bensz-api/task-{yyyymmdd-hhmm}-{简短描述}/`：共享材料放 `shared/input|output|log`，本 skill 材料放 `bensz-notes-vibe-config/input|output|log`。不要把 Token、`remote.env` 或不必要的原始笔记复制进去；正式笔记和用户指定交付物仍放项目约定或用户指定位置。

首次声明任务目录后，后续步骤必须复用它，不得为同一逻辑任务另建目录。

## 本地笔记上传与镜像同步

本 skill 的工作区同步采用“本地优先”语义：本地 Markdown 是要上传的最新版本。它会读取一次云端 manifest，仅上传新增或内容变化的文件。若要保存成功基线并识别后续的改名，请显式把 `--state-file` 放入当前 `.bensz-api` 任务目录；脚本默认不再向本地笔记工作区写入隐藏状态。

先预览实际动作，再上传：

```bash
cd skills/bensz-notes-vibe-config
python3 scripts/sync_workspace.py /absolute/path/to/local-notes --env ../../remote.env --dry-run
python3 scripts/sync_workspace.py /absolute/path/to/local-notes --env ../../remote.env \
  --state-file ../../.bensz-api/task-{yyyymmdd-hhmm}-{简短描述}/bensz-notes-vibe-config/output/sync-state.json
```

普通上传不会删除云端独有的笔记。若目标是让云端严格镜像本地，请先确认预览中的删除项，再显式执行：

```bash
python3 scripts/sync_workspace.py /absolute/path/to/local-notes --env ../../remote.env --dry-run --delete-missing --confirm-delete
python3 scripts/sync_workspace.py /absolute/path/to/local-notes --env ../../remote.env --delete-missing --confirm-delete \
  --state-file ../../.bensz-api/task-{yyyymmdd-hhmm}-{简短描述}/bensz-notes-vibe-config/output/sync-state.json
```

目录或文件名改变时，未改正文的项目会自动识别为 `rename`：先在新路径创建/更新，再将旧路径软删除。一次同时改名和改正文时无法从路径协议中安全判定同一身份，镜像模式会按“新路径 + 删除旧路径”处理。执行窗口内发生远端并发修改会返回 `SYNC_CONFLICT` 并停止，重新预览后再处理。

## 常用命令

```bash
# 当前身份
python3 scripts/client.py me

# 笔记
python3 scripts/client.py notes list --q keyword --limit 20
python3 scripts/client.py notes show --id <note-id>
python3 scripts/client.py notes create --title "草稿" --markdown "# 草稿"
python3 scripts/client.py notes update --id <note-id> --base-revision 3 --title "新标题"

# 版本与回收站
python3 scripts/client.py notes versions --id <note-id> --take 10
python3 scripts/client.py notes restore-version --id <note-id> --revision 2
python3 scripts/client.py notes trash-restore --id <note-id>

# 同步
python3 scripts/client.py sync manifest
python3 scripts/client.py sync upsert --path folder/note.md --markdown "# Note" --create-folders
python3 scripts/client.py sync delete --path folder/note.md --base-revision 3 --base-content-hash sha256:... --confirm-delete

# 工作区级本地优先上传（推荐）
python3 scripts/sync_workspace.py /absolute/path/to/local-notes --env ../../remote.env --dry-run
python3 scripts/sync_workspace.py /absolute/path/to/local-notes --env ../../remote.env \
  --state-file ../../.bensz-api/task-{yyyymmdd-hhmm}-{简短描述}/bensz-notes-vibe-config/output/sync-state.json

# 目录、标签、设置、成员、审计
python3 scripts/client.py folders list
python3 scripts/client.py tags list
python3 scripts/client.py settings get
python3 scripts/client.py members list
python3 scripts/client.py audit --limit 20
```

发布和删除必须显式确认：

```bash
python3 scripts/client.py notes update --id <note-id> --base-revision 4 --status published --allow-publish
python3 scripts/client.py notes delete --id <note-id> --confirm-delete
python3 scripts/client.py tokens revoke --id <token-id> --confirm-delete
```

## Markdown 表格

新增或更新笔记时，优先使用标准 GFM Markdown 表格。`bensz-notes` 公开渲染会自动为表格应用 `AI-Based-TB` 默认样式；只有迁移旧 blognas HTML 表格时才需要保留 `<table class="AI-Based-TB">`。

## 安全规则

- 不输出完整 token。
- 默认只访问 `{BENSZ_NOTES_URL}{BENSZ_NOTES_API_PREFIX}`。
- 真实站点联调优先只读命令。
- 写操作先 `--dry-run`，再执行真实请求。
- 遇到 `409` 冲突时重新读取远端 revision/hash，不盲写覆盖。
- `sync upsert` 未传 `--status` 时不覆盖既有状态；`sync delete` 必须带 manifest 中的 revision/hash 基线。
- 工作区同步只有在同时提供 `--delete-missing --confirm-delete` 时才会删除云端多余路径；删除是可恢复的软删除。

## 测试

```bash
python3 -m py_compile scripts/*.py
python3 -m unittest discover -s tests -p 'test_*.py'
```
