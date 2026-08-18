WINDOW=D
TASK_ID=D-C11-ACTION-ENTRY-SCHEMA-COMPOSITION-INDEPENDENT-REVIEW-01
STATUS=COMPLETE
VERDICT=CONTRACT_MACHINE_ENTRY_GAP_FOUND
DELIVERABLE_ROOT=/Users/a1234/挣钱/小说架构/TEMP/d_c11_action_entry_schema_composition_independent_review_20260819_r01/
PRIMARY_RESULT=CZ_ONE_PAGE_VERDICT.md
MACHINE_RECEIPT=results/gate_ledger.json；results/SHA_RECEIPT.json
API_MODEL_RETRY=0／0／0
FORMAL_WRITES=0
NEW_FAILURE=YES；正式 action Schema 拒绝 `change_kind=INITIAL`，公开 `validate_action` 却返回 `PRECHECK_ALLOWED`
DEPENDENCY_OR_WRITE_CONFLICT=无输入漂移、无写集冲突；未扫描外部调用者，影响范围保持窄判
CZ_DECISION_REQUIRED=YES；由 C11 owner 决定是否另开正式修复票，将 action Schema 强制组合进公开入口
SHARED_REVIEW_NEEDED=NO
NEXT_SAFE_TASK=IDLE；等待总控／owner 新票，不自行修正式件
ONE_PARAGRAPH_SUMMARY=独立 fail-first 审查实际执行 2/5 子例。合法 REPLACE 的 Schema 与 `validate_action` 都通过；同一 action 仅改 `items[0].change_kind=INITIAL` 后，Schema 返回 `SCHEMA_REJECT`，公开入口却返回 `PRECHECK_ALLOWED`，命中合同机器入口缺口并立即停止。BOGUS、缺 contract、缺 version 三例按规则未再执行。最小原因是入口未组合 action Schema，且当前代码把所有非 RESTORE 值走 REPLACE 分支。本窗仅提供“入口先校验完整 Schema、非法即稳定拒绝、通过后只分 REPLACE／RESTORE”的候选差分，未修改任何正式件。8 份输入 SHA 无漂移，API、模型、重试、正式写入、产品、小说、Gold、R13、Notion、Git 和越权路径均为 0。

来源：Codex
