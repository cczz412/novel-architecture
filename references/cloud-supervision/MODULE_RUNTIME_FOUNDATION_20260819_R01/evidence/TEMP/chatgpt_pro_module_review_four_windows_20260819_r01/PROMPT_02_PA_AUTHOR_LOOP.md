# ChatGPT Pro 窗口 2：作者工作稿、检测、收工与显式交棒

请使用你当前可用的最高推理强度，完整阅读共用 ZIP 后再作答。

你是这个小说创作系统的资深架构审查员。这次只审下面这条能力链：

`作者工作稿 → T14 当场检测 → 作者处置 finding → full_check / skip_check / no_prose 收工 → 作者显式“以这篇为准” → C10 材料身份 → C11 章节版本 → C1 current 章节视图 → planstore handover_parts`

这不是产品愿景讨论，也不是让你重做整个平台。请把现有合同、当前代码和已经通过的局部切片拼成一条诚实可施工的路线，并明确哪些地方还不能拼。

## 硬边界

- 工作稿是作者工作态资产，不是 C1、冻结书稿、事实证据或 actual。
- AI 不得续写、润色、补写或修改作者正文。
- T14 provider 只负责 finding 分类、逐字证据和诊断理由；正式身份、水位、coverage、Schema 与 stale 判断由程序负责。
- `status=completed` 只表示检测完整发生，不表示 PASS、clean 或 all clear。
- `mismatch / missing / unplanned / unknown` 都可以存在于合法 completed 结果中。
- 只有作者能决定改工作稿、保持规划、进入规划编辑、跳过检测或显式交棒。
- `skip_check` 不等于检测通过；`no_prose` 不等于写成、关章、actual 或自动开下一章。
- 收工动作本身不能产生 C1、handover、facts、actual 或 chapter close。
- 显式交棒必须逐字采用 current 作者原文，不得改标点、清洗或补写。
- C11 INITIAL 必须一次通过 ledger、INITIAL 位置、C10 origin 和 current `CONFIRMED + CHAPTER` 门。
- `CHAPTER_REVISION_COMMIT_ACTION` 不能自行发新 `chapter_id`；C1 只是 C11 current revision 的物化视图。
- planstore 只能消费已成功持久化并复核 current ref 的 C1 v1，不能自己伪造 C1。
- AuthorWorkspace 是作者隔离边界；业务入口不得接任意路径、调用方作者号或项目号。
- 不建设统一工作流平台，不新建第二套 plan writer、fact writer、真值锁、幂等系统或治理账。

## 请先核实的现状

- current 工作稿可保存、严格递增、幂等重放并在重启后读回；
- 显式交棒、skip_check、no_prose 已有只读 preflight，但没有 C10／C11／C1 接收 runtime；
- current 工作稿和 current 章槽可冻结成零模型检测输入包；
- provider 只能交 `judgments`，程序生成并验证正式 14 字段 `WRITING_DESK_CHECK_RESULT v1`；
- 检测结果还没有明确长期 runtime owner／持久化入口；
- C11 有合同、Schema、validator 和 fixtures，但缺完整产品 writer 与跨 owner coordinator；
- chapter workspace 只保存调用方给出的合法 C1 v1，不创建 C11 revision；
- 旧 `planstore.accept_work_draft_handover` 会自行分配 chapter ID 并写 legacy C1 v0；
- AuthorWorkspace 与旧 planstore 是两套物理事务边界。

这些是待核摘要，若代码证明不同，以代码和直接测试为准。

## 必须回答

### 1. T14 结果 owner 必须二选一

请在当前 MVP 明确选主路线，不要回答“都可以”：

- A：完整、已程序验证的检测结果对象直接交给 `full_check` preflight；接收端重新逐字段复核，不长期保存检测结果。
- B：检测结果先保存到 T14 owner 持久层；后续消费者只携带 `check_result_ref`，从 owner 解析并校验 current／stale。

请重点判断：

- 应用重启后能否解析 `check_result_ref`；
- 作者隔一段时间后再处置 finding 或 full-check 怎么办；
- mismatch 的 `finding_ref` 和 unknown 裁决怎样回到原结果；
- 工作稿或章纲变化后，旧结果怎样保留但不再 current；
- 是否会产生第二份结果真值；
- AuthorWorkspace 隔离、未来只替换 StorageBackend 是否成立；
- 幂等、竞态、损坏、读中变化和失败不覆盖怎样处理。

如果 A 只能当 intake／transport，而 B 才是 owner，可以这样裁决，但不能继续说两个并列。给出最小存储形态：一个可见逻辑键、不可变 blob＋轻索引，或更小的现有机制，并说明理由。不要顺手造通用检测平台。

### 2. 设计 `full_check` 最小只读 preflight

写清：

- 输入与输出；
- 从哪里解析正式检测结果；
- 复验哪些工作稿、正文 SHA、章纲、plan 水位和 scope；
- 怎样证明 requirement coverage 是当前全章且完整；
- provider 或 preflight 读取期间来源变化时怎样失败；
- 哪些错误必须在任何写入前发生；
- 为什么含 mismatch／missing／unplanned／unknown 的 completed 结果仍可被引用；
- 返回怎样只表达 `completed_result_referenced`，同时 handover、chapter close、truth 都为 none；
- 哪些回执需要幂等，哪些只是短命投影。

不要加 all-clear 门，也不要把 preflight 写成收工状态机。

### 3. 判断检测后作者处置的真实消费者

逐项判断：

- `mismatch` 的 `edit_work / keep_plan / edit_plan` 合同是否够用；
- `unknown` 的作者人工裁决是否够用；
- `missing / unplanned` 是否真需要新动作；
- 哪些动作只返回下一入口，哪些需要保存；
- 处置后怎样让旧结果 stale，什么时候需要重新检测；
- 为什么 `keep_plan` 不能把 finding 改成 resolved；
- 处置回执由谁保存、保存多久、是否有消费者。

没有消费者就不要新建 disposition ledger。

### 4. 设计显式交棒到 C10／C11／C1 的最小安全接缝

现在四个核心缺口是：

- 工作稿没有冻结 source、material unit、identity revision 和 source span；
- INITIAL 前没有唯一 chapter ID 分配 owner；
- C11 没有 runtime writer／持久化入口；
- AuthorWorkspace 与 planstore 不是同一事务边界。

请回答：

- current 工作稿是否应先冻结为受控 source；
- source 怎样产生可逐字回放的 C10 material unit；
- `CONFIRMED + CHAPTER` 使用什么现有 authority，为什么不是模型自行确认；
- 谁唯一分配 stable chapter ID；
- C11 ledger、C1 current view、C10→revision projection receipt 各由谁写；
- planstore 何时才可消费 C1 v1；
- 旧 handover 入口哪些能复用，哪些必须拆掉或退役；
- C1 成功但 planstore 失败后怎样安全重试；
- 正式合同的原子组与两套物理事务是否存在真矛盾；
- 若无法真正跨 owner 原子，最小诚实状态、恢复方式和禁止宣称是什么。

不能用“先写再说”或默认最终一致糊过去。合同与 runtime 不一致时，请明确标 GAP 和最小决策点。

### 5. 判断 `no_prose` 与规划进度

“规划进度 +1”的 owner 是否必须现在解决？若没有唯一消费者或 owner，建议继续保持 GAP，不要为了流程漂亮造 progress ledger，也不能让 no_prose 写 plan、actual、chapter close 或自动开下一章。

### 6. 拆成 3～6 张本地施工票

每张写清：

- 一句话目的；
- owner／模块；
- 精确输入和输出；
- 最小建议写集与禁改文件；
- 前置依赖；
- 一个正常例和关键失败例；
- 完成后作者能多做什么；
- 仍不能宣称什么；
- 哪种情况必须停下问 CZ。

优先单 owner、语义唯一、能独立验收的切片。不要为了七窗常亮造票。

## 交付

请返回 ZIP，根目录只放：

`PA_AUTHOR_DRAFT_CHECK_CLOSEOUT_HANDOVER_REVIEW.md`

Markdown 至少包含：

1. 一页结论：主路线、T14 owner 选择、三个最大阻断；
2. 现状能力图：已可运行／只有 preflight／缺 runtime；
3. T14 owner 二选一裁决和淘汰路线的失败场景；
4. full_check 精确调用顺序和失败顺序；
5. 作者处置的消费者与持久化判断；
6. 显式交棒时序图，标明 C10、C11、C1、AuthorWorkspace、planstore owner；
7. 合同与 runtime 冲突清单；
8. 3～6 张按依赖排序的施工票；
9. 最小验收场景表，至少覆盖重启、work stale、plan stale、coverage 缺项、completed 含 mismatch、skip_check、no_prose、C10 不合格、chapter ID 双号源、C11 成功但 planstore 失败、跨作者拒绝、失败不留半份状态；
10. 仍需 CZ 拍板的问题。

每个重要结论引用包内相对路径，能给行号就给行号。明确区分现有正式规则、代码现状、你的建议和待拍板事项。不要只给抽象图，也不要直接重写代码。

来源：Codex
