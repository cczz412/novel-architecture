# 输出很干净，不等于没有漏抽

身份：已拍加固

## 遇到什么

抽出来的每条事实都挺准，误报很少。后续 Agent 能不能据此写“本段已完整抽取”？

## 对的做法

**已拍：**漏抽不能只从输出列表里看。要从源文反向核对：关键对白、数字、专名、设定块等候选锚点，必须能说明被哪条事实覆盖，或为什么合法排除；还要按不同事实族补漏。没查到只能写当前覆盖内未发现，不能写完整无漏。

**加固：**高 Precision 只说明“报出来的较干净”，不说明 Recall 高。质量账应同时保留 TP、FP、FN、未读取范围、证据不足和不确定项，过滤与去噪也要防误杀。[CLM-DR-EVAL-02-K06] [CLM-DR-EVAL-02-K09]

## 错的做法

只检查已输出事实，不反看源文。验真器没驳回就当没有漏抽。把“输出条数少、看起来整洁”当完整性证明。把本卡升级成执行票；把反向覆盖的加固形状写成已拍字段表或阈值。

## 出处

- [R14 抽取页](../../shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/04_EXTRACTION_MODEL_AND_DATA_STRATEGY.md)（ADD-021：源文反向覆盖账本＋分事实族补漏）
- [EKB 抽取评测页](../../external-knowledge-base/EXTERNAL_KNOWLEDGE_BASE_20260815_R01/background/05_EXTRACTION_EVALUATION_AND_EVIDENCE.md)（K06／K09）
- [SI-004 评测回包](../../survey-inbox/packages/MANUS_R06_CLOUD_RESEARCH_20260812_R01/returns/RETURN_01_FACT_EXTRACTION_EVAL_SURVEY_20260812_R01.md)（Precision／Recall／原始计数分开）

来源：#115；批次 A；2026-08-24
