# 便签收件箱总览

当前身份：`ADVISORY_ONLY_NO_PRODUCT_OR_EXECUTION_AUTHORITY`

这里是人读入口；字段、状态和关系只以 [registry.json](registry.json) 为准。便签正文保留想法和上下文，不能代替需求、合同、任务 Issue 或 CZ 的施工授权。

## 当前便签

| 编号 | 标题 | 材料情况 | 决策情况 | 选择题 |
|---|---|---|---|---|
| [MN-0001](items/MN-0001_asr_tts_product_candidates.md) | ASR／TTS 产品集成技术备选 | `UNVERIFIED` | `UNDECIDED` | `voice.asr.product_candidate`；`voice.tts.product_candidate` |

## 当前跨目录关系

| 从哪里 | 到哪里 | 关系 | 当前判断 |
|---|---|---|---|
| `MN-0001` | [SI-015](../survey-inbox/items/SI-015_external_knowledge_research_returns.md) | `OVERLAPS` | `AGENT_CANDIDATE`；只是提示联读，不是冲突或采用结论 |

## 开工前怎么用

只按当前任务的选择题、具体主题和模块查询相关小簇，不全读。命中未裁决的 `DUPLICATES`／`CONFLICTS_WITH`，或准备采用的条目已经 `SUPERSEDED` 时，停对应写集交 CZ；无关模块继续。

候选发现采用 `memo-overlap-hint-v1`。标题和摘要相同可提示 `EXACT_DUPLICATE_CANDIDATE`；宽标签不会单独触发；至少共享 2 个具体标签且文字 Jaccard 达到 0.2，才可提示 `POSSIBLE_OVERLAP`。相同 `decision_keys` 可提示 `SAME_DECISION_REVIEW`。这三种提示都不能自动写成重复、冲突或替代关系。

来源：Codex
