# STAGE FINAL CAPSULE

- WINDOW：T03-A
- TASK_ID：A-C11-INITIAL-RESTORE-REFERENCE-FAIL-FIRST-01
- STATUS：COMPLETE
- VERDICT：CONTRACT_MACHINE_GAP_FOUND
- DELIVERABLE_ROOT：`/Users/a1234/挣钱/小说架构/TEMP/a_c11_initial_restore_reference_fail_first_20260819_r01/`
- PRIMARY_RESULT：`ONE_PAGE_GAP_VERDICT.md`
- MACHINE_RECEIPT：`MACHINE_LEDGER.json`；`CASE_RESULTS.jsonl`；`INPUT_NO_TOUCH_SHA_RECEIPT.json`
- API_MODEL_RETRY：0 / 0 / 0
- FORMAL_WRITES：0
- NEW_FAILURE：YES；6/6 反例出现合同机器错误成功。
- DEPENDENCY_OR_WRITE_CONFLICT：NO
- CZ_DECISION_REQUIRED：NO；现行语义已足够判断门应存在，但任何正式修复仍需新授权。
- SHARED_REVIEW_NEEDED：NO
- NEXT_SAFE_TASK：另开受控 C11 machine-gate 修复票，从 `IMPACT_AND_MINIMAL_DIFF_OPTIONS.md` 选择最小实现；A 不自行施工。
- ONE_PARAGRAPH_SUMMARY：INITIAL 的 current C10 helper 能正确拒绝 Setting、Candidate、stale ref，但它没有和 ledger Schema／validate_ledger 组成唯一入口，r1/r2 的 INITIAL 位置也未上机器，因此 FF-01～05 全被直接 ledger 路径接受。RESTORE 对 C10 chain `[1,2]` 中不存在的历史 ref 999 仍返回 PRECHECK_ALLOWED，FF-06 也成立。该结论只证明合同机器缺口，不证明产品已发生错误写入；正式 C10/C11 字节前后完全一致。

来源：Codex
