# 产品架构外部调查回包｜2026-08-09

状态：**外部候选先验，不产生运行权**

这个包保存 2026-08-09 产品架构调查的九题九回包，以及当时形成的一份消化稿。这里解决的是“以后能追到原问题、原回包和当时判断”的问题，不负责决定当前系统怎么跑。

九份回包都按原字节保存。它们可以帮助提出候选方案，但不能授权训练、模型推理、API 调用、Notion 写入、Git 操作或生产晋级。若外部报告与本地代码、冻结合同、运行回执或正式结果票冲突，以本地真源为准。

## 九题九回包

| 编号 | 调查题 | 问题原文在 TEMP 的位置 | 本包完整回包 |
|---|---|---|---|
| BRIEF_01 | 长篇小说创作系统的分层记忆与压缩，业界怎么做的？ | `TEMP/bgboard-audit-20260809-r01/external_research/BRIEF_01_hierarchical_memory_compression.md` | [RETURN_01_HIERARCHICAL_MEMORY_COMPRESSION_20260809_R01.md](returns/RETURN_01_HIERARCHICAL_MEMORY_COMPRESSION_20260809_R01.md) |
| BRIEF_02 | 怎么评测“结构化事实供给 → 下游创作”的承接效率？ | `TEMP/bgboard-audit-20260809-r01/external_research/BRIEF_02_downstream_consumption_eval.md` | [downstream_fact_consumption_evaluation.md](returns/downstream_fact_consumption_evaluation.md) |
| BRIEF_03 | 网文／小说创作方法论，怎么变成机器可用的“配方包”？ | `TEMP/bgboard-audit-20260809-r01/external_research/BRIEF_03_craft_methodology_structuring.md` | [RESEARCH_03_CRAFT_RECIPE_PACK_20260809_R01.md](returns/RESEARCH_03_CRAFT_RECIPE_PACK_20260809_R01.md) |
| BRIEF_04 | “情绪不够、钩子不强、期待感弱”能不能自动判定？标准从哪来？ | `TEMP/bgboard-audit-20260809-r01/external_research/BRIEF_04_reader_experience_metrics.md` | [RESEARCH_04_READER_EXPERIENCE_METRICS.md](returns/RESEARCH_04_READER_EXPERIENCE_METRICS.md) |
| BRIEF_05 | 长篇“吃书”检测——新内容和几千条旧事实怎么高效查矛盾？ | `TEMP/bgboard-audit-20260809-r01/external_research/BRIEF_05_longrange_consistency_checking.md` | [DEEP_RESEARCH_05_LONGRANGE_CONSISTENCY_CHECKING_20260809_R01.md](returns/DEEP_RESEARCH_05_LONGRANGE_CONSISTENCY_CHECKING_20260809_R01.md) |
| BRIEF_06 | 在 4B 小模型上找到的微调配方，换到更大的商用模型还有效吗？ | `TEMP/bgboard-audit-20260809-r01/external_research/BRIEF_06_small_model_proxy_transfer.md` | [RESEARCH_06_4B_PROXY_TO_COMMERCIAL_MOE_2026-08-09.md](returns/RESEARCH_06_4B_PROXY_TO_COMMERCIAL_MOE_2026-08-09.md) |
| BRIEF_07 | 拆解 4 个 Agent 持久记忆开源项目，哪些架构我们能直接学？ | `TEMP/bgboard-audit-20260809-r01/external_research/BRIEF_07_agent_memory_projects_study.md` | [AGENT_MEMORY_OPEN_SOURCE_ARCHITECTURE_RESEARCH_20260809_R01.md](returns/AGENT_MEMORY_OPEN_SOURCE_ARCHITECTURE_RESEARCH_20260809_R01.md) |
| BRIEF_08 | 叙事因果图——事件因果怎么抽、怎么判定、链怎么控制长度？ | `TEMP/bgboard-audit-20260809-r01/external_research/BRIEF_08_narrative_causal_graph.md` | [DEEP_RESEARCH_08_NARRATIVE_CAUSAL_GRAPH_20260809_R01.md](returns/DEEP_RESEARCH_08_NARRATIVE_CAUSAL_GRAPH_20260809_R01.md) |
| BRIEF_09 | 下游直接调 API 生成剧情——五个行为红线怎么测、哪家模型行？ | `TEMP/bgboard-audit-20260809-r01/external_research/BRIEF_09_downstream_api_behavior_eval.md` | [investigation_9_plot_api_redlines_R01.md](returns/investigation_9_plot_api_redlines_R01.md) |

## 原始来源链

原接收索引是 `TEMP/bgboard-audit-20260809-r01/returns/INDEX.md`。它记录：CZ 从 ChatGPT 各窗口拿回文件，原件放在 Downloads，随后复制进 TEMP 接收区。下表把两层来源逐份列清；BRIEF_01 的 Downloads 原名是“1结论.md”，进入 TEMP 时只改了文件名，文件内容没有变化。

| 编号 | TEMP 接收副本 | Downloads 原件 |
|---|---|---|
| BRIEF_01 | `TEMP/bgboard-audit-20260809-r01/returns/RETURN_01_HIERARCHICAL_MEMORY_COMPRESSION_20260809_R01.md` | `/Users/a1234/Downloads/1结论.md` |
| BRIEF_02 | `TEMP/bgboard-audit-20260809-r01/returns/downstream_fact_consumption_evaluation.md` | `/Users/a1234/Downloads/downstream_fact_consumption_evaluation.md` |
| BRIEF_03 | `TEMP/bgboard-audit-20260809-r01/returns/RESEARCH_03_CRAFT_RECIPE_PACK_20260809_R01.md` | `/Users/a1234/Downloads/RESEARCH_03_CRAFT_RECIPE_PACK_20260809_R01.md` |
| BRIEF_04 | `TEMP/bgboard-audit-20260809-r01/returns/RESEARCH_04_READER_EXPERIENCE_METRICS.md` | `/Users/a1234/Downloads/RESEARCH_04_READER_EXPERIENCE_METRICS.md` |
| BRIEF_05 | `TEMP/bgboard-audit-20260809-r01/returns/DEEP_RESEARCH_05_LONGRANGE_CONSISTENCY_CHECKING_20260809_R01.md` | `/Users/a1234/Downloads/DEEP_RESEARCH_05_LONGRANGE_CONSISTENCY_CHECKING_20260809_R01.md` |
| BRIEF_06 | `TEMP/bgboard-audit-20260809-r01/returns/RESEARCH_06_4B_PROXY_TO_COMMERCIAL_MOE_2026-08-09.md` | `/Users/a1234/Downloads/RESEARCH_06_4B_PROXY_TO_COMMERCIAL_MOE_2026-08-09.md` |
| BRIEF_07 | `TEMP/bgboard-audit-20260809-r01/returns/AGENT_MEMORY_OPEN_SOURCE_ARCHITECTURE_RESEARCH_20260809_R01.md` | `/Users/a1234/Downloads/AGENT_MEMORY_OPEN_SOURCE_ARCHITECTURE_RESEARCH_20260809_R01.md` |
| BRIEF_08 | `TEMP/bgboard-audit-20260809-r01/returns/DEEP_RESEARCH_08_NARRATIVE_CAUSAL_GRAPH_20260809_R01.md` | `/Users/a1234/Downloads/DEEP_RESEARCH_08_NARRATIVE_CAUSAL_GRAPH_20260809_R01.md` |
| BRIEF_09 | `TEMP/bgboard-audit-20260809-r01/returns/investigation_9_plot_api_redlines_R01.md` | `/Users/a1234/Downloads/investigation_9_plot_api_redlines_R01.md` |

当前归档时，九份 TEMP 接收副本与对应 Downloads 原件都已逐字节比对一致。Downloads 只是来源位置，后续即使清理，也不影响本包保存的完整回包。

## 消化稿与排除项

- [02_RETURNS_DIGEST.md](02_RETURNS_DIGEST.md) 逐字节保存自 `TEMP/bgboard-audit-20260809-r01/04_RETURNS_DIGEST.md`。它记录当时如何消化九份回包，不是当前执行票。
- [02_PRODUCT_OPEN_DESIGN_NOTES.md](02_PRODUCT_OPEN_DESIGN_NOTES.md) 保存消化稿引用的当时开放问题记录。
- [returns/INDEX.md](returns/INDEX.md) 是本知识包内可点击的九份回包索引。
- 三个文件名带 `-2-` 的材料是当时发给 ChatGPT 的背景副本，不是真正回包，因此没有复制进本包：
  - `04-03_CREATION_AND_MEMORY_PIPELINES-2-.md`
  - `07-05_CURRENT_DECISIONS_AND_OPEN_QUESTIONS-2-.md`
  - `08-02_SYSTEM_ARCHITECTURE_AND_TRUTH_LAYERS-2-.md`
- [REPORT_MANIFEST.json](REPORT_MANIFEST.json) 保存九份回包、消化稿和配套文档的路径、字节数、SHA-256 摘要，以及六项执行权限均为关闭的机器记录。

来源：Codex
