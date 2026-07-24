# 小说流水线治理索引

> 本页由 `tools/governance_index.py` 从 `governance/CURRENT_STATE.json` 生成。人从这里看，机器读取当前任务／运行状态只认这份真源；模块与实验路线各看自己的登记册；Notion 账序和队列仍是最终真源。根 `current.md` 与模块 README 只作历史上下文。

## 一页回答关键问题

| 问题 | 当前答案 |
|---|---|
| 现在跑到哪道 | **九项落地第四道·⑥语料授权清单**（`NINE-ITEMS-04-CORPUS-RIGHTS-REGISTRY`）；状态＝**2026-07-24 08:20 Notion统一审收PASS；⑥道与并行A/B/C各自收口；0模型API**；当前运行＝无独立模型运行；授权时间＝`2026-07-23T23:58:00+08:00` |
| 金标哪版哪指针 | 正式金标共 6 个入口：X01 第3章 **v1.2**＋五本 v1.3；统一登记 `config/gold/formal_gold_registry.json` |
| 各模块什么状态 | 可用 10 个版本／在改 5 个版本／试验 2 个版本；见 [模块状态登记](module_registry.json) |
| 银标候选在哪 | 五本底稿、正反例候选、第75道样张及沙箱观察均在 [银标候选索引](indexes/silver_candidates.md)；正式件不从候选标题自动推断 |
| 实验路线能不能再开 | 在试 2 条／失败 0 条／退役 3 条／当前允许重开 0 条；见 [路线状态登记](route_registry.json) |
| 当前任务有什么阻断 | 0 项 |

## 当前正式入口

- 默认链：`config/defaults/zbatch_v1.2_full_chain.json`，版本 `v1.2`。
- 旧运行入口：`tools/zbatch.py`，继续保留。
- 新统一薄入口：`tools/novel_pipeline.py`；现役命令原样转发给旧入口，不复制运行逻辑。
- 密钥加载入口：只用 `tools/sensenova_deepseek_key.sh`；共享环境和外部项目加载器已退役。
- 试验专区：`experiments/`；旧试验原件不搬，新试验从这里起。

## 快速入口

- [当前停点](current_run.md)
- [机器当前状态](CURRENT_STATE.json)
- [实验路线状态](route_registry.json)
- [正式金标](indexes/gold_current.md)
- [银标候选](indexes/silver_candidates.md)
- [运行与回包](indexes/runs_and_reports.md)
- [材料与参考](indexes/source_registry.md)
- [旧路牌健康检查](indexes/route_health.md)
- [模块依赖图](dependency_map.json)
- [合同说明](contracts/README.md)
- [试验专区](../experiments/INDEX.md)

## 下一件

等待CZ拍三题：授权凭据补齐范围、跨书盲测发网预算、并行B产品参数。硬前置顺序＝补齐授权凭据→逐书权利票→G2选章→CZ拍发网预算；此前不发网、不启用20本提案。并行C只按长期令低优先续产候选，不得直接训练。

来源：Cursor（仓库治理窗）
