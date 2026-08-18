# 反例与边界案例关闭矩阵

| 案例 | 输入风险 | 预期机器层 | 实际结果 | 结论 |
|---|---|---|---|---|
| FF-01 | INITIAL 引用 Confirmed Setting | INITIAL 组合入口 / C10 eligibility | `C10_CHAPTER_EMISSION_NOT_ELIGIBLE` | PASS |
| FF-02 | INITIAL 引用 Candidate Chapter | INITIAL 组合入口 / C10 eligibility | `C10_CHAPTER_EMISSION_NOT_ELIGIBLE` | PASS |
| FF-03 | INITIAL 引用 stale identity revision | INITIAL 组合入口 / current revision gate | `C10_IDENTITY_REVISION_STALE` | PASS |
| FF-04 | r1 使用 REPLACE | Schema + ledger structure | `REJECTED_INITIAL_POSITION` | PASS |
| FF-05 | r2 使用 INITIAL | Schema + ledger structure | `REJECTED_INITIAL_POSITION` | PASS |
| FF-06 | RESTORE 引用链中不存在的 identity revision 999 | historical identity existence gate | `C10_HISTORICAL_IDENTITY_REVISION_NOT_FOUND` | PASS |
| MG-01 | 合法 INITIAL + current Confirmed Chapter | INITIAL 组合入口 | `C10_CONFIRMED_CHAPTER_ELIGIBLE` | PASS |
| MG-02 | 合法历史 RESTORE | lineage + historical identity + current reactivation | `PRECHECK_ALLOWED` | PASS |
| MG-03 | RESTORE 引用真实存在但非 current 的历史 identity | historical identity + current reactivation | `PRECHECK_ALLOWED` | PASS |
| MG-04 | C10 chain 数组位置与 revision_no 不一致 | C10 record / append-only chain validation | `C10_MATERIAL_RECORD_INVALID` | PASS |

六个旧反例已从“helper 能拒绝但正式入口仍可能放行”变为正式 fixture 和 validator 的硬门。

来源：Codex
