# R13 六身份当前正式字节大审 R04｜执行判断

审查身份：外部高级审查员  
权限：ADVISORY_ONLY  
证据范围：随附 R04 review ZIP 内四层材料  
总判决：ADVISORY_ONLY__FORMAL_BYTES_CURRENT__END_TO_END_CAPABILITY_HOLD

## 一句话判断

C10 双 SHA 与 C11 四件应按当前正式字节承认，D 的 5/5 窄重放也成立；但这些证据还不能推出章节修订链已经在产品中端到端可用。INITIAL 的 C10 门没有在包内形成可调用的机器入口，revision 向 C1/C2、C3/C4/C6、planstore 与事实准入的跨对象等式和 stale 传播也没有完整的现役 runtime 证明。C9/M11 仍无正式运行链，T03 仍无语义能力结论。

当前事实与权限边界见：

- 01_current_truth/TEMP/t03_pro_package_r04_final_20260818_r01/00_R04_REVIEW_SCOPE.md
- 01_current_truth/TEMP/t03_pro_package_r04_final_20260818_r01/PROMPT_CHATGPT_PRO.md
- 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/00_READ_ME_FIRST.md
- 01_current_truth/references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/06_SYNC_AND_CHANGE_PROTOCOL.md

## 接受的当前事实

| ID | 接受项 | 审查结论 | 证据 |
|---|---|---|---|
| A-01 | C11 四件正式落地 | 接受；它们是当前正式合同字节，不再是未应用候选 | 03_upstream_evidence/TEMP/t03_c11_eligibility_restore_formalization_20260818_r01/FORMAL_SHA_RECEIPT.json；02_current_route/novel-mvp/contracts/CHAPTER_REVISION_COMMIT_ACTION.md |
| A-02 | C10 C1/C2 双 SHA 刷新 | 接受；现役 validator SHA 为 aeac1c…024ab，旧“未应用”说法已过期 | 03_upstream_evidence/TEMP/t03_c10_dual_sha_lock_formal_refresh_20260818_r01/SHA_RECEIPT.json；01_current_truth/TEMP/t03_pro_package_r04_final_20260818_r01/00_R04_REVIEW_SCOPE.md |
| A-03 | D 5/5 窄重放 | 接受为指定接缝机械证据；不扩大为产品能力或完整合同证明 | 03_upstream_evidence/TEMP/t03_d_c11_narrow_replay_batch_20260818_r01/CZ_ONE_PAGE_VERDICT.md；03_upstream_evidence/TEMP/t03_d_c11_narrow_replay_batch_20260818_r01/results/narrow_replay_ledger.json |
| A-04 | C owner closure | 接受其“来源 owner 与声明方向”结论；runtime producer/consumer、若干输入 owner 与 evidence recall 继续 OPEN | 03_upstream_evidence/TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/01_ONE_PAGE_JUNCTION_MAP.md；03_upstream_evidence/TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/results/field_owner_matrix.json |
| A-05 | T03 两代证据 | 旧八次为 NO_VERDICT；新两次只判运输握手，Flash PASS、豆包 FAIL；均无 Recall、Precision、排名或 C3/C4 资格 | 03_upstream_evidence/TEMP/v0_c3_auto_candidate_ability_b_paired_20260818_r01/FINAL_RECEIPT.json；03_upstream_evidence/TEMP/v0_c3_output_contract_handshake_two_call_20260818_r01/FINAL_RECEIPT.json |

## 主要 blocker

### B-01｜INITIAL 只有规则声明，没有包内可审计的完整机器入口

CHAPTER_REVISION_COMMIT_ACTION v1 的 items 只允许 REPLACE/RESTORE；C11 ledger schema 可以直接出现 r1，但无法跨文件校验 C10 current identity。现役 validator 的 EG-01 只单独验证一个已知合法 initial material；validate_ledger 本身不接收 C10 material records，也没有非 Chapter／Candidate 的 INITIAL 负例。因此，“INITIAL 必过 current C10 门”在文字层成立，在本包机器接口层没有证明为不可绕过。

证据：

- 02_current_route/novel-mvp/contracts/CHAPTER_REVISION_COMMIT_ACTION.md
- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.schema.json
- 02_current_route/novel-mvp/contracts/validate_c11_chapter_revision_ledger.py
- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.fixtures.jsonl

### B-02｜RESTORE 未证明 historical identity_revision_no 真实存在

RESTORE 会按历史 material_unit_id 重读当前 C10 record，这个方向正确；但 validator 在 reactivation 时故意不要求历史 identity revision 等于 current，同时也没有检查历史 origin_material_ref.identity_revision_no 是否存在于该 C10 revision chain。若一个初始或迁移 ledger 带了虚构的历史 identity revision，只要 material id、当前 Chapter 身份和 source ref 对得上，现有 helper 仍可能放行。

证据：

- 02_current_route/novel-mvp/contracts/validate_c11_chapter_revision_ledger.py
- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md
- 02_current_route/novel-mvp/contracts/CHAPTER_REVISION_COMMIT_ACTION.md

### B-03｜跨对象“同一 current revision”多由说明文字保证

C1 的 id/text/ref 与 C11 current、C2/C3 的 ref 继承、C4 的 top-level chapter/ref/anchor、C6 的 CURRENT 派生，均缺少包内统一的跨对象 validator。各 schema 能检查形状，却不能证明这些重复身份彼此相等。C1、C6、reconciliation v2 的产品升级又明确尚未施工。

证据：

- 02_current_route/novel-mvp/contracts/C1_CHAPTER_DOC.md
- 02_current_route/novel-mvp/contracts/C2_SEGMENT.md
- 02_current_route/novel-mvp/contracts/C3_FACT_CANDIDATE.md
- 02_current_route/novel-mvp/contracts/C4_FACT_QUERY.md
- 02_current_route/novel-mvp/contracts/C6_HEALTH_REPORT.md
- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.schema.json
- 02_current_route/novel-mvp/contracts/RECONCILIATION_FACT_ADMISSION_ACTION.md

### B-04｜planstore r07 的语义版本与落盘版本不能可靠区分

PLAN_LEDGER_STORAGE 自称 plan-v2-candidate-r07，r07 revision 接缝正式冻结、产品待施工，但落盘 schema 字符串仍是 plan-v2。它要求旧 reader 遇到 r07 ref fail closed，却没有在本包提供可供 reader 判别 r06/r07 的版本字段或 schema。旧 RE、旧 reader 和 actual 支持因此仍有静默降级风险。

证据：

- 02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md

### B-05｜事实准入的 quote 与 candidate identity 仍有空口

C4 说明要求 quote 逐字存在且唯一命中；RECONCILIATION_FACT_ADMISSION_ACTION 的写前硬门只写“逐字存在”。C3 又允许 quote 为空，并且人读表把 quote/seg 写成非必填，而 C11 schema 把两者列入 required。当前 route 也没有定义 fact_candidate_refs 的稳定 ID owner。弱实现可能用空 quote、重复 quote 或临时数组位置生成 VERIFIED anchor。

证据：

- 02_current_route/novel-mvp/contracts/C3_FACT_CANDIDATE.md
- 02_current_route/novel-mvp/contracts/C4_FACT_QUERY.md
- 02_current_route/novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.schema.json
- 02_current_route/novel-mvp/contracts/RECONCILIATION_FACT_ADMISSION_ACTION.md

### B-06｜C9/M11 仍不是正式上下文包能力

owner closure 没有新增正式 C9、字段或 runtime。包内证据明确写出 mvp/packer.py 不存在、mvp/plan.py 仍直接读 facts、真实 runtime consumer 不存在；task scope、budget、estimator、actuality mapping、obligation/rank 与 evidence recall 等 owner 仍开口。

证据：

- 03_upstream_evidence/TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/01_ONE_PAGE_JUNCTION_MAP.md
- 03_upstream_evidence/TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/results/field_owner_matrix.json
- 03_upstream_evidence/TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/STAGE_FINAL_CAPSULE.txt
- 02_current_route/novel-mvp/contracts/PLAN_LEDGER_STORAGE.md

### B-07｜T03 无能力裁决，且禁止第三次调用

豆包与 Flash 都返回单层小写 json 围栏；差异来自冻结运输政策只给 Flash 适配权。豆包未进入 shared validator，不是语义能力失败。对旧 raw 事后剥围栏、重算能力分或排列模型都会改变实验身份。

证据：

- 03_upstream_evidence/TEMP/v0_c3_output_contract_handshake_two_call_20260818_r01/STAGE_RESULT.md
- 03_upstream_evidence/TEMP/v0_c3_output_contract_handshake_two_call_20260818_r01/FINAL_RECEIPT.json
- 03_upstream_evidence/TEMP/v0_c3_auto_candidate_ability_b_paired_20260818_r01/STAGE_RESULT.md

## 允许怎样继续

只建议开放两个 TEMP-only、零 API 的窄任务：

1. A：给 INITIAL 与 RESTORE historical identity revision 做 fail-first 负例和门控差分，不改正式件；
2. D：用一个 r1→r2 删除证据的端到端场景，检查 C1、C4、pin/RE、C6 与事实准入的 stale/原子性，不重复已有五票。

T03、B、C 保持 INTENTIONAL_IDLE。完整任务定义见 05_NEXT_TASK_PORTFOLIO.md。

## 不成立的结论

- C11 四件已正式落地，不等于 revision-aware 产品已上线。
- D 5/5 不等于所有消费者、迁移、并发和恢复路径已覆盖。
- C10 validator PASS 不等于 Tags 产品已实现；也不能把 Title 的已知机器标签债读成产品未实现。
- C owner closure PASS 不等于正式 C9 或 runtime packer 已存在。
- Flash handshake PASS 不等于裸 JSON、语义能力或生产资格通过。
- 豆包 handshake FAIL 不等于语义能力失败。
- 外部报告中的 RUN、PASS 或建议采用，不是 CZ 授权。

来源：本审查包内当前事实、正式合同、上游回执与上一轮外审材料。
