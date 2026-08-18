# 逐字段 owner 闭包

完整机器表：`results/field_owner_matrix.json`。下面只写人读结论。

## 输入字段

| 字段 | 唯一 owner | 允许 producer | 当前 consumer | 缺失／冲突谁停 | 闭包 |
|---|---|---|---|---|---|
| `task_id` | 未正式分配 | 设计稿称 M0/M8 任务入口 | M11 候选输入门 | M11 停；任务 producer 修 | OPEN |
| `task_actuality_scope` | 未正式分配 | 任务 producer 角色 | M11 | M11 停 OPEN | OPEN |
| `budget_tokens` | O1 仍未拍 | 版本化任务／配置源 | M11 | M11 停；配置 owner 修 | OPEN |
| `token_estimator_ref` | 未正式分配 | 版本化估算器 | M11 | M11 停 | OPEN |
| `candidate_materials[].id` | 各源账 writer | C4 M4/factstore 或 planstore 读视图 | M11 | M11 停；源 owner 修 | 源 owner 已闭合，C9 路由 OPEN |
| `estimated_tokens` | 估算器 owner 未定 | 与 estimator ref 同版本 | M11 | M11 停 | OPEN |
| `actuality_class` | 统一映射 owner 未定 | 权威源语义的正式映射层 | M11 | M11 停 OPEN；源语义 owner 修 | OPEN |
| `obligation_tier` | 义务 owner 未定 | 作者／任务合同角色待冻 | M11 | M11 停；义务 owner 修 | OPEN |
| `selection_rank` | 同义务 owner，未定 | 与 obligation 同 owner | M11 | M11 停冲突 | OPEN |

## 输出字段

`decision_state`、`load_ids`、`omitted`、`loaded_token_estimate`、预算回显、`why_loaded`、`errors` 的候选生产权都属于 M11；输入预算 owner 不因“回显”而转给 M11。

这些字段的声明 consumer 是 M8，但实际 C9 runtime consumer 不存在。因此当前只能写：

- producer 方向：候选已明确；
- consumer 方向：设计／合同声明存在；
- runtime acceptance gate：OPEN，不能写成已接通。

未来 M8 consumer 收到缺字段、非 READY、预算复算不一致或 stale 包时必须拒绝，但这道运行时门尚未施工。

来源：Codex
