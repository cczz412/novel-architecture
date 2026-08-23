# PACK_00 包头｜SURVEY_PACK_20260823

- 包名：`SURVEY_PACK_20260823`
- 打包日期：2026-08-23
- 源 commit（写死）：`87aad7abf70599ce0ce9ba3b0eefdaa1525fe762`
- 短号：`87aad7ab`
- 提交说明：`docs(work): #110 挂上对照表续跑备忘`
- 分支：`cursor/issue-110-lost-design-inventory`（PR #112 同分支）
- 工单：GitHub issue #110

## 本包怎么用（先看完再读别的分册）

**与本包冲突的任何旧材料以本包为准。**

ChatGPT／Deep Research 项目里只放这次打的快照包。旧的三栏背景卡、原子需求卡、旧报告卡、旧对话记忆，一律删掉或忽略。包外链接在网页项目里常常打不开——以本包已经收录的正文为准，不要靠记忆补。

本包是调查用快照，不是合同修订，不是产品拍板。

## 两个网页项目分别上传什么

平铺这几个大 md 即可（ChatGPT 工作区全文件展开或平铺都行；本包已经合成少数文件，按平铺传最省事）。

| 项目 | 上传 | 不要上传 |
|---|---|---|
| 单A Deep Research（外调） | PACK_00、PACK_01、PACK_02、PACK_03、PACK_04 | 原子需求卡；R14 另外 10 份；仓内其它文件 |
| 单B ChatGPT Pro（内审） | PACK_00、PACK_01、PACK_02、PACK_03 | **PACK_04**；原子需求卡；任何外网材料 |

内审项目不放 PACK_04，是为了防止外部建议被当成我们已经拍过的决定。

## 这轮故意没收的

| 东西 | 为什么没收 |
|---|---|
| R14 另外 10 份（01 北极星、04 抽取策略、06 同步、08 校验风险、00 先读、用户数据权、REFERENCE 集成、语义债、两个 json） | 制度背景只需要 02／03／05／07；14 份全放＝放得过多 |
| 原子需求卡（现行 142 条；旧 127 条更过期） | 调查对象是台账形态不是题目，放着会带偏 |
| 报告背景卡进内审项目 | 外调才用；内审只读制度＋合同＋#110 三件 |

## 分册文件

| 文件 | 用途 | 源文件数 | 大约体积 | sha256 |
|---|---|---|---|---|
| `PACK_00_HEADER.md` | 本包头 | — | 约 7 KB | （本文件，不另算） |
| `PACK_01_INSTITUTION.md` | R14 四份 | 4 | 224 KB | `9eff3dd95d206b853c7e68271cd7c632b60bd1838c47454f9dacadb3328d4954` |
| `PACK_02_CONTRACTS.md` | 34 份合同 | 34 | 263 KB | `05d47b3c3227dc79384cc772cdcd40dca62aeba5fa1a1b1a9dbee54d6ab6def3` |
| `PACK_03_ISSUE110.md` | #110 三件 | 3 | 53 KB | `79e7f6f95e5e8d631449bced6058712007473dd7b27666a80dcd826ff19afc1f` |
| `PACK_04_EXTERNAL_KB.md` | 外调报告背景 | 4 | 22 KB | `3cdf2dfc9b9186b21228c6b0a6561580b6c2b5fb8803f72af0042e4a63c0cbc6` |

## 源文件清单（git blob 对应该 commit）

### PACK_01

| 源路径 | blob 前 12 位 | 字节 |
|---|---|---|
| `references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/02_SYSTEM_ARCHITECTURE_AND_TRUTH_LAYERS.md` | `dd194756e29a` | 48271 |
| `references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/03_CREATION_AND_MEMORY_PIPELINES.md` | `386d16a4bd53` | 71542 |
| `references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/05_CURRENT_DECISIONS_AND_OPEN_QUESTIONS.md` | `ea91f2971e7f` | 47998 |
| `references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/07_GLOSSARY.md` | `4b15b22ef4c0` | 53531 |

### PACK_02

| 源路径 | blob 前 12 位 | 字节 |
|---|---|---|
| `novel-mvp/contracts/LEDGER_ENTRY_ENVELOPE.md` | `05adab4b392e` | 8043 |
| `novel-mvp/contracts/LEDGER_RECALL_CODE.md` | `b3535dc634cd` | 3773 |
| `novel-mvp/contracts/SETTING_LEDGER_STORAGE.md` | `d46a1bdbaba7` | 5930 |
| `novel-mvp/contracts/PLAN_LEDGER_STORAGE.md` | `afdc31e62c8c` | 71935 |
| `novel-mvp/contracts/CHARACTER_LEDGER_CONTENT.md` | `ba6cd88cb156` | 9729 |
| `novel-mvp/contracts/LOCATION_LEDGER_CONTENT.md` | `68dd37dd6026` | 3535 |
| `novel-mvp/contracts/ITEM_LEDGER_CONTENT.md` | `6f4d6add4f39` | 3164 |
| `novel-mvp/contracts/FACTION_LEDGER_CONTENT.md` | `d7610b573e09` | 3241 |
| `novel-mvp/contracts/SYSTEM_LEDGER_CONTENT.md` | `0e2a12e9a260` | 3717 |
| `novel-mvp/contracts/WORLD_RULE_LEDGER_CONTENT.md` | `969e5c3c146a` | 3644 |
| `novel-mvp/contracts/PLAN_VOLUME_CONTENT.md` | `5b1ad04ec871` | 3780 |
| `novel-mvp/contracts/PLAN_DESTINY_CONTENT.md` | `d1e627f86189` | 4220 |
| `novel-mvp/contracts/PLAN_INSPIRATION_CONTENT.md` | `12ad8c66d426` | 3430 |
| `novel-mvp/contracts/C1_CHAPTER_DOC.md` | `5ae20dc1882e` | 4774 |
| `novel-mvp/contracts/C2_SEGMENT.md` | `c193ad57afaf` | 2733 |
| `novel-mvp/contracts/C3_FACT_CANDIDATE.md` | `a7a6c1080f50` | 2303 |
| `novel-mvp/contracts/C4_FACT_QUERY.md` | `15d0869894ad` | 6256 |
| `novel-mvp/contracts/C6_HEALTH_REPORT.md` | `d5f3d3d3d3bb` | 9025 |
| `novel-mvp/contracts/C7_PLOT_LAYER.md` | `5064f613608d` | 6477 |
| `novel-mvp/contracts/C7_SELECTION_ACTION.md` | `d1b2b0a702ce` | 5613 |
| `novel-mvp/contracts/C10_INTAKE_MATERIAL_IDENTITY.md` | `2fc40f15b057` | 18803 |
| `novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md` | `6c02565783c2` | 6518 |
| `novel-mvp/contracts/CHAPTER_SLOT_SNAPSHOT.md` | `576feb283872` | 3524 |
| `novel-mvp/contracts/FACT_REVIEW_ACTION.md` | `cfae2c518e07` | 3771 |
| `novel-mvp/contracts/RECONCILIATION_CANDIDATE.md` | `8f05011a2c8c` | 3913 |
| `novel-mvp/contracts/RECONCILIATION_FACT_ADMISSION_ACTION.md` | `9a70d47a44cf` | 4756 |
| `novel-mvp/contracts/WRITING_DESK_WORK_DRAFT.md` | `3f2559e3995d` | 4304 |
| `novel-mvp/contracts/WORK_DRAFT_HANDOVER_ACTION.md` | `69467c245875` | 4214 |
| `novel-mvp/contracts/WRITING_DESK_CHECK_RESULT.md` | `e6234a935e59` | 8958 |
| `novel-mvp/contracts/WRITING_DESK_CHECK_DISPOSITION_ACTION.md` | `20fc2c628f90` | 7222 |
| `novel-mvp/contracts/WRITING_DESK_CHECK_UNKNOWN_ADJUDICATION_ACTION.md` | `49fc9f947b5f` | 6940 |
| `novel-mvp/contracts/WRITING_DESK_CLOSEOUT_ACTION.md` | `f67a0a4929b9` | 4366 |
| `novel-mvp/contracts/CHAPTER_REVISION_COMMIT_ACTION.md` | `b7746c0ddb06` | 4913 |
| `novel-mvp/contracts/CHAPTER_REVISION_COMMIT_RECEIPT.md` | `553278b4166c` | 2070 |

### PACK_03

| 源路径 | blob 前 12 位 | 字节 |
|---|---|---|
| `work/issue110_lost_design_inventory_20260823/00_READ_ME.md` | `6781db88ccc9` | 3008 |
| `work/issue110_lost_design_inventory_20260823/CANDIDATE_LIST.md` | `af302ed1157d` | 34242 |
| `work/issue110_lost_design_inventory_20260823/CHECKPOINT_20260823.md` | `08b9020e0e58` | 14393 |

### PACK_04

| 源路径 | blob 前 12 位 | 字节 |
|---|---|---|
| `references/external-knowledge-base/README.md` | `54a25ec78a3a` | 1374 |
| `references/external-knowledge-base/EXTERNAL_KNOWLEDGE_BASE_20260815_R01/background/02_CRAFT_AND_READER_EXPERIENCE.md` | `883d0a3c8cb5` | 5966 |
| `references/external-knowledge-base/EXTERNAL_KNOWLEDGE_BASE_20260815_R01/background/05_EXTRACTION_EVALUATION_AND_EVIDENCE.md` | `211ada42890e` | 3777 |
| `references/external-knowledge-base/EXTERNAL_KNOWLEDGE_BASE_20260815_R01/04_CONFLICT_AND_SUPERSESSION_MAP.md` | `c0f0d3539956` | 8676 |

## 打包时没动的东西

- 不改 `novel-mvp/contracts/` 任何文件
- 不改 R14 原件
- 不关 #110
- 不把对照表 v0.1 写成终稿

来源：CZ 2026-08-23 拍板（先调查再动笔；背景包只放这次快照；外发网页项目由人贴）。
