# R01.1 真源与漂移清单

## 当前工程真源

本轮只认 GitHub `cczz412/novel-architecture`。

读取快照：

- `main@fa287f5f24f81c1c84e710f056f7099e390d7225`
- 合并来源：PR #173，`feat(factstore): add FACT_CAUSAL_EDGE writer`
- Draft PR #166：仍为 Open Draft
- PR #166 base：`6153fa339b1d1c3df71cd708c3e1a7b175cc3071`
- PR #166 head：`0d7989502693c28cad1f9196af999d72b5916ce2`

## R01 里已经过期或互相冲突的内容

| R01／旧 PR 内容 | 当前真相 | R01.1 处理 |
|---|---|---|
| 现场 `main@1eb9640...` | 当前已到 `fa287f5...` | 所有施工前重新读 current main |
| FACT_CAUSAL_EDGE writer 仍待实现 | PR #173 已进入 main，现役 writer 是 `factstore` | 不再新造 writer；只设计怎样调用现役候选入口 |
| 旧 PR 把骨架放在 M3 与 M4 之间 | 当前 C2→M3→C3→M4 合同已经明确 | 定位改为 M3 内部控制面，在 C3 发出以前工作 |
| `replace_module: M03` | 与“不替换 M3”冲突 | 删除替换身份，只增强 M3 内部接收、诊断和候选生成 |
| 持久 `RelationCandidate` | 正式对象已是 FACT_CAUSAL_EDGE | 不再建第二套正式关系对象 |
| `causal_review_hint` 被叫作短命，但又进入 Patch、版本和 checkpoint | 实际已经是持久内部状态 | 明确改成有期限、可审计、非正式账的侧车 artifact |
| Agent 回合既读 `tool_calls`，又要求 `final content JSON` | 合法工具调用可能没有普通正文 | 分开旧抽取回包与 Agent 动作回包 |
| 47 个 JSON 都能解析 | 21 个工具片段含本地 `$ref`，片段自身没有 `$defs` | 增加独立 Schema 打包与引用检查 |
| 当前状态每轮改变工具列表，同时承诺稳定缓存前缀 | 工具定义变化会改变请求前缀 | 使用分阶段固定工具包；跨包切换不承诺缓存命中 |

## 正式输入、输出与产品缺失

当前 M3 读取一个 current `C2_SEGMENT v1`，里面有章节版本身份、责任段正文、段序和左右背景；必要时只能按诊断窄读同一 current C1 的明确范围。M3 能够输出 `C3_FACT_CANDIDATE v1`，字段是章节版本身份、事实文本、原文引文和段号。

小说辅助产品还缺少两项正式能力：

1. 还没有明确规定内部修复出来的 `status`、`speaker` 由谁长期保存、哪个后续模块读取；
2. 现役底层 `factstore.add_fact_candidates` 会在事务回执里返回按输入顺序排列的 `new_f_ids`，但上层 `store.add_fact_candidates` 只返回数量，C3 条目本身也没有稳定 item key。小说辅助产品还没有一份正式映射回执，把 M3 内部候选稳定对应到 M4 分配的 `f...`，再安全交给现役 `factstore.add_fact_causal_edge_candidates`。

这会卡住作者两个操作：作者不能稳定回看“谁说的、事实处于什么状态”；作者也不能从抽取结果可靠进入“因为哪条事实，所以发生哪条事实”的候选确认。

## 开工边界

- 本修订沿用设计入口 GitHub Issue #165，但只提交候选文档；不把 Draft PR #166 当现成施工分支。
- 后续 A 票必须重新读当时的 `main`、工单标签、写集和阻塞关系。
- A 票通过只表示离线硬外壳能工作，不表示 API 或小说语义已经通过。

来源：Codex
