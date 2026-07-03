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

## 安全规则

- 不输出完整 token。
- 默认只访问 `{BENSZ_NOTES_URL}{BENSZ_NOTES_API_PREFIX}`。
- 真实站点联调优先只读命令。
- 写操作先 `--dry-run`，再执行真实请求。
- 遇到 `409` 冲突时重新读取远端 revision/hash，不盲写覆盖。
- `sync upsert` 未传 `--status` 时不覆盖既有状态；`sync delete` 必须带 manifest 中的 revision/hash 基线。

## 测试

```bash
python3 -m py_compile scripts/*.py
python3 -m unittest discover -s tests -p 'test_*.py'
```
