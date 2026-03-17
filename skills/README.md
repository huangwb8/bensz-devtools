# Skills Index

这个目录用于聚合不同软件的远程 bridge skill。

## 当前收录

### `bensz-channel-vibe-config`

- 来源仓库：`/Volumes/2T01/winE/Starup/bensz-channel`
- 目标系统：`bensz-channel`
- 受限接口：`/api/vibe/*`
- 主要对象：频道、标签、文章、评论、用户

### `dudu-vibe-config`

- 上游业务仓库：`/Volumes/2T01/winE/Starup/dudu`
- 目标系统：`dudu`
- 受限接口：`/vibe/agent/*`
- 主要对象：模板、订阅、报道、域名规则

## 收录约定

- 每个产品单独一个 skill 目录
- 保留各自的 `SKILL.md`、`README.md`、`config.yaml`、`scripts/`
- 推荐保留 `docs/`、`plans/`、`tests/` 等演进沉淀，并纳入版本控制
- 不收录缓存文件、编译产物和临时密钥文件
