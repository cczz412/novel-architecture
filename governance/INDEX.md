# 小说架构仓库治理索引

> 本页是人读 current。机器当前执行状态只认 [`CURRENT_STATE.json`](CURRENT_STATE.json)；版本、路径和候选身份只认 [`current_pointers.json`](current_pointers.json)。产品拍板仍以 CZ 最新明确指令和 Notion 账序／队列为准。

## 当前主线

| 项目 | 当前答案 |
|---|---|
| 当前工作线 | `CLEAN-BASELINE-M1-M11-INTEGRATION-20260821` |
| 当前阶段 | 工单 1：唯一 current 收口；候选 PR 未合并前不得冒充 main 完成态 |
| main 基准 | `f8680907f5be5c199479ba52510e9ab4f16eded7` |
| 模块候选 | `codex/module-runtime-foundation-20260819-r01@cc793c4719fb6470946c70e744f463147989547b` |
| 产品共同背景 | `R13`；工单 2 才允许升 `R14` |
| 原子需求 | `R03 / 142 条`仍在候选分支；工单 2 才允许上 main |
| 当前模型运行 | 无；本线 API、训练、Gold、生产权限均为 0 |

## 唯一入口

- [机器当前状态](CURRENT_STATE.json)
- [当前版本与路径](current_pointers.json)
- [人类接力](progress/current-progress.md)
- [历史机器快照](CURRENT_STATE_HISTORY.json)
- [根旧进度全文](../history/root_current_snapshot_20260720.md)
- [模块状态登记](module_registry.json)
- [路线状态登记](route_registry.json)
- [目录路由](directory_registry.json)

## 下一件

CZ 复核并合并工单 1 PR；随后从新 main 开工单 2，只引入 R14、原子需求 R03 和对应 CURRENT，不夹带 runtime 或 evidence。

更新时间：`2026-08-21T02:49:17+08:00`

来源：ChatGPT（工单 1 云端候选）
