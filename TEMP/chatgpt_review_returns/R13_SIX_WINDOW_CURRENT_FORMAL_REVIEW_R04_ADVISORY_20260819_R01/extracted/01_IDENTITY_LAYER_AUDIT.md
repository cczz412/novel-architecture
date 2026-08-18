# 身份分层审计

审查身份：ADVISORY_ONLY  
判决：IDENTITY_SEPARATION_PARTIAL__CURRENT_FORMAL_BYTES_CLEAR__PRODUCT_AND_RUNTIME_STATUS_MIXED

## 1. 权威顺序

本轮应按以下顺序读冲突：

1. 01_current_truth 的当前明示事实与权限；
2. 02_current_route 的正式合同、schema、fixtures、validator；
3. 03_upstream_evidence 的结果票与停点；
4. 04_external_reviews 的顾问建议和本地分诊。

R13 自己也规定：共同背景板不自动提供施工、模型调用、训练、外发、生产或上线权限；正式版应新建受控版本，不在 R13 原位静默改字。

证据：

- 00_READ_ME_FOR_REVIEWER.md
- 00_ROUTE_MAP.md
- 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/00_READ_ME_FIRST.md
- 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/06_SYNC_AND_CHANGE_PROTOCOL.md

## 2. 已落正式件与未应用／历史候选

| 对象 | 正确身份 | 易错读法 | 纠正依据 |
|---|---|---|---|
| C11 action/schema/validator/fixtures | 当前正式四件 | 仍是 A 的 TEMP 候选 | 03_upstream_evidence/TEMP/t03_c11_eligibility_restore_formalization_20260818_r01/FORMAL_SHA_RECEIPT.json |
| C10 validator 双 SHA | 当前正式，SHA aeac1c…024ab | 仍是候选或旧 f27008…bea61 | 03_upstream_evidence/TEMP/t03_c10_dual_sha_lock_formal_refresh_20260818_r01/SHA_RECEIPT.json |
| PRO_ROUTE_CANDIDATE_R03 | 历史 DRAFT_NOT_EXECUTABLE；其 C10 “未应用”快照已过期 | 当前 route 或回滚依据 | 03_upstream_evidence/TEMP/t03_pro_review_route_final_snapshot_20260818_r01/PRO_ROUTE_CANDIDATE_R03.json；01_current_truth/TEMP/t03_pro_package_r04_final_20260818_r01/00_R04_REVIEW_SCOPE.md |
| 上一轮外审 A/D/C 判断 | 有价值的历史顾问意见，部分已被后续正式化、刷新与重放取代 | 当前执行票 | 04_external_reviews/prior_r13_six_window_review/LOCAL_TRIAGE_R01.md；04_external_reviews/prior_r13_six_window_review/RETURN_INTAKE_RECEIPT.json |
| PLAN_LEDGER r07 | 当前人读合同中的 revision 接缝冻结；名称仍带 candidate，产品实现待票，落盘仍 plan-v2 | 已有可区分的 r07 runtime/schema | 02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md |
| R13 BUILD_RECEIPT | R13 包组装与机械完整性回执 | 产品模块完成证据 | 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/BUILD_RECEIPT.json；01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/00_READ_ME_FIRST.md |

### 已知机器标签债

C10 人读合同明确写 v3 Title 产品路径已实现；validator 的最终报告仍输出 title_product_implementation=NOT_IMPLEMENTED，同时另报 NON_BLOCKING_ADOPTION_STATUS_DEBT。当前正确读法是“Title 已采用、机器标签仍欠修”，不能让机器字段反向覆盖正式 adoption 状态，也不能把债当绿灯证明所有消费路径。

证据：

- 02_current_route/novel-mvp/contracts/C10_INTAKE_MATERIAL_IDENTITY.md
- 02_current_route/novel-mvp/contracts/validate_c10_intake_material_identity.py

## 3. 机械 PASS 与产品能力

| 机械证据 | 它证明什么 | 它不证明什么 |
|---|---|---|
| C10 validator PASS | 28 fixtures、负例、版本兼容、SHA 锁与当前静态合同关系通过 | Tags 产品实现、C11 runtime、端到端用户流程 |
| C11 validator 65/65 | 冻结的 65 个规则标签按当前 helper/样例得到预期结果 | 所有外部 C10 关联、C1/C4 跨对象等式、真实事务并发与迁移 |
| D 5/5、34/34、83/83 | A 四件当前字节通过指定窄重放和相邻回归 | 产品可用、C9 可用、T03 语义、所有 stale 消费者闭合 |
| R13 build PASS | 文件数、SHA、父版与组装约束通过 | R13 中描述的 UI、模型、context packer 或产品流程已实现 |
| C owner closure 21/21 | TEMP owner matrix 无双 owner、无越权默认，OPEN 被明确保留 | 正式 C9、producer、consumer、recall 或产品 parser |

证据：

- 03_upstream_evidence/TEMP/t03_c10_dual_sha_lock_formal_refresh_20260818_r01/VALIDATION_RESULTS.json
- 03_upstream_evidence/TEMP/t03_c11_eligibility_restore_formalization_20260818_r01/VALIDATION_RESULTS.json
- 03_upstream_evidence/TEMP/t03_d_c11_narrow_replay_batch_20260818_r01/CZ_ONE_PAGE_VERDICT.md
- 03_upstream_evidence/TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/results/final_validation_receipt_v2.json

正式合同也主动承认产品差距：

- C1 v1：现役产品仍输出 v0-r01；
- C6 v1：check.py 尚未施工；
- reconciliation v2：现役 reconcile.py 仍为 v1；
- planstore r07：revision 接缝产品待下一票；
- C10 v4 Tags：producer/consumer 未实现。

证据：

- 02_current_route/novel-mvp/contracts/C1_CHAPTER_DOC.md
- 02_current_route/novel-mvp/contracts/C6_HEALTH_REPORT.md
- 02_current_route/novel-mvp/contracts/RECONCILIATION_FACT_ADMISSION_ACTION.md
- 02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md
- 02_current_route/novel-mvp/contracts/C10_INTAKE_MATERIAL_IDENTITY.md

## 4. 运输格式失败与语义能力失败

| 项 | 当前事实 | 禁止偷换 |
|---|---|---|
| 旧八次能力批次 | 8 raw、0 sealed candidate、NO_VERDICT | 不能把评分表中的 0 写成 Recall=0 或 Precision=0 |
| Flash 新握手 | 单层 json fence，经冻结的 Flash-only adapter 后通过 shared validator | 不能写成原生裸 JSON；不能写成语义能力通过 |
| 豆包新握手 | 同样单层 json fence，但该 route 不允许豆包 adapter，停在 transport gate | 不能写成豆包语义失败；不能产生模型排名 |
| 事后去 fence | 只可诊断 raw 形状 | 不能补 seal、补成绩或把旧 raw 变成预注册结果 |

证据：

- 03_upstream_evidence/TEMP/v0_c3_auto_candidate_ability_b_paired_20260818_r01/STAGE_RESULT.md
- 03_upstream_evidence/TEMP/v0_c3_auto_candidate_ability_b_paired_20260818_r01/FINAL_RECEIPT.json
- 03_upstream_evidence/TEMP/v0_c3_output_contract_handshake_two_call_20260818_r01/STAGE_RESULT.md
- 03_upstream_evidence/TEMP/v0_c3_output_contract_handshake_two_call_20260818_r01/FINAL_RECEIPT.json

## 5. 外部顾问建议与 CZ 授权

上一轮 ChatGPT Pro 回包与本报告都只有顾问身份。RETURN_INTAKE_RECEIPT 明确列出：不得修改正式合同、R13、产品、Gold，不得调用模型、训练、上传或写作者真值。LOCAL_TRIAGE 进一步指出，顾问文本中的 SHOULD_RUN、PASS、立即运行或普通错误自修都不是授权。

证据：

- 04_external_reviews/prior_r13_six_window_review/RETURN_INTAKE_RECEIPT.json
- 04_external_reviews/prior_r13_six_window_review/LOCAL_TRIAGE_R01.md
- 04_external_reviews/prior_r13_six_window_review/extracted/MACHINE_RECOMMENDATION.json
- 01_current_truth/TEMP/t03_pro_package_r04_final_20260818_r01/00_R04_REVIEW_SCOPE.md

因此：

- 顾问可以建议任务和风险；
- 总控/CZ 才能分配正式写集和权限；
- 机械 PASS 不能自生审批；
- 沉默、无人反对、建议采用、推荐 RUN 都不等于授权。

## 6. 计划、书稿、facts、actual 的写权

| 身份 | 唯一写权／正式入口 | 不得写什么 | 证据 |
|---|---|---|---|
| 计划 | 作者/M8 只能提出或确认；planstore 是 plan.json 唯一持久 writer | 不得把 planned、digested、paid 写成已发生；模型不能直接替作者决定 | 02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md |
| 书稿 | C11 保存 stable chapter 的不可变 revision chain；C1 只是 current projection；commit action 固定 AUTHOR | C1 不得保存第二历史；M4/planstore/C10 identity rev 不得冒充 chapter revision；冻结 revision 不得回拨或改写 | 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md；02_current_route/novel-mvp/contracts/CHAPTER_REVISION_COMMIT_ACTION.md；02_current_route/novel-mvp/contracts/C1_CHAPTER_DOC.md |
| facts | M5 作者动作提出，M4/factstore 事务 writer 落 C4；模型只产 C3 extracted candidate | C3/模型不能指定 f、不能直接 confirmed；needs_recheck 不能供 M6/M8/M11 当 current truth | 02_current_route/novel-mvp/contracts/C3_FACT_CANDIDATE.md；02_current_route/novel-mvp/contracts/C4_FACT_QUERY.md；02_current_route/novel-mvp/contracts/RECONCILIATION_FACT_ADMISSION_ACTION.md |
| actual | 不保存裸 actual；只从 active/current RE、exact/variant、current confirmed facts、current revision、current mapping 派生 | PE digested、handover、模型观察、文件存在都不能直接产生 actual | 02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md；02_current_route/novel-mvp/contracts/RECONCILIATION_FACT_ADMISSION_ACTION.md |

R13 的上位钢线与此一致：计划事件和已发生事实分账，投影可以纠错但进真值必须作者确认，冻结书稿永不自动改写。

证据：

- 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/02_SYSTEM_ARCHITECTURE_AND_TRUTH_LAYERS.md
- 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/03_CREATION_AND_MEMORY_PIPELINES.md
- 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/05_CURRENT_DECISIONS_AND_OPEN_QUESTIONS.md

## 7. 身份审计结论

当前最危险的不是某个旧文件存在，而是弱 consumer 选错身份：

- 读取 R03 route，就会把已刷新的 C10 validator 复活成“未应用候选”；
- 读取 validator 的 Title 标签，就会反写正式 adoption 状态；
- 读取 C11 65/65，就会把未施工 consumer 当成现役；
- 读取 owner closure PASS，就会把 C9 OPEN 变成 runtime READY；
- 读取 handshake FAIL，就会把运输政策差异写成模型语义失败；
- 读取外审 RUN，就会把顾问建议升级成施工授权。

安全门应是：当前事实指针 → 正式字节 SHA → 产品结果票 → 任务权限，四者缺一时保持 fail closed。

来源：本审查包内四层材料。
