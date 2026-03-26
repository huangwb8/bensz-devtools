# 本地 Derived 工作流

## 默认模式：AI 宿主型本地生成

适用：用户正在 Codex / Claude Code / Cursor 等 AI 宿主里直接使用 `dudu-vibe-config` skill。

默认执行顺序：

1. 宿主 AI 先在当前对话里本地生成 `derivedQuery + derivedPlan`
2. 再调用 `python3 scripts/client.py subscriptions create|update ... --derived-query ... --derived-plan-file|--derived-plan-json ...`
3. 只有在用户明确要求“让 dudu 自己重算”，或本地无法稳定生成时，才退回 `subscriptions parse-prompt`

建议：

- 对订阅 prompt 的修改，默认不要只传 `--prompt` 然后把派生完全交给 dudu 服务端
- 本地生成出的 `derivedPlan` 至少应包含：`derivedQuery`、`booleanLines`、`keywords`、`coreQuestions`、`scenario`
- 若本地生成结果存在明显不确定性，可在 `qualityIssues` 里显式标出

## 可选模式：脚本自驱型本地生成

适用：用户希望通过命令行直接让 skill 自己调用本地 `codex` / `claude` CLI 生成 derived 数据。

预览结果：

```bash
python3 scripts/local_derive.py \
  --prompt '"agentic coding" OR codex OR "claude code"' \
  --topic-name "开发工具追踪"
```

一条命令写回订阅：

```bash
python3 scripts/client.py subscriptions update \
  --topic-id <topic-uuid> \
  --prompt '"agentic coding" OR codex OR "claude code"' \
  --local-derived-script
```

可选参数：

- `--local-derived-runner auto|codex|claude`
- `--local-derived-model ...`
- `--local-derived-effort ...`
- `--local-derived-timeout ...`

## 模板边界

当前 `/vibe/agent/templates` 只接受模板元数据，不支持显式写入模板级 `derivedQuery / derivedPlan`。

这意味着：

- 订阅可以“本地生成 derived_* 再显式写回”
- 模板只能“本地先优化 query/prompt”，然后仍由 dudu 服务端在创建模板时持久化模板级 derived 字段
