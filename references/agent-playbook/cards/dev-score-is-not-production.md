# 开发集高分，不是生产证明

身份：已拍加固

## 遇到什么

同一批 DEV 已经反复拿来改 Prompt、Schema、评分器和模型，现在某个候选得分最高。能不能把它叫 blind 胜出或直接晋级生产？

## 对的做法

**已拍：**被用于选 checkpoint、调格式或改规则的数据只能叫 DEV。真实 final blind 未建立时，不能做正式终局评测；正式教材候选还要过来源权利、作者／书／来源切分、评测器与数据版本冻结、可重复构建等门。当前没有生产证明就明确写没有。

**加固：**DEV 适合淘汰明显差项和做晋级筛选；候选结构全部冻结后，再用一次未见确认集做窄确认。任何接触过训练、示例、评分调参或人工规则迭代的样本，都应降级登记，不能继续冒充 blind。

## 错的做法

一边看 DEV 一边改，一边仍称盲测。把多次使用的小集合冠军写成普遍最优或生产默认。让训练、开发、确认集互相回流。把本卡升级成执行票；把外部样本规模、显著性门或开封方法写成已拍。

## 出处

- [R14 抽取页](../../shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/04_EXTRACTION_MODEL_AND_DATA_STRATEGY.md)（“当前数据资产”“Production Canonical 的门”“当前可做和不可做”）
- [SI-002 消化稿](../../survey-inbox/packages/T5_R04_FACT_EXTRACTION_RESEARCH_RETURNS_20260811_R01/02_RETURNS_DIGEST.md)（DEV 与确认集分开；开发集不能回流训练）
- [SI-004 评测回包](../../survey-inbox/packages/MANUS_R06_CLOUD_RESEARCH_20260812_R01/returns/RETURN_01_FACT_EXTRACTION_EVAL_SURVEY_20260812_R01.md)（作者／书／来源切分；开发接触降级）

来源：#115；批次 A；2026-08-24
