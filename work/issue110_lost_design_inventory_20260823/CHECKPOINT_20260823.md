# #110 续跑备忘｜2026-08-23 21:32

给下一窗／网络差时接着用。只登记，不改 contracts，不关票，不登对照表终稿。

团队 W1 六子被中断，**没有团队结论**。下面都是主会话已经核对过的底料。

---

## 接着从哪读

1. 本文件（先看「报告背景板已摘」和「对照表 v0.1」）
2. [CANDIDATE_LIST.md](CANDIDATE_LIST.md)（39 条）
3. [00_READ_ME.md](00_READ_ME.md)
4. 合同目录：`novel-mvp/contracts/`
5. 报告背景板入口：[references/external-knowledge-base/README.md](../../references/external-knowledge-base/README.md)

下一手建议（少派人）：只读 SI-010 消化稿 + 技法页，把漏项补进对照表备注，**不要**再一次派 6 个子 agent。

---

## 三份底料对齐

| 件 | 路径 | SHA／状态 |
|---|---|---|
| PR | https://github.com/cczz412/novel-architecture/pull/112 | OPEN，未合主干 |
| 分支 HEAD | `cursor/issue-110-lost-design-inventory` | `56d90040ee3175f52655e9f1e6f0670c31ced571`（含 Notion 已销） |
| 登记评论第一帖 | 候选清单首次进仓 | `7485821261d60aac51afad698810be953a620e6c` |
| 候选清单／工作页 | 本目录两页 | 工作区已在该分支，与 HEAD 一致 |
| 现行合同 | `novel-mvp/contracts/` | 34 个 `.md` |

人物账抽查（对照表自称对过全文）：[CHARACTER_LEDGER_CONTENT.md](../../novel-mvp/contracts/CHARACTER_LEDGER_CONTENT.md)

- 七字段：正名／别名／角色标签／背景卡／可见性／命运指针；**无** `predicament`／`pursuit`
- `state_timeline[]`：`state_key` 可为 `injury:left_arm`、`location`、`alive`（约 L53–64）
- `relationships[]` 只有 `kind` + 时间区间（约 L69–79）
- 约 L81：**拒绝** `knowledge_edges`

C7 抽查：[C7_PLOT_LAYER.md](../../novel-mvp/contracts/C7_PLOT_LAYER.md)

- `purpose`＝作者出题目的，不是人物渴望／达成态

Notion 原页：CZ 2026-08-23 拍**不搜**（旧废案＋防污染）。跟「报告背景板」不是同一堆东西。

---

## 对照表 v0.1（对话里的稿，未登票）

口径：✅ 有落位／🟡 半落位／❌ 悬空。声称真正接住 3、半接住 5、悬空 8。悬空都能在旧设计找到真身。

| # | 评分点 | 状态 | 旧设计条号（候选清单） |
|---|---|---|---|
| 1 | 受伤 | ✅ | —（现行 `state_timeline`） |
| 2 | 在什么地点 | ✅ | — |
| 3 | 伏笔埋／兑 | ✅ | 条21（NVM hook 三义要拆） |
| 4 | 人物状态（章末快照） | 🟡 | 条15、16、19 |
| 5 | 人物关系怎么变 | 🟡 | 条17、28 |
| 6 | 故事线有没有推进 | 🟡 | 条33 |
| 7 | 因果链 | 🟡 | 条10–14（合同只有 D） |
| 8 | 读者承诺／期待债 | 🟡 | 条23（近亲 `must_carry`） |
| 9 | 每个人有什么困境 | ❌ | 条1–4 |
| 10 | 有什么目的（渴望） | ❌ | 条20（2026-08-22 落合同时掉） |
| 11 | 达没达成 | ❌ | 条21、22 |
| 12 | 有没有秘密被揭露 | ❌ | 条5–8；合同拒绝知情边 |
| 13 | 有没有视角差 | ❌ | 条9、32 |
| 14 | 目的达成后新渴望 | ❌ | 条20 |
| 15 | 性格／心理标签在抉择时起没起作用 | ❌ | 条36 |
| 16 | 爽点／钩子／情绪窝心 | ❌ | 条24–27 |

三个坑（原表自带，尚未本地补证完）：

1. 第 12 行制度打架：`decisions.md` D-COORD-001 vs 人物合同禁止知情边。**待对 commit。**
2. 悬空 ≠ 文件被删。常见丢法＝2026-08-22 十本账草案收成七字段。
3. 金标 9–16 格现在填了也没账可对，不能假装自动判分。

团队未审这张表。主会话未推翻 3／5／8，也未替 CZ 拍「9–16 哪些补落位」。

---

## 报告背景板有没有用？

**有用，但跟候选清单不是同一层。**

- 候选清单／设计稿／合同：回答「我们当初设计过什么、现行台账收没收」
- 报告背景板：回答「外面证据怎么拆对象、评测时别把词混成一个机器标签」
- 不能把背景板建议写成产品决定（CURRENT.json：`EXTERNAL_REFERENCE_ONLY_NO_PRODUCT_OR_EXECUTION_AUTHORITY`）
- 不是 Notion NVM 废页；CZ 已拍不搜的是 Notion 原页，不是这套已编译背景板

入口：

- [README.md](../../references/external-knowledge-base/README.md)
- 当前包 R01：`references/external-knowledge-base/EXTERNAL_KNOWLEDGE_BASE_20260815_R01/`
- 人读技法页：[02_CRAFT_AND_READER_EXPERIENCE.md](../../references/external-knowledge-base/EXTERNAL_KNOWLEDGE_BASE_20260815_R01/background/02_CRAFT_AND_READER_EXPERIENCE.md)
- 人读评测页：[05_EXTRACTION_EVALUATION_AND_EVIDENCE.md](../../references/external-knowledge-base/EXTERNAL_KNOWLEDGE_BASE_20260815_R01/background/05_EXTRACTION_EVALUATION_AND_EVIDENCE.md)
- 冲突图：[04_CONFLICT_AND_SUPERSESSION_MAP.md](../../references/external-knowledge-base/EXTERNAL_KNOWLEDGE_BASE_20260815_R01/04_CONFLICT_AND_SUPERSESSION_MAP.md)
- 原始 30 报告：[SI-015](../../references/survey-inbox/items/SI-015_external_knowledge_research_returns.md)

### 已摘、能直接帮对照表的结论

| 对照表行 | 背景板说了什么 | 编号 | 怎么用 |
|---|---|---|---|
| 3 伏笔、8 读者承诺、16 钩子／爽点 | 钩子、悬念、伏笔、期待、作者—读者承诺要拆开；章末留钩 ≠ 提前埋伏笔；悬念偏读者状态，伏笔偏后文要兑现的文本安排 | CLM-DR-CRAFT-02-K01/K02/K03 | 支持表里「条21 三义要拆」；✅ 伏笔三态接住的是伏笔对象，不是爽点／悬念债 |
| 8 | 「读者承诺」现象存在（HE、不换男主、某卷揭密、书名简介标签），但是否单开一等对象仍 U | CLM-DR-CRAFT-02-K04/K05/K12；冲突图仍未裁决 | 支持 🟡：`must_carry` 是近亲不是同一对象；不要把 8 和 3 合成一行 |
| 16 | 能查目标推进、承诺兑现、冲突升级、资源／信息／关系变化；不能把这些直接换算成「爽度」 | CLM-DR-CRAFT-01-K01 | 16 若当自动分，背景板反对；最多软提醒 |
| 16 | 负面情绪 ≠ 质量差；不能写成「本章憋屈、获得感低」 | CLM-DR-CRAFT-01-K02/K18 | 「情绪窝心」不宜当硬对错格 |
| 15 | 人格标签最多软先验；失败结果不能单独证明降智；要看当时知情、目标、能力、情绪、可选行动 | CLM-DR-CRAFT-04-K01/K02/K04 | 金标不该挂爽点，该挂抉择时的知情＋目标；和条36、行12/13 绑在一起 |
| 12、13 | 硬检查只处理可追源事实、知情、时间、约束、明确计划 | 技法页「对产品设计的候选启示」 | 知情／视角差一旦落账，走硬检查；爽点走软提醒 |
| 评测方法 | 正文事件、规划、作者声明、人物知情、跨来源链接、规划兑现、长期入账是不同 Gold 单位；一个大 Prompt 覆盖全部没有证据 | CLM-DR-EVAL-01-U01 | 金标答卷 9–16 不能假装自动判；应对分任务 |
| 民间词 | 爽点、期待、卡文、吃书留作作者语言，后台改成可观察结构 | CLM-DR-CN-01-K04 等；冲突图「民间术语作为机器标签」 | 行16 用词不要直接当字段名 |

冲突图里还点名 SI-010-R005（钩子／伏笔／悬念／承诺合并）→ 被 DR-CRAFT-02 拆开。续跑应读 SI-010 消化稿，不必先啃 30 份原文。

### 调查收件箱里、还没拆进这张表的近亲包

这些是**仓内已编译／已登记**的报告，不是 Notion 废页。网络差时优先读消化稿，不读外链。

| 包 | 卡片 | 和对照表的关系 |
|---|---|---|
| SI-009 大纲／账本承重 | [SI-009](../../references/survey-inbox/items/SI-009_outline_loadbearing_research_returns.md) | 户口、指针、伏笔、知情、未来件分家 |
| SI-010 账本咬合 | [SI-010](../../references/survey-inbox/items/SI-010_ledger_bite_research_returns.md) | 关系边、读者承诺 ADD-044、伏笔；消化稿建议读者承诺 A-lite |
| SI-011 R10.2 补丁审查 | [SI-011](../../references/survey-inbox/items/SI-011_r10_2_patch_design_review.md) | 状态账、义务、交棒（冲突图标 PROJECT_HISTORY_ONLY，不当行业知识） |
| SI-016 规划账合同审查 | [SI-016](../../references/survey-inbox/items/SI-016_plan_contract_review.md) | 交棒、投影、关章；对行6／38／39 |

foundation 里 V06「评测与金标体系调查」仍是待贴骨架，几乎没正文，**先别当证据**。

六本金标 UCR 回包只说明候选银标、不替换现役金标，**不回答台账字段落位**。

---

## 对照表可能还缺的格子（仅线索，未审）

候选清单组7 有、v0.1 16 行没单独成行：

- 条29 离屏实体
- 条30 五档注意力／待唤回
- 条31 状态变化一句话暗稿
- 条34 切线包
- 条35 不可逆
- 条37 铺垫时机五档／剧情大抓手
- 条38 关章清账不清零
- 条39 章节／故事线交接

这些不一定要升成评分点；续跑时标「表外近亲」，别冒充已覆盖。

---

## 第二波已读（2026-08-23 21:40，消化稿不是 30 份原文）

对照表 v0.1 写完时，背景板只读了技法页＋评测页＋冲突图。下面三份**仓内消化稿**这波补上了。仍是候选先验，不能改合同。

### SI-010 账本咬合消化｜对第 5、8 行

路径：[02_RETURNS_DIGEST.md](../../references/survey-inbox/packages/LEDGER_BITE_RESEARCH_RETURNS_20260814_R01/02_RETURNS_DIGEST.md)

- 关系：边带类型；名单是投影；「露过一次」≠ 线成员。对表第 5 行：现行 `relationships[].kind` 连这个形状都没到。
- 当前状态：事件是历史真源，「现在什么样」现算；快照要能删掉重建。对第 4 行：章末快照若做，不能另开第二真值。
- ADD-044 读者承诺：建议 **A-lite**＝极薄创作约束，**不是**故事真值，不要整本并进伏笔。升格门：删掉这条后读者能否拿明确来源说「你答应过」。对第 8 行：比 `must_carry` 更接近「读者承诺」，但仍要 CZ 拍；不要和伏笔三态合成一行。
- 义务 v1 明确不开。对第 11 行：旧设计有义务状态机，外部消化维持「先不开」——和「金标要达成态」不是同一层决定。
- 不覆盖梦境／认知／感知分账。

### SI-009 大纲承重消化｜对第 4、12、11 行

路径：[02_RETURNS_DIGEST.md](../../references/survey-inbox/packages/OUTLINE_LOADBEARING_RESEARCH_RETURNS_20260814_R01/02_RETURNS_DIGEST.md)

- 中改不翻树。缺的是户口＋指针，不是第六层大纲。
- **人物知情硬账：方向早已拍，字段还没锁。** 对第 12 行「合同拒绝知情边」：外面／旧拍是「要硬账」，现行人物合同是「v1 拒绝」。这是制度打架的第二条旁证（第一条是 D-COORD-001）。
- 倒计时／冷却／「现在什么样」不要另开状态表，事件上要能查。对第 4、11 行。
- 伏笔单独成账；**义务 v1 不开**（P5 想单开，大纲 R02 否掉）。
- 反对假扩面：爽点账／弧光账／情绪曲线真值账。对第 16 行：背景板＋SI-009 都反对把爽点做成一等真值。
- P3 读者承诺 vs P10 只准三组硬账：两份打架，要 CZ 拍。和 SI-010 A-lite 是同一未决。

### SI-016 规划账合同审查消化｜对第 6、38、39 行

路径：[02_RETURNS_DIGEST.md](../../references/survey-inbox/packages/PLAN_CONTRACT_REVIEW_RETURNS_20260815_R01/02_RETURNS_DIGEST.md)

- 关章没有字段宿主；`closed` 曾和存储枚举打架；交棒／收工／关章要拆开。对组 7 条 38／39，表 v0.1 没单列。
- 对账不以交棒为前提。对第 6 行「故事线推进」：现行规划账三件套接不住「关章清账」。
- 候选稿能当下一稿底子，**不能**冒充已落合同。消化当时建议关章合同单开。

### 背景板另两页（这波扫过，信息密度低于技法页）

- [04_MEMORY_TRUTH_TIME_AND_RULES.md](../../references/external-knowledge-base/EXTERNAL_KNOWLEDGE_BASE_20260815_R01/background/04_MEMORY_TRUTH_TIME_AND_RULES.md)：current 是带锚投影；时间先后 ≠ 因果；伤势等从变化汇总，不双写 current。对第 1、4、7 行备注有用，不改 3/5/8 切分。
- [03_AUTHOR_WORKFLOW_AND_INPUTS.md](../../references/external-knowledge-base/EXTERNAL_KNOWLEDGE_BASE_20260815_R01/background/03_AUTHOR_WORKFLOW_AND_INPUTS.md)：拆书≠抄正文；对评分格子几乎无新字段。

### 找过、这波没读正文（避免假装齐）

| 件 | 为什么先放下 |
|---|---|
| SI-007 十五份设计审查原文 | 卡片写消化稿在 TEMP，本轮 glob **没找到** `26_THIRD_ROUND*`；原件曾被 checkout 清掉，可能只在 TEMP 残包 |
| SI-008 Agent 工具管线 | 触发器／画布，离评分格子远 |
| SI-002／T5 抽取评测包 | 评测方法已有背景板 05；不新增困境／知情字段 |
| SI-011～014 | 冲突图定为 PROJECT_HISTORY_ONLY；原件已退出 Git |
| 背景板 01／06／07／08 | 生态、UX、合规、知识治理；不解决 9–16 落位 |
| V06 金标调查 | 仍是待贴骨架 |

---

## 这波之后，表上该补的备注（仍不改状态灯，除非 CZ 拍）

1. **第 8 行**应写：近亲不止 `must_carry`；SI-010 有「读者承诺 A-lite」候选，和伏笔、义务都不是同一个对象；P3/P10 打架未拍。
2. **第 12 行**应写：知情硬账在 SI-009 是「已拍方向、字段未锁」；现行合同是拒绝。不是「从来没设计过」。
3. **第 11 行**应写：义务状态机在候选清单里，但 SI-009/010 消化维持 v1 不开——「金标要达成态」≠「义务账要开」。
4. **第 16 行**更硬：SI-009 点名反对爽点／情绪曲线真值账；和技法页一致。
5. **表外近亲升格候选**：关章清账（SI-016）比切线包更像评分流程缺口；知情硬账比「视角差」这个词更接近可落账对象。

---

## 明确还没做

- [ ] 知情边从 D-COORD-001 变成合同禁止，对到哪次 commit
- [x] 读 SI-010／SI-009／SI-016 消化稿；第 8／11／12／16 行备注已写在本备忘「这波之后」——未回写对照表正文（表还在对话里）
- [ ] CZ 批：9–16 哪些要补落位（补字段走正式问题清单）
- [ ] 登票／改 contracts／关票——都不做，除非 CZ 另说
- [ ] 团队三轮——上次已中断；续跑不要一次派满编

来源：2026-08-23 主会话核对；报告背景板 R01；#110 候选清单 HEAD `56d9004`
