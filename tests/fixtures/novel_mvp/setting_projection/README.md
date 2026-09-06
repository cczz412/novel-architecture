# 北塔手写绑定夹具

这是本次新增的合成夹具，不是已抽取真书，也没有冒充既有北塔金标。包内没有北塔正文；GitHub 关键词检索也没有找到可复用来源。本夹具只用来跑 #311 的文件读写和内容合同检查。

`facts.json` 有 9 条 confirmed、1 条 extracted、1 条 rejected；绑定文件是手写的 9 条记录。前六条覆盖六本设定账，第七条同名追加人物状态，第八条同名追加地点状态，第十条证明未确认事实不会落账。f009 已确认但没有绑定，必须计数列出。

`chapters.json` 只供测试搭建真实 AuthorWorkspace；投影入口不需要读正文。全部事实、名称和引文都是测试数据。

`plan.json` 是没有情节内容的手写规划底座，只供现有 settingstore 复用发号器。生产入口不会复制这份夹具，也不会私建规划账；未初始化底座会报 PROJECTION_PLAN_REQUIRED。

已放入本夹具四份 JSON 的空白项目预期：六本账各 1 条候选定义卡；新建 6 次、追加 2 次、跳过 2 条（f009 无绑定，f010 未确认）。生成的条目始终是 draft_inferred / candidate；proposer=author 不等于 AUTHOR_ATTESTATION。
