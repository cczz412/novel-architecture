# C11 action Schema 与公开入口组合窄修报告

任务：`A-C11-ACTION-SCHEMA-COMPOSITION-FORMAL-FIX-01`

状态：`CONTRACT_LOCAL_PASS`

## 结论

D 窗复现的机器缺口已经关闭。公开 `validate_action` 现在先验证完整 action Schema；Schema 无效时不会再进入 REPLACE／RESTORE 业务分支，也不会把 jsonschema 的原文和路径暴露成公共错误协议，而是稳定返回 `REJECTED_ACTION_SCHEMA`。

Schema 通过后只接受显式 `REPLACE` 或 `RESTORE`。未知值不再通过旧的 `else=REPLACE` 路径。

原有错误语义保持：作者或意图不合法仍是 `REJECTED_AUTHOR_INTENT_REQUIRED`；stale 仍是 `REJECTED_STALE`；合法 REPLACE、合法 RESTORE、no-change、eligibility 和 batch 原子门没有变化。

## 正式写集

只修改两件：

1. `novel-mvp/contracts/validate_c11_chapter_revision_ledger.py`
2. `novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.fixtures.jsonl`

`CHAPTER_REVISION_COMMIT_ACTION.md` 与正式 Schema 字节未变。没有修改 C10 或第三个正式文件。

## D 五例重放

| 子例 | Schema | 公开入口 | 结果 |
|---|---|---|---:|
| 合法 REPLACE | 通过 | `PRECHECK_ALLOWED` | PASS |
| INITIAL | 拒绝 | `REJECTED_ACTION_SCHEMA` | PASS |
| BOGUS | 拒绝 | `REJECTED_ACTION_SCHEMA` | PASS |
| 缺 contract | 拒绝 | `REJECTED_ACTION_SCHEMA` | PASS |
| 缺 version | 拒绝 | `REJECTED_ACTION_SCHEMA` | PASS |

五例全部执行，失败路径写入 0。详细机器账见 `D_FIVE_CASE_REPLAY.json`。

## 验收

| 检查 | 结果 |
|---|---:|
| 原 C11 正式结果 | 75/75 PASS |
| 新 action-entry cases | 5/5 PASS |
| C11 总结果 | 80/80 PASS |
| C10 v4 validator | PASS；28 fixtures、33 negative probes |
| Schema JSON / fixtures JSONL | PASS；80 行 |
| validator Ruff | PASS |
| 依赖非法 action 被放行的直接公开调用者 | 0 |
| 新失败 | 0 |
| API / 模型 / 自动重试 | 0 / 0 / 0 |

## 停点

`A-C11-ACTION-SCHEMA-COMPOSITION-FORMAL-FIX-01 = CONTRACT_LOCAL_PASS`

本窗口不自行领取下一单。

来源：Codex
