# 评测三本账 · 0 API 空骨架检查器

说白了就是：先让程序能挡住几类糊涂账。不跑模型，不读小说正文。

施工票：[GitHub #168](https://github.com/cczz412/novel-architecture/issues/168) ／ Linear [CCZ-122](https://linear.app/ccz/issue/CCZ-122)  
合同只认：[GitHub #167](https://github.com/cczz412/novel-architecture/issues/167)

这是 #167 冻结的唯一根路径。R03 里的 `eval-system-v0/` 只是顾问示意，这里不另起一套目录。

## 怎么跑

在仓库根：

```bash
uv run --locked python work/eval_system_v0_zero_api_skeleton/scripts/run_v0_checks.py
```

合法合成记录要通过；合同里的非法边必须被拒绝。回执写在 [`reports/self_check.json`](reports/self_check.json)。

## 三本账谁能写

| 目录 | 允许写入 | 禁止 |
|---|---|---|
| `common/versions/` | 新版本身份 | 覆盖旧版本 |
| `common/artifacts/` | 原件追加、修复副本另建 | 改原件字节或哈希 |
| `common/reviews/` | 人工意见旁路 | 改模型 verdict／原因码／旧状态 |
| `evidence_gate/` | J1/J2 引用、机械判定、Pair 对照 | 改考卷参照、改 #165 结果 |
| `exam/` | 题、分卷、曝光、泄漏组 | 被模型 run 自动回写参照 |
| `api_eval/` | case 和三栏结果 | 改考卷、改抽取纠错结果 |

跨账引用必须是 `id + version + hash + access=READ_ONLY`。哈希对不上，准备阶段就停。

## 合成 envelope 槽位（只给这套检查器用）

检查器不接真实供应商响应。夹具长这样：

- `transport.complete` / `transport.http_status` / `transport.generation_complete`
- `final_raw`：指定 final 槽的原始字节（字符串）。机械解析只看这一槽。
- `reasoning_raw`：思考栏。检查器**读了也不会拿来当 JSON**。
- `expected_nonce`：跟解析后的 `request_nonce` 对。

三道机械门：运输 → 解析 → Schema。别的都是失败码，不另开顶层主状态。

| 现象 | 落在哪一层 | 失败码 |
|---|---|---|
| 传输没完、HTTP 非 2xx、`generation_complete=false` | 运输 | `INCOMPLETE` / `HTTP_ERROR` / `GENERATION_INCOMPLETE` |
| `final` 空、围栏、尾随散文、重复键、截断、根不是对象 | 解析 | `FINAL_MISSING` 等 |
| 缺字段、nonce 不符、哈希不是 64 位小写 hex | Schema | `MISSING_FIELD` / `NONCE_MISMATCH` / `HASH_NOT_64_HEX` |

62 位哈希直接拒，不要左补成 64。机械失败时 `verdict_match`、`reason_code_match` 必须是 `null`。

## 本骨架操作枚举（不是产品合同）

下面这组只为了让空跑检查器有的判，标在 `V0_SKELETON_CONTRACT` 里。正式产品枚举仍是 `CANDIDATE`，见 [`schemas/CANDIDATE.md`](schemas/CANDIDATE.md)。

- `task_kind`：`SHORT_DIAGNOSIS` / `FULL_CHAPTER`
- `split`：`HELD_OUT` / `DEV` / `PUBLIC_DIAG` / `UNASSIGNED`
- `reference_status`：`NONE` / `CANDIDATE` / `PROVISIONAL`（**禁止 `GOLD`**）
- `rights_status`：`UNKNOWN` / `LOCAL_SYNTHETIC`

## 硬不变量（不得自行改写）

- 机械失败 → `semantic_result=NOT_EVALUATED`
- 分歧 → `DISPUTE_STOP` + `UNRESOLVED_DISPUTE`
- 两边都 `REJECTED` 且原因码相同 → `COMPARISON_PASS` + `REJECTED`（对照通过 ≠ 语义通过）
- 修复副本必须有 `derived_from_raw_sha256`，且 `primary_eval_eligible=false`
- 评测账对 #165 只有 `READ_ONLY`，不能写 Patch、不能改句
- 禁止第三票、0.5、改已落盘 JSON、从思考栏捞 JSON、子任务 STOP 变父任务 DONE、`UNREVIEWED` 自动变错

原因码夹具是合成短句结构检查，**不宣布正式枚举，不说已校准**。

来源：Cursor；GitHub #167／#168
