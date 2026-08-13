# 已验证结论账（首批 12 条，2026-08-12 核对版）

每条格式固定：一句人话结论 → 适用边界 → 证据在哪。标签只有五种：`已验证`（正式票直接支持）、`负结果`（正式证明此路不通）、`待复验`（只在一个环境成立）、`教训`（事故换来的规矩）、`候选先验`（外部证据或未进正式合同的建议）。

这页只做索引。条目与票冲突时以票为准；进度页只用来找最新入口，不单独充当实验结果票。

## 抽取效果类

**E-01｜未微调本地 4B 的当前 DEV 组合** `已验证＋待复验`  
在当前物理 REAL24／DEV24 上，未微调本地 4B 依次保留了 READ2、OUT2-IDLIST、每侧 H180、完整目标责任段、RULE0、EX0，形成当前临时守擂组合；完整目标段实测为 620–923 个 Unicode 字符。  
边界：这是同一本地 4B、同一 DEV24 上逐家族筛出的 Demo 组合，不是商用 API 排名、Mini 结论、未见确认结果或生产默认。  
证据：`finetuning/experiments/T5_R04_FACT_EXTRACTION_EXPERIMENT_ROADMAP_20260810_R06/BASE_CONTEXT_DEMO_RESULT_TICKET.json`、`finetuning/experiments/T5_R04_FACT_EXTRACTION_EXPERIMENT_ROADMAP_20260810_R07/BASE_READ2_OUT_FORMAT_RESULT_TICKET.json`、`finetuning/experiments/T5_R04_FACT_EXTRACTION_EXPERIMENT_ROADMAP_20260810_R08/CONTEXT_HALO_RESULT_TICKET.json`、`finetuning/experiments/T5_R04_FACT_EXTRACTION_EXPERIMENT_ROADMAP_20260810_R09/TARGET_BLOCK_RESULT_TICKET.json`、`finetuning/experiments/T5_R04_FACT_EXTRACTION_EXPERIMENT_ROADMAP_20260810_R10/RULE_RESULT_TICKET.json`、`finetuning/experiments/T5_R04_FACT_EXTRACTION_EXPERIMENT_ROADMAP_20260811_R11/EX_RESULT_TICKET.json`。

**E-02｜训练 READ 三臂无承接者** `负结果`  
当前低剂量 TRAIN36、24 microsteps、单 seed 的训练 READ 三臂没有一臂获得承接资格：READ1 格式门失败，READ4 证据越界，只有 READ2 完成语义比较，但 LoRA F1 低于同题 matched Base。  
边界：只否定这套训练条件下从 READ 接到 OUT 的路线；不永久淘汰 4B，不否定 Mini，也不证明未来换教材或配方仍无效。  
证据：`finetuning/experiments/T5_R04_FACT_EXTRACTION_EXPERIMENT_ROADMAP_20260810_R05/TRAINED_READ_NO_WINNER_RESULT_TICKET.json`。

**E-03｜结构优先于立即追加微调（当前证据范围内）** `已验证＋待复验`  
唯一完成同题语义比较的 READ2 中，未微调 Base F1 为 0.352941，LoRA F1 为 0.342967；另外两条训练 READ 没过资格门。当前工程判断是先把输入结构、Prompt 和管线跑明白，再讨论用微调压成本、压时延或固化稳定窄错误。  
边界：证据只覆盖当前本地 4B、当前 DEV24 和当前训练条件；不能简写成“Base 打赢所有训练版”或“微调永远没用”。  
证据：同 E-02 结果票；教材归因边界见 `finetuning/experiments/T5_R04_CURRICULUM_ATTRIBUTION_ELIGIBILITY_20260811_R01/ATTRIBUTION_ELIGIBILITY_RESULT.json`。

**E-04｜缺资源账时，追加旧块语义复核也分不出候选** `已验证`  
两块精确分加两块未知边界后，20 个模型组仍有 18 个留在相对前沿；Token、费用或时延缺失造成跨模型不可比，继续审 C02-B01 或 C03-B01 不能补回这些账，因此停止补审。  
边界：这是当前 DEV4 部分覆盖派生的停止判例，不表示盲审无用，也不是 DISCRIM17 的候选名单。  
证据：`TEMP/t5_r04_overnight_control_20260811_r01/dev4_two_exact_shortlist_r01/SHORTLIST_DECISION.json`。

## 实验方法类

**E-05｜逻辑题与真实请求分账** `已验证`  
逻辑题记录“原本要测什么”，真实请求记录“网络实际发了什么、失败与重试怎样发生”；两本账绑定后，才能同时回答模型质量和运输成本。费用没完成对账时保留待对账，不把空值写成 0。  
边界：这是当前 DISCRIM 评分和执行合同采用的口径；它不允许补写、吞掉或重算历史请求。  
证据：`TEMP/t5_r04_overnight_control_20260811_r01/fresh_discrim_scoring_contract_and_synthetic_gate_r03/FRESH_DISCRIM_SCORING_CONTRACT_R03.json`，以及 `TEMP/t5_r04_overnight_control_20260811_r01/.fresh_discrim4_formal_grid_preflight_r03.staging/CANARY_TASKS_7.jsonl`、`CANARY_ATTEMPTS_7.jsonl`、`CANARY_COMPLETION_RECEIPT_R02.json`。

**E-06｜结构化输出 Prompt 必须把取值合同写进实际发送正文** `教训`  
DISCRIM4 材料复核 R01 的 8 次真实请求都因 Prompt 与 Schema 接线不一致形成输出合同失败；R02 保留同模型、同切片、同参数，只把完整枚举和精确 JSON 骨架写入 Prompt。R02 的结构接线检查通过，但 8 份里仍有 3 份因复述正文被原样判失败，只有 5 份获得材料裁决资格。  
规矩：凡是要求固定 JSON 的调用，枚举值、字段约束和完整 JSON 骨架都要出现在实际发送 Prompt 里；不能只把约束留在旁边的 Schema 文件。  
证据：`TEMP/t5_r04_overnight_control_20260811_r01/fresh_discrim4_selected_blocks_material_review_r01/MATERIAL_REVIEW_RECEIPT.json` 与 `TEMP/t5_r04_overnight_control_20260811_r01/fresh_discrim4_selected_blocks_material_review_recovery_r02/MATERIAL_REVIEW_RECOVERY_RECEIPT_R02.json`。

**E-07｜盲标 A／B＋C 仲裁＋halo 禁令** `已验证＋教训`  
A、B 各自冻结后交第三角色仲裁，并用七字段等价门把仲裁结果绑定到正式 Gold。事故教训是 O04-G010：只能由责任区外 halo 支持的“误信”不能写进正分 Gold，修订后只保留责任区直接支持的“霁月作出转述”。  
边界：这证明当前 DISCRIM4 Gold 流程和这一次定向修复可用，不自动变成所有任务的通用标注合同。  
证据：`TEMP/t5_r04_overnight_control_20260811_r01/FRESH_DISCRIM4_GOLD_R02_INDEPENDENT_ACCEPTANCE_R01.json` 与 `TEMP/t5_r04_overnight_control_20260811_r01/fresh_discrim4_final_gold_and_task_lock_r02/GOLD_AND_TASK_LOCK_RECEIPT.json`。

**E-08｜材料门先保单事件完整，再看字数** `已验证`  
DISCRIM4 的正式材料选择按同一件事或连续动作／因果链是否讲完整来判断；去空白 Unicode 字符硬范围 450–1000，推荐 600–800，动态目标 760，短拟声词和承接动作不单独切断。旧硬合格池耗尽时，第 10 章预冻结 3 个自然窗，只对第一个窗双审即通过，后两个窗没有调用。  
边界：这是 DISCRIM4 判别材料的冻结口径，不覆盖 E-01 的本地 DEV 完整目标段 620–923 实测范围，也不是全产品永久切块参数。  
证据：`TEMP/t5_r04_overnight_control_20260811_r01/fresh_discrim4_o10_semantic_natural_window_reselection_r01/O10_SEMANTIC_NATURAL_WINDOW_RESELECTION_RECEIPT_R01.json`，以及该轮受控路线入口 `00_READ_ME_FIRST.md` 的材料门记录。

**E-09｜部分覆盖试选的方法已批，真实试选器仍未过门** `待复验`  
方法是：已审行算精确分，未审行只算未知人工标签的最坏／最好边界；若足以分出 3–5 个候选就停止全量盲审，否则只补审能改变结论的行。真实数据接入前，试选器必须通过独立反例审查。  
当前状态：R08 虽通过 46 项自测，但独立反例仍发现边界硬编码、私有成员未纳入签名、并发可双消费、晚命中依赖隐藏标记等问题；R08 已作为失败证据封存，下一步只允许 R09 合成退修，不能读取真实 225／691。  
证据：方法边界见 `TEMP/t5_r04_overnight_control_20260811_r01/00_READ_ME_FIRST.md` 第 2e 节；当前失败票见 `TEMP/t5_r04_overnight_control_20260811_r01/FRESH_DISCRIM17_PARTIAL_SHORTLIST_PREP_R08_INDEPENDENT_CODE_REVIEW_R01.json`。

**E-10｜零重试 runner＋一次性实体执行票** `已验证`  
当前 DISCRIM4 API 执行把授权校验下沉到真正会建锁、写账和发送请求的函数；缺票或错票要在锁、账和运输前硬停。7 格无书稿 canary 经独立验收后一次性运行，7 次物理请求、0 自动重试、0 人工重试、0 正文调用。  
边界：证明的是这版 canary 执行外壳和授权门，不是模型质量，也不自动授权后续正文调用。  
证据：`TEMP/t5_r04_overnight_control_20260811_r01/FRESH_DISCRIM4_CANARY_EXECUTION_AUTHORITY_R03_R01.json` 与 `TEMP/t5_r04_overnight_control_20260811_r01/.fresh_discrim4_formal_grid_preflight_r03.staging/CANARY_COMPLETION_RECEIPT_R02.json`。

## 质量标准类

**E-11｜DISCRIM17 两级质量阶梯** `已验证（标准已冻结）`  
A 产品线要求总 Precision≥0.85、Recall≥0.75、micro-F1≥0.80，且每个主章 Recall≥0.65、F1≥0.70。只有 A 线可能前沿少于 3 组时才启用 B 筛选线；B 线要求总 Precision≥0.70、Recall≥0.60、micro-F1≥0.65，且每主章 Recall≥0.50、F1≥0.55。B 线以下在本轮候选选择、Prompt A/B/C 和管线验收周期内永久淘汰。  
边界：这是 DISCRIM17 及其后续候选验收的冻结门，不是生产晋升票；仅过 B 线者最终仍须通过 A 线。  
证据：`TEMP/t5_r04_overnight_control_20260811_r01/FRESH_DISCRIM17_TWO_STAGE_THRESHOLD_POLICY_R01.json`。

**E-12｜成绩分层展示** `候选先验（未固化）`  
候选展示把交付、格式、定位／SHA、语义事实、证据支持和端到端结果分开，并同时展示“成功交付条件下的语义分”和“把失败算进去的端到端分”。  
边界：这是 SI-004 外部调查带回、且与当前双账口径相容的展示建议；尚未进入正式评分合同，不能写成已敲定评分器。  
证据：`references/survey-inbox/items/SI-004_manus_r06_cloud_research.md`。

---

补账规则：只有正式票直接支持的内容才能标“已验证”或“负结果”；外部回包只标候选先验。任何人话改写都不得扩大票的适用范围或执行权限。

来源：Codex
