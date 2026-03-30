# 本地 Derived 工作流

## 默认模式：AI 宿主型本地生成

适用：用户正在 Codex / Claude Code / Cursor 等宿主里直接使用本 skill。

默认顺序：
1. 宿主 AI 先本地生成 `derivedQuery + derivedPlan`
2. 再通过 `subscriptions create|update --derived-query --derived-plan-file|--derived-plan-json` 显式写回
3. 只有用户明确要求“让 dudu 自己重算”，或本地生成不可用时，才退回 `subscriptions parse-prompt`

建议：
- 修改订阅 prompt 时，默认不要只传 `--prompt` 然后把派生完全交给服务端
- `derivedPlan` 至少应包含：`derivedQuery`、`booleanLines`、`keywords`、`coreQuestions`、`scenario`
- 若本地结果存在明显不确定性，可在 `qualityIssues` 中标注

## 可选模式：脚本自驱型本地生成

适用：用户希望通过命令行让 skill 自己调用本地 `codex` / `claude` CLI 生成 derived 数据。

先预览：

```bash
python3 scripts/local_derive.py \
  --prompt '"agentic coding" OR codex OR "claude code"' \
  --topic-name "开发工具追踪"
```

再一条命令写回：

```bash
python3 scripts/client.py subscriptions update \
  --topic-id <topic-uuid> \
  --prompt '"agentic coding" OR codex OR "claude code"' \
  --local-derived-script
```

常用覆盖参数：`--local-derived-runner`、`--local-derived-model`、`--local-derived-effort`、`--local-derived-timeout`

## 模板边界

当前 `/vibe/agent/templates` 只接受模板元数据，不支持显式写入模板级 `derivedQuery / derivedPlan`。

因此：
- 订阅可以“本地生成 `derived_*` 后显式写回”
- 模板只能“先在本地优化 query/prompt”，再调用服务端创建
