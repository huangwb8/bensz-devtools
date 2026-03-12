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
- 文章：`--id` 支持 **数值 ID / public_id / slug**
- 评论：`--id` 使用 **数值 ID**
- 用户：`--id` 使用 **数值 ID**

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
python3 scripts/client.py articles show --id 42
python3 scripts/client.py articles create \
  --channel-id 1 \
  --title "Hello World" \
  --body "这是正文内容" \
  --published \
  --pinned
python3 scripts/client.py articles create \
  --channel-id 1 \
  --title "精选文章" \
  --body "正文" \
  --published \
  --featured
python3 scripts/client.py articles update --id 42 --channel-id 3 --title "新标题" --featured true
python3 scripts/client.py articles delete --id 42

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

## 服务端约束

- 只允许调用 `/api/vibe/*` 端点
- 不修改软件源代码，只操作数据库内容
- 精华频道不能作为文章主频道
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
