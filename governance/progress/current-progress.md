# 当前进度接力｜M1～M11 干净基线主线

> 本页只负责新窗口接力，不是机器真源。机器当前状态只认 `governance/CURRENT_STATE.json`；版本、路径和候选身份只认 `governance/current_pointers.json`。

## 当前主线

- 当前业务主线以 `governance/CURRENT_STATE.json` 为准；旧状态页只保留恢复协议兼容入口：[`mainline/STATUS.md`](mainline/STATUS.md)

## 当前焦点支线

- 微调支线不是本轮产品主线；旧状态页只保留恢复协议兼容入口：[`branches/finetuning/STATUS.md`](branches/finetuning/STATUS.md)

## 已关闭历史

- 历史关闭项继续从 [`closed/INDEX.md`](closed/INDEX.md) 回取，不得覆盖当前机器状态。

## 当前身份

- 更新时间：`2026-08-21T02:49:17+08:00`
- 当前工作线：`CLEAN-BASELINE-M1-M11-INTEGRATION-20260821`
- `main` 基准：`f8680907f5be5c199479ba52510e9ab4f16eded7`
- 模块候选分支：`codex/module-runtime-foundation-20260819-r01`
- 候选 tip：`cc793c4719fb6470946c70e744f463147989547b`
- 当前产品共同背景：`R13`，入口 `references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/00_READ_ME_FIRST.md`
- R14 与原子需求 R03：仍在候选分支；工单 2 才允许上 main，本工单不得抢跑。

## 现在做什么

按已拍工单顺序执行：`1 → 2 →（3、4 并行）→ 5 → 6 → 7`。当前只做工单 1：唯一 current 收口。工单 1 不改产品语义、需求、设计、合同或 runtime；完成后由 CZ 在 PR 页复核并合并，再开工单 2。

## 当前边界

- 候选分支包含产品语义、需求、设计、runtime、测试和 evidence，不能整体当成已完成产品，也不能整支直接合并。
- 机械测试通过不等于真实小说语义质量通过。
- 本线模型 API、训练、Gold、Notion 写入、生产和自动合并权限均为 0。
- 精确分支与版本身份从 `governance/current_pointers.json` 读取；本页不得覆盖它。

## 下一步

1. 复核并合并工单 1 PR；
2. 从新 main 开工单 2，把 R14 与原子需求 R03 作为纯语义层上 main；
3. 工单 3／4 未开始前，不把追踪表或 design registry 写成正式 current。

来源：ChatGPT（工单 1 云端候选）
