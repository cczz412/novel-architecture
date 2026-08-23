# 投影必须知道自己基于哪一版

身份：已拍加固

## 遇到什么

故事概览、体检报告、C7 快照或其他派生视图只有 `generated_at`／最后修改时间。后续 Agent 准备用时间新旧判断它是否还能支撑当前操作。

## 对的做法

**已拍：**R14 把概览、摘要、体检和执行材料视为可重建投影，不是独立真值。它们必须能说明读取了哪些权威版本、覆盖什么、是否已经过期；一次读取要落在一致的提交点。生成时间只能说明“什么时候做的”，不能代替“基于哪一版真源”。R14 登记了读一致性水位的工程方向，但精确字段名和落盘合同仍要服从当前正式合同。

**加固：**SI-016 发现当时候选 C5／C6／C7 有的缺精确来源水位，有的用时间字符串或局部卡号代替版本。这个审查支持“来源版本＋stale”纪律，但不把回包里的 `source_commit_seq`、卡号格式或物化缓存方案升格成现行 Schema。

## 错的做法

只比较最后修改时间。报告生成得晚就默认比账本新。把 `stale=false` 解释成“没有风险”或“可以关章”。拿来源不明的旧投影做高影响写操作。把 R14 的工程方向写成已经实现，或把 SI-016 候选字段直接冻结。把本卡升级成执行票。

## 出处

- [R14 系统架构与真值分层](../../shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/02_SYSTEM_ARCHITECTURE_AND_TRUTH_LAYERS.md)（派生视图可重建、带覆盖与过期状态；ADD-032 读一致性）
- [R14 术语表](../../shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/07_GLOSSARY.md)（`story_commit_seq` 的身份；覆盖回执）
- [SI-016 消化稿](../../survey-inbox/packages/PLAN_CONTRACT_REVIEW_RETURNS_20260815_R01/02_RETURNS_DIGEST.md)（A12、A15、A17）

来源：#115；批次 D；2026-08-24
