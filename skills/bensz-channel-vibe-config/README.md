# bensz-channel-vibe-config

通过 Vibe Coding 工具（Claude Code、Codex CLI 等）远程管理 bensz-channel 社区平台内容。

## 快速上手

### 1. 获取 API 密钥

登录 bensz-channel → 管理员菜单 → **DevTools 远程管理** → 生成 API 密钥（仅显示一次，请立即保存）。

### 2. 配置环境变量

**通用方式：使用配置向导**

```bash
cd skills/bensz-channel-vibe-config
python3 scripts/env_init.py
```

**在本仓库内工作时，推荐直接复用现成配置：**

```bash
python3 skills/bensz-channel-vibe-config/scripts/env_check.py --env ./self/remote.env
python3 skills/bensz-channel-vibe-config/scripts/client.py --env ./self/remote.env ping
```

说明：

- `./self/remote.env` 仅作为配置输入使用
- 不要修改 `./self` 里的任何文件
- 如果不在本仓库里，可改为自己的 `.env` 文件路径

**手动配置方式：**

```bash
export BENSZ_CHANNEL_URL=http://your-server:6542
export BENSZ_CHANNEL_KEY=bdc_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

cat > .env << 'EOF_ENV'
BENSZ_CHANNEL_URL=http://your-server:6542
BENSZ_CHANNEL_KEY=bdc_xxxxxxxx...
EOF_ENV
```

### 3. 验证连接

```bash
cd skills/bensz-channel-vibe-config
python3 scripts/env_check.py
python3 scripts/env_check.py --verbose
python3 scripts/client.py ping
python3 scripts/client.py doctor
```

## 标识规则

- 频道：`--id` 支持 **数值 ID / public_id / slug**
- 标签：`--id` 支持 **数值 ID / public_id / slug**
- `tags ensure` 会先按 **slug / public_id / name** 查找现有标签；命中则复用，未命中才新建
- 文章：`--id` 支持 **数值 ID / public_id / slug**
- 文章标签：`articles list --tag-id`、`articles create/update --tag-id` 使用 **标签数值 ID**
- 评论：`--id` 使用 **数值 ID**
- 用户：`--id` 使用 **数值 ID**

## 标签复用优先

当 AI 或脚本要为文章生成标签时，推荐固定遵循下面的顺序：

1. 先执行 `python3 scripts/client.py tags list` 查看现有标签。
2. 如果已有语义一致或完全等价的标签，直接复用已有标签，不再重复创建。
3. 只有在确实没有合适标签时，才执行 `tags ensure` 或 `tags create` 新建。

推荐命令：

```bash
python3 scripts/client.py tags ensure --name Laravel --slug laravel --description "Laravel 相关文章"
```

`tags ensure` 会先读取现有标签；如果 `name`、`slug` 或 `public_id` 精确命中已有标签，就直接返回该标签。只有未命中时，才会走创建流程。

## 常用命令

```bash
# 频道管理
python3 scripts/client.py channels list
python3 scripts/client.py channels create --name 公告 --icon 📢 --accent-color '#3b82f6' --show-in-top-nav false
python3 scripts/client.py channels update --id 1 --name 新名称 --show-in-top-nav true
python3 scripts/client.py channels delete --id 1

# 文章管理
python3 scripts/client.py articles list
python3 scripts/client.py articles list --channel-id 1 --published true --featured true
python3 scripts/client.py articles list --tag-id 2 --published true
python3 scripts/client.py articles show --id 42
python3 scripts/client.py articles create \
  --channel-id 1 \
  --title "Hello World" \
  --body "这是正文内容" \
  --published \
  --tag-id 2 \
  --tag-id 7 \
  --pinned
python3 scripts/client.py articles create \
  --channel-id 1 \
  --title "精选文章" \
  --body "正文" \
  --published \
  --featured
python3 scripts/client.py articles update --id 42 --channel-id 3 --title "新标题" --featured true --tag-id 2 --tag-id 7
python3 scripts/client.py articles update --id 42 --clear-tags
python3 scripts/client.py articles delete --id 42

# 标签管理
python3 scripts/client.py tags list
python3 scripts/client.py tags ensure --name Laravel --slug laravel --description "Laravel 相关文章"
python3 scripts/client.py tags create --name Laravel --slug laravel --description "Laravel 相关文章"
python3 scripts/client.py tags update --id laravel --name "Laravel 12"
python3 scripts/client.py tags delete --id laravel

# 评论管理
python3 scripts/client.py comments list
python3 scripts/client.py comments list --article-id 42 --visible false
python3 scripts/client.py comments update --id 10 --visible false
python3 scripts/client.py comments delete --id 10

# 用户管理
python3 scripts/client.py users list
python3 scripts/client.py users list --q alice --role member
python3 scripts/client.py users update --id 5 --role admin --avatar-url "https://cdn.example.com/avatar.png"
python3 scripts/client.py users delete --id 5

# 使用特定 .env 文件
python3 scripts/client.py --env /path/to/.env channels list
```

## 发布安全红线

- `articles create`、`articles update --published true`、`articles delete` 会影响真实内容流，可能触发 RSS、邮件订阅或外部收录。
- 因此，**不要**为了测试链路或确认接口状态去多发一篇“占位文章”“测试文章”或“同文不同 slug 的重复文章”。
- 如果一次发布后终端输出不完整、执行会话卡住、网络看起来不稳定，默认把它当成“服务端可能已经成功接收”的情况处理。
- 这时只做两件事：
  1. 暂停等待一会，不做新的写操作
  2. 用只读命令回查：
     ```bash
     python3 scripts/client.py articles list --channel-id 7 --published true
     python3 scripts/client.py articles show --id <slug-or-public-id>
     ```
- **禁止**通过再次 `articles create`、改 `slug` 重发、轻微改标题重发等方式测试是否成功；这会制造重复内容，并且订阅推送通常无法撤回。
- 如果请求看起来没跑通，优先判断为网络或终端侧暂时不稳定；多数情况下，等待后再回查比重试更安全。

## 服务端约束

- 只允许调用 `/api/vibe/*` 端点
- 不修改软件源代码，只操作数据库内容
- 精华频道不能作为文章主频道
- 公开文章、频道、标签及对应 RSS 外链当前统一以 `public_id` 作为规范标识
- 文章标签关联通过 `tag_ids` 数组完成，需传标签数值 ID
- 标签 RSS 入口为 `/feeds/tags/{tag-public-id}.xml`；全站与频道 RSS 分别为 `/feeds/articles.xml`、`/feeds/channels/{channel-public-id}.xml`
- 站点 SEO、canonical、Open Graph、Twitter Card、`robots.txt` 与 `sitemap.xml` 由服务端自动生成；当前 DevTools API 不提供单独的 SEO 设置写接口
- 用户至少保留一个联系方式（邮箱或手机号）
- 最后一位管理员不可降级
- 管理员账号不可通过 DevTools 删除
- `doctor` 在 heartbeat 非 200 或服务端要求 terminate 时会返回失败

## 故障排查

| 错误 | 原因 | 解决 |
|------|------|------|
| `Missing BENSZ_CHANNEL_KEY` | 未配置密钥 | 设置环境变量或 `.env` |
| `HTTP 401 invalid_or_revoked_api_key` | 密钥无效或已撤销 | 重新生成密钥 |
| `connect failed` | 服务器不可达或 KEY 无效 | 检查 URL、容器状态、密钥 |
| `heartbeat.status != 200` | 连接已失效或服务端拒绝继续 | 重新执行 `doctor` 并检查后台 DevTools 连接状态 |
| `HTTP 422` | 参数验证失败 | 检查 JSON 响应中的字段错误 |
