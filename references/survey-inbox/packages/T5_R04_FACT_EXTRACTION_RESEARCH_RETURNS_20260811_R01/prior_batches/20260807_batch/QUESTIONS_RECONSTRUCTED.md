# 2026-08-07 批次问题主题（按回包恢复）

⚠️ 这里记录的是根据报告标题和正文恢复出来的调查主题，不是当时外发 Prompt 的逐字原文，也不能冒充原问题。

六份报告按源文件时间戳排列。归档件与 Downloads 原件逐字节一致；这些外部研究回包只作为历史材料，不产生当前运行、训练、上传或方案晋升权限。

| 编号 | 恢复的问题主题 | 源绝对路径 | 目标相对路径 | 报告标题 | 字节数 | SHA-256 |
|---|---|---|---|---|---:|---|
| 01 | 小说事实抽取模型该怎样加入简化语义监督，才能提升事实识别，又不污染正式输出结构？ | `/Users/a1234/Downloads/deep-research-report - 2026-08-07T221722.575.md` | `prior_batches/20260807_batch/returns/01_semantic_core_auxiliary_task_tradeoffs.md` | SEMANTIC_CORE 辅助任务：帮助事实理解，还是污染结构化输出？ | 32,215 | `9ae5df05ce093fa4789a1d83534fa25ac35fefcb52e41a3b27f033586c67c624` |
| 02 | 小模型微调后已经抽出正确事实，却不断复读并毁掉 JSON，真正故障在哪里，又该怎样诊断和修复？ | `/Users/a1234/Downloads/deep-research-report - 2026-08-07T221726.599.md` | `prior_batches/20260807_batch/returns/02_sft_repetition_and_json_termination_failures.md` | 小模型 SFT 后疯狂复读与 JSON 崩坏：真实根因、诊断与修复研究 | 34,693 | `dad155294392ff15a3b299db528dff20e547e8e82136c08a674035a080e61863` |
| 03 | 怎样公平评价事实抽取模型，既不把非法 JSON 误当成完全不会抽事实，也不把不可交付结果包装成成功？ | `/Users/a1234/Downloads/deep-research-report - 2026-08-07T221731.365.md` | `prior_batches/20260807_batch/returns/03_fact_extraction_evaluation_framework.md` | 事实抽取评分体系研究：把语义能力、结构交付和生成故障彻底拆开 | 34,197 | `4d9be7dfd45af32ade870e378d3af80918bc4482f76a3eab08b049fb94ad8d7c` |
| 04 | 特殊长尾样本单独放在微调第二阶段，会不会在补能力时一并教坏输出习惯；混训和阶段训练该怎样选择？ | `/Users/a1234/Downloads/deep-research-report - 2026-08-07T221751.047.md` | `prior_batches/20260807_batch/returns/04_staged_sft_and_special_data_mixing.md` | 第二阶段“特殊教材”为什么可能把模型教偏：阶段式 SFT 与混合训练研究 | 34,513 | `73202c6e19c4ee191d2e458715c29504d41d810962393678b6b3427f31ec8cc8` |
| 05 | 同一句证据在原文中重复出现时，哪些位置算合法金标，哪些只是待消歧候选，训练和评估合同该怎样表达？ | `/Users/a1234/Downloads/deep-research-report - 2026-08-07T221753.782.md` | `prior_batches/20260807_batch/returns/05_duplicate_evidence_gold_and_provenance.md` | 重复证据文本下，Gold 与 Provenance 应该怎样定义 | 33,053 | `b9b6ba6a0ecf28229567d7dcd62cdecd023dec26a649ed6c323f3e34693318a5` |
| 06 | C2 证据切分怎样兼顾边界干净与语义完整，避免细单元和大量编号反过来拖垮小模型理解？ | `/Users/a1234/Downloads/deep-research-report - 2026-08-07T221844.055.md` | `prior_batches/20260807_batch/returns/06_c2_unit_evidence_granularity.md` | C2_UNIT 证据粒度研究：从“证据更干净”到“模型仍然看得懂” | 36,294 | `7ae2c89485bb68d837425cd950e9245b24c490f83e1353b9d8e3797739a806bd` |

来源：Codex
