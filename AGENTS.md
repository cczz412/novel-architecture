# 小说架构仓库 · Agent 极薄入口（候选）

## 1. Repository entry / authority

- 人看全仓治理状态：[治理索引](governance/INDEX.md)；机器读取当前执行状态只认 [`governance/CURRENT_STATE.json`](governance/CURRENT_STATE.json)。CZ 拍板仍以当前明确指令和 Notion 账序／队列为准。
- 新窗口接力先看 [`governance/progress/current-progress.md`](governance/progress/current-progress.md)，再读它点名的专题页。它只负责接力，不能覆盖 `CURRENT_STATE.json`、正式结果票或 CZ 指令；两者时间或结论冲突时停下校准。
- 产品共同理解从 [共同背景板 R13 入口](references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/00_READ_ME_FIRST.md) 开始。它不是执行票、训练许可、当前状态或生产默认；简单机械任务直接走下表，不通读整包。
- 外部论文、官方文档、行业材料和作者经验的可复用结论从[外部报告知识库当前入口](references/external-knowledge-base/README.md)开始。它与产品共同背景板分开，只提供证据、反例和待核缺口。
- 路径职责与新文件落点只认 [`governance/directory_registry.json`](governance/directory_registry.json) 和生成的 [`governance/indexes/new_file_routing.md`](governance/indexes/new_file_routing.md)。

## 2. Task routing

| 你要做什么 | 第一站 | 需要时的第二站 |
|---|---|---|
| 理解产品目标 | `references/shared-context/.../01_PRODUCT_NORTH_STAR.md` | `02_SYSTEM_ARCHITECTURE_AND_TRUTH_LAYERS.md` |
| 理解创作／记忆流程 | `references/shared-context/.../03_CREATION_AND_MEMORY_PIPELINES.md` | 无 |
| 看当前微调实验 | `finetuning/CURRENT.json` | 它指向实验的 `MANIFEST.json`／结果票 |
| 判断能否训练 | `finetuning/CURRENT.json` 的授权字段 | 当前实验的路线图／执行锁；没有明确许可就是不能训练 |
| 查抽取研究 | `governance/route_registry.json` | 对应实验结果票；产品解释再看 R04 第 04 页 |
| 查已验证的工程结论、技术选型或管线骨架 | `references/engineering-ledger/00_READ_ME_FIRST.md` | 按账内指针回正式结果票／冻结合同核对；当前执行状态仍看 `governance/CURRENT_STATE.json` |
| 查已吸收的外部证据、行业经验、冲突或研究缺口 | `references/external-knowledge-base/README.md` | 按主题页的 claim ID 追 `02_CLAIM_LEDGER.jsonl`、来源登记和原报告；不能替产品拍板 |
| 查历史外部调查，避免同类问题重做 | `references/survey-inbox/INDEX.md` | 对应 `SI-*` 卡和 `packages/.../00_READ_ME_FIRST.md`；历史报告只作证据与候选先验，不产生执行权 |
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

## 4. Minimum-sufficient execution

- 广泛读取前，先估计能安全完成任务的最小文件范围、依赖范围和验证范围。
- 初始范围只分三档：`LOCAL` 只碰明确目标；`COUPLED` 纳入直接机械依赖；`REPO_WIDE` 只用于用户明确要求、公共架构／协议迁移或局部证据证明必须扩大。拿不准时先做廉价探针，不直接选全仓。
- 明确的局部任务从局部开始；默认不做全仓扫描，也不跑全套测试。
- 相关时先廉价检查直接耦合：登记身份、派生视图、manifest 和已知直接消费者。
- 按最小可靠路径执行；验证依次为 `V0` 精确／语法／解析、`V1` 定向测试、`V2` 依赖／身份闭包、`V3` 全套检查，前一级足够就不升级，合同明确要求除外。
- 只有出现具体触发才扩大：目标不唯一、缺依赖、发现直接消费者、登记身份或派生视图耦合、定向验证失败、身份不匹配、Schema／协议受影响，或用户明确要求全仓范围。
- 改动行数不决定复杂度；一行修改发现机械身份闭包时，也要一次纳入那组最小派生文件。
- 不因材料可用就读取无关历史或共同背景，也不以“更放心”为由追加更广测试。

## 4b. 治理强度三档（错误代价决定流程重量）

流程重量跟着**错误的代价**走，不跟着任务名字走。开工先定档；拿不准问 CZ，不默认升重档。

| 档 | 什么任务 | 允许的流程 |
|---|---|---|
| 轻 | 个人 Skill、工具脚本、草稿、TEMP／work 内可逆施工（文件可回退、不碰真实数据、不花额度） | 做完自测一遍就交付启用。**禁止**：独立复审、冻结 SHA、退修票、staging 隔离、多轮新鲜复审 |
| 中 | 仓库正式件、登记册、progress、合同文本、索引 | 一轮机械自查＋一轮复核，过了就落盘；不开第二路复审 |
| 重 | API 调用、训练、金标／Gold、盲审与密封数据、权限系统、生产晋升、删除外置对象 | 维持全套：执行票、独立复审、冻结 SHA、失败留档，一分不减 |

- 轻档任务要的是**结果**，不是可复用制度；测试完就会扔的东西不配基础设施。
- 停损规则：同一对象连续两轮复审仍在发现新问题时，先停下问「它值得第三轮吗」，默认答案是否；要开第三轮必须先向 CZ 说明代价。
- 反例锚点（校准用）：给个人窗口板 Skill 加防篡改哈希链＝轻档活干成重档，错；试选器三轮独立复审＝碰真实密封数据的重档应得，对。
- 测试文件只有三种合法身份：①登记在 `governance/test_policy.json`／`tests/` 注册表的长期件；②实验包内被该实验 MANIFEST 收录的冻结证据件；③其余全是过渡脚本，只能放 TEMP／work，任务收线时随手删掉。给一次性验证写的 `test_*.py` 用完即弃，不留"以后可能有用"的尸体。
- 新建或修改 Skill 时，描述里必须同时写清「什么时候用」和「什么时候不用」；触发含糊的 Skill 按坏件处理，谁发现谁修描述。

来源：CZ 2026-08-13 拍板，根治过度治理

## 5. Environment / commands

本仓普通 Python、测试和 Ruff 固定走锁定环境，Python 为 3.12.12：

```bash
uv run --locked python ...
uv run --locked pytest ...
uv run --locked ruff check ...
```

不要把裸 `python3`、`pytest`、`ruff` 当默认入口，也不要向系统 Python 临时补依赖。

## 6. Nested AGENTS precedence

- 进入子目录时，离目标文件最近的 `AGENTS.md` 优先；根规则只补它没说的部分。
- 当前正式 Git 只发现根 `AGENTS.md`，没有 tracked nested AGENTS。复杂领域已有 README／CURRENT 就先复用，不因规则多自动新建下级 AGENTS。

来源：Codex
