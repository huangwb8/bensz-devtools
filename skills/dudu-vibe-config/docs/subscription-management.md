# 已有订阅管理（2026-10-02 契约审计）

## 常用操作

以下本机示例以用户已授权只读查询数据库为前提，修改授权由用户任务提供。既有授权直接复用；脚本不会默认启用数据库查询。

```bash
# 列出当前 Vibe Key 用户的订阅，含 ID、名称、频率、AI 与生成 AI
python3 scripts/client.py subscriptions list --local-db-readonly

# 查看单个订阅；需要 prompt/derived 原文时另加 --include-content
python3 scripts/client.py subscriptions show --topic-id UUID --local-db-readonly

# 保留 SDK 和未指定的 AI 字段，只调整模型与推理强度
python3 scripts/client.py subscriptions update --topic-id UUID \
  --model gpt-6-luna --reasoning-effort high --local-db-readonly

# 一次更新当前用户全部现有订阅，逐项核验
python3 scripts/client.py subscriptions update-many --all \
  --model gpt-6-luna --reasoning-effort high --local-db-readonly

# 指定多个订阅；重复 ID 会去重
python3 scripts/client.py subscriptions update-many \
  --topic-id UUID1 --topic-id UUID2 --frequency weekly --local-db-readonly

# 本机批量预览：只读枚举并合并配置，不发任何 HTTP 写请求
python3 scripts/client.py --dry-run subscriptions update-many --all \
  --model gpt-6-luna --reasoning-effort high --local-db-readonly

# 远程场景：已知 ID，显式替换 AI，未指定的字段使用服务端默认值
python3 scripts/client.py subscriptions update --topic-id UUID \
  --replace-ai --sdk codex_cli --model gpt-6-luna --reasoning-effort high

# 修改名称或频率可直接执行，数据库读取仅用于可选回读核验
python3 scripts/client.py subscriptions update --topic-id UUID --name '新的名称' --frequency daily
```

`--replace-ai` 必须给出 `--sdk` 和 `--model`（空字符串表示 provider/CLI 默认模型）。切换 SDK 时也必须指定模型；不把旧 provider 的 thinking 配置带给新 provider。单改 AI 且未传 prompt 时自动下发 `refreshDerived=false`；需要服务端重算时显式加 `--refresh-derived`。

## 读取与权限

当前上游源码 `services/api/src/modules/vibe/vibe.agent.controller.ts` 无 `GET /subscriptions` 或订阅详情 GET；实机请求 `GET /vibe/agent/subscriptions` 返回 404，`ping` 仅返回连通性和时间。

因此 `list/show/--all` 当前需要显式 `--local-db-readonly`。缺少该选项时返回 `unsupported_server_capability`，不自动访问数据库、不改走主站 `/topics/*`。远程服务器只支持用户提供 ID 后执行写操作，缺少回读时返回 `verified=false`，不能声称已经核验持久化配置。

本机读取通过 Docker 的 `psql` 执行固定 SQL：

- 仅支持 `localhost`、`127.0.0.1`、`::1` 的 URL，防止混用本机清单与远程写入。
- 使用配置 Key 的 SHA-256 匹配唯一有效 Key 及活跃用户，只查询该用户的 `topic_subscriptions` 与对应 topic；原始 Key 不进入命令行、SQL 或输出。
- 强制 `BEGIN READ ONLY`、查询超时、`ROLLBACK`；不读取数据库中的原始 Key，不执行数据库写入。
- `config.yaml` 维护 `local_db_container/local_db_database/local_db_user` 默认值；可用 `--db-container/--db-name/--db-user` 覆盖。需 Docker 可用及容器内 `psql` 权限。
- 默认查询不返回 prompt/derived 原文；`show --include-content` 可按需返回，避免把私有原文归档到公共日志。

## 修改字段与服务端行为

| 操作 | 当前支持 |
| --- | --- |
| 单订阅修改 | name、prompt、frequency、ai、derivedQuery、derivedPlan、refreshDerived |
| 批量修改 | SDK、model、reasoningEffort、thinkingMode、frequency、refreshDerived |
| AI 部分修改 | 先读取并合并当前主题 AI，保持未指定字段；明确替换可用 `--replace-ai` |
| 生成默认 AI | 修改 ai 后由 Vibe 服务端同步 generation_ai_config |
| 查询参数 | ID、名称、频率、主题 AI、生成 AI、来源类型、tier/style/groupId/searchMode |
| 不支持修改 | tier、style、groupId、独立 generationAi、searchMode、更新来源类型/OPML（Vibe PATCH 未开放） |

AI 是主题级设置，修改共享 topic 时会影响使用同一 topic 的其他订阅者；生成 AI 同步仅针对当前 Vibe Key 用户。查询到的参数不等于当前 Vibe API 允许修改的参数。

单改 AI 的默认策略保留 prompt 和 derived 工件。修改 prompt 时仍沿用现有本地生成/显式写回流程，详见 [local-derived-workflow.md](local-derived-workflow.md)。新增订阅默认值仍为 `codex_cli + model="" + medium`，本次批量设置不改变新增订阅默认值。

## 批量执行与结果

1. 读取初始集合，校验所有 UUID、用户归属及每个 AI 合并结果；预检失败不发写请求。`--all` 作用于此次初始集合。
2. 一个连接内依次 PATCH；旧服务器仅在 404/405 时尝试 PUT，所有写请求均不重试。
3. 已启用读取时，每次写入后核验主题 AI、生成 AI、请求修改字段和应保留字段；不通过即停止下一项。
4. `finally` 断开连接。失败、超时、终止和核验不通过时输出已完成数量和每项结果，不自动回滚；超时后的失败项是否写入须回读判断。

成功返回 `success/updated_count/target_count/verified/results`；`results` 保留每项 HTTP 结果和核验状态。`updated_count` 表示已收到成功响应的数量，核验失败的一项也可能已写入。用户终止返回 `terminate_requested=true` 与退出码 0，应检查该字段而非仅依赖退出码。

手动写入 derived 时，上游会规范化计划并重算版本/hash，核验使用服务端回传的 canonical query、数据库 query/plan 一致性及 prompt hash，不要求原始计划 JSON 逐字相等。`parse-prompt` 附带 AI 会持久化配置，须按同样的读取合并或 `--replace-ai` 策略操作；它不是临时生成覆盖。

`--dry-run` 不发 HTTP 请求。指定 ID 时可完全离线预览，无法读取的 AI 保留字段通过 `unresolved_ai_fields=true` 标记；带 `--local-db-readonly` 时会执行获授权的只读查询以得到实际预览，但不会连接 Vibe 或修改数据。

## 其他本轮对齐

- AI 选项补齐 `sdk=kimi`、`reasoningEffort=max`。
- 上游模板创建/删除已收敛到管理员 API，用户级 Vibe 路由返回 403；保留历史 CLI，不越权改走管理员接口。
- `reports generate --idempotency-key KEY` 发送服务端支持的幂等请求头；服务端返回 `attemptId`，重复请求可返回 `idempotentReplay`，不自动重试。
- 创建订阅仍可能触发 derived 解析及初始报道生成；本轮实机验证仅执行查询与 dry-run，不创建订阅或触发报道。

## 验证记录

- `python3 -B -m unittest discover -s skills/dudu-vibe-config/tests -p 'test_*.py'`：51 项通过，覆盖预检、AI 合并、批量失败/终止/超时停止、只读范围、配置核验和幂等请求头。
- `skill-creator/scripts/quick_validate.py skills/dudu-vibe-config`：通过。
- 本机授权查询成功返回 12 个订阅，`show` 与 12 项 `update-many --all --dry-run` 成功；未发 HTTP 写请求。本次未在线验证新的写入路径，写入与失败分支使用模拟 HTTP/数据库验证。

## 上游仍需补齐

要在纯远程 Vibe 模式下完成枚举、AI 部分合并和回读核验，上游需提供用户隔离的订阅列表/详情 GET，并返回 AI 与生成 AI 配置。本仓库不修改上游代码，当前只读入口解决的是本机部署的操作闭环。
