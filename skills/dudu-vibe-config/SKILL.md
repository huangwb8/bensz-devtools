---
name: dudu-vibe-config
description: dudu 氛围配置“桥梁”Skill：通过 Vibe Agent API（/vibe/agent/*）在受限范围内管理模板/订阅/报道/域名规则，适用于 Claude Code/Codex 远程优化配置。
metadata:
  author: Bensz Conan
  short-description: dudu 氛围配置远程桥梁（Vibe Agent API）
  keywords:
    - dudu
    - vibe
    - 氛围配置
    - 远程配置
    - templates
    - subscriptions
    - domains
    - reports
  category: 运维支持
  platform: Claude Code | OpenAI Codex | Cursor | ChatGPT
---

# dudu-vibe-config（桥梁 Skill）

## 目标

把“人类的配置意图”稳定地翻译成对 `dudu` **Vibe Agent API** 的一组受限操作（仅 `/vibe/agent/*`），以支持远程优化：

- 模板：创建/删除
- 订阅：创建/更新/退订（支持显式透传主题 `ai.*` 与按用户保存的 `generationAi.*`）
- 报道：触发生成/删除（支持生成时临时覆盖 AI 配置）
- 域名规则：读取/更新（allowlist/blocklist/keywords）

## 安全边界（强制）

- 只允许调用：`{DUDU_VIBE_URL}/vibe/agent/*`
- 不做越权访问（不调用其它路径；不绕过 KEY/connection 机制）
- 严禁修改 **dudu 软件源代码**（本 skill 仅用于调用受限 API 更新“氛围配置”相关数据）
- 不输出完整 Key；日志中必须脱敏（仅显示前缀）
- 任何 **变更类请求**（POST/PUT/DELETE，除 `heartbeat`/`disconnect` 外）默认使用 `connect → 执行 → disconnect`，并携带 `x-dudu-vibe-connection`
- 若服务端返回 `x-dudu-vibe-terminate: 1` 或 409 `terminate_requested`：立刻停止后续变更操作并 `disconnect`

## 环境变量

优先从环境变量读取：

- `DUDU_VIBE_URL`：默认 `http://localhost:3001`
- `DUDU_VIBE_KEY`：长度需 ≥ 16

兼容别名：

- URL：`dudu_vibe_url`、`dudu_base_url`
- KEY：`dudu_vibe_key`、`dudu_vibe_api`

## 标准工作流（推荐）

1) 环境检查（不泄露 Key）

```bash
python3 scripts/env_check.py
```

2) 连接健康检查（最小闭环）

```bash
python3 scripts/client.py ping
python3 scripts/client.py doctor
```

3) 执行配置变更（按用户意图选择子命令）

- 域名规则：先 `domains get`，再决定是否 `domains set`（默认安全合并；需要“完全替换”时才用 `--reset`）
- 模板/订阅/报道：按需创建/删除；所有变更类操作默认自动 connect/disconnect

4) 不确定时先 dry-run（推荐）

```bash
python3 scripts/client.py --dry-run domains set --reset --allowlist example.com
```

## 常见任务映射（意图 → 命令）

- “把 example.com 加入白名单”：`domains set --allowlist example.com`
- “屏蔽 bad.com”：`domains set --blocklist bad.com`
- “添加关键词过滤 X”：`domains set --keywords X`
- “新增一个每日订阅”：`subscriptions create --frequency daily`
- “把已有订阅切到 Codex CLI + 更高推理强度”：`subscriptions update --topic-id ... --sdk codex_cli --reasoning-effort high`
- “把手动生成默认模型改成 Claude，并清空分组”：`subscriptions update --topic-id ... --generation-sdk claude --group-id default`
- “用 Claude Code 建一个开发工具类订阅”：`subscriptions create --frequency daily --sdk claude_code --thinking-mode thinking`
- “触发某个订阅生成新报道”：`reports generate --topic-id ...`
- “这次生成临时改用 Codex CLI 高推理”：`reports generate --topic-id ... --sdk codex_cli --reasoning-effort high`

## 订阅更新兼容策略

- `subscriptions update` 的参数语义对齐 `dudu` 最新源码中的 `PUT /topics/:id` 与 `POST /topics/:id/subscribe`
- 客户端会优先尝试 `PATCH /vibe/agent/subscriptions/:topicId`，再回退尝试 `PUT /vibe/agent/subscriptions/:topicId`
- 若当前 dudu 服务仍未暴露该能力，客户端会输出结构化 `unsupported_server_capability`
- **不会** 自动走“删除旧订阅 + 新建订阅”的危险兜底，因为那会改变 topic id，并可能丢失历史报道/进度/引用关系

## 订阅提示词策略

`--prompt` 字段不必使用自然语言。**专业检索式语法**信噪比更高，且对 AI 和搜索引擎后端同样有效。

dudu 默认搜索引擎为 **SearXNG**。SearXNG 本身不解析布尔运算符，而是将查询字符串**原样透传**给后端引擎（如 Google、Bing、Brave 等）。因此：

- `"phrase"`、`-term`、`OR`、`(group)` 等语法的实际效果取决于后端引擎是否支持
- SearXNG 自身只处理 `!engine`（指定引擎）和 `:lang`（指定语言）两类前缀

### 核心原则

- 用关键词组合替代描述性句子，优先领域术语
- 用引号锁定精确短语，用 `-` 排除噪音（主流后端均支持）
- 避免依赖复杂嵌套布尔表达式（后端支持程度不一）

### 算子速查

| 算子 | 支持范围 | 示例 |
|------|---------|------|
| `"phrase"` | 主流后端均支持 | `"interest rate decision"` |
| `-term` | 主流后端均支持 | `crypto -scam -pump` |
| `OR` | 多数后端支持 | `LLM OR "large language model"` |
| `(group)` | 部分后端支持 | `(iPhone OR iPad) release` |
| `!engine` | SearXNG 原生 | `!news AI regulation` |
| `:lang` | SearXNG 原生 | `:zh AI 监管` |

### 示例对比

| 场景 | ❌ 自然语言 | ✅ 检索式 |
|------|------------|----------|
| AI 研究动态 | 关注人工智能领域最新进展 | `"large language model" OR LLM OR "foundation model" paper OR benchmark -hype` |
| 苹果产品新闻 | 苹果公司的新产品和发布会 | `Apple iPhone OR Mac OR "Vision Pro" OR WWDC -rumor -leak` |
| 宏观经济 | 关注美联储和全球经济形势 | `Fed OR "Federal Reserve" OR ECB "interest rate" OR inflation OR "rate cut"` |
| 开源项目 | 关注 GitHub 上的热门开源项目 | `GitHub OR "open source" release OR "breaking change" -tutorial -beginner` |
| 安全漏洞 | 关注网络安全漏洞和补丁 | `CVE OR vulnerability OR "zero-day" critical OR high -FUD` |

> 注：示例中刻意减少嵌套括号，以提升跨后端兼容性。

### 构造模板

```
[核心主题词] [子类型1] OR [子类型2] -[噪音词1] -[噪音词2]
```

例：
```bash
python3 scripts/client.py subscriptions create \
  --name "AI 安全周报" \
  --prompt '"AI safety" OR "AI alignment" OR "model safety" paper OR research OR incident -marketing' \
  --frequency weekly
```

## 失败处理（必须执行）

- 401：Key/URL 错误或 Key 被吊销 → 停止，提示用户去 Web “氛围配置”页创建新 Key（不尝试暴力重试）
- 409 terminate_requested：用户已在 Web 端终止连接 → 立刻停止并断开
- 5xx / 超时：最多重试 2 次（指数退避），仍失败则输出可复现命令与诊断建议

## 输出约定（用于工具调用）

- `scripts/client.py` 的 `doctor` 与 `doctor --watch-seconds` 仅输出 JSON（便于工具稳定解析）
- 遇到终止请求（`terminate_requested`）时：输出 `{"terminate_requested": true, ...}` 并以退出码 `0` 结束（视为用户主动终止）
