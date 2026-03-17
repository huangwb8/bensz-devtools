# bensz-devtools

聚合多个软件的 vibe / devtools 远程桥梁 skill，统一沉淀到一个仓库中管理。

当前仓库已经收录两个同类但面向不同产品的 skill：

- `dudu-vibe-config`：通过 `dudu` 的 `/vibe/agent/*` 接口管理模板、订阅、报道和域名规则
- `bensz-channel-vibe-config`：通过 `bensz-channel` 的 `/api/vibe/*` 接口管理频道、标签、文章、评论和用户

这类 skill 的共同点是：都通过受限 API 把“人类意图”翻译成远程配置或远程管理动作，不直接修改对应产品的软件源代码。

## 仓库定位

- 这是一个 skill 聚合仓库，不是 `dudu` 或 `bensz-channel` 的业务代码仓库
- 每个 skill 保持独立目录，保留自己的 `SKILL.md`、`README.md`、`config.yaml`、`scripts/`；`docs/`、`plans/`、`tests/` 为推荐沉淀目录
- 未来新增软件时，优先继续沿用同样的桥梁型目录结构，而不是把不同产品的逻辑混写在一个 skill 里

## 当前 Skills

### `skills/dudu-vibe-config`

- 上游业务仓库：`/Volumes/2T01/winE/Starup/dudu`
- 目标系统：`dudu`
- 能力范围：模板、订阅、报道、域名规则
- 安全边界：仅访问 `/vibe/agent/*`

### `skills/bensz-channel-vibe-config`

- 来源：`/Volumes/2T01/winE/Starup/bensz-channel`
- 目标系统：`bensz-channel`
- 能力范围：频道、标签、文章、评论、用户
- 安全边界：仅访问 `/api/vibe/*`

更详细的入口说明见 [skills/README.md](skills/README.md)。

## 共同设计原则

- 只通过受限 API 操作远程配置或数据，不越界修改上游业务代码
- 所有敏感凭据都通过环境变量或 `.env` 提供，日志输出必须脱敏
- 写操作优先采用 `connect -> operate -> disconnect` 闭环
- 优先使用 Python 标准库脚本，尽量降低 skill 的环境依赖
- 当多个 skill 出现同类模式时，先比较稳定性和可复用性，再决定是否抽取共享组件

## 使用方式

1. 进入目标 skill 目录并阅读其 `README.md` 与 `SKILL.md`
2. 先运行 `scripts/env_check.py` 检查 URL / KEY
3. 再运行 `scripts/client.py ping` 与 `scripts/client.py doctor`
4. 最后按目标 skill 的命令集执行具体的远程管理动作

## 目录结构

```text
bensz-devtools/
├── docs/
│   └── plans/
├── skills/
│   ├── README.md
│   ├── bensz-channel-vibe-config/
│   └── dudu-vibe-config/
├── AGENTS.md
├── CHANGELOG.md
├── CLAUDE.md
└── Prompts.md
```

## AI 协作

- `AGENTS.md` 是仓库级单一事实来源
- `CLAUDE.md` 通过 `@./AGENTS.md` 自动复用相同约束
- 任何结构性调整、skill 迁移或规则更新，都要同步记录到 `CHANGELOG.md`
