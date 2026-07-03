# bensz-notes API 合同摘记

来源：`/Volumes/2T01/Github/bensz-notes/docs/api/v1.md` 与 `apps/api/src/*/*.controller.ts`。

## Base 与认证

- Web 部署默认：`{BENSZ_NOTES_URL}/api/backend`
- 直连 API：`BENSZ_NOTES_API_PREFIX=-`
- 认证：`Authorization: Bearer <bnt_... 或 scoped JWT>`
- 写操作建议：`X-Request-Id`、`Idempotency-Key`

scope：`read` 读取；`write` 创建/编辑/追加/移动/删除/恢复；`publish` 发布/取消发布；`admin` 管理 token、成员和控制台设置。

## 冲突保护

- `PATCH /notes/{id}`、`POST /notes/{id}/move` 要求 `baseRevision`。
- `PUT /sync/notes/by-path/{path}` 更新既有路径时要求匹配 `baseRevision` 与 `baseContentHash`。
- `DELETE /sync/notes/by-path/{path}` 必须携带同步基线；客户端强制 `--base-revision` 与 `--base-content-hash`。
- `409` 后必须重新读取远端状态，不盲写覆盖。

## 高风险动作

- 发布：`status=published`，需要 `publish` scope；客户端要求 `--allow-publish`。
- 删除：笔记、同步路径、成员、token 撤销；客户端要求 `--confirm-delete`。
- 平台治理：`/admin/*` 需要 `platformRole=super_admin`。
