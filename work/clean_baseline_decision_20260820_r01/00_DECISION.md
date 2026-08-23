# 干净基线重构 · 决策书 R01（2026-08-20）

给 CZ：你让我决定「仓库重构怎么做」。这页就是决定本身；每一步怎么施工，见同目录 [01_WORK_ORDERS.md](01_WORK_ORDERS.md)。

- 本件身份：work 区施工方案稿。归位条件：CZ 过目后按工单执行；每张工单落地时把对应内容转进正式件，全部做完本目录整体归档退役。
- 依据：ChatGPT Pro 总审包 `NOVEL_ARCH_CLEAN_BASELINE_AND_TRACEABILITY_REVIEW_20260820_R01.zip`（SHA256 `d357f41e0f978bdea8581bf8374a9074baed417c3b632cb01996344f5343047c`，两次上传件哈希一致）＋ 我在 Git 上的独立复核。Pro 的判词我逐条对过仓库实况；采纳的、改判的、留给你拍的，下面都分开写。
- 三份后续工单要用的机器种子：追踪表／需求 schema 已迁到 [capability_traceability_sources_r01/](../../governance/capability_traceability_sources_r01/)，来历见那边的 [PROVENANCE.md](../../governance/capability_traceability_sources_r01/PROVENANCE.md)；归档候选仍在 [pro_review_seed/15_ARCHIVE_CANDIDATES.json](pro_review_seed/15_ARCHIVE_CANDIDATES.json)。

## 总决定（一句话）

**不先删东西，先钉「现行」。** 顺序固定为：收口唯一 current → 把 R14＋R03＋追踪表送上 main → 模块分支拆小合并 → 最后才瘦身归档。做完之后，Cursor 云、Codex 云、ChatGPT 打开 GitHub main 看到的是同一套现行真相。

为什么是这个顺序——现在最大的病不是文件多，是「哪个是现行」有好几个答案，我在 Git 上逐一验过：

- 机器真源 [`governance/CURRENT_STATE.json`](../../governance/CURRENT_STATE.json) 还停在 2026-08-08 的仓库卫生任务，而且一个文件里塞了一千多行 Z80／Z83 历史运行流水；
- 根 [`current.md`](../../current.md) 第一行自己声明停更，正文冻在 7 月 20 日，但文件名还像现行入口；
- main 的 [`AGENTS.md`](../../AGENTS.md) 指背景板 R13，模块分支的 AGENTS 已指 R14——两套产品理解并存；
- [`governance/progress/current-progress.md`](../../governance/progress/current-progress.md) 写分支 tip 是 `288f4fd`，远端实际已到 `cc793c4`——手写指针天然追不上；
- 背景板 R03～R13 共 12 个历史版本全躺在现役树里，原子需求 main 停在 R02、分支已到 R03。

先删文件治不了这个病，反而可能删坏还被引用的东西。先钉现行，删起来才安全。

## 八个决定

### 决定 1｜重构基线放 main；模块分支冻结为「待拆料场」

- 模块分支 `codex/module-runtime-foundation-20260819-r01` 方向没歪（Pro 与我复核一致），但它已经领先 39 个提交、落后 1 个提交，而且改动里约一半是外审证据（`references/cloud-supervision` 97 件＋`references/survey-inbox` 40 件），一半才是产品（`novel-mvp/mvp` 90 件＋测试）。**不整包合并。**
- 分支冻结在 `cc793c4`，只作拆料来源；新工作不再往这根分支堆，一律从新 main 开小分支。
- main 上你 8/21 凌晨提交的 Codex 外审标准包（`f868090`）分支还没含，拆分前必须先 rebase。

### 决定 2｜current 只留一个全仓的，不拆两个（替你拍板 Pro 留的问题①）

Pro 把「CURRENT_STATE 拆不拆成 repository／product 两份」留给你。我拍：**不拆**。理由：两个全局 current 就是在重新制造「多个现行」这个病。做法：

- [`governance/CURRENT_STATE.json`](../../governance/CURRENT_STATE.json) 保持全仓唯一机器 current，但瘦身：一千多行历史运行流水搬到同目录 `CURRENT_STATE_HISTORY.json`（单文件，不新建目录），当前执行刷新为 M1～M11 产品主线；
- 各域保留自己的域 CURRENT（`finetuning/CURRENT.json` 已有，原子需求已有，背景板补齐），和全仓 current 是上下级，不是竞争者；
- 新增一个很小的 `governance/current_pointers.json`：一处列全所有长期件的现行版本（背景板哪版、原子需求哪版、设计登记哪版、追踪表哪版）。任何升版只改这一处＋自己目录。

### 决定 3｜三件长期件不合并，用「一张指针表＋改判台账」锁同步（治「改了这边忘了那边」）

背景板、报告知识库、原子需求三件**不合并**——职责本来不同：背景板管产品语义，知识库管外部证据，原子需求管可验收预期。脱节的根子是升版互相不知会，所以上两道机械锁：

1. **改判先记账**：任何产品改判先落 ADD 台账条目（复用现行 ADD-xxx 惯例，不发明新制度），条目里必须写「下游要跟改哪几件」（背景板？需求？设计？合同？），跟改完成才能销账；
2. **脚本核对**：`tools/check_current_freshness.py` 核对 `current_pointers.json` 与各件自述版本一致；某件升版而下游没表态（跟改或显式声明不受影响），检查直接报错。

### 决定 4｜需求层：142 个 ID 一个不动，补五个轴（不再继续拆细）

- 现在 142 条（78 核心／64 附加／83 硬门）不是不够细，是缺分类和追踪。**停止拆细。**
- 给每条补五个轴：用户旅程位置、能力 owner、能力类型、真值写入级别、验收成熟度。owner 允许写共享服务（工作区／存储／路由／安全），不硬塞进 M1～M11。
- Pro 已把 142/142 的候选追踪表做完（种子见 [08_CAPABILITY_TRACEABILITY.json](../../governance/capability_traceability_sources_r01/08_CAPABILITY_TRACEABILITY.json)），以**候选**身份落进 `governance/capability_traceability.json`，owner 等推断字段逐条复核后才转正式。⚠️ 142/142 mapped 是「追踪关系建好了」，不是「都实现了」。
- 缺口按序补：15 条新需求先定优先级（见「必须你拍的」第 4 条），再补 90 个六例测试设计；`M3-B03` 缺来源，补上前该条挂显式豁免。

### 决定 5｜设计稿：不集中重写，谁开工谁先补

- [`novel-mvp/design/INDEX.md`](../../novel-mvp/design/INDEX.md) 已经人工标了哪些稿等待改版，缺的是机器可读。落一个 `novel-mvp/design/design_registry.json`：每份稿 CURRENT／WAITING_REWRITE／HISTORICAL／superseded_by，默认路由只指 CURRENT。
- 立一条**就近重写规则**：哪个模块要开工，先把它的设计稿升到 R14 口径，才准动代码。不为了整齐一次性重写全部旧稿——那是把轻活干成重活。

### 决定 6｜加功能走固定小门（治「临时想加点东西就全链路返工」）

以后任何新想法，固定走这一条：

```text
想法 → 在原子需求表加一条（挂旅程位置、owner、真值级别、来源）
     → 追踪表自动告诉你要动哪些设计／合同／模块／测试
     → 才开工
```

- 配套规矩：模块代码不允许出现找不到需求来源的产品行为（`implementation_trace` 检查先 WARNING，分支拆分合并完成后升 ERROR）；
- 反过来不逼进度：需求条目允许长期停在 REQUIREMENT_ONLY，登记了不等于马上要做。
- 这样「临时想加一点」的成本从「补需求＋改管线设计＋重写背景」降为「加一行需求＋挂 owner」，剩下照表施工。

### 决定 7｜瘦身归档的范围（只退出视野，不消灭历史；每条你都可以否）

main 现在 3018 个 tracked 文件，处置如下，全部走 [`governance/external_archive_registry.json`](../../governance/external_archive_registry.json) 登记＋SHA＋恢复演练，禁止改写 Git 历史：

| 对象 | 规模 | 处置 |
|---|---|---|
| `finetuning/` 批量结果 | 1206 件（全仓 40%，最大瘦身项） | 域 CURRENT＋人类接力页留仓，批量结果外置 |
| 模块分支里的 cloud-supervision TEMP 证据镜像 | 约 97 件 | 冻结打包外置，仓里留 index＋SHA，不随 runtime 合并 |
| survey 顾问回包原件 | 约 40 件 | 外置，留 admission 卡＋已吸收结论 |
| `foundation/`（7 月快照） | 33 件 | 外置，留指针卡 |
| 背景板 R03～R13、原子需求 R01/R02 | 12＋2 个版本目录 | **留 Git**（版本链要连续可查），只退出默认路由 |
| 根 `current.md` | 1 件 | 改成一屏 stub 指向 governance，全文移 `history/` |
| `config/batches/` 根下 Z00* 历史批次 | 若干 | 收进已有 active/archive 指针后面 |

真正的产品核心——R14、R03、合同、工程账、知识库 digest、现役测试——**一件不出 main**。这满足你说的「不要少太多内容，核心要用的都得在」。

### 决定 8｜云端协同：GitHub main 是所有 AI 的唯一共同入口

- 不建第二套「AI 基线」目录。Pro 提议的 00_AI_START_HERE 等 8 件薄路由，改成复用现有件：[`AGENTS.md`](../../AGENTS.md) 就是 START_HERE，`current_pointers.json` 就是指针表，仓库地图由 AGENTS 路由表承担（Pro 自己也写了「优先复用现有对象」）。
- 本地只保留不能上 GitHub 的：正文库、真实小说材料、金标、密钥、Notion 原始拍板。其余产品语义材料一律以 GitHub main 为准——本地窗口不再因为「多读过几百份报告」而得出不同产品结论。
- 视角对齐的最小补齐（来自 Pro 的 parity 缺口，我核准）：修机器 current（工单 1）；5 条引用了未分发本地旅程材料的需求，压成可公开的最小证据卡进仓（不上传真实材料）；`M3-B03` 补来源；以后每次外审一律封四元组「branch＋commit＋source release＋test baseline」。

## 必须你亲自拍的 5 件（产品语义，我不能代拍；括号里是我的推荐）

1. **章事实稿确认粒度**：交棒后逐条确认／整包确认／分级？（推荐：低影响批量确认＋高影响单条签字。这条不拍，分支拆分里的章事实稿竖切 PR 不能合。）
2. **M8／M10／M11 的 owner 三问**：selection card 谁保存、时间区间数据谁产、recall handle 的权限归谁？（倾向：M8 拥有规划卡、写 planstore 走共享存储；M10 的时间区间由章事实稿链产出、M10 只做投影；handle 存在性归 M11、权限归共享安全层。只是倾向，请拍。）
3. **`M3-B03` 的来源**：fact_core＋qualifiers 这条要么在 R14 找到对应段落，要么你亲自补一条 ADD 拍板作来源。
4. **15 条新需求的优先级**：（默认建议：与主线阻断直接相关的——交棒、M8 写回、M10 时间状态、M11 handle、十本账——先定核心并优先补六例，其余定附加。）
5. **R14 的 Notion 镜像**：建不建、谁维护？（建议：建。Notion 是你拍板层的真源，每次升版由做升版的窗口同步并回读，GitHub 只记镜像指针。）

## 和 Pro 建议不一样的三处（防止两边打架）

1. current 拆不拆：Pro 留给你，我拍了**不拆**（决定 2）。
2. AI 基线八件套：Pro 给了新目录方案，我改成**复用 AGENTS＋指针表**，不建第二套（决定 8）。
3. 归档范围：Pro 只列候选和前置检查，我给了**逐条处置**（决定 7），你逐条可否。

来源：Cursor 云端 Agent，2026-08-20；依据 Pro 总审 R01 与 Git 实况独立复核
