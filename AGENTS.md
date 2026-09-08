# 小说架构仓库 · Agent 极薄入口

## 0. 先认清内容归属

- 长期决定与内容分工：[Notion 分工决定 R2](https://app.notion.com/p/3d45cadc4d0f8115b10cc1fb4ba7786f)。
- 工程交接与 Slack 规则：[COLLAB 协作流程](governance/COLLAB_GITHUB_LINEAR_SLACK.md)。
- 未迁项按[逐项主存登记](https://app.notion.com/p/3d45cadc4d0f81c9aa9dcd6bdd4cce3c)回原主存；具体任务按下文路由，工程能力仍回 GitHub `main` 核对。

## 1. Repository entry / authority

- 上工先读 [`governance/START_HERE.md`](governance/START_HERE.md)。工程真源是 GitHub；活动任务看 [Linear 总入口](https://linear.app/ccz/document/4ddff334d4f0)；长期决定、原话和产品说明／规格看 [Notion 决定与规格入口](https://app.notion.com/p/9ee897f5b8e54320a8aeb1f98569f133)及逐项主存登记。短通知进 Slack `#施工`，批复／阶段门进 `#主控聊天`。细则见[协作约定](governance/COLLAB_GITHUB_LINEAR_SLACK.md)。
- 仓库[治理索引](governance/INDEX.md)只负责稳定寻路。查负责人、交付、父子、硬前置、验收、状态和未决问题，现场读取 Linear 总入口所路由的相关 Project 与活动票；查 Issue、PR、检查和合并，现场读取 [GitHub](https://github.com/cczz412/novel-architecture)。不另建总看板，不只搜索旧总 Project。
- 迁移按项确认：本轮范围是门1、置信度、后端优先三项已核对决定，具体主存与版本查 Notion 迁移登记；未迁内容仍以原 Linear 文档为主存，Notion 只登记指路。登记不等于迁入，不能宣称全库已迁。原始记录和历史保留，读 Notion 不产生施工授权。
- [`governance/CURRENT_STATE.json`](governance/CURRENT_STATE.json) 是带日期的技术兼容／控制快照，供现有工具读取旧机器字段；它不是全局任务地图，不能据此判断当前谁在做、哪些票被领、最新阻塞或下一张票。
- 当前版本、路径和候选身份只认 [`governance/current_pointers.json`](governance/current_pointers.json)；它不保存全局任务进度、运行成绩或领票状态，也不替产品或领域 CURRENT 拍板。
- 新需求和未决问题进入 Linear 所属任务；已核对且可长期复用的决定进入 Notion，任务保留短背景和采用版本链接。完整内容只留一个主存，不要求每项任务在三处各建一份。
- 工程能力只认 GitHub 当前 `main` 上的正式合同、Schema、登记册、测试和已合并代码。Notion 只索引工程合同，不改写合同，也不证明能力已落地。
- 外部论文、官方文档、行业材料和作者经验先保留来源与 SHA；可复用证据登记到 [CCZ-64](https://linear.app/ccz/issue/CCZ-64)，是否吸收回所属模块票。外部材料不能替 CZ 拍板，也不能直接变成产品合同。
- 路径职责与新文件落点只认 [`governance/directory_registry.json`](governance/directory_registry.json) 和生成的 [`governance/indexes/new_file_routing.md`](governance/indexes/new_file_routing.md)。

## 2. Task routing

| 你要做什么 | 第一站 | 需要时的第二站 |
|---|---|---|
| 理解产品目标或模块边界 | [Notion 决定与规格入口](https://app.notion.com/p/9ee897f5b8e54320a8aeb1f98569f133)与逐项主存登记 | 已落地能力再核 GitHub 正式合同与 `main`；新需求先登记 [CCZ-128](https://linear.app/ccz/issue/CCZ-128) |
| 查当前版本、路径和候选分支 | `governance/current_pointers.json` | 技术兼容快照才看 `governance/CURRENT_STATE.json`；任务进度不从仓库读取 |
| 理解创作／记忆流程 | Notion 已核对规格；未迁项回登记指向的 Linear 主存 | 再核 GitHub 已落合同；不要从历史设计反推当前产品 |
| 看产品试跑示例（代码偏旧，不是现行产品） | `novel-mvp/README.md` | `novel-mvp/design/INDEX.md` |
| 看微调结论 | [finetuning/README.md](finetuning/README.md) | 正线已放弃；CURRENT 只是空落点 |
| 判断能否训练 | `finetuning/CURRENT.json` 的授权字段 | 没有明确许可就是不能训练；正线已关 |
| 查抽取研究 | `governance/route_registry.json` | 对应实验结果票；产品解释再看 R04 第 04 页 |
| 查已验证的工程结论、技术选型或管线骨架 | `references/engineering-ledger/00_READ_ME_FIRST.md` | 按账内指针回正式结果票／冻结合同核对；当前任务状态仍现场读取 Linear／GitHub |
| 查外部证据、行业经验、冲突或研究缺口 | [CCZ-64](https://linear.app/ccz/issue/CCZ-64) 冻结证据登记 | 需要原文时再按 [survey-inbox](references/survey-inbox/README.md) 的来源卡追原报告；吸收决定回模块票 |
| 拿不准账本／工具／执行包／权限，或抽取／评测／记忆、需求／产品形态、日常循环／插件／画布／平台／人格标签、规划账／保存对照交棒／状态轴、局部复核／反馈外发／切片验收会不会做歪 | [情景问答](references/agent-playbook/README.md) | [卡片目录](references/agent-playbook/INDEX.md)。只打开对得上的一张；再回它标出的现行 Linear 票或 GitHub 合同核对 |
| 查模块长期需求、测试配方或评分维度 | Notion 主存登记；未迁项回原 Linear 文档 | 任务归属可从 [CCZ-128](https://linear.app/ccz/issue/CCZ-128)／[CCZ-83](https://linear.app/ccz/issue/CCZ-83) 追；工程方案、合同、Schema 和测试回 GitHub |
| 查历史外部调查，避免同类问题重做 | `references/survey-inbox/INDEX.md` | 先对情景问答；仍要对原文时才打开对应 `SI-*` 卡和那一份消化稿。历史报告只作证据与候选先验，不产生执行权 |
| 接仓库重构任务 | 当前 GitHub 施工 Issue | 回 Linear 核对父子、硬前置、领票和停点；没有明确票与授权就停下 |
| 找历史外置对象 | `governance/external_archive_registry.json` | 对象登记的 manifest／恢复方式 |
| 跑本机证据或历史测试 | `governance/test_policy.json` | `tests/local_evidence_registry.json`／`config/test_replay/historical_replays.json` |
| 做 Repo Bridge 交接／外审 | `experiments/repo_bridge_v1_prototype_20260807/README.md` | 当前任务的 handoff／review 包 |
| 做 ChatGPT 外发包 | `config/review_pack/README.md` | `config/review_pack/routes.json` |
| Cursor 窗口 Skill（团队／便宜助手／探路／外发） | `.cursor/skills/` | 外发打包仍回 `config/review_pack/README.md` |
| 查当前产品口径 | [Notion 决定与规格入口](https://app.notion.com/p/9ee897f5b8e54320a8aeb1f98569f133)及逐项主存登记 | 未迁项回原 Linear 文档；工程支持程度再核 GitHub `main` |
| 查原话或长期决定 | [Notion 决定与规格入口](https://app.notion.com/p/9ee897f5b8e54320a8aeb1f98569f133) | 核对适用范围、采用凭据与版本；历史原话不自动成为现行决定 |
| 查四台和插件频道 | [`governance/START_HERE.md`](governance/START_HERE.md) | [协作约定](governance/COLLAB_GITHUB_LINEAR_SLACK.md) |
| 看整体任务进度 | 现场读取 Linear | 再现场读取 GitHub Issue／PR／合并；不从仓库静态页猜 |
| 决定新文件放哪 | `governance/indexes/new_file_routing.md` | `governance/directory_registry.json` |

情景问答：**什么时候用**＝施工时怕账本／工具／执行包／权限，或抽取／评测／记忆、需求／产品形态、规划账／状态轴、局部复核／反馈外发做歪，先打开一张对得上的卡。**什么时候不用**＝当执行票、训练许可、已拍清单，或代替现行模块票与正式合同；也不许拿它当理由通读 `survey-inbox/packages/` 或把 `work/` 当知识库。

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
| 中 | 仓库正式件、登记册、治理入口、合同文本、索引 | 一轮机械自查＋一轮复核，过了就落盘；不开第二路复审 |
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
