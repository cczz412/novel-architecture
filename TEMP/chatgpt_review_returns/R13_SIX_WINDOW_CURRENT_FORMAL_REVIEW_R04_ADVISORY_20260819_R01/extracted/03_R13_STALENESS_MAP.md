# R13 新旧差分与陈旧地图

审查身份：ADVISORY_ONLY  
动作边界：只给证据与建议，不重写 R13  
判决：R13_STEEL_LINES_VALID__FORMAL_STATUS_NOTES_STALE__CZ_SEMANTICS_STILL_OPEN

## 1. 仍然有效的产品钢线

| Steel ID | 仍有效语义 | 当前合同／停点对照 | 证据 |
|---|---|---|---|
| S-01 | 产品导写＋核对，不替作者生成书稿，没有一键成文后门 | C1/C11 只接作者原文与明确采用动作 | 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/03_CREATION_AND_MEMORY_PIPELINES.md；02_current_route/novel-mvp/contracts/C1_CHAPTER_DOC.md；02_current_route/novel-mvp/contracts/CHAPTER_REVISION_COMMIT_ACTION.md |
| S-02 | 计划、书稿、facts、actual 身份分开；计划不等于已发生 | PLAN_LEDGER 明确 planned/digested/paid 均非 actual，actual 只可派生 | 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/02_SYSTEM_ARCHITECTURE_AND_TRUTH_LAYERS.md；02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md |
| S-03 | 投影可以纠错，进真值必须作者确认；模型不能自签 | C3 只能 candidate，C4/事实准入只接受作者动作 | 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/02_SYSTEM_ARCHITECTURE_AND_TRUTH_LAYERS.md；02_current_route/novel-mvp/contracts/C3_FACT_CANDIDATE.md；02_current_route/novel-mvp/contracts/RECONCILIATION_FACT_ADMISSION_ACTION.md |
| S-04 | 冻结书稿不可静默覆盖；改版追加新版本；恢复不是回拨 | C11 append-only、RESTORE-as-new 已正式写入 | 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/02_SYSTEM_ARCHITECTURE_AND_TRUTH_LAYERS.md；02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md |
| S-05 | 证据坐标必须回到冻结书稿；派生摘要不是第二真值 | C11 正式 anchor 与 C2 normalized offset 分家 | 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/07_GLOSSARY.md；02_current_route/novel-mvp/contracts/C2_SEGMENT.md；02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md |
| S-06 | 上下文应最小充分且可扩张；缺料可回捞；每项能解释为何加载 | C9 runtime 仍 OPEN，但这是正确产品目标 | 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/02_SYSTEM_ARCHITECTURE_AND_TRUTH_LAYERS.md；03_upstream_evidence/TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/results/field_owner_matrix.json |
| S-07 | stable slot mapping 不因章节正文修订自动改变；对账依赖必须 stale | PLAN_LEDGER r07 与 C11 方向一致 | 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/03_CREATION_AND_MEMORY_PIPELINES.md；02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md |
| S-08 | 未检出不等于不存在；unknown、覆盖不足、证据冲突应分开 | T03 NO_VERDICT 和 C9 evidence recall OPEN 更强化此钢线 | 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/02_SYSTEM_ARCHITECTURE_AND_TRUTH_LAYERS.md；03_upstream_evidence/TEMP/v0_c3_auto_candidate_ability_b_paired_20260818_r01/FINAL_RECEIPT.json |
| S-09 | 打开项目第一屏是梗概＋概览＋战报；黄金三章另设工作台 | 本轮没有相反正式合同 | 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/03_CREATION_AND_MEMORY_PIPELINES.md |
| S-10 | 本地正式 R13 不自动给施工、训练、模型调用、外发或上线权 | 本轮 ADVISORY_ONLY 边界完全一致 | 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/06_SYNC_AND_CHANGE_PROTOCOL.md；01_current_truth/TEMP/t03_pro_package_r04_final_20260818_r01/00_R04_REVIEW_SCOPE.md |

## 2. 已被现行正式合同或新停点取代的说法

| Delta ID | R13/旧材料中的旧读法 | 当前替代事实 | 建议 |
|---|---|---|---|
| D-01 | 章版本、anchor、restore 仍主要是 N21 设计债／专项设计对象 | C11 ledger、action、schema、fixtures、validator 已正式落地；D 已做 5/5 窄重放 | R13 后续版本只更新“正式状态与指针”，不复制 C11 字段；产品实现仍标 pending |
| D-02 | 旧 route 写 C10 双锁是未应用候选、validator 为 f27008… | 当前 validator 已刷新为 aeac1c…，C1/C2 双 SHA 正式 | 旧 route 保留历史，不回写；任何 current 路由不得再引用旧 SHA |
| D-03 | chapter revision owner 仍完全未定 | C11 已声明 CHAPTER_REVISION_LEDGER 为唯一章节历史/current owner | 人读说明改成“合同 owner 已定，runtime writer/迁移/消费者实现仍待票”，不要把旧外审 owner-open 原句继续当当前事实 |
| D-04 | D 的章节修订验证仍等待 current-byte replay | 当前 D 已完成 C11 五票窄重放 | 保留旧 4/4 历史报告，但 current 状态应指向 5/5 窄重放；不扩大范围 |
| D-05 | C10 full validator 仍被旧 C1 SHA 锁阻断 | 后续双 SHA 正式刷新已解除该已知阻断 | R13/人读状态可删“当前仍阻断”；旧回执不可改 |
| D-06 | 共同前提包似乎已派专项即可接入 M8 | C owner closure 明确 C9 formal/runtime/producer/consumer/recall 均未闭合，M8 仍直读 facts | R13 中所有“已派设计”旁增加“不是现役能力”状态，不改产品钢线 |
| D-07 | 早期 MVP API/模型实测可被读成当前 T03 能力排名 | T03 旧八次 NO_VERDICT，新两次只判 transport handshake | 04 研究页应把早期数据标成 dated prior；不能据此给 C3/C4 资格或当前模型排名 |
| D-08 | 上一轮 ChatGPT Pro 的 RUN/IDLE 组合是当前计划 | 它是 ADVISORY_ONLY，且 A/D/C10/T03/C 已出现新停点 | 只保留为历史顾问材料，不进入当前执行真值 |

证据：

- 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/PRODUCT_SEMANTIC_DEBT_REGISTER.md
- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md
- 03_upstream_evidence/TEMP/t03_c11_eligibility_restore_formalization_20260818_r01/FORMAL_SHA_RECEIPT.json
- 03_upstream_evidence/TEMP/t03_c10_dual_sha_lock_formal_refresh_20260818_r01/RUN_REPORT.md
- 03_upstream_evidence/TEMP/t03_d_c11_narrow_replay_batch_20260818_r01/CZ_ONE_PAGE_VERDICT.md
- 03_upstream_evidence/TEMP/t03_pro_review_route_final_snapshot_20260818_r01/PRO_ROUTE_CANDIDATE_R03.json
- 03_upstream_evidence/TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/01_ONE_PAGE_JUNCTION_MAP.md
- 03_upstream_evidence/TEMP/v0_c3_output_contract_handshake_two_call_20260818_r01/FINAL_RECEIPT.json
- 04_external_reviews/prior_r13_six_window_review/LOCAL_TRIAGE_R01.md

## 3. 仍需 CZ 拍板的产品语义

| Decision ID | 需要拍板的语义 | 不拍的风险 | 证据 |
|---|---|---|---|
| CZ-01 | ADD-043：规则／能力／例外是否拆条 | 规则对象与消费权限继续混装 | 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/00_READ_ME_FIRST.md；01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/05_CURRENT_DECISIONS_AND_OPEN_QUESTIONS.md |
| CZ-02 | ADD-044：读者承诺是否独立于 foreshadow/伏笔 | M8、读者知情与提示系统会共用错误身份 | 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/00_READ_ME_FIRST.md；01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/05_CURRENT_DECISIONS_AND_OPEN_QUESTIONS.md |
| CZ-03 | 题 16 的触发字段、枚举、组合优先级、unknown 与机器判据；方向只优先绑故事事件/故事时间，不硬绑纯章号 | 各 consumer 自造触发默认 | 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/02_SYSTEM_ARCHITECTURE_AND_TRUTH_LAYERS.md；01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/03_CREATION_AND_MEMORY_PIPELINES.md；01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/05_CURRENT_DECISIONS_AND_OPEN_QUESTIONS.md |
| CZ-04 | 暗稿算不算完整签字、哪些低/高影响项可批量、能否开下一章 | 事务 writer PASS 被偷换成作者授权 | 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/03_CREATION_AND_MEMORY_PIPELINES.md；02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md |
| CZ-05 | INITIAL 的正式 command/writer 形状；同正文不同标题是否 NO_CHANGE | 文字门无法落为唯一机器入口，或标题修订被吞 | 02_current_route/novel-mvp/contracts/CHAPTER_REVISION_COMMIT_ACTION.md；02_current_route/novel-mvp/contracts/validate_c11_chapter_revision_ledger.py |
| CZ-06 | C9 的 task scope、budget cap、estimator、actuality mapping、obligation tier/rank、unresolved 与 evidence recall owner | M11 或 M8 被迫推断输入，形成隐藏默认 | 03_upstream_evidence/TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/results/field_owner_matrix.json |
| CZ-07 | planstore r07 是否升明确落盘版本；旧 reader/migration 的判别规则 | plan-v2 无法区分 r06/r07，旧 RE 可能继续支持 actual | 02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md |
| CZ-08 | C3 quote/seg 的正式必填性、candidate stable key、quote 唯一性与 VERIFIED anchor 准入 | producer/schema/action 三种读法分叉 | 02_current_route/novel-mvp/contracts/C3_FACT_CANDIDATE.md；02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.schema.json；02_current_route/novel-mvp/contracts/RECONCILIATION_FACT_ADMISSION_ACTION.md |
| CZ-09 | C11 revision 对 basis_pin、RE、C6、C9 的 stale 原子组是否全含；C6 过期只按 revision 还是也按 story commit | 绿色投影继续引用已退出 current truth 的事实 | 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md；02_current_route/novel-mvp/contracts/C6_HEALTH_REPORT.md；02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md |

## 4. 只应更新人读说明、不应改合同的内容

| Human-only ID | 建议更新 | 不应做 |
|---|---|---|
| H-01 | R13/N21 状态注：C11 正式合同已存在，exact 字段去 C11；产品 migration/runtime 未完成 | 不把 C11 字段复制进 R13，避免双重合同 |
| H-02 | R13/D11 状态注：共同前提包仍是钢线，formal C9/runtime/recall OPEN | 不据 owner closure 新造 C9 schema |
| H-03 | R13/04 研究页追加 dated stop：T03 旧八次 NO_VERDICT；新握手只有 transport | 不修改旧实验票或重算 raw |
| H-04 | route/current status 文档改为 C10 aeac1c…；R03 snapshot 标 historical | 不编辑历史 R03 JSON |
| H-05 | C10 adoption 说明保留 Title 已实现与 validator label debt并存 | 不为追求全绿把正式 adoption 改回 NOT_IMPLEMENTED |
| H-06 | C1/C6/reconciliation/planstore 的产品状态统一写“正式合同已冻／产品待升级” | 不把文档存在写成 runtime READY |
| H-07 | 上一轮外审及其 WINDOW_INSTRUCTIONS 标为 superseded advisory | 不删除历史建议，也不将其改写成当前指令 |
| H-08 | Notion 继续写现行镜像 R09，本地正式 R13 | 未授权时不推 Notion，不伪造页面 |

证据：

- 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/04_EXTRACTION_MODEL_AND_DATA_STRATEGY.md
- 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/06_SYNC_AND_CHANGE_PROTOCOL.md
- 02_current_route/novel-mvp/contracts/C10_INTAKE_MATERIAL_IDENTITY.md
- 02_current_route/novel-mvp/contracts/C1_CHAPTER_DOC.md
- 02_current_route/novel-mvp/contracts/C6_HEALTH_REPORT.md
- 02_current_route/novel-mvp/contracts/RECONCILIATION_FACT_ADMISSION_ACTION.md
- 02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md

## 5. 更新纪律

R13 协议要求：产品语义变化应建立新版本，不在已发布 R13 中静默改字；共同背景板也不提供施工权。所以上述 H 项只能在 CZ 明字和受控版本任务中更新。当前报告只提供差分证据。

证据：

- 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/06_SYNC_AND_CHANGE_PROTOCOL.md

来源：本审查包内 R13、正式合同与新停点。
