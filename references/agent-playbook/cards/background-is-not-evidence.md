# 背景能帮理解，不能替目标段作证

身份：已拍加固

## 遇到什么

模型读到了人物卡、别名、前态、整章背景或检索回来的旧段落。目标责任段里没写这件事，模型能不能仍把它登记成这次新事实？

## 对的做法

**已拍：**背景卡能帮助识别主角、别名、类型和已确认设定，不能替书稿补证据。只读前态也不能被抄进本次新事实。查询回答只服务当前问题，不能默认写成永久底账。

**加固／预检：**检索块、事实责任段和理解上下文要分工。P4 预检合同写过“可以读更宽的只读上下文，但只能在目标责任区产生新事实和合法证据”；这仍是预检，不是产品已拍，也不能把固定块长、窗口大小或 Wide Read / Narrow Write 冻结成默认。

## 错的做法

把人物卡、计划、旧摘要或 RAG 命中当本次事实证据。背景里出现过就写成目标段已发生。让前态泄漏进新答案。把 180 字、300 字、整章宽读或某种切块法冻结成产品默认。把 P4 预检写成已拍。把本卡或窗口切块建议升级成执行票。

## 出处

- [R14 真值分层页](../../shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/02_SYSTEM_ARCHITECTURE_AND_TRUTH_LAYERS.md)（“作者确认背景和书稿证据”；“查询回答和永久事实”）
- [R14 抽取页](../../shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/04_EXTRACTION_MODEL_AND_DATA_STRATEGY.md)（P4 预检：宽读窄写；正文写明仍只是预检）
- [SI-002 消化稿](../../survey-inbox/packages/T5_R04_FACT_EXTRACTION_RESEARCH_RETURNS_20260811_R01/02_RETURNS_DIGEST.md)（检索块／责任核心／只读 Halo 三层分开）
- [SI-004 评测回包](../../survey-inbox/packages/MANUS_R06_CLOUD_RESEARCH_20260812_R01/returns/RETURN_01_FACT_EXTRACTION_EVAL_SURVEY_20260812_R01.md)（T／T±／C 只是候选对照，不是默认）

来源：#115；批次 A；CZ 2026-08-24 已拍段去掉 P4
