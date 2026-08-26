# 04｜真实回件重放验收表

## 验收原则

下一轮实现只读取已经进 GitHub 的冻结证据，不发网、不重跑模型。每个案例先按 [`fixtures/replay_cases.json`](fixtures/replay_cases.json) 固定预期，再运行程序。

程序通过只能说明“机械检查和路由符合预期”，不能说明模型答案正确。

## 预注册案例

| 案例 | 真实来源 | 必须发现什么 | 允许动作 | 预期停点 |
|---|---|---|---|---|
| `R01_GLM52_OUTER_FENCE_Q1` | GLM-5.2 非思考 Q1 原始 stdout | `JSON.OUTER_FENCE` | 只剥一层完整围栏；前后叶子和数组顺序相同 | 机械派生后继续 Schema／evidence |
| `R02_DOUBAO_MINI_DUPLICATE_STATUS_Q2` | Doubao Mini Q2 原始 stdout | content 中同一对象重复 `status` | 不得让普通解析器静默保留后值 | `STOP_UNSAFE_JSON` |
| `R03_DOUBAO_TURBO_EMPTY_SPEAKER_Q1` | Doubao Turbo Q1 原始 stdout | 空 `speaker` 导致 `SCHEMA.EMPTY_OPTIONAL` | 只诊断，不自动删除或猜说话人 | `STOP_HUMAN_REQUIRED` |
| `R04_DOUBAO_LITE_BROKEN_JSON_Q2` | Doubao Lite Q2 原始 stdout | `JSON.PARSE_ERROR` | 保存错误位置，不猜修数组和引号 | `STOP_UNSAFE_JSON` |
| `R05_MINIMAX_THINKING_TRUNCATED_Q1` | MiniMax 最低思考 Q1 原始 stdout／meta | 输出预算耗尽且没有完整任务 JSON | 只保存截断和 usage | `STOP_TRUNCATED` |
| `R06_DEEPSEEK_OLD_ID_MISSING` | 冻结模型身份和派生纠正回执 | 旧请求 ID 不在保存的实时目录 | 不换成相似新 ID | `STOP_IDENTITY_MISMATCH` |
| `R07_DOUBAO_TURBO_CAUSAL_REVIEW_Q4` | Doubao Turbo Q4 原始 stdout和 Q4 题面 | 因果只进入旁路复核候选，不能写回 facts | A 票只记录复核候选；B 票才允许生成 `RelationCandidate` 草稿 | `STOP_HUMAN_REQUIRED` |
| `R08_DOUBAO_TURBO_MECHANICAL_CONTROL_Q3` | Doubao Turbo Q3 原始 stdout | 外壳、JSON、Schema、evidence 机械门可完成 | 保留语义轴 `NOT_CHECKED` | `READY_FOR_HUMAN` |
| `R09_EVIDENCE_NOT_FOUND_SYNTHETIC_NEGATIVE` | 从冻结 Q1 派生的明确不存在 evidence 测试件 | `EVIDENCE.NOT_FOUND` | 不修 evidence | `STOP_EVIDENCE_NOT_FOUND` |

R09 是检查器负例，不是模型成绩，不能混进 API 观察表。

## 每个案例都要保存什么

- 案例 ID 和来源路径；
- 来源文件当前 SHA；
- Attempt ID 和原始回复 SHA；
- 实际命中的 Diagnostic；
- 实际状态转移；
- 实际停止原因；
- 检查了哪些轴、没检查哪些轴；
- 派生前后内容 SHA；
- 叶子值、键值和数组顺序不变量；
- 网络请求数和模型调用数；
- ReplayReport SHA。

## 全批机械验收

| 检查 | 通过条件 |
|---|---|
| 原件保护 | 所有上游请求、响应和 meta 的 SHA 前后完全相同 |
| 预期路由 | 9/9 案例命中预注册 Diagnostic 和终态 |
| 两层 JSON | 外壳与 content 分开报告；重复键不会被静默吞掉 |
| 安全围栏 | R01 派生后所有叶子值、键值和数组顺序不变 |
| 坏 JSON 停损 | R02、R04 不生成猜修 CandidateVersion |
| Schema 分层 | R03 明确是 JSON 可解析但 Schema 失败 |
| 截断分层 | R05 不进入 Schema 或语义 PASS |
| 身份闸 | R06 不替换模型 ID、不产生网络请求 |
| 因果边界 | R07 只记录旁路候选诊断，不改 v2.1 `facts`；A 票不生成关系对象 |
| 非总 PASS | R08 的说话人、因果和覆盖保持 `NOT_CHECKED` |
| evidence 负例 | R09 被拒绝，不改成相似原文 |
| 零调用 | `network_requests=0`、`model_calls=0`、`tokens_consumed=0` |

## 失败怎么报

任一案例失败时，ReplayReport 保存：

- 预期和实际差异；
- 最早发生偏差的状态；
- 是否改变上游字节；
- 是否产生越权派生或 Patch；
- 后续轴为何没有继续检查。

不为了追求 9/9 在运行后改预期。若预注册本身写错，另开设计修订提交，保留旧版本。

来源：Codex
