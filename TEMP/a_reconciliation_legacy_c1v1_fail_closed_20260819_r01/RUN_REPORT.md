# A-RECONCILIATION legacy C1 v1 强停窄修报告

任务：`A-RECONCILIATION-LEGACY-C1V1-FAIL-CLOSED-01`

状态：`CONTRACT_LOCAL_PASS`

## 结论

三个候选错误成功在修前全部真实成立，满足自动继续条件；随后只修改了 `novel-mvp/mvp/reconcile.py`，没有碰第二个正式文件。

修后行为是：

- 旧 r06 / v1 observe 遇到 revision-aware C1 v1，会在 transaction prepare 之前以 `LEGACY_RECONCILIATION_V1_REQUIRES_LEGACY_C1` 拒绝，0 写入。
- 已存在旧 RE 时，旧 v1 facts admission 遇到 C1 v1，同样在写 facts 和 plan 之前拒绝，0 写入。
- reader 遇到 C1 v1 且旧 RE 缺 `chapter_revision_ref`，派生 `LEGACY_RE_CHAPTER_REVISION_UNKNOWN`，`current=false`、`actual_support=false`，不写账。
- legacy C1 v0 保持原行为：观察生成 6 条 RE，作者准入写 4 条 facts，exact / variant 两条边仍可提供 actual 支持。

## 修前证据

- FF-01：C1 v1 下旧 observe 返回 COMMITTED，写出 6 条均缺 `chapter_revision_ref` 的 RE。
- FF-02：C1 v1 下旧 admission 返回 COMMITTED，写入 4 条 confirmed facts。
- FF-03：C1 v1 + r06 RE 缺 revision ref 时，reader 仅凭相同正文 SHA 仍给 `RE-0001`、`RE-0002` 两条 actual 支持。

详细的写前/写后 SHA、文件集合和变更文件见 `FAIL_FIRST_RESULTS.json`。修前运行时 `reconcile.py` SHA 前后均为 `ecc6617973e7211c5c552baf3c2ef362430d7eeb77a8149f7fb01e77aadf6d1d`，正式写入为 0。

## 验收

| 检查 | 结果 |
|---|---:|
| 三个错误成功修后拒绝/降级 | 3/3 PASS |
| 三条失败路径文件变化 | 0/3 |
| legacy C1 v0 正例 | PASS |
| 指定 pytest | 50/50 PASS |
| Ruff | PASS |
| 新失败 | 0 |
| API / 模型 / 自动重试 | 0 / 0 / 0 |

## 写集

唯一正式修改：

`novel-mvp/mvp/reconcile.py`

SHA：

- 修前：`ecc6617973e7211c5c552baf3c2ef362430d7eeb77a8149f7fb01e77aadf6d1d`
- 修后：`bb6f70635ba0f41d70c91cb60fad11f5af3ce1d96f49c0cfe26b84e9cb281a40`

C1、C11、PLAN_LEDGER_STORAGE、RECONCILIATION_FACT_ADMISSION_ACTION 和两份指定测试文件的对照 SHA 未变。没有修改合同、Schema、planstore、R13、Gold 或产品其他模块。

## 停点

`A-RECONCILIATION-LEGACY-C1V1-FAIL-CLOSED-01 = CONTRACT_LOCAL_PASS`

本窗口不自行领取下一单。

来源：Codex
