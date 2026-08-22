# 当前进度接力｜M1～M11 干净基线主线

> 本页只负责新窗口接力，不是机器真源。机器当前状态只认 [`governance/CURRENT_STATE.json`](../CURRENT_STATE.json)；版本、路径和候选身份只认 [`governance/current_pointers.json`](../current_pointers.json)。

## 当前主线

- 当前业务主线以 `governance/CURRENT_STATE.json` 为准；旧状态页只保留恢复协议兼容入口：[`mainline/STATUS.md`](mainline/STATUS.md)

## 当前焦点支线

- 微调支线不是本轮产品主线；旧状态页只保留恢复协议兼容入口：[`branches/finetuning/STATUS.md`](branches/finetuning/STATUS.md)

## 已关闭历史

- 历史关闭项继续从 [`closed/INDEX.md`](closed/INDEX.md) 回取，不得覆盖当前机器状态。

## 当前身份

- 更新时间：`2026-08-22T12:00:00+08:00`
- 当前工作线：`CLEAN-BASELINE-M1-M11-INTEGRATION-20260821`
- `main` 基准：`dd201deaee4cf60cf133eb7511ac94dd60bca2c7`（Merge PR #53：工单 7）
- 模块候选分支：`codex/module-runtime-foundation-20260819-r01`
- 候选 tip：`cc793c4719fb6470946c70e744f463147989547b`
- 当前产品共同背景：`R14`，入口 [`00_READ_ME_FIRST.md`](../../references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/00_READ_ME_FIRST.md)
- R13 与原子需求 R02：留 Git 作历史，已退出默认路由。R14／R03 已在 main，不要再开工单 2。

## 现在做什么

干净基线七张工单里，1～5 和 7 已经进 main。工单 6 还停在 [Issue #32](https://github.com/mhchen1/novel-architecture/issues/32)，标签是 `needs-cz`，不是施工票。

产品下一张是拍板题 3：六本设定账共用一个落盘方，照规划账 `planstore` 那种原子提交来写。这张票还没切 GitHub 施工卡。

本页这次只刷路牌（Issue #27）。不要把「runtime 已按小票上 main」读成「作者能用的完整产品」。

## 当前边界

- 超级候选分支 `codex/module-runtime-foundation-20260819-r01@cc793c4719fb6470946c70e744f463147989547b` 禁止整支再合。工单 5 已按 PR-C～G 拆票进 main；没拆完的内容不得当完成态。
- 机械测试通过不等于真实小说语义质量通过。检查器绿灯 ≠ 852 条语义测试，也 ≠ 全仓 pytest 全绿。
- 本线模型 API、训练、Gold、Notion 写入、生产和自动合并权限均为 0。
- 精确分支与版本身份从 `governance/current_pointers.json` 读取；本页不得覆盖它。
- 工单 6 未获 CZ 对象许可前，不得移动、删除、打包外置材料。

## 下一步

1. 产品：切「设定账统一 writer」施工票（拍板题 3）；
2. 工单 6：等 CZ 在 Issue #32 拍 31 个对象怎么处理，再交给本地 Codex 做大件外置；
3. 不要回头领工单 1～5 或工单 7，那些已经在 main。

来源：Issue #27 路牌刷新（云端 Agent）
