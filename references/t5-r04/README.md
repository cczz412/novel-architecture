# T5 R04 微调兼容路牌

这页是机器派生视图，删除后可以从微调域当前入口、当前 MANIFEST 和历史路线目录完整重建。

## 当前实验

- experiment_id：`T5_R04_CPLUS_20260807_R01`
- MANIFEST revision：`r01`
- MANIFEST SHA：`7f5818391b9988be2ddeb0d5ac89fe49363c0d0e245a7d02660cf649cab08216`
- 每臂母集：398 行
- 每臂训练：350 行
- 当前考卷：每臂 41 题
- 当前金标：每臂 355 条

当前实验身份只认 [微调域入口](../../finetuning/CURRENT.json) 和它绑定的 MANIFEST。本目录不再人工维护“C 未生成”或“哪个候选最新”一类当前状态。

## 历史路线

历史来源位置和依赖关系保存在 `route_catalog.json`。它只负责“旧东西去哪里找”，不能决定当前实验或授权训练。

机器兼容视图是 `route_registry.json`；现有消费者应把它当可重建导航，不得当唯一真源。

来源：Codex
