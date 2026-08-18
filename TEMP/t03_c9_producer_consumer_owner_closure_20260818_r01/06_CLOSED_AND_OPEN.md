# 已闭合与仍 OPEN

## 已闭合

1. C4 事实源 owner：M4/M5 作者确认路径；下游只读 current confirmed。
2. plan.json owner：planstore；计划不等于 actual，consumer 不能改写。
3. C9 候选 producer 方向：M11。
4. C9 声明 consumer 方向：M8。
5. C9 来源变化：stale／重编；不能回写真源。
6. M11 只拥有候选包的选择、遗漏记录、预算复算和错误输出。
7. permission、capability、project scope、handle 仍在外部 preflight。

## 仍 OPEN

1. 运行时 M11 packer。
2. 运行时 M8 C9 consumer。
3. 正式任务票合同和唯一 producer。
4. 预算 cap 的 owner 与值。
5. token estimator owner 与版本。
6. C4／planstore 跨源统一 actuality 映射。
7. HARD/SHOULD/MAY 与 `selection_rank` owner。
8. unresolved-state 语义。
9. evidence recall policy。
10. C9→C7 lineage 和 consumer acceptance gate。

这些 OPEN 不阻塞本轮 TEMP 闭包，因为本轮目的就是把缺口显式化；它们全部阻止“正式 C9 已接通”这一说法。

来源：Codex
