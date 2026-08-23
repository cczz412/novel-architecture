# 评测不能压成一个总分

身份：已拍加固

## 遇到什么

评测脚本准备只输出一个“准确率”或 F1，再按总分排模型。这样够不够？

## 对的做法

**已拍：**评分不能压成一个总分。任何单一“准确率”都会把格式失败、事实错误和证据绑定错误互相遮住。格式失败不能从总表消失，语义高分也不能掩盖不可交付。

**加固：**当前评分至少分六层（能否正常产出、JSON／Schema、逐字命中、事实语义、证据编号／位置／SHA、证据是否真的托住语义）。这是当前拆法，不是新评测合同或门线。外部材料还建议同时报 Precision、Recall、F1 和原始计数，并可并列“结构合法时的语义分”和“真实管线端到端分”，但不能用其中一张吞掉另一张。验真器自身 F1 也不能替代整条管线的净改善。

## 错的做法

只看一个总分。只测 JSON 合法，或只测事实语义。把 invalid JSON、复读、截断和无证据事实平均掉。用验真器自评分、模型自信或两模型一致替代端到端结果。把六层清单写成已拍验收合同。把本卡升级成执行票；把外部评测建议写成已拍门线或权重。

## 出处

- [R14 抽取页](../../shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/04_EXTRACTION_MODEL_AND_DATA_STRATEGY.md)（“评分不能压成一个总分”；六层是当前拆法）
- [SI-002 消化稿](../../survey-inbox/packages/T5_R04_FACT_EXTRACTION_RESEARCH_RETURNS_20260811_R01/02_RETURNS_DIGEST.md)（评分拆层；验真看净效果）
- [SI-004 评测回包](../../survey-inbox/packages/MANUS_R06_CLOUD_RESEARCH_20260812_R01/returns/RETURN_01_FACT_EXTRACTION_EVAL_SURVEY_20260812_R01.md)（格式门、事实门、证据门、端到端门）
- [EKB 抽取评测页](../../external-knowledge-base/EXTERNAL_KNOWLEDGE_BASE_20260815_R01/background/05_EXTRACTION_EVALUATION_AND_EVIDENCE.md)（K01／K06／K09）

来源：#115；批次 A；CZ 2026-08-24 六层不当已拍清单
