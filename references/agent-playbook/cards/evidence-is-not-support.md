# 引文能对上，不等于事实被证明

身份：已拍加固

## 遇到什么

抽取器给了一段逐字引文，位置、来源版本和证据编号也都合法。后续 Agent 能不能因此把对应事实直接标成“已验证”？

## 对的做法

**已拍：**程序可以证明“引文确实来自这份书稿的这个位置”，不能单独证明“这段引文在语义上足以托住这条事实”。定位合法、事实正确、证据承托要分别过门；生产模型不能给自己的输出签质量绿票。材料不够时返回“材料不足＋回取轨迹”，不能补故事。

**加固：**外部评测材料把来源定位、语义支持和覆盖拆开。短引文不一定更可靠，过窄可能丢掉条件、指代和比较对象；模型置信度或多个模型一致也不是证据。[CLM-DR-EVAL-02-K01] [CLM-DR-EVAL-02-K11] [CLM-DR-EVAL-02-K12]

## 错的做法

看到逐字命中就判事实成立。把 Schema、位置或 SHA 合法当成语义承托。让同一个模型或两个一致的模型自动签绿票。把本卡升级成自动入账执行票；把短引文、模型一致等加固建议写成已拍。

## 出处

- [R14 抽取页](../../shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/04_EXTRACTION_MODEL_AND_DATA_STRATEGY.md)（“长期不轻易变的抽取原则”“评分不能压成一个总分”）
- [EKB 抽取评测页](../../external-knowledge-base/EXTERNAL_KNOWLEDGE_BASE_20260815_R01/background/05_EXTRACTION_EVALUATION_AND_EVIDENCE.md)（K01／K11／K12）
- [SI-004 评测回包](../../survey-inbox/packages/MANUS_R06_CLOUD_RESEARCH_20260812_R01/returns/RETURN_01_FACT_EXTRACTION_EVAL_SURVEY_20260812_R01.md)（证据“合法—定位—承托”分门）

来源：#115；批次 A；2026-08-24
