# 2026-08-11｜A／B／C 对照前置三问三回包

这批共有 3 个逐字 Prompt 和 3 份完整回包。Prompt 来自当时实际外发的 `T5_R04_EXTERNAL_RESEARCH_API_PIPELINE_FORK_20260811_R02`，回包从 Downloads 原文件逐字节复制，原文件没有移动或覆盖。

## 时间与身份边界

- 三份报告在新的 A／B／C Prompt 对照和最终模型筛选完成前返回。
- 报告中的 GLM、DeepSeek、Doubao、Ling 等具体模型与岗位，只保留为当时证据条件下的候选建议；不能据此认定某模型已经入选、淘汰、成为默认或获准训练。
- 报告可以帮助冻结后续评测口径、数据分层、成本公式、独立验真和多步管线的实验合同，但不能覆盖后续同批 A／B／C 结果。
- 这批材料不授权模型调用、训练、数据回流、Notion、Git 或生产晋级。

## 问题与回包对应

| 问题 | 逐字 Prompt | 完整回包 | 回包大小 | 回包 SHA-256 |
|---|---|---|---:|---|
| 主抽取＋盲补漏＋逐条验真能否稳定修到可用 | [Prompt](prompts/01_post_extraction_repair.md) | [回包](returns/01_multistage_pipeline.md) | 26,352 | `8b2778e6e206cf3edf030d7b7a082a3ab91fc1833718ca1775a34434fa93faa7` |
| 何时保留多步 API，何时微调 Mini／Lite | [Prompt](prompts/02_api_vs_finetune.md) | [回包](returns/02_api_vs_finetune_constraint_optimization.md) | 20,477 | `ed5ce5c22c23315c4750291242fedec601a1005a21d1c4b1e701560d8c73ec8f` |
| 怎样证明独立验真器没有与提议模型共同犯错 | [Prompt](prompts/03_verifier_and_confirm.md) | [回包](returns/03_independent_verifier_preregistration.md) | 34,149 | `03bdb3449dd00828b5853eb86f84d9e181fda81e73fb3715aa08ac870b0e1d07` |

## 外发包追源

- 外发包：`TEMP/T5_R04_EXTERNAL_RESEARCH_API_PIPELINE_FORK_20260811_R02.zip`
- ZIP SHA-256：`c54ade00961f1396ae0248da51961f721c171296de19c725c145072f71f28d1a`
- 包内 manifest SHA-256：`5024dc37a81664d25cdc8090a9575c578793e3fd13755a5d2ef2b1347837967e`
- 三份 Prompt SHA-256：`30fa9391356ae80799f87a2c5b014a8839772325e126d40b4a0d459d32cd4b81`、`63f1b80bb806cf0ecccc38a0bc85cc56f4e58e60510bb0aa544109de13b321f7`、`2c6e3ae95936e0b856e84fe5888c885e7c0255f03a4c0c42f3bdbb93cecc72eb`。

来源：Codex
