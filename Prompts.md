# General

- 创建tag v1.0.1 ； /git-commit ;   /git-publish-release 。 
- 使用 [$awesome-code](/Users/bensz/.codex/skills/awesome-code/SKILL.md) 辅助规划、优化。所有问题都要解决。 如果工作时有疑问，或者有更好的方案，自己选个最优方案优化，不要问我。不要破坏其它功能。要保证最终成品能正常、稳定、高效地工作。 
- 根据目前 /Volumes/2T01/winE/Starup/bensz-channel 项目的最新代码， skills/bensz-channel-vibe-config 要不要调整下？ 使用 awesome-code skill 辅助规划、优化。所有问题都要解决。 如果工作时有疑问，或者有更好的方案，自己选个最优方案优化，不要问我。不要破坏其它功能。要保证最终成品能正常、稳定、高效地工作。
- 根据目前 /Volumes/2T01/winE/Starup/dudu 项目的最新代码， skills/dudu-channel-vibe-config 要不要调整下？ 使用 awesome-code skill 辅助规划、优化。所有问题都要解决。 如果工作时有疑问，或者有更好的方案，自己选个最优方案优化，不要问我。不要破坏其它功能。要保证最终成品能正常、稳定、高效地工作。

---

# Bensz-channel

---

https://channel.hwb0307.com/channels/716f55930b26ce88/articles/e175fb843cd0ce88 这个文章有后续了，今天OpenAI已经修复了这个问题，Codex Plugin的版本号是 26.5318.11754 （预发布版本）。 你联网调查一下，根据之前文章的情况，写一个文章告诉用户这个好消息。 相关的文章我之前还有：  https://channel.hwb0307.com/channels/716f55930b26ce88/articles/4862306d68d2377e 总之，这个问题存在很长时间了。 能解决就很舒服。文章写完后发布到 bensz channel 上

---

自从上次在频道里更新动态以来， /Volumes/2T01/winE/Starup/bensz-channel 已经迭代了几个release。 请总结最近一些进展。 发布在 开发 频道。

---

把 /Volumes/2T01/winE/PythonCloud/Agents/pipelines/deep_research/reports/AI-自动科研系统调研这个报告发到 科研 频道上

# ChineseResearchLaTeX

---

/Volumes/2T01/Github/ChineseResearchLaTeX 在2026-03-17有不少commit/release。 请写个非常详细的文章介绍主要的改进， 发到 bensz channel 的 科研 频道上。 要求：

- 重点突出，有煽动性
- 较为详尽，让读者能切实地感受到项目的变化
- 文末要附带项目github地址

---

https://github.com/huangwb8/ChineseResearchLaTeX 的v4.0.0和v3之间有非常大的变动。 请你：

- 仔细读它们之间的commit信息
- 读 v4.0.0 的release note
- 写个非常详细的文章介绍变化， 发到 科研 频道上
- 要求：
  - 重点突出，有煽动性
  - 文末要附带项目github地址

# skills

---

介绍/Volumes/2T01/Github/skills 的最新release的情况，发到 vibe 频道里。

# dudu

---

dudu-vibe-config添加新订阅或新模板时，除非用户指定，SDK的默认设置是：

- SDK： Codex CLI（注意，不是OpenAI Response API）;  模型：
- gpt-5.4
- reasoning 强度： medium

使用 [$awesome-code](/Users/bensz/.codex/skills/awesome-code/SKILL.md) 辅助规划、优化。所有问题都要解决。 如果工作时有疑问，或者有更好的方案，自己选个最优方案优化，不要问我。不要破坏其它功能。要保证最终成品能正常、稳定、高效地工作。 

---

skills/dudu-vibe-config 优化

- 允许 dudu-vibe-config 远程修改已有订阅的各种参数，比如SDK类型

请结合dudu最新源代码（只读）来支持这个功能。使用 [$awesome-code](/Users/bensz/.codex/skills/awesome-code/SKILL.md) 辅助规划、优化。所有问题都要解决。 如果工作时有疑问，或者有更好的方案，自己选个最优方案优化，不要问我。不要破坏其它功能。要保证最终成品能正常、稳定、高效地工作。 

---

- dudu添加一个模板，内容如下：

```
模板名：苹果产品爆料
关注点：apple公司产品的爆料。 要求是各种可靠信源（你调研下哪些可造信源）
SDK： Claude Code
Model: claude 4.6 sonnet
```

- 使用这个模板购建一个订阅

# Others

---

请：

- /Volumes/2T01/winE/Starup/dudu-devtools 的skill迁移到 ./skills 里
- /Volumes/2T01/Github/bensz-channel 的skill迁移到 ./skills 里
- 上述skill的功能都是很类似的；它们控制了不同软件的vibe配置。 因为我以后可能会开发很多软件，因此我想把它们的vibe配置相关的skill聚合在一起。
- 完成迁移后，在充分理解上述2个项目的情况下， 使用 init-project 对本项目进行初始化

