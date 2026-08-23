# T5 R04 微调兼容路牌

这页是机器派生视图，删除后可以从微调域当前入口、当前 MANIFEST 和历史路线目录完整重建。

## 当前实验

- experiment_id：`T5_R04_LINE_ABANDONED_20260823_R01`
- MANIFEST revision：`r01`
- MANIFEST SHA：`9b72a76c9b14230fb20b71ad380ab7e5201458edff4be34977fc1617e817d1e9`
- 每臂母集：0 行
- 每臂训练：0 行
- 当前考卷：每臂 0 题
- 当前金标：每臂 0 条

当前实验身份只认 [微调域入口](../../finetuning/CURRENT.json) 和它绑定的 MANIFEST。本目录不再人工维护“C 未生成”或“哪个候选最新”一类当前状态。

## 历史路线

历史来源位置和依赖关系保存在 `route_catalog.json`。它只负责“旧东西去哪里找”，不能决定当前实验或授权训练。

机器兼容视图是 `route_registry.json`；现有消费者应把它当可重建导航，不得当唯一真源。

来源：Codex
