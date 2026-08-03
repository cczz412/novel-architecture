# ChatGPT Deep Research Prompt｜生成侧（消费端）五个调查

你收到的 ZIP 不是一个已完成的生成系统，而是我们当前的事实抽取合同、大纲中枢方向、长线账方向和研究空白。请先读 `00_READ_ME_FOR_REVIEWER.md`、`00_ROUTE_MAP.md`，再按四层路线阅读。

## 包内身份顺序

- `01_current_truth/.../NOTION_TRUTH_SNAPSHOT.md`：已拍、现行、设计支撑和历史候选的身份边界。
- `01_current_truth/.../01_CURRENT_SYSTEM_BRIEF.md`：你必须对齐的当前系统概况。
- `02_current_route/.../02_FACT_STORE_AND_EXTRACTION_CONTRACT.md`：事实库可提供什么。
- `02_current_route/.../03_OUTLINE_EXECUTION_AND_RETRIEVAL.md`：第 N+1 章的既有执行包与检索候选。
- `02_current_route/.../04_LONG_TERM_MEMORY_CONFLICT_QC.md`：长期记忆和冲突检测的已有分层。
- `02_current_route/.../05_RESEARCH_GAPS_AND_DECISIONS.md`：真正缺的公开证据和回包后待 CZ 决定的题。
- `03_upstream_evidence/.../HISTORICAL_CANDIDATE_NOT_TRUTH.md`：只供证伪的历史候选，不是已实现功能。

## 你要完成的五项深研

1. 长篇一致性生成：outline-conditioned generation、递归/检索式记忆、人物卡/事实库/剧情状态，重点看几十万字尺度的实测与局限。
2. 事实库→生成接口：第 N+1 章取哪些事实、用什么键、如何重排/分配 token、哪些检索失败最常见。
3. 冲突检测器：程序硬冲突与模型软冲突的类型学、精度/召回/一致率、误报、调用成本和实用边界。
4. 剧情控制引擎：伏笔回收、反转节奏、信息揭示、爽点密度等效果怎样变成章/场景/节拍级控制信号，以及效果证据。
5. 大纲规模上限：全书→卷→章的分层大纲和事实库在当前模型上下文中的有效利用率，以及分层规划＋局部检索的工程实践。

这里的“从头生成”包含两个连续阶段：先研究首章前没有历史事实账时，人物、世界规则、全书/卷目标和初始剧情状态怎样冷启动；再研究从第 2 章起按第 N+1 章循环消费事实库与大纲。不要只回答续写。目标域以中文百章、几十万字长篇网文为主。

## 证据标准

- 调查截止日为 2026-08-01。
- 优先学术论文、官方技术报告/文档、公开代码和公开数据集。商业产品的宣传语只能标为供应商声称。
- 每个重要结论紧跟可点开的原始来源。数字必须标注数据集、任务单位、文本长度、模型、对照组和日期。
- 必须区分短故事、单章、几章和几十万字长篇；不得把短尺度成绩直接外推。
- 必须区分标称窗口和有效利用量，并调查 lost-in-the-middle、干扰、过期摘要、检索漏项与错误记忆累积。
- 没有可靠数字时直接写“未找到可支持数字”。
- 你的建议是外部顾问候选，不改写本包的现行边界，不替 CZ 选默认。
- 本路线的任务单和授权票覆盖通用 SOP；通用 SOP 中的 Notion 回写、回包后本地施工等条款不适用于本轮。不得替我们写回 Notion、调用模型/API 或改本地仓库。

## 必答的映射表

在综合报告中给出一张“公开证据→我们现有对象”映射表，至少覆盖：

- 事实、状态、知情/误信、因果、Hook、义务/承诺、世界规则、故事线、章节大纲、章节出口、体验目标。
- 建议常驻、按需回取、冲突时回证据，还是应当废弃。
- 索引键、时间范围、排序信号、token 预算和失败发现方式。

## 回件 ZIP

请生成一个可下载 ZIP。ZIP 根目录包含恰好 8 份实质文件：

1. `00_EXECUTIVE_VERDICT.md`
2. `01_LONG_FORM_COHERENCE.md`
3. `02_FACT_TO_GENERATION_INTERFACE.md`
4. `03_CONFLICT_DETECTOR.md`
5. `04_PLOT_CONTROL_ENGINE.md`
6. `05_OUTLINE_SCALE_LIMITS.md`
7. `06_RECOMMENDED_ARCHITECTURE_AND_EXPERIMENTS.md`
8. `SOURCE_EVIDENCE_MATRIX.csv`

另附 `MANIFEST.json` 和 `SHA256SUMS`，不占上面 8 份；ZIP 根目录总共恰好 10 个成员，不得加其他业务文件。

`06_RECOMMENDED_ARCHITECTURE_AND_EXPERIMENTS.md` 要给出：

- 适合我们当前对象的 2～3 个候选架构，不要只给一个答案。
- 每个候选的优点、失败方式、调用量、运维复杂度和适用边界。
- 一个最小实验阶梯：零 API 夹具→短篇/几章→卷级→长篇；每阶段写输入、对照组、指标、预算变量和停止线。
- 一张“现在能做/需验证/公开证据不足”分界表。

CSV 每行至少包含：`claim_id,topic,claim,source_title,source_url,source_type,published_date,evaluation_scale,metric,result,limitations,confidence,applies_to_our_object`。

运输规则：成员路径必须是相对路径；禁止绝对路径、`..`、重复成员和符号链接。`SHA256SUMS` 覆盖 8 份实质文件并可逐项复算。不要输出完整思考过程，只给证据、分析、限制和候选方案。

来源：Codex
