---
name: bensz-channel-vibe-config
description: bensz-channel 社区平台 DevTools：通过 API 密钥让 Vibe Coding 工具（Claude Code、Codex 等）远程管理频道、标签、文章、评论和用户，操作数据库层面配置，不修改软件源代码。
metadata:
  author: Bensz Conan
  short-description: bensz-channel 远程管理桥梁（DevTools API）
  keywords:
    - bensz-channel-vibe-config
    - bensz-channel
    - devtools
    - 远程配置
    - channels
    - tags
    - articles
    - comments
    - users
  category: 运维支持
  platform: Claude Code | OpenAI Codex | Cursor
---

# bensz-channel-vibe-config

## 与 bensz-collect-bugs 的协作约定

- 设计缺陷先用 `bensz-collect-bugs` 记录到 `~/.bensz-skills/bugs/`，不要直接改用户本地已安装的 skill。
- 若存在 workaround：先记 bug，再继续完成任务。
- 只有用户明确要求公开上报时，才用 `gh` 上传新增 bug；不要 pull / clone 整个 bug 仓库。

## 目标

把“人类的管理意图”翻译为对 `bensz-channel` `DevTools API` 的受限操作，仅覆盖：
- 频道：列表 / 新增 / 修改 / 删除 / 顶栏显隐
- 标签：列表 / 复用优先创建 / 新增 / 修改 / 删除
- 文章：列表 / 查看 / 验证草稿 / 发布 / 修改 / 删除 / 置顶 / 精华 / 标签关联
- 评论：列表 / 改可见性 / 删除
- 用户：列表 / 修改资料和角色 / 删除普通用户

## 安全边界（强制）

- 只调用 `{BENSZ_CHANNEL_URL}/api/vibe/*`
- 不修改软件源代码，只操作数据（数据库层面）
- 不输出完整 Key；日志中必须脱敏（仅显示前缀）
- 所有变更类请求（POST / PUT / PATCH / DELETE）默认使用 `connect → 执行 → disconnect` 闭环
- 所有变更类请求一旦发出，**禁止**把“再次执行一次”当作测试或确认手段；结果不确定时只能暂停等待，然后用只读命令回查
- 客户端默认启用“保守重试”策略：非幂等写操作默认不自动重试；仅 `articles create` 在携带幂等键时允许自动重试
- 若服务端 heartbeat 返回 `terminate: true`：立刻停止操作并 disconnect
- `ping` 可无 KEY 执行；`doctor` 和所有鉴权接口必须带 KEY

## 高风险发布规则（强制）

- `articles create`、`articles update --published true`、`articles delete` 属于**高风险不可逆操作**：可能触发 RSS、邮件订阅、Webhook 或外部索引收录。
- 只要是在验证“创建文章 / 绑定标签 / 封面参数 / 幂等键”等链路，**只允许创建草稿**。
- 验证链路优先使用 `python3 scripts/client.py articles create-draft ...`；该命令会强制 `is_published=false`。
- `articles create` 默认自动附带确定性 `X-Idempotency-Key`（同 URL + 同 payload 生成同一个 key），用于降低网络抖动导致的重复发文风险。
- 需要跨终端 / 跨会话对齐时，可显式传入 `--idempotency-key <key>` 覆盖自动 key。
- 对这些操作，**任何时间都不允许为了测试链路而额外发布 / 删除 / 重发文章**。
- 若终端输出延迟、会话返回不稳定或网络疑似抖动，默认视为“服务端可能已接受”，**不要重试**。
- 正确做法只有两步：先等待，再用只读命令回查，例如 `articles list` / `articles show`。
- **禁止**通过换 `slug`、微调标题、复制正文再发一篇等方式“确认是否成功”；这会制造重复内容并污染订阅流。
- 如果用户明确要发正式文章，AI 必须把“避免重复推送”放在首位，宁可多等一会，也不能多发一次。

## 环境变量

- `BENSZ_CHANNEL_URL`：默认 `http://localhost:6542`
- `BENSZ_CHANNEL_KEY`：长度需 ≥ 20
- URL 兼容别名：`bensz_channel_url`、`bdc_url`
- KEY 兼容别名：`bensz_channel_key`、`bdc_key`
- 脚本支持 `--env /path/to/.env` 显式指定配置文件

## 首次使用流程

1. 在 bensz-channel 管理界面进入“管理员 → DevTools 远程管理”
2. 生成 API 密钥并保存
3. 配置环境变量或 `.env`
4. 验证连接：

```bash
python3 scripts/env_check.py
python3 scripts/client.py ping
python3 scripts/client.py doctor
```

## 标准工作流

1. 环境检查

   ```bash
   python3 scripts/env_check.py
   python3 scripts/env_check.py --verbose
   ```

2. 连通性验证

   ```bash
   python3 scripts/client.py ping
   python3 scripts/client.py doctor
   ```

3. 先用只读命令看现状，再做写操作

   ```bash
   python3 scripts/client.py channels list
   python3 scripts/client.py --env /path/to/.env articles list --published true
   ```

4. 处理文章标签时，先复用已有标签

   ```bash
   python3 scripts/client.py tags list
   python3 scripts/client.py tags ensure --name Laravel --description 'Laravel 相关文章'
   python3 scripts/client.py articles create-draft --channel-id 1 --title 标题 --body 正文 --tag-id 2
   ```

   规则：
   - AI 生成文章标签时，**必须先检查已有标签**，优先沿用语义一致的既有标签。
   - `tags ensure` 会先读取现有标签；若 `name`、`slug` 或 `public_id` 精确命中，则直接复用，否则再创建。
   - 只是验证“文章创建 + 标签关联”链路时，必须停留在草稿状态，不要补 `--published`。

5. 写操作结果不确定时，暂停并回查

   ```bash
   python3 scripts/client.py articles list --channel-id 7 --published true
   python3 scripts/client.py articles show --id <slug-or-public-id>
   ```

   规则：
   - 对 `articles create/update/delete`，如果终端返回不稳定、输出缺失或疑似网络抖动，**不要再次执行写操作**。
   - 默认假设“服务端可能已经成功处理”，先等待，再用 `list/show` 回查。
   - 除非用户明确要求补救，且已确认前一次写操作未生效，否则不允许再次发文。

## 标识规则

- `channels show/update/delete`：支持数值 ID / `public_id` / `slug`
- `tags update/delete`：支持数值 ID / `public_id` / `slug`
- `tags ensure`：按 `slug → public_id → name` 优先复用已有标签，命中失败时才创建
- `articles show/update/delete`：支持数值 ID / `public_id` / `slug`
- `articles list --tag-id` 与 `articles create/update --tag-id`：使用标签数值 ID
- `comments`、`users` 的 update/delete：使用数值 ID

## 常见任务映射

- 查看频道：`channels list`
- 新增频道并隐藏顶栏：`channels create --name 公告 --icon 📢 --accent-color '#3b82f6' --show-in-top-nav false`
- 查看 / 复用标签：`tags list`、`tags ensure --name Laravel --slug laravel --description 'Laravel 相关文章'`
- 创建验证草稿并绑定标签：`articles create-draft --channel-id 1 --title 标题 --body 正文 --tag-id 2`
- 正式发布文章：`articles create --channel-id 1 --title 标题 --body 正文 --published`
- 指定幂等键发布：`articles create --channel-id 1 --title 标题 --body 正文 --published --idempotency-key release-20260327-a1`
- 更新文章频道 / 标签：`articles update --id 42 --channel-id 3`、`articles update --id 42 --tag-id 2 --tag-id 7`
- 清空文章标签：`articles update --id 42 --clear-tags`
- 隐藏或删除评论：`comments update --id 42 --visible false`、`comments delete --id 42`
- 查看或删除普通用户：`users list --role member`、`users delete --id 1`

## 服务端约束

- `featured`（精华）频道只负责聚合展示，**不能**作为文章主频道
- 公开页面与 RSS 链接当前统一以 `public_id` 作为规范外链；`slug` 仍可用于部分兼容访问，但不应再把它当作长期稳定外链
- 标签 RSS 已由上游公开为 `/feeds/tags/{tag-public-id}.xml`；全站和频道 RSS 分别为 `/feeds/articles.xml`、`/feeds/channels/{channel-public-id}.xml`
- 首页、频道页、文章页、RSS alternate、`robots.txt` 与 `sitemap.xml` 的 SEO 输出由服务端自动生成；当前 DevTools API **没有**单独暴露站点级 SEO 配置写接口
- 用户更新时，邮箱与手机号至少保留一个
- **最后一位管理员不可降级**
- **管理员账号不可通过 DevTools 删除**
- `doctor` 在 heartbeat 非 200 或 `terminate: true` 时会返回失败

## API 端点速查

Base URL：`{BENSZ_CHANNEL_URL}/api/vibe`
- 无鉴权：`GET /ping`
- 连接闭环：`POST /connect`、`POST /heartbeat`、`POST /disconnect`
- 频道：`/channels`、`/channels/{channel}`
- 标签：`/tags`、`/tags/{tag}`
- 文章：`/articles`、`/articles/{article}`
- 评论：`/comments`、`/comments/{comment}`，更新使用 `PATCH`
- 用户：`/users`、`/users/{user}`
- 认证头：`X-Devtools-Key: <key>`
- `articles create` 支持 `X-Idempotency-Key`；skill 默认自动注入，也可手动传入
