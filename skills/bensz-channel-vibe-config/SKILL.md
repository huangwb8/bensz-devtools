---
name: bensz-channel-vibe-config
description: bensz-channel 社区平台 DevTools：通过 API 密钥让 Vibe Coding 工具（Claude Code、Codex 等）远程管理频道、文章、评论和用户，操作数据库层面配置，不修改软件源代码。
metadata:
  author: Bensz Conan
  short-description: bensz-channel 远程管理桥梁（DevTools API）
  keywords:
    - bensz-channel
    - devtools
    - 远程配置
    - channels
    - articles
    - comments
    - users
  category: 运维支持
  platform: Claude Code | OpenAI Codex | Cursor
---

# bensz-channel-vibe-config

## 目标

把“人类的管理意图”稳定翻译为对 `bensz-channel` **DevTools API** 的一组受限操作：

- 频道：列表 / 新增 / 修改 / 删除 / 顶栏显隐
- 文章：列表 / 查看 / 发布 / 修改 / 删除 / 发布状态 / 置顶 / 精华
- 评论：列表 / 修改可见性 / 删除
- 用户：列表 / 修改资料和角色 / 删除普通用户

## 安全边界（强制）

- 只调用 `{BENSZ_CHANNEL_URL}/api/vibe/*`
- 不修改软件源代码，只操作数据（数据库层面）
- 不输出完整 Key；日志中必须脱敏（仅显示前缀）
- 所有变更类请求（POST / PUT / PATCH / DELETE）默认使用 `connect → 执行 → disconnect` 闭环
- 若服务端 heartbeat 返回 `terminate: true`：立刻停止操作并 disconnect
- `ping` 可无 KEY 执行；`doctor` 和所有鉴权接口必须带 KEY

## 环境变量

所需变量：

- `BENSZ_CHANNEL_URL`：默认 `http://localhost:6542`
- `BENSZ_CHANNEL_KEY`：长度需 ≥ 20

兼容别名：URL 支持 `bensz_channel_url` / `bdc_url`，KEY 支持 `bensz_channel_key` / `bdc_key`。

脚本均支持通过 `--env /path/to/.env` 显式传入 `.env` 文件以完成鉴权。

## 首次使用流程

1. 登录 bensz-channel 管理界面，进入 **管理员 → DevTools 远程管理**
2. 生成一个 API 密钥并复制（仅显示一次）
3. 配置环境变量或 `.env`
4. 验证连接：
   ```bash
   python3 scripts/env_check.py
   python3 scripts/client.py ping
   python3 scripts/client.py doctor
   ```

## 标准工作流

1. **环境检查**
   ```bash
   python3 scripts/env_check.py
   python3 scripts/env_check.py --verbose
   ```

2. **连通性验证**
   ```bash
   python3 scripts/client.py ping
   python3 scripts/client.py doctor
   ```

3. **执行管理命令**
   ```bash
   python3 scripts/client.py channels list
   python3 scripts/client.py --env /path/to/.env articles list --published true
   ```

## 标识规则

- `channels update/show/delete`：支持 **数值 ID / `public_id` / `slug`**
- `articles show/update/delete`：支持 **数值 ID / `public_id` / `slug`**
- `comments update/delete`：使用 **数值 ID**
- `users update/delete`：使用 **数值 ID**

## 常见任务映射

| 意图 | 命令 |
|------|------|
| 查看所有频道 | `channels list` |
| 新增频道并隐藏顶栏入口 | `channels create --name 公告 --icon 📢 --accent-color '#3b82f6' --show-in-top-nav false` |
| 修改频道顶栏显隐 | `channels update --id 1 --show-in-top-nav true` |
| 查看文章列表 | `articles list --published true --featured true` |
| 发布文章并置顶 | `articles create --channel-id 1 --title 标题 --body 正文 --published --pinned` |
| 发布文章并设为精华 | `articles create --channel-id 1 --title 标题 --body 正文 --published --featured` |
| 将文章切换频道 | `articles update --id 42 --channel-id 3` |
| 隐藏评论 | `comments update --id 42 --visible false` |
| 删除评论 | `comments delete --id 42` |
| 查看用户 | `users list --role member` |
| 修改用户头像 | `users update --id 1 --avatar-url https://cdn.example.com/a.png` |
| 删除普通用户 | `users delete --id 1` |

## 服务端约束

- `featured`（精华）频道只负责聚合展示，**不能**作为文章主频道
- 用户更新时，邮箱与手机号至少保留一个
- **最后一位管理员不可降级**
- **管理员账号不可通过 DevTools 删除**
- `doctor` 在 heartbeat 非 200 或 `terminate: true` 时会返回失败

## API 端点速查

所有端点 Base URL：`{BENSZ_CHANNEL_URL}/api/vibe`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/ping` | 健康检查（无需鉴权） |
| POST | `/connect` | 建立连接 |
| POST | `/heartbeat` | 发送心跳 |
| POST | `/disconnect` | 断开连接 |
| GET | `/channels` | 频道列表 |
| POST | `/channels` | 创建频道 |
| PUT | `/channels/{channel}` | 更新频道 |
| DELETE | `/channels/{channel}` | 删除频道 |
| GET | `/articles` | 文章列表（支持 `channel_id` / `published` / `pinned` / `featured` 过滤） |
| GET | `/articles/{article}` | 文章详情 |
| POST | `/articles` | 创建文章 |
| PUT | `/articles/{article}` | 更新文章 |
| DELETE | `/articles/{article}` | 删除文章 |
| GET | `/comments` | 评论列表（支持 `article_id` / `visible` 过滤） |
| PATCH | `/comments/{comment}` | 更新评论（如修改可见性） |
| DELETE | `/comments/{comment}` | 删除评论 |
| GET | `/users` | 用户列表（支持 `q` / `role` 过滤） |
| PUT | `/users/{user}` | 更新用户 |
| DELETE | `/users/{user}` | 删除普通用户 |

认证方式：请求头 `X-Devtools-Key: <你的密钥>`
