# 当前进度接力｜M1～M11 干净基线主线

> 本页只负责新窗口接力，不是机器真源。机器当前状态只认 [`governance/CURRENT_STATE.json`](../CURRENT_STATE.json)；版本、路径和候选身份只认 [`governance/current_pointers.json`](../current_pointers.json)。

## 当前主线

- 当前业务主线以 `governance/CURRENT_STATE.json` 为准；旧状态页只保留恢复协议兼容入口：[`mainline/STATUS.md`](mainline/STATUS.md)

## 当前焦点支线

- 微调正线已放弃（CZ 2026-08-23）。Git 只留[此路不通](../../finetuning/README.md)；旧状态页改成收口说明：[`branches/finetuning/STATUS.md`](branches/finetuning/STATUS.md)

## 已关闭历史

- 历史关闭项继续从 [`closed/INDEX.md`](closed/INDEX.md) 回取，不得覆盖当前机器状态。

## 当前身份

- 更新时间：`2026-08-22T23:46:41+08:00`
- 当前工作线：`CLEAN-BASELINE-M1-M11-INTEGRATION-20260821`
- `main` 刷新时的 base（本页复核到）：`c91ecffa084dd8a5cb834a2789e8fb408c0229e3`（Merge PR #81：Issue #63）。运行时 HEAD 由 [`tools/check_current_freshness.py`](../../tools/check_current_freshness.py) 另报。
- 模块候选分支：`codex/module-runtime-foundation-20260819-r01`
- 候选 tip：`cc793c4719fb6470946c70e744f463147989547b`
- 当前产品共同背景：`R14`，入口 [`00_READ_ME_FIRST.md`](../../references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/00_READ_ME_FIRST.md)
- R13 与原子需求 R02：已退出本 Git，本机备份。后续改板从现行 R14／R03 接着做。不要再开工单 2。
- 工单 6 拍板：[`DR-20260822-01.md`](../decision_records/DR-20260822-01.md)
- 工程真源拍板：[`DR-20260822-02.md`](../decision_records/DR-20260822-02.md)；上工入口 [`START_HERE.md`](../START_HERE.md)

## 现在做什么

干净基线七张工单里，1～5 和 7 已经进 main。工单 6 只读核验已按 [Issue #32](https://github.com/cczz412/novel-architecture/issues/32) 回执结账：2026-08-22 06:24 复跑 25/25＋6/6 PASS at main@`3c387ca5336daadc001c85f253186259da4a6c68`。搬删仍禁止。

产品：拍板题 3 六本设定账已共用落盘方 `settingstore`，施工票是 [Issue #59](https://github.com/cczz412/novel-architecture/issues/59)，已经进 main。

不要把「runtime 已按小票上 main」读成「作者能用的完整产品」。

## 当前边界

- 超级候选分支 `codex/module-runtime-foundation-20260819-r01@cc793c4719fb6470946c70e744f463147989547b` 禁止整支再合。工单 5 已按 PR-C～G 拆票进 main；没拆完的内容不得当完成态。
- 机械测试通过不等于真实小说语义质量通过。检查器绿灯 ≠ 852 条语义测试，也 ≠ 全仓 pytest 全绿。
- 本线模型 API、训练、Gold、Notion 写入、生产和自动合并权限均为 0。
- 精确分支与版本身份从 `governance/current_pointers.json` 读取；本页不得覆盖它。
- 工单 6 本轮不得移动、删除、退出 Git、恢复写入或退休旧目录。T7 没挂上就是 `NOT_RUN`。
- 工程队列只认 [GitHub Issues](https://github.com/cczz412/novel-architecture/issues)，不认 Notion 旧账序页。

## 下一步

1. 施工入口是带 `status:ready` 的 GitHub Issues，先读 [`START_HERE.md`](../START_HERE.md)；
2. 工单 6 只读核验已经结账，不要再当没做；搬删禁令仍在，不要把结账读成可以搬家；
3. 不要回头领工单 1～5 或工单 7，那些已经在 main。

来源：[#64](https://github.com/cczz412/novel-architecture/issues/64) 档位 B 批尾刷新；工单 6 拍板 DR-20260822-01
