# 小说流水线治理索引

> 本页由 `tools/governance_index.py` 从仓库登记册生成，只负责稳定寻路，不保存整体任务进度。主线、支线、领票、依赖和阻塞现场读取 Linear；工程 Issue、PR、检查和合并现场读取 GitHub。`CURRENT_STATE.json` 只是带日期的技术兼容／控制快照。

## 去哪里看

| 要看什么 | 入口 | 边界 |
|---|---|---|
| 整体任务、主支线、领票、父子、硬前置、阻塞、并行线 | [Linear 项目](https://linear.app/ccz/project/novel-architecture-e0f2a433c335)，推荐 `$linear-github-task-map` | 必须现场读取，不从仓库静态页复原 |
| 工程施工、PR、检查、合并 | [GitHub](https://github.com/cczz412/novel-architecture) | GitHub 是工程线真值 |
| 上工规矩 | [START_HERE](START_HERE.md) 与 [三边协作约定](COLLAB_GITHUB_LINEAR_SLACK.md) | CZ 最新明确指令仍优先 |
| 版本、路径、候选身份 | [current pointers](current_pointers.json) | 不保存领票、依赖或运行成绩 |
| 技术兼容／控制字段 | [CURRENT_STATE](CURRENT_STATE.json) | 带日期快照，不是全局任务地图 |
| 金标入口 | 正式金标共 6 个入口：X01 第3章 **v1.2**＋五本 v1.3；统一登记 `config/gold/formal_gold_registry.json` | 只认正式登记，不从文件名猜 |
| 模块登记 | 可用 10 个版本／在改 5 个版本／试验 2 个版本；见 [模块状态登记](module_registry.json) | 模块登记不是施工票 |
| 实验路线登记 | 在试 2 条／失败 0 条／退役 3 条／允许重开 0 条；见 [路线状态登记](route_registry.json) | 路线身份不等于当前开工 |

## 当前正式入口

- 默认链：`config/defaults/zbatch_v1.2_full_chain.json`，版本 `v1.2`。
- 旧运行入口：`tools/zbatch.py`，继续保留。
- 新统一薄入口：`tools/novel_pipeline.py`；现役命令原样转发给旧入口，不复制运行逻辑。
- 密钥加载入口：只用 `tools/sensenova_deepseek_key.sh`；共享环境和外部项目加载器已退役。
- 试验专区：`experiments/`；旧试验原件不搬，新试验从这里起。

## 快速入口

- [技术兼容／控制快照](CURRENT_STATE.json)
- [当前版本、路径和候选身份](current_pointers.json)
- [实验路线状态](route_registry.json)
- [正式金标](indexes/gold_current.md)
- [银标候选](indexes/silver_candidates.md)
- [运行与回包](indexes/runs_and_reports.md)
- [材料与参考](indexes/source_registry.md)
- [旧路牌健康检查](indexes/route_health.md)
- [模块依赖图](dependency_map.json)
- [合同说明](contracts/README.md)
- [试验专区](../experiments/INDEX.md)

来源：Codex
