# Vibe Skill Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 `dudu-devtools` 与 `bensz-channel` 中的 vibe 配置相关 skill 聚合迁移到当前仓库，并在迁移完成后初始化本项目的 AI 协作文档。

**Architecture:** 当前仓库作为“聚合型 skill 仓库”，保留每个来源 skill 的独立目录、脚本、配置与文档，仅剔除缓存与系统垃圾文件。迁移后基于实际目录结构运行 `init-project`，生成项目级 `AGENTS.md`、`CLAUDE.md`、`README.md`、`CHANGELOG.md` 与 `.gitignore`。

**Tech Stack:** Markdown, Python 3 standard library scripts, shell file operations, init-project generator

---

### Task 1: 审计来源 skill 并确定迁移边界

**Files:**
- Create: `docs/plans/2026-03-12-vibe-skill-migration.md`
- Read: `/Volumes/2T01/winE/Starup/dudu-devtools/skills/dudu-vibe-config/SKILL.md`
- Read: `/Volumes/2T01/Github/bensz-channel/skills/bensz-channel-devtools/SKILL.md`

**Step 1: 读取 skill 元数据与脚本结构**

Run: `find .../skills/<skill-name> -maxdepth 3 -type f | sort`
Expected: 明确 `README.md`、`SKILL.md`、`config.yaml`、`scripts/`、`tests/`、`plans/` 等组成部分。

**Step 2: 识别应保留与应剔除内容**

Keep: `SKILL.md`、`README.md`、`CHANGELOG.md`、`config.yaml`、`scripts/`、`docs/`、`tests/`、`plans/`
Drop: `.DS_Store`、`__pycache__/`、`*.pyc`

**Step 3: 记录聚合仓库定位**

Result: 当前仓库定位为“多项目 vibe / devtools 远程配置 skill 聚合仓库”。

### Task 2: 迁移 skill 到当前仓库

**Files:**
- Create: `skills/dudu-vibe-config/**`
- Create: `skills/bensz-channel-vibe-config/**`

**Step 1: 创建目标目录**

Run: `mkdir -p skills`
Expected: 仓库根目录出现 `skills/`

**Step 2: 复制保留文件并排除缓存**

Run: 使用 `rsync -a --exclude '.DS_Store' --exclude '__pycache__' --exclude '*.pyc'`
Expected: 两个 skill 目录完整迁入当前仓库。

**Step 3: 检查迁移结果**

Run: `find skills -maxdepth 3 -type f | sort`
Expected: 两个 skill 的关键文件均在当前仓库可见，无缓存文件残留。

### Task 3: 初始化聚合仓库

**Files:**
- Modify/Create: `AGENTS.md`
- Modify/Create: `CLAUDE.md`
- Modify/Create: `README.md`
- Modify/Create: `CHANGELOG.md`
- Modify/Create: `.gitignore`

**Step 1: 基于迁移后结构运行生成器**

Run: `python3 /Users/bensz/.codex/skills/init-project/scripts/generate.py --auto`
Expected: 根目录生成项目级文档。

**Step 2: 审阅生成内容是否符合聚合仓库定位**

Check: README 是否描述为 skill 聚合仓库；AGENTS 是否反映“只管理 skill，不碰外部业务代码”的边界。

**Step 3: 如模板输出过于泛化则做最小必要修正**

Method: 使用最小修改补足仓库用途、目录结构、工作流与变更边界。

### Task 4: 完成度校验与审查

**Files:**
- Read: `skills/**`
- Read: `README.md`
- Read: `AGENTS.md`
- Read: `CHANGELOG.md`

**Step 1: 校验目录**

Run: `find . -maxdepth 3 -type f | sort`
Expected: 迁移内容与初始化文件同时存在。

**Step 2: 做一次需求对齐审查**

Checklist:
- 两个来源项目的相关 skill 已进入 `./skills`
- 聚合定位在项目文档中可见
- 初始化文件已生成
- 忽略规则覆盖 `.env`、缓存与系统垃圾文件

**Step 3: 输出结果**

Result: 用简洁说明总结迁移内容、初始化结果、验证方式与未执行项（如未跑联网 API 测试）。
