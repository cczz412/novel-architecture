# 下一批五窗任务组合

审查身份：ADVISORY_ONLY  
组合判决：RUN_A_AND_D_TEMP_ONLY__T03_B_C_INTENTIONAL_IDLE

这只是下一步建议，不是执行授权。所有 RUN 项均限定为零 API、零模型、零 Gold、零正式合同/产品/R13/作者真值写入。

## 总表

| 窗口 | 姿态 | 唯一最小任务 | 目的 |
|---|---|---|---|
| T03 | INTENTIONAL_IDLE | 无 | 无第三次调用或新能力批次授权；旧八次与新握手均已到 RESULT_STOP |
| A | RUN_ONE_NARROW_TASK | A-C11-INITIAL-RESTORE-REFERENCE-FAIL-FIRST-01 | 只验证 INITIAL 机器入口与 RESTORE historical identity revision 存在性 |
| B | INTENTIONAL_IDLE | 无 | 当前 R04 route 已正确覆盖旧 R03；A/D 新停点前重建 route 只会制造新陈旧快照 |
| C | INTENTIONAL_IDLE | 无 | owner closure 已完成；runtime/recall/输入 owner 需要 CZ 与正式权限，继续 TEMP 归纳会重复 |
| D | RUN_ONE_NARROW_TASK | D-C11-R2-STALE-PROPAGATION-ONE-SCENARIO-01 | 用一个 r1→r2 删除证据场景检查跨对象 stale/原子性，不重复旧五票 |

## T03｜INTENTIONAL_IDLE

### 理由

- call cap=2 已用完；
- third_call_authorized=false；
- ability_batch_started=false；
- 豆包失败是 route transport policy，不是应自动重试的普通故障；
- 旧八次 raw 不可事后修理成新实验。

证据：

- 03_upstream_evidence/TEMP/v0_c3_output_contract_handshake_two_call_20260818_r01/FINAL_RECEIPT.json
- 03_upstream_evidence/TEMP/v0_c3_output_contract_handshake_two_call_20260818_r01/STAGE_RESULT.md
- 03_upstream_evidence/TEMP/v0_c3_auto_candidate_ability_b_paired_20260818_r01/FINAL_RECEIPT.json

### 解除 idle 的停点

仅在 CZ 明字给出新实验 identity、预先冻结 adapter policy、prompt/validator 和新调用帽后再议。当前不做第三次调用。

## A｜RUN_ONE_NARROW_TASK

### Task

A-C11-INITIAL-RESTORE-REFERENCE-FAIL-FIRST-01

### 唯一目标

确认两个当前机器门是否真实 fail closed：

1. 非 CONFIRMED+CHAPTER 或 stale C10 identity 能否被直接构造成 C11 r1；
2. RESTORE 历史 origin_material_ref.identity_revision_no 不存在时能否仍通过 reactivation。

不重新设计 C11，不重复四件正式化，不刷新 C10 SHA。

### 输入

- 02_current_route/novel-mvp/contracts/C10_INTAKE_MATERIAL_IDENTITY.md
- 02_current_route/novel-mvp/contracts/C10_INTAKE_MATERIAL_IDENTITY.schema.json
- 02_current_route/novel-mvp/contracts/validate_c10_intake_material_identity.py
- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md
- 02_current_route/novel-mvp/contracts/CHAPTER_REVISION_COMMIT_ACTION.md
- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.schema.json
- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.fixtures.jsonl
- 02_current_route/novel-mvp/contracts/validate_c11_chapter_revision_ledger.py
- 03_upstream_evidence/TEMP/t03_d_c11_narrow_replay_batch_20260818_r01/results/narrow_replay_ledger.json

### 写集

仅允许：

TEMP/a_c11_initial_restore_reference_fail_first_20260818_r01/**

禁止正式合同、schema、fixtures、validator、产品、R13、Gold、API、Git 与作者真值写入。

### 验收门

- 一张 fail-first ledger，至少含：
  - INITIAL Setting；
  - INITIAL Candidate；
  - INITIAL stale identity ref；
  - r1 change_kind 非 INITIAL；
  - r2 change_kind INITIAL；
  - RESTORE historical identity revision 不存在；
- 每例登记当前 schema、validate_ledger、eligibility helper、action path 的实际到达关系；
- 区分“明确拒绝”“未覆盖”“只能由外部 writer 保证”；
- 当前正式输入 SHA 全部不变；
- API/model/Gold/formal writes 均 0。

### 停点

- 若全部已由现役唯一入口拒绝：停为 NO_NEW_GAP，并指出唯一入口证据；
- 若任一可通过：停为 CONTRACT_MACHINE_GAP_FOUND，提交最小差分选项给 CZ，不改正式件；
- 若必须选择 INITIAL command 身份或同文异题 NO_CHANGE 语义：停为 CZ_DECISION_REQUIRED。

## B｜INTENTIONAL_IDLE

### 理由

R04 包的 current truth 已明确修正三件事：C11 正式、C10 双锁正式、T03 新握手/C9 runtime OPEN。B 的旧 R03 snapshot 明确是 DRAFT_NOT_EXECUTABLE。此刻再造 route，而 A/D 还未跑新负例，会立即形成下一份可能陈旧的快照。

证据：

- 01_current_truth/TEMP/t03_pro_package_r04_final_20260818_r01/00_R04_REVIEW_SCOPE.md
- 03_upstream_evidence/TEMP/t03_pro_review_route_final_snapshot_20260818_r01/PRO_ROUTE_CANDIDATE_R03.json
- 03_upstream_evidence/TEMP/t03_pro_review_route_final_snapshot_20260818_r01/ROUTE_CONSISTENCY_CHECK_R03.json

### 解除 idle 的停点

A 与 D 均收口，且总控明确要求生成下一代 route/package；届时只做一次 current refreeze，不复活 R03 的旧 C10 身份。

## C｜INTENTIONAL_IDLE

### 理由

C 已完成 owner closure，且结论本身要求 IDLE_UNTIL_TOTAL_CONTROL_ASSIGNMENT。未闭合项不是再画一张 owner 表能解决的：

- runtime producer/consumer 不存在；
- task/budget/estimator/actuality/obligation owner 未分配；
- unresolved 与 evidence recall 没有默认；
- 正式 C9 与产品写入都需新权限。

证据：

- 03_upstream_evidence/TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/STAGE_FINAL_CAPSULE.txt
- 03_upstream_evidence/TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/results/field_owner_matrix.json

### 解除 idle 的停点

CZ 明字分配上述 owner、正式 C9/产品写集，并收到 A/D 的 current revision 与 stale 停点。此前不实现 packer、不改 plan.py、不补默认。

## D｜RUN_ONE_NARROW_TASK

### Task

D-C11-R2-STALE-PROPAGATION-ONE-SCENARIO-01

### 唯一场景

同一 c01 从 r1 修订到 r2；r1 中唯一支持 confirmed fact f001 的 quote 在 r2 消失。只沿这一条链检查：

C11 current → C1 current view → C4 needs_recheck → basis pin/RE stale → actual unsupported → C6 stale → reconciliation old action rejected。

不重复 D 已完成的 C10 role/REPLACE/RESTORE 五票。

### 输入

- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md
- 02_current_route/novel-mvp/contracts/C1_CHAPTER_DOC.md
- 02_current_route/novel-mvp/contracts/C4_FACT_QUERY.md
- 02_current_route/novel-mvp/contracts/C6_HEALTH_REPORT.md
- 02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md
- 02_current_route/novel-mvp/contracts/RECONCILIATION_FACT_ADMISSION_ACTION.md
- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.schema.json
- 02_current_route/novel-mvp/contracts/validate_c11_chapter_revision_ledger.py
- 03_upstream_evidence/TEMP/t03_d_c11_narrow_replay_batch_20260818_r01/CZ_ONE_PAGE_VERDICT.md

### 写集

仅允许：

TEMP/d_c11_r2_stale_propagation_one_scenario_20260818_r01/**

禁止正式件、产品、R13、Gold、API、模型、Git 与作者真值写入。

### 验收门

同一 fixture 必须登记：

1. C1 id/ref/text SHA 与 C11 r2 current 全等；
2. f001 转 needs_recheck/evidence_gone，M6/M8/M11 均不可消费；
3. 引用 f001 的 basis pin 进入 needs_recheck，active RE 进入 stale；
4. actual 支持集为空或显式 unsupported，不能保留旧派生；
5. C6 r1 报告由 current reader 判 STALE，不能靠输入自报 CURRENT；
6. r1 reconciliation admission action 在任何写入前拒绝；
7. revision commit 与 concurrent fact admission 经同一 lock 串行，后提交者重读 current；
8. 同 operation/payload 回放不重复写，异 payload 冲突；
9. 任一点故障只能 all-before/all-after；
10. 若现役产品不存在相应路径，结果必须记 NOT_IMPLEMENTED/UNTESTABLE，不能用文档模拟 PASS。

### 停点

- 全部由现役产品/validator证明：PASS_ONE_SCENARIO；
- 文档要求存在但 runtime/schema 无法执行：RUNTIME_OR_CONTRACT_GAP_FOUND；
- 涉及 pin、C6 或落盘版本的新语义：CZ_DECISION_REQUIRED；
- 无论何种结果都不自动改正式件，不开启第二场景。

## 推荐顺序

A 与 D 可并行，因为只写各自 TEMP。两者收口后再做一次总控判断；B/C 不提前造新 route/C9，T03 不调用模型。

来源：本审查包内当前事实、正式合同与停点回执。
