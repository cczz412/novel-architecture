# A-C11 INITIAL / RESTORE 机器门正式窄修运行报告

任务：`A-C11-INITIAL-RESTORE-MACHINE-GATE-FORMAL-FIX-01`

状态：`CONTRACT_LOCAL_PASS`

## 结论

这张票点名的三个机器缺口已经在四件正式写集内关闭：

- INITIAL 现在只有一个正式组合入口：`validate_initial_commit(ledger, material_records)`。它会一次完成 ledger 结构、r1/r2 动作位置、origin material ref、当前 C10 `CONFIRMED + CHAPTER` 资格检查；缺少 C10 record 或 resolver 时拒绝，不再退化成只验 ledger。
- Schema 和 validator 同时要求：第一条 revision 必须是 INITIAL，第二条及以后不得是 INITIAL。
- RESTORE 会先证明历史 `identity_revision_no` 确实存在于同一 material 的 C10 append-only revision chain，再继续检查该 material 当前最后一条 identity 是否仍有 `CONFIRMED + CHAPTER` 资格。

没有修改 C10 的 role、state、authority 或 owner，也没有增加 pending 状态。

## 正式改动

只改了授权的四件：

1. `novel-mvp/contracts/CHAPTER_REVISION_COMMIT_ACTION.md`
2. `novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.schema.json`
3. `novel-mvp/contracts/validate_c11_chapter_revision_ledger.py`
4. `novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.fixtures.jsonl`

改法分别是：写清 INITIAL 唯一机器入口；把 revision 位置约束下沉到 Schema；让 validator 组合调用资格门并核验 RESTORE 历史 identity；把 6 个旧反例和 4 个合法/边界例纳入正式 fixture。

## 验收

| 检查 | 结果 |
|---|---:|
| C11 原正式题 | 42/42 PASS |
| 两个 WRONG_SUCCESS 门 | 2/2 PASS |
| 原 eligibility 门 | 15/15 PASS |
| 原 RESTORE / reactivation 门 | 5/5 PASS |
| batch 原子性 | 1/1 PASS |
| 本票机器门题 | 10/10 PASS |
| C11 总结果 | 75/75 PASS |
| Schema 示例 | 9/9 PASS |
| 上轮六个 fail-first 反例 | 6/6 在预期机器层拒绝 |
| Schema JSON / fixtures JSONL 解析 | PASS，75 行 |
| C11 validator Ruff | PASS |
| C10 v4 validator | PASS |

C11 报告同时确认：API 调用 0，自动重试 0。

## 写集与兼容

四件正式文件都从开工 SHA 产生了预期变化。C11 合同正文、C10 四件、C1/C2/C3/C4/C6、PLAN_LEDGER_STORAGE、RECONCILIATION_FACT_ADMISSION_ACTION 的抽查 SHA 与开工记录一致。

仓库内没有发现其他代码调用原来的公开 `validate_ledger`；结构检查已收窄为 validator 内部 helper，INITIAL 对外只保留组合入口，不留绕过 current C10 eligibility 的公开路径。

## 停点

`A-C11-INITIAL-RESTORE-MACHINE-GATE-FORMAL-FIX-01 = CONTRACT_LOCAL_PASS`

本窗口不领取下一单。

来源：Codex
