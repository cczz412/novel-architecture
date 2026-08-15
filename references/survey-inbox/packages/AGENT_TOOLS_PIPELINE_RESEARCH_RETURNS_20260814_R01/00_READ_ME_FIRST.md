# 七份 Agent 工具／管线回包｜2026-08-14

状态：**历史外部调查证据／候选先验，不产生产品结论或执行权**

这个包逐字节保存 CZ 于 2026-08-14 发回的七份 ChatGPT 调查回包。七份 Prompt 出自 [17_EXTERNAL_PROMPTS_AGENT_TOOLS_PIPELINE_20260814_R01.md](../../../../novel-mvp/design/17_EXTERNAL_PROMPTS_AGENT_TOOLS_PIPELINE_20260814_R01.md)（相对本仓根再上溯到同级 `novel-mvp/`）。与 SI-006（产品长什么样）、SI-007（设计审查＋技术空白）分工：这轮管「工具怎么暴露、管线怎么走、生成前怎么拦」。

七份回包可以帮助设计：Agent 工具菜单、管线游标、聊天／点选双通道、执行包编译、生成前守卫、触发器外壳、画布指示器。它们是公开材料整理＋外部模型推断，不是实测，不能单独改 R10 或开工。结论与 CZ 当前指令、Notion 正式账序、现行共同背景板、项目 CURRENT、正式合同或结果票冲突时，以更高层真源为准。

本包不授权产品拍板、施工、训练、模型推理、API 调用、Notion 写入、Git 操作、外发或生产晋级。

## 回包

| 编号 | 对应 Prompt | 本包文件 | 原始归因 |
|---|---|---|---|
| RETURN_01 | P1 工具面：产品该暴露哪些工具 | [公开产品怎样处理“管线各站”.md](returns/公开产品怎样处理“管线各站”.md) | ChatGPT |
| RETURN_02 | P2 管线进度：防止跳跃和误关工作 | [2222调查结论.md](returns/2222调查结论.md) | ChatGPT |
| RETURN_03 | P3 双通道：聊天自动调工具 vs 一步一步点选 | [1. 成熟产品怎样收住双通道.md](returns/1. 成熟产品怎样收住双通道.md) | ChatGPT |
| RETURN_04 | P4 编大纲时怎样挑上下文、压缩、缺料再读 | [1. 编译、RAG、Agent 各管什么.md](returns/1. 编译、RAG、Agent 各管什么.md) | ChatGPT |
| RETURN_05 | P5 生成前检查；规则 vs 子 Agent 只回 OK | [1. 四类系统怎么做生成前守卫.md](returns/1. 四类系统怎么做生成前守卫.md) | ChatGPT |
| RETURN_06 | P6 世界规则／Hook／义务／规划的触发器 | [1. 各类系统的触发器通常有什么.md](returns/1. 各类系统的触发器通常有什么.md) | ChatGPT |
| RETURN_07 | P7 画布指示器、节奏、理论插件选用 | [✅ 核心结论.md](returns/✅ 核心结论.md) | ChatGPT |

## 保存口径

- 七份正文保持 Downloads 原文件名和原字节，不加前言、不删改结论。
- [机器清单](REPORT_MANIFEST.json) 保存每份的 Downloads 来源、SHA-256、字节数、换行数、对应 Prompt 主题。
- 交叉消化（可复用、仍是候选）：[02_RETURNS_DIGEST.md](02_RETURNS_DIGEST.md)

Downloads 里另有一份未点名、未入本包的 `B：故事内触发器.md`（约 495KB）。要并进来再说一声。

来源：CZ 发出与回收（2026-08-14）；Cursor 搬运登记
