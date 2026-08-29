# 高质量访谈节目与观点视频：混合订阅

该配置用于 dudu 的 `sourceType=hybrid` 订阅：先轮询 OPML 中的稳定 RSS/Atom 源，再用搜索补充没有 RSS、RSS 延迟或嘉宾出现在其它节目的更新。OPML 只收录从 Apple Podcasts、BBC、节目官网或托管商解析到的公开 feed；十三邀、B 站、晚点聊、张小珺等没有稳定官方 feed 的节目交给搜索层发现。

建议订阅参数：

- 名称：`高质量访谈节目与观点视频｜RSS + 搜索`
- 频率：`daily`
- 风格：`deep_research`
- RSS：同目录的 [`high-quality-interviews-hybrid.opml`](high-quality-interviews-hybrid.opml)
- 搜索提示词：

  ```text
  （高质量访谈 OR 深度访谈 OR 观点视频 OR podcast OR interview） AND （Dwarkesh OR "Conversations with Tyler" OR EconTalk OR Mindscape OR "In Our Time" OR Acquired OR Founders OR "Ezra Klein" OR "Hard Fork" OR Decoder OR "Odd Lots" OR "All-In" OR "Lex Fridman" OR "Diary of a CEO" OR "Modern Wisdom" OR 十三邀 OR 半拿铁 OR 硅谷101 OR 知行小酒馆 OR 忽左忽右 OR 东腔西调 OR 张小珺 OR 晚点聊 OR 乱翻书）
  ```

搜索层应优先返回节目官网、Apple/Spotify 播客页、YouTube/B 站官方频道和嘉宾本人发布，排除搬运、短视频剪辑、营销软文、泛榜单和无具体单集的聚合页。争议较大的 Diary of a CEO、Lex Fridman、Modern Wisdom、All-In 只作为“有值得嘉宾/论题才收录”的信号，不把频道口碑当作事实背书。
