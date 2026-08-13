# T5 R04｜P3 权利补件＋输入合同零训练筛查

## 当前结论

P3 双轨已完成并硬停，没有训练、API、Notion、Git、现役微调指针或 P2 封版改动。

## Track A｜权利补件

- P2 的 314 行／2,783 条事实已机械聚合为 74 个书／来源组；
- 74 组全部仍是权利未知，本地直接放行 0 组；
- CZ 后续可按 74 组裁决，不必逐行重复确认。

裁决入口：`finetuning/experiments/T5_R04_INPUT_CONTEXT_CONTRACT_P3_20260808_R01/sealed_inputs_r01/track_a/RIGHTS_DECISION_REQUEST_TO_CZ.md`

## Track B｜输入合同

- C0 当前极简：语义 F1 0.894；
- C1 八条规则：语义 F1 0.622，召回从 87.5% 降到 47.9%，当前写法淘汰；
- C2 任务目的：语义 F1 0.891，与 C0 基本打平，未证明有收益；
- C4 确认前态：语义 F1 0.825，并有 2 案把只读前态当答案、引用 `B01`，不晋升；
- C3 安全身份／别名只有 1/24，不运行；
- C5 没有真实章节／块坐标，不运行。

四个已运行臂都是 24/24 正常停止，0 复读、0 触顶。

## 下一动作

仍回到 P2 主线：由 CZ 给 74 个来源组补权威训练权利或裁决。权利和真实 canonical 没有补齐前，不训练、不把本地合成输入结论迁移给豆包。

详细结果：`finetuning/experiments/T5_R04_INPUT_CONTEXT_CONTRACT_P3_20260808_R01/P3_RESULT_TICKET.md`

来源：Codex
