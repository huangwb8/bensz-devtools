# 2026-04-19 Vibe 契约审计与加固计划

## 背景

基于 `/Volumes/2T01/winE/Starup/dudu` 当前最新源码，重新审计 `services/api/src/modules/vibe/vibe.agent.controller.ts`、`vibe.routes.test.ts`、`report-styles.service.ts` 与相关 changelog，确认 `skills/dudu-vibe-config` 是否仍与真实 `Vibe Agent API` 契约一致。

## 本轮确认的真实能力

- `/vibe/agent/styles` 已稳定开放 `list/create/update/delete`
- `styles list` 当前暴露的是 `available` 目录，而不是 `mine/market/builtin` 可选 scope
- `styles create/update` 已支持 `visibility=private|market` 与 `baseStyle`
- `subscriptions update` / `subscriptions/:topicId/parse-prompt` 仍只开放 `name/prompt/frequency/ai/derivedQuery/derivedPlan/refreshDerived` 这一组 Vibe 字段
- 删除最后一个订阅时，服务端会继续清理 orphan topic 相关工件，而不是只删订阅关系

## 本轮确认的边界

- dudu 主项目虽已存在订阅级 `search_mode`，但当前 `/vibe/agent/subscriptions*` 仍未开放该字段
- 当前 Vibe 路由下，`rss_opml` 模板也仍要求非空 `query`
- bridge skill 不应越权改走 `/topics/*` 或其他非 `/vibe/agent/*` 路由

## 加固动作

1. 更新 `SKILL.md` / `README.md` / CLI help，把上述能力与边界写实
2. 保持 `subscriptions update` 对旧字段的本地结构化拒绝，避免请求打成 400
3. 补充风格市场字段透传测试，确保 `visibility` / `baseStyle` 不被后续改动吞掉
4. 同步仓库级入口文档，避免 `AGENTS.md` 与聚合 README 继续落后于实际能力

## 验证

- 运行 `python3 -m unittest` 覆盖 `tests/` 与 `tests/unit/` 下回归测试
- 人工复核 `README.md` / `SKILL.md` 与 dudu 最新控制器源码的字段一致性
