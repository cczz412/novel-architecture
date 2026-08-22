# 小说架构仓库治理索引

> 本页是人读 current。机器当前执行状态只认 [`CURRENT_STATE.json`](CURRENT_STATE.json)；版本、路径和候选身份只认 [`current_pointers.json`](current_pointers.json)。产品拍板仍以 CZ 最新明确指令和 Notion 账序／队列为准。

## 当前主线

| 项目 | 当前答案 |
|---|---|
| 当前工作线 | `CLEAN-BASELINE-M1-M11-INTEGRATION-20260821` |
| 当前阶段 | 工单 1～5、十本账 L1～L5、工单 7 已进 `main`。工单 6 已拍只读核验（31 个全部 target），本轮仍不许移动、删除、退出 Git、恢复写入或退休旧目录。不得把 M1～M11 写成完整作者能力。 |
| main 基准 | `49533178945ce5a9a6df59e20b4d57eb18706acb`（Merge PR #54 Issue #27） |
| 模块候选 | `codex/module-runtime-foundation-20260819-r01@cc793c4719fb6470946c70e744f463147989547b`（超级分支，禁止整支再合；工单 5 已按 PR-C～G 拆票进 main） |
| 产品共同背景 | `R14`；入口 [`00_READ_ME_FIRST.md`](../references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/00_READ_ME_FIRST.md)。R13 留 Git，已退出默认路由。 |
| 原子需求 | `R03 / 142 条`已在 main；六例设计 CURRENT 组合覆盖是 142 条／852 例（旧 127×6 加新增 15×6），不能冒充 852 已跑完。 |
| 当前模型运行 | 无；本线 API、训练、Gold、生产权限均为 0 |

## 唯一入口

- [机器当前状态](CURRENT_STATE.json)
- [上工先读](START_HERE.md)
- [当前版本与路径](current_pointers.json)
- [人类接力](progress/current-progress.md)
- [历史机器快照](CURRENT_STATE_HISTORY.json)
- [根旧进度全文](../history/root_current_snapshot_20260720.md)
- [模块状态登记](module_registry.json)
- [路线状态登记](route_registry.json)
- [目录路由](directory_registry.json)
- [工单 6 只读核验拍板](decision_records/DR-20260822-01.md)

## 下一件

产品下一张：六本设定账共用一个落盘方（拍板题 3，照 planstore 样式）。工单 6 按 [Issue #32](https://github.com/mhchen1/novel-architecture/issues/32) 做只读核验，不能当搬删票开干。

更新时间：`2026-08-22T16:30:00+08:00`

来源：工单 6 只读核验拍板（[DR-20260822-01](decision_records/DR-20260822-01.md)）
