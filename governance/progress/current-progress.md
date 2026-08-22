# 当前进度接力｜M1～M11 干净基线主线

> 本页只负责新窗口接力，不是机器真源。机器当前状态只认 [`governance/CURRENT_STATE.json`](../CURRENT_STATE.json)；版本、路径和候选身份只认 [`governance/current_pointers.json`](../current_pointers.json)。

## 当前主线

- 当前业务主线以 `governance/CURRENT_STATE.json` 为准；旧状态页只保留恢复协议兼容入口：[`mainline/STATUS.md`](mainline/STATUS.md)

## 当前焦点支线

- 微调支线不是本轮产品主线；旧状态页只保留恢复协议兼容入口：[`branches/finetuning/STATUS.md`](branches/finetuning/STATUS.md)

## 已关闭历史

- 历史关闭项继续从 [`closed/INDEX.md`](closed/INDEX.md) 回取，不得覆盖当前机器状态。

## 当前身份

- 更新时间：`2026-08-22T21:30:00+08:00`
- 当前工作线：`CLEAN-BASELINE-M1-M11-INTEGRATION-20260821`
- `main` 基准：`49533178945ce5a9a6df59e20b4d57eb18706acb`（Merge PR #54：Issue #27）
- 模块候选分支：`codex/module-runtime-foundation-20260819-r01`
- 候选 tip：`cc793c4719fb6470946c70e744f463147989547b`
- 当前产品共同背景：`R14`，入口 [`00_READ_ME_FIRST.md`](../../references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/00_READ_ME_FIRST.md)
- R13 与原子需求 R02：留 Git 作历史，已退出默认路由。R14／R03 已在 main，不要再开工单 2。
- 工单 6 拍板：[`DR-20260822-01.md`](../decision_records/DR-20260822-01.md)

## 现在做什么

干净基线七张工单里，1～5 和 7 已经进 main。工单 6 已在 [Issue #32](https://github.com/mhchen1/novel-architecture/issues/32) 拍成精确施工票：31 个全部 target，只做只读核验。

产品：拍板题 3 六本设定账已共用落盘方 `settingstore`，施工票是 [Issue #59](https://github.com/mhchen1/novel-architecture/issues/59)。

不要把「runtime 已按小票上 main」读成「作者能用的完整产品」。

## 当前边界

- 超级候选分支 `codex/module-runtime-foundation-20260819-r01@cc793c4719fb6470946c70e744f463147989547b` 禁止整支再合。工单 5 已按 PR-C～G 拆票进 main；没拆完的内容不得当完成态。
- 机械测试通过不等于真实小说语义质量通过。检查器绿灯 ≠ 852 条语义测试，也 ≠ 全仓 pytest 全绿。
- 本线模型 API、训练、Gold、Notion 写入、生产和自动合并权限均为 0。
- 精确分支与版本身份从 `governance/current_pointers.json` 读取；本页不得覆盖它。
- 工单 6 本轮不得移动、删除、退出 Git、恢复写入或退休旧目录。T7 没挂上就是 `NOT_RUN`。

## 下一步

1. 产品：拍板题 3 设定账统一 writer 已落 `settingstore`（Issue #59）。等人「检查再合并」，不要再平行领同一张票；
2. 工单 6：Git 补 31 个 target、嵌套合计、本机绑定和 T7 `NOT_RUN`；本地 Codex 在绑定后核 25 个旁仓对象，T7 挂上后再核 6 次；
3. 不要回头领工单 1～5 或工单 7，那些已经在 main。

来源：工单 6 只读核验拍板（DR-20260822-01）
