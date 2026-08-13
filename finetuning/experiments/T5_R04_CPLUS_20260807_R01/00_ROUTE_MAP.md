# T5 R04 C+｜现役寻路

## 这条线现在做什么

当前任务不是继续扩大旧 A/C 教材，也不是宣布 C 胜出。现在只验证旧实验的三个病因，再冻结 C2_UNIT 的新合同。

## 权威顺序

1. CZ 已拍决定：`decisions/P0_DECISION.md`
2. 事前阈值：`decisions/DECISION_THRESHOLDS.md`
3. 本实验机器总账：`MANIFEST.json`
4. 可恢复进度：`RUN_STATE.json`
5. 阶段回执：各 `stage_*` 目录
6. 上游旧实验：只读，不回写

## 当前身份

- experiment_id：`T5_R04_CPLUS_20260807_R01`
- 当前阶段：阶段 1，三个零训练根因证伪
- 当前证据合同：`C2_UNIT`
- 当前训练授权：无；阶段 1 不训练
- 当前大规模抽数授权：无；500 本候选池尚未启动

## 上游只读资产

- 旧 A/C 实验：`/Users/a1234/挣钱/小说架构_隔离实验/T5_R04_A_C_FORMAT_COMPARE_20260807_R01`
- 旧实验每臂母集：398 行
- 旧实验每臂实际训练：350 行＝278＋72
- 当前历史回归卷：41 题
- 旧冻结隔离卷：48 题

旧 `governance/progress/t5-r04-a-curriculum-quality-mainline.md` 的 585 行只保留历史说明，不能作为当前 C+ 或上游 A/C 实验分母。

## 唯一下一动作

按冻结阈值串行运行阶段 1A：同一 41 题下比较 stage1 checkpoint 与 final checkpoint；完成后再进入 1B、1C。

来源：Codex
