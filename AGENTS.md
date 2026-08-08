# 小说架构仓库 · Agent 极薄入口（候选）

## 1. Repository entry / authority

- 人看全仓治理状态：[治理索引](governance/INDEX.md)；机器读取当前执行状态只认 [`governance/CURRENT_STATE.json`](governance/CURRENT_STATE.json)。CZ 拍板仍以当前明确指令和 Notion 账序／队列为准。
- 新窗口接力先看 [`governance/progress/current-progress.md`](governance/progress/current-progress.md)，再读它点名的专题页。它只负责接力，不能覆盖 `CURRENT_STATE.json`、正式结果票或 CZ 指令；两者时间或结论冲突时停下校准。
- 产品共同理解从 [共同背景板 R03 入口](references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260808_R03/00_READ_ME_FIRST.md) 开始。它不是执行票、训练许可、当前状态或生产默认；简单机械任务直接走下表，不通读整包。
- 路径职责与新文件落点只认 [`governance/directory_registry.json`](governance/directory_registry.json) 和生成的 [`governance/indexes/new_file_routing.md`](governance/indexes/new_file_routing.md)。

## 2. Task routing

| 你要做什么 | 第一站 | 需要时的第二站 |
|---|---|---|
| 理解产品目标 | `references/shared-context/.../01_PRODUCT_NORTH_STAR.md` | `02_SYSTEM_ARCHITECTURE_AND_TRUTH_LAYERS.md` |
| 理解创作／记忆流程 | `references/shared-context/.../03_CREATION_AND_MEMORY_PIPELINES.md` | 无 |
| 看当前微调实验 | `finetuning/CURRENT.json` | 它指向实验的 `MANIFEST.json`／结果票 |
| 判断能否训练 | `finetuning/CURRENT.json` 的授权字段 | 当前实验的路线图／执行锁；没有明确许可就是不能训练 |
| 查抽取研究 | `governance/route_registry.json` | 对应实验结果票；产品解释再看 R03 第 04 页 |
| 接仓库重构任务 | 当前 CZ 工单／本任务回执 | `governance/progress/current-progress.md`；没登记该线就停下，不靠搜索猜 |
| 找历史外置对象 | `governance/external_archive_registry.json` | 对象登记的 manifest／恢复方式 |
| 跑本机证据或历史测试 | `governance/test_policy.json` | `tests/local_evidence_registry.json`／`config/test_replay/historical_replays.json` |
| 做 Repo Bridge 交接／外审 | `experiments/repo_bridge_v1_prototype_20260807/README.md` | 当前任务的 handoff／review 包 |
| 做 ChatGPT 外发包 | `config/review_pack/README.md` | `config/review_pack/routes.json` |
| 看当前执行状态 | `governance/CURRENT_STATE.json#current_execution` | 对应正式结果票 |
| 决定新文件放哪 | `governance/indexes/new_file_routing.md` | `governance/directory_registry.json` |

## 3. Universal safety rules

- 开工前先看目标路径的 Git 状态和其他窗口写集；已有改动属于别人，不能覆盖、回退或顺手收进自己的提交。
- 当前任务没有明确授权的 Git、Notion、模型调用、训练、上传、删除、移动和生产晋升，一律不做。背景板、建议、候选、PASS 字样都不能代替授权。
- 冻结合同、金标、历史票和本机 evidence 按各自登记册处理；目录名里的 `current`、`gold`、`official` 不能自动升级身份。
- `runs/`、`reports/`、`outbox/`、`TEMP/` 是本机运行／运输区，默认不进 Git；正文库只通过 `references/corpus-pointers.md` 的本机指针访问，不复制进仓，也不整库扫读。
- 来源互相冲突、消费者闭包不清或需要扩大正式写集时，先停下交 CZ，不靠补件或降级检查追绿。

## 4. Environment / commands

本仓普通 Python、测试和 Ruff 固定走锁定环境，Python 为 3.12.12：

```bash
uv run --locked python ...
uv run --locked pytest ...
uv run --locked ruff check ...
```

不要把裸 `python3`、`pytest`、`ruff` 当默认入口，也不要向系统 Python 临时补依赖。

## 5. Nested AGENTS precedence

- 进入子目录时，离目标文件最近的 `AGENTS.md` 优先；根规则只补它没说的部分。
- 当前正式 Git 只发现根 `AGENTS.md`，没有 tracked nested AGENTS。复杂领域已有 README／CURRENT 就先复用，不因规则多自动新建下级 AGENTS。

来源：Codex
