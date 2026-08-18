WINDOW: A

TASK_ID: A-C11-INITIAL-RESTORE-MACHINE-GATE-FORMAL-FIX-01

STATUS: COMPLETE

VERDICT: CONTRACT_LOCAL_PASS

DELIVERABLE_ROOT: /Users/a1234/挣钱/小说架构/TEMP/a_c11_initial_restore_machine_gate_formal_fix_20260819_r01/

PRIMARY_RESULT: /Users/a1234/挣钱/小说架构/TEMP/a_c11_initial_restore_machine_gate_formal_fix_20260819_r01/RUN_REPORT.md

MACHINE_RECEIPT: /Users/a1234/挣钱/小说架构/TEMP/a_c11_initial_restore_machine_gate_formal_fix_20260819_r01/VALIDATION_RESULTS.json ; /Users/a1234/挣钱/小说架构/TEMP/a_c11_initial_restore_machine_gate_formal_fix_20260819_r01/FORMAL_SHA_RECEIPT.json

API_MODEL_RETRY: 0/0/0

FORMAL_WRITES: 仅 CHAPTER_REVISION_COMMIT_ACTION.md、C11 Schema、C11 validator、C11 fixtures 四件；没有第五件。

NEW_FAILURE: NONE

DEPENDENCY_OR_WRITE_CONFLICT: NONE

CZ_DECISION_REQUIRED: NO

SHARED_REVIEW_NEEDED: NO

NEXT_SAFE_TASK: 等待总控验收和另行派单；本窗口不自行领取下一单。

ONE_PARAGRAPH_SUMMARY: 三个已复现机器缺口全部关闭。INITIAL 现在必须走组合入口，一次验证 ledger、r1/r2 位置、origin ref 和当前 C10 Confirmed Chapter 资格；第一条 revision 只能 INITIAL，后续不得 INITIAL；RESTORE 历史 identity revision 必须真实存在于同一 material 的 C10 chain，随后仍检查当前 eligibility。上轮六个反例 6/6 正确拒绝，新合法/边界题 4/4 通过；C11 原 42/42、WS 2/2、eligibility 15/15、restore 5/5、batch 1/1、本票机器门 10/10，总结果 75/75；C10 v4 validator、JSON/JSONL 解析和 Ruff 均 PASS。C10/C1～C6/planstore/fact-admission 抽查 SHA 未变，API/模型/重试为 0。

来源：Codex
