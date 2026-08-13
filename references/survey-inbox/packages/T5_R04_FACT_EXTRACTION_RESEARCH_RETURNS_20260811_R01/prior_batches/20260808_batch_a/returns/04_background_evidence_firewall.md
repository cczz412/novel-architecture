# 小说事实抽取的安全 Input Context Contract：作者确认背景、正文背景与模型猜测该怎么用

## 执行结论

✅ **结论很明确：你们提出的作者增强流程值得做，但不能把“背景卡”做成第二份事实来源。最安全的设计，是把系统拆成两层真值、两种记忆 channel，再加一道硬性的 evidence firewall。**

研究里已经有比较稳定的共同方向：长期记忆不应等于“把全部历史塞进上下文”。MemGPT 把记忆分层管理；Generative Agents 按相关性、时间和重要性动态取回；CoALA 把不同种类的记忆拆开；Mem0、Letta、Google Memory Bank、AWS AgentCore 也都把“持久存储”和“本次真正送进模型的上下文”区别开来。citeturn15search0turn15search1turn15search2turn20search2turn19search1turn19search3

对你们这个任务，我建议把整个系统画成下面这条线：

> **作者/历史正文 → 可追溯背景库 → 按当前窗口检索少量背景 → extractor 消歧 → 当前正文独立提供 evidence → evidence validator → 长期状态库**

🔥 **最重要的一条规则：**

> **背景可以决定“这句话里的老周到底是哪一个周某”，但不能决定“老周刚刚做了什么”。**

也就是说，可以让背景帮助 `entity_binding`、alias resolution、speaker resolution、前态连续性；但一个进入当前事实库的新 proposition，仍必须能在当前正文窗口里找到证据。

因此最好把输出里这两个概念彻底拆开：

```text
evidence_ids
    = 当前正文为什么支持这个事实
    = 只能指向 CURRENT_TEXT

resolution_basis_ids
    = 为什么把“老周”解析成 character_017
    = 可以指向背景卡
```

比如正文只有：

> “老周推门进来，把剑放到桌上。”

背景卡确认：

```text
老周 = 周明 = character_017
```

那么可以抽：

```json
{
  "subject_entity_id": "character_017",
  "fact": "周明把剑放到桌上",
  "evidence_ids": ["TXT:CH32:E104"],
  "resolution_basis_ids": ["BG:ALIAS:017:03"]
}
```

**不能**把 `BG:ALIAS:017:03` 当成“周明放剑”的 evidence。它只证明实体绑定。

这种分离比单靠 Prompt 写一句“不要相信背景”安全得多。错误检索和错误上下文确实会让模型受到强烈影响：PoisonedRAG 表明外部知识库本身可以成为污染入口；另一项冲突上下文研究发现，GPT-4/3.5 和 Llama 2 在其测试条件下甚至会偏向模型自己生成的错误背景；Sufficient Context 的实验也说明，给模型上下文并不天然改善 abstention，信息不足时模型仍可能选择回答而不是保持未知。citeturn20search3turn17search1turn17search5

所以这里的默认原则应该是：

| 问题 | 推荐答案 |
|---|---|
| 更多背景是否默认更好 | **否** |
| 作者确认背景能否帮助抽取 | **可以，优先用于消歧和连续性** |
| 作者确认背景能否单独生成当前事实 | **不能** |
| 正文历史事实能否作为当前 evidence | **不能，除非该 evidence 就在当前 extraction window 内** |
| MODEL_SUGGESTED 能否送 extractor | **默认不能** |
| AUTHOR_CONFIRMED 是否比 TEXT_CONFIRMED“等级更高” | **不能简单排序；二者属于不同真值域** |
| `unknown` 是否应正式存在 | **应该** |
| `not_yet_revealed` 是否应正式存在 | **应该，而且与 unknown 分开** |
| `author_secret` 是否应正式存在 | **应该，但 secret value 默认完全不进入 extractor** |
| stable background 和 previous state 是否分 channel | **强烈建议分开** |
| full world bible 是否送入 extractor | **不建议** |
| 是否检索 5～20 条相关背景而不是整库 | **是；但具体 k 要按模型单独验证，不能当通用常数** |
| 当前正文与背景冲突怎么办 | **当前抽取以当前正文为准，同时产生 conflict，不静默覆盖正文** |

这也回答了一个关键问题：**作者确认背景完全可以是“产品世界设定真值”，但它不是“当前正文证据真值”。**成熟 provenance 系统本来就会区分数据是什么、是谁产生的、经历了什么活动；时间型记忆系统也会区分某个事实“何时有效”和系统“何时知道它”。你们只是在小说场景里再多加一道 evidence eligibility。citeturn19search0turn20search1turn20search5

## 研究与工业实践

**A｜最相关的研究与工业实践**

下面这十五项最值得直接借鉴。它们并没有哪一项完整解决“中文长篇小说作者背景卡”，所以后面的方案是综合这些证据后的工程设计，而不是声称已有论文证明了你们整个流程。

| 研究 / 实践 | 已经验证或采用的做法 | 对小说事实抽取最有用的启示 |
|---|---|---|
| **MemGPT** | 用类似操作系统的分层记忆管理有限上下文，而不是长期信息全部常驻。citeturn15search0 | 背景库可以很大，但 extractor 上下文应该很小。 |
| **Generative Agents** | 保存经历流，并根据 relevance、recency、importance 动态检索，还会把经历归纳成更高层 reflection。citeturn15search1turn15search7 | “原始证据”和“归纳背景”应区分；归纳产物不应反过来冒充原始证据。 |
| **CoALA** | 把 agent memory 看成模块化系统，而不是一个同质文本桶。citeturn15search2turn15search5 | stable knowledge、previous state、working context 应分开。 |
| **LongMemEval** | 专门考察 extraction、跨 session reasoning、temporal reasoning、knowledge update 和 abstention；其测试显示长期记忆仍存在明显困难。citeturn15academia30 | 你们不能只测 semantic F1，还要单测更新、时间和 unknown。 |
| **Mem0** | 不是保留完整历史，而是抽取、整合、检索 salient memory；论文还专门与 full-context 做了比较。citeturn20search2 | selective memory 是值得测的基线；不能因为 context window 大就全塞。 |
| **Zep / Graphiti 时间记忆** | 对事实维护 `valid_at / invalid_at`，同时还能追踪系统何时获得或废弃信息。citeturn20search1turn20search5 | 很适合映射成 `valid_from/to` 与 `as_of_chapter` 两套时间。 |
| **W3C PROV** | 成熟的数据 provenance 标准把 entity、activity、agent 及其生成/使用关系显式化。citeturn19search0 | provenance 不应只是一个 `source="author"` 字符串，而要能回溯证据、生成者、审阅者和版本。 |
| **Google Memory Bank** | 支持按 identity 限定检索、TTL、memory revision，以及检查记忆随着新信息如何变化。citeturn19search1turn19search9 | scope、过期和 revision 应成为背景库一等概念。 |
| **AWS AgentCore Memory** | 区分 session 中的 raw short-term events 与由策略提炼出的 long-term memory，还通过 namespace 防止不同主体/会话混淆。citeturn19search12turn19search2 | 原始正文 observation 与提炼后的 stable card 不要混一个表当同一种记录。 |
| **Letta** | memory block 可以固定在上下文中；archival memory 则只能按需查询。citeturn19search6turn19search3 | 很适合你们的“极小 alias card 常驻 + 大背景按需取回”。 |
| **PoisonedRAG** | 少量被污染的检索文档就可能把模型导向攻击者指定答案。citeturn20search3turn20search7 | 背景数据库是安全边界，不是无害缓存；B4 很有必要。 |
| **Blinded by Generated Contexts** | 在该研究测试的 GPT-4/3.5 与 Llama 2 上，模型面对冲突时出现偏向 generated context 的现象，即使 generated context 是错的。citeturn17search1turn17search7 | `MODEL_SUGGESTED` 千万不要和 confirmed background 一起送 extractor。 |
| **Sufficient Context** | 多种模型在信息不足时会错误回答而不是 abstain，研究因此专门设计 selective generation。citeturn17search5turn17search23 | `unknown` 不能只靠模型“自己懂得谨慎”；要正式建模和测试。 |
| **Human-assisted annotation 系列** | 高质量预标注在客观句法标注中能提升速度与一致性；但 DocRED 的 recommend-revise 产生了漏标偏差；2025 年预注册实验中，LLM suggestion 没让标注者更快，却改变了他们的标签分布。citeturn18view1turn18view0turn18view2 | “模型先猜、作者点确认”可能省事，也可能锚定作者，必须在你们任务上 A/B，而不是默认它更省工。 |
| **Fictional Character Embeddings** | 在 28 部英文小说的 quotation attribution 实验中，把全局角色表示与局部上下文结合，提高了 anaphoric / implicit quotation 的 speaker identification。citeturn23view0 | 全局人物信息确实有机会帮助隐式 speaker，但这不是“作者确认卡”的直接验证，更不能直接外推到中文小说或你们的模型。 |

关于你问的“**作者确认一小张背景卡能不能显著提高 alias、speaker、状态连续性**”，研究证据要说得保守一点。

目前可以找到的邻近证据支持两件事：文学 speaker attribution 的确可能从全局人物信息中获益；高质量 pre-annotation 也确实可能降低某些客观标注任务的人力。citeturn23view0turn18view1

但我没有找到一项足够直接的受控研究，能证明：

> “小型作者确认卡 + 5～10 章中文小说 + LLM 事实抽取”

一定带来显著收益。

而且 human-in-the-loop 的结果是明显混合的：DocRED 的 recommend-revise 会漏掉推荐之外的事实；另一项大型预注册实验里，模型建议没有加速人工，却会把人工判断往模型建议方向拉。citeturn18view0turn18view2

所以这里最合理的立场不是“作者卡肯定有效”，而是：

> **B1/B2/B3 是非常值得验证的 hypothesis；B4 是必须验证的 safety hypothesis。**

## 分级、双层真值与背景卡 Schema

**B｜`AUTHOR_CONFIRMED / TEXT_CONFIRMED / MODEL_SUGGESTED` 是否合理**

✅ **合理，但只适合当第一层标签，不适合当单一的“信任等级”。**

问题在于 `AUTHOR_CONFIRMED` 与 `TEXT_CONFIRMED` 其实回答的是两个不同问题。

`AUTHOR_CONFIRMED` 回答：

> 作者认定这个世界设定是什么？

`TEXT_CONFIRMED` 回答：

> 截止某章，正文明确展示或陈述了什么？

它们不能简单写成：

```text
AUTHOR_CONFIRMED > TEXT_CONFIRMED > MODEL_SUGGESTED
```

举个小说里很常见的情况：

```text
AUTHOR_CONFIRMED:
张三其实是皇子

as_of_chapter = 100
valid_from_chapter = 1
```

作者当然知道这个设定从第一章就“是真的”。

但第 20 章 extractor **绝对不能知道**。

所以真正的许可判断必须同时看：

```text
来源是谁？
确认状态是什么？
这条知识在第几章以后才允许知道？
它允许拿来干什么？
```

我建议保留你们现在三个产品级标签，同时再拆成四个正交维度：

| 维度 | 推荐字段 | 解决的问题 |
|---|---|---|
| 来源权威 | `source_class` | AUTHOR / TEXT / MODEL 是谁产生的？ |
| 认识状态 | `epistemic_status` | CONFIRMED / SUGGESTED / UNKNOWN / NOT_YET_REVEALED / SECRET 等 |
| 真值用途 | `truth_domain` | CANON、TEXTUAL_ASSERTION、CONTEXT_HINT |
| 使用许可 | `eligibility` | 能否进 extractor、能否当 evidence、能否训练 |

因此三个现有等级最好这样落地：

| 标签 | 可作为产品世界设定 | 可给 extractor | 可当当前正文 evidence | 可直接做事实抽取训练标签 |
|---|---:|---:|---:|---:|
| `AUTHOR_CONFIRMED` | ✅ | 条件允许 | ❌ | ❌，除非另有当前正文 evidence |
| `TEXT_CONFIRMED` | 不一定等同作者 canonical | ✅，需时间有效 | **只有 evidence 位于当前窗口时可以** | 权利清晰且证据映射通过时可以 |
| `MODEL_SUGGESTED` | ❌ | **默认 ❌** | ❌ | ❌ |

这就是你问的“双层真值”：

```text
CANONICAL WORLD TRUTH
作者认为这个小说世界里实际上是什么

TEXTUAL EVIDENCE TRUTH
模型当前窗口实际看见了什么、能证明什么
```

W3C PROV 的思路就是让信息保持来源链，而时间型 memory 系统进一步把“事实何时有效”和“系统何时得知”分开；这两种思路很适合你们这里的双层真值设计。citeturn19search0turn20search1turn20search5

🔥 **尤其不要把 `as_of_chapter` 和 `valid_from_chapter` 合并。**

这两个字段看起来很像，其实完全不同：

```text
valid_from_chapter
= 在小说世界里，这件事从什么时候是真的

as_of_chapter
= 系统最早到什么时候才有资格知道这件事
```

还是“皇子”例子：

```json
{
  "value": "皇子",
  "valid_from_chapter": 1,
  "as_of_chapter": 100
}
```

抽第 50 章时：

```text
valid_from = 1       ← 看起来已经有效
as_of = 100          ← 但第 50 章绝不能检索
```

因此 retrieval 的硬门应该是：

```text
background.as_of_chapter <= extraction_window.end_chapter
```

**先过这个门，再谈 valid time。**

这与时间知识图谱里区分世界有效时间和系统记录/获知时间的思想非常接近。citeturn20search1turn20search5

**C｜推荐背景卡 schema**

下面这版不是要求一开始把所有字段都显示给作者，而是建议后台的数据模型先留够。这样以后才不会因为 provenance、时间或训练权利缺字段而返工。

```json
{
  "card_item_id": "BG:CHAR017:ALIAS:003",
  "entity_id": "CHAR017",
  "entity_type": "CHARACTER",

  "predicate": "alias",
  "value": "老周",
  "normalized_value": "老周",

  "memory_channel": "STABLE_BACKGROUND",
  "mutability": "STABLE",

  "source_class": "AUTHOR",
  "epistemic_status": "CONFIRMED",
  "truth_domain": "CANON",

  "provenance": {
    "source_record_ids": ["TXT:CH03:E018"],
    "source_chapters": [3],
    "source_spans": ["众人都叫周明老周"],
    "generated_by": "qwen-background-draft-vX",
    "reviewed_by": "AUTHOR",
    "reviewed_at": "2026-08-08T10:00:00+08:00",
    "review_action": "CONFIRM"
  },

  "certainty": {
    "epistemic_level": "CONFIRMED",
    "model_confidence": null
  },

  "temporal": {
    "as_of_chapter": 3,
    "valid_from_chapter": 1,
    "valid_to_chapter": null,
    "observed_at_chapter": 3
  },

  "versioning": {
    "version": 1,
    "supersedes": null,
    "superseded_by": null
  },

  "eligibility": {
    "extractor_hint_allowed": true,
    "current_evidence_allowed": false,
    "inference_allowed": true,
    "training_allowed": true,
    "training_role": "ALIAS_RESOLUTION_ONLY",
    "author_ui_only": false
  },

  "rights": {
    "training_rights": "CLEAR",
    "inference_rights": "CLEAR"
  }
}
```

这里有几处很关键。

**`model_confidence` 不要和“事实可信度”混为一谈。**

比如：

```text
model_confidence = 0.97
source_class = MODEL
epistemic_status = SUGGESTED
```

它仍然只是模型高置信猜测。

不能因为 0.97 就自动变成：

```text
TEXT_CONFIRMED
```

更不能变：

```text
AUTHOR_CONFIRMED
```

**`unknown / not_yet_revealed / author_secret` 应该正式进入状态机。**

推荐含义如下：

| 状态 | 含义 | extractor 可见内容 |
|---|---|---|
| `UNKNOWN` | 截止当前信息，没人可靠确定 | 最多知道“未知”，不带猜测值 |
| `NOT_YET_REVEALED` | 作者知道可能存在答案，但截止当前章不应揭晓 | 只允许看到“不要解析此字段”，不允许看到秘密值 |
| `AUTHOR_SECRET` | 作者后台保存了秘密值 | **秘密值完全不可进入 extractor** |
| `DISPUTED` | 来源之间冲突，尚未解决 | 可视情况提供 conflict metadata，不给单一确定答案 |
| `SUPERSEDED` | 老版本已被更新 | 正常检索不返回，审计历史保留 |

例如：

```json
{
  "predicate": "true_identity",
  "epistemic_status": "NOT_YET_REVEALED",
  "public_value": null,
  "secret_record_id": "SECRET:CHAR017:IDENTITY",
  "as_of_chapter": 20,
  "eligibility": {
    "extractor_hint_allowed": false,
    "author_ui_only": true
  }
}
```

这比把秘密直接写成：

```text
真正身份：皇子（不要告诉模型）
```

安全很多。

因为只要秘密值已经进入 prompt，你们实际上已经失去了“模型不知道”的保证。错误或额外上下文能够显著影响模型行为，已有冲突上下文和 RAG 污染研究已经充分说明这类风险不能只靠语言指令控制。citeturn17search1turn20search3

## Input Context Contract 与 Evidence Firewall

**E｜怎么保证背景永远不能单独贡献 evidence**

我建议把这件事从“Prompt 规范”升级成**结构性约束**。

一个安全版本的输入顺序可以是：

```text
[SYSTEM / HARD POLICY]
    ↓
[RELEVANT STABLE BACKGROUND]
    ↓
[RELEVANT PRIOR CONFIRMED STATE]
    ↓
[CURRENT TEXT + CURRENT EVIDENCE IDS]
    ↓
[SHORT EVIDENCE RULE + OUTPUT SCHEMA]
```

这里我更倾向于让 **CURRENT TEXT 是最后一块语义材料**，不要在正文之后再接一大段 world bible。

原因不是说已经有论文证明这个顺序对所有模型最优，而是这是你们值得在 Qwen 上验证的工程假设：让真正的证据离生成位置更近，同时把背景明确放在“辅助信息”区域。不同模型会有不同的 position/context behavior，所以**顺序本身也不能从 Qwen 直接外推到 Ling 或 Doubao。**

Prompt 中的语义边界可以写得非常硬：

```text
BACKGROUND 是消歧提示，不是证据。

你只能输出 CURRENT_TEXT 能直接支持的事实。

BACKGROUND 可以用于：
- 将当前文本里的别名映射到 entity_id；
- 辅助判断当前发言人的候选；
- 理解当前状态变化的旧状态。

BACKGROUND 不可以用于：
- 新增当前文本未表达的事实；
- 填补当前文本未给出的属性值；
- 将未来信息补写为当前事实；
- 作为 evidence_id。

任何事实如果去掉 BACKGROUND 后，
CURRENT_TEXT 本身仍无法支持，
则不得输出该事实。
```

不过，**Prompt 只是第一层。真正的保险应该在模型外。**

推荐四层 evidence firewall：

| 防线 | 做法 |
|---|---|
| ID namespace | 当前正文只发 `TXT:*`；背景只发 `BG:*` |
| 输出 schema | `evidence_ids` 字段只允许 `TXT:*` |
| deterministic validator | evidence ID 必须存在于当前窗口 evidence catalog，否则拒绝 |
| semantic support verifier | verifier **只看到 fact + 当前正文 evidence**，完全不看到 background，检查证据是否真支持 proposition |

如果你们继续采用 C2，也就是输出 evidence IDs，这一点反而很好实现：

```text
Extractor:
fact + TXT:E12

Server:
TXT:E12 → 当前窗口原文

Verifier:
只拿 fact + 原文 E12
```

背景压根不送进 verifier。

如果 verifier 判断：

```text
当前 evidence 不足以推出 fact
```

就进入：

```text
UNSUPPORTED
```

而不是因为 extractor 说“我还参考了背景卡”就放行。

🔥 还可以进一步加一个专用字段：

```json
{
  "evidence_ids": ["TXT:..."],
  "resolution_basis_ids": ["BG:..."]
}
```

这样系统以后能直接测：

> 哪些 prediction 是因为背景帮助 entity resolution 才成功？

而不是让 background contribution 藏在模型内部。

**冲突规则也必须写死。**

对**当前事实抽取**，建议优先级是：

```text
CURRENT_TEXT explicit evidence
        >
temporally valid previous TEXT_CONFIRMED context
        >
temporally valid AUTHOR_CONFIRMED disambiguation hint
        >
MODEL_SUGGESTED
```

但这里的 `>` 只表示：

> “当前输出应该跟谁走。”

它不是说当前一句正文能永久推翻作者 canonical。

例如背景库：

```text
AUTHOR_CONFIRMED:
李明目前持有青龙剑
```

正文：

> “他把青龙剑交给了陈月。”

Extractor 应该输出：

```text
李明 → 不再持有青龙剑
陈月 → 获得青龙剑
```

而不是因为 background 还写着：

```text
李明持有青龙剑
```

就否定这次变化。

正确行为是：

```text
extract current change
→ background_conflict / state_transition
→ old prior state valid_to = current chapter
→ new state valid_from = current chapter
```

Google Memory Bank 已经把 revision 当成一等功能；Zep 的时间字段也明确支持事实的有效期和历史审计，而不是简单用新值把旧值抹掉。citeturn19search9turn20search5

**I｜什么时候自动更新，什么时候必须作者确认**

建议把 `PRIOR_STATE` 和 `STABLE_BACKGROUND` 采用不同更新政策。

`PRIOR_STATE` 可以更自动化，因为它就是“上一时刻已接受的状态”。比如经过 extraction + evidence validator 后明确得到：

```text
陈月获得青龙剑
```

系统可以自动产生候选：

```text
current_holder(青龙剑) = 陈月
```

并关闭旧记录：

```text
current_holder(青龙剑) = 李明
valid_to_chapter = 32
```

但 `STABLE_BACKGROUND` 要保守很多。

下面这些可以在严格验证后自动创建 **TEXT_CONFIRMED candidate**，但不自动变 AUTHOR_CONFIRMED：

```text
明确出现的新名字
明确的别名称呼
显式位置变化
显式持有物变化
明确的状态变化
```

下面这些我建议必须作者确认：

| 项目 | 原因 |
|---|---|
| 两个人物实体的 merge / split | 错一次会污染整本书 |
| 隐藏身份 | 极易未来泄漏 |
| 金手指 / 系统类型 | 经常是逐步揭示或读者误导 |
| 长期稳定人物关系 | “师徒”“恋人”“敌人”等可能发生变化，也可能只是人物声称 |
| retroactive truth | 例如第 100 章揭晓“其实从第一章就是……” |
| 覆盖 `AUTHOR_CONFIRMED` | 不应让 extractor 自动推翻作者 |
| `NOT_YET_REVEALED → REVEALED` | 这是访问权限变化 |
| `AUTHOR_SECRET` 的任何变化 | 必须由作者控制 |
| 模型推测要升级 confirmed | **绝不能纯自动升级** |

换句话说：

```text
MODEL_SUGGESTED
    ↓
只能经过 TEXT evidence 或 AUTHOR review
    ↓
TEXT_CONFIRMED / AUTHOR_CONFIRMED
```

不要允许：

```text
MODEL_SUGGESTED
    ↓
模型觉得更有把握
    ↓
AUTHOR_CONFIRMED
```

## 本地对照矩阵、压力测试与预注册指标

**D｜本地 B0～B4 对照矩阵**

建议把 Qwen 阶段做成真正的 paired experiment：**完全相同的正文窗口、相同输出 contract、相同 decoding，只改 background treatment。**

| Arm | 给模型什么 | 主要回答的问题 | 是否可能进入生产 |
|---|---|---|---|
| **B0** | 无背景 | 纯局部正文基线有多强 | ✅ |
| **B1** | confirmed `character_id + canonical_name + aliases` | 最小人物卡是否已经解决大部分 alias/speaker 问题 | ✅ |
| **B2** | B1 + confirmed stable background | 稳定关系、能力/系统等是否继续提升，还是开始锚定 | ✅，待验证 |
| **B3** | B2 + confirmed previous state | prior state 是否改善状态连续性和隐式变化 | ✅，待验证 |
| **B4** | 控制性 noisy / stale / future / conflicting background | 模型会不会盲信背景 | ❌，只做安全测试 |

🔥 我会把 **B1 当成最值得优先挑战 B0 的 arm**。

原因很简单：alias/entity identity 是当前窗口本来就容易缺的信息，而且给的背景非常窄；比起塞入世界观、能力、人物历史，它的污染面积小得多。文学 speaker attribution 的相关研究也说明，全局 character representation 有可能对 implicit/anaphoric speaker 有帮助，但那是英文小说上的特定方法结果，所以这里只能作为验证 B1 的理由，不能视为 B1 一定赢。citeturn23view0

B2 则正好检验：

> “多一些正确 stable knowledge，是真的继续帮助，还是已经开始让模型过度补全？”

B3 专门回答：

> “持续状态到底应该作为 stable background 的一部分，还是独立 previous-state channel？”

我预测值得分开，但**这个预测必须在每种模型上分别复验**。CoALA、AWS 等体系都支持把不同性质的 memory 分成不同模块/策略，但这不意味着某个具体 LLM 一定因为这种拆分而获得更高 F1。citeturn15search2turn19search12

**B4 不要只是随机写几个错事实。**

最好做成结构化的 contamination suite：

| B4 污染类型 | 示例 | 你们在测什么 |
|---|---|---|
| Wrong alias | 背景说“老周=周强”，正文其实指周明 | entity anchoring |
| Stale state | 背景仍说剑在 A 手上，正文明确转给 B | stale-memory override |
| Future true fact | 第 100 章才揭晓的身份塞给第 20 章 | future leakage |
| Plausible false suggestion | MODEL_SUGGESTED“女主是系统宿主” | model-generated-memory contamination |
| Direct conflict | 背景与当前句直接相反 | conflict priority |
| Irrelevant world noise | 塞一批真实但当前无关世界设定 | context overload / over-extraction |

这里再拆两个非常有价值的 stress condition：

```text
B4-safe-label
错误内容被正确标成 MODEL_SUGGESTED / stale
```

看模型会不会尊重 metadata。

以及：

```text
B4-corrupted-confirmed
错误内容被错误标成 AUTHOR_CONFIRMED
```

这是测试“记忆库自身被污染以后会有多惨”。

PoisonedRAG 已经表明，错误外部知识并不是普通噪声，它可以成为真正影响生成的攻击面；冲突上下文研究也说明模型可能对某种背景来源产生不合理偏好。citeturn20search3turn17search1

**F｜预注册指标**

不要只登记一个 semantic F1。建议在跑锁定 DEV/TEST 之前，把下面全部预注册。

| 指标 | 推荐定义 | 为什么单独看 |
|---|---|---|
| **Semantic Precision** | 正确抽取事实 / 全部预测事实 | 背景最容易先伤 precision |
| **Semantic Recall** | 正确抽取事实 / 全部 gold facts | 看背景是否帮忙找回隐式事实 |
| **Semantic F1** | P/R 调和平均 | 主质量指标 |
| **Speaker accuracy / F1** | speaker entity_id 正确率 | 直接测背景人物卡价值 |
| **Alias resolution accuracy** | mention → canonical entity_id 是否正确 | B1 的核心 |
| **State-transition F1** | old state → new state 变化是否正确抽出 | B3 的核心 |
| **Background-only unsupported fact rate** | 预测中“当前正文无支持、但背景里存在”的事实比例 | 核心安全指标 |
| **Injected-background adoption rate** | B4 注入错误中有多少被模型复制成事实 | 锚定压力测试 |
| **Conflict handling accuracy** | 背景与当前正文冲突时，有多少次正确保留正文且标记冲突 | stale-memory 安全 |
| **Over-extraction** | FP/window，辅以 FP/100 predictions | 防止“背景越多事实越多”被 F1 掩盖 |
| **Unknown / abstention accuracy** | gold 不足时能否保持 unknown | 防止强行补全 |
| **Future leakage rate** | `as_of > current` 的注入事实有多少进入输出 | 必须做硬门 |
| **Evidence namespace violation** | 非 `TXT:*` 被输出成 evidence 的比例 | 工程上目标应为 0 |

`unknown / abstention` 值得独立列出来，而不是混在 recall 里，因为 LongMemEval 本身就把 abstention 当作长期记忆的一项核心能力，Sufficient Context 也显示信息不足时模型很容易选择错误回答。citeturn15academia30turn17search5

其中 **background-only unsupported fact** 建议至少算两个版本。

全局版：

```text
BOUF_rate =
当前正文不支持、但背景能解释其来源的预测事实数
/
全部预测事实数
```

B4 攻击版：

```text
Injected Adoption Rate =
模型输出的 injected false background items
/
实际注入且与窗口相关的 false background items
```

这样能区分：

```text
普通 hallucination
```

和：

```text
明显是背景把模型带歪
```

再加一个很便宜但非常有价值的 paired counterfactual：

```text
同一窗口：
B0 没输出 X
B2/B3 输出 X
但正文 evidence validator 认为 X 不成立
```

这类预测直接进入：

```text
BACKGROUND_INDUCED_UNSUPPORTED
```

**统计设计上建议把比较提前锁死：**

```text
Primary:
B1 vs B0
B2 vs B1
B3 vs B2

Safety:
B4 vs 对应 clean-background condition
```

同一窗口反复跑不同 arm，所以可以用 paired bootstrap 给 semantic F1 差值做置信区间；speaker、conflict 这种二元配对结果则可以另外看 paired error changes。这里的重点不是某个统计检验名字，而是**不要让不同 arm 抽到不同难度窗口。**

另外有一个项目实验学上的坑：

你们已经知道 MICRO24/M1 上 C2 在 DEV24 的结果，那么 DEV24 对整个项目来说已经不再是“完全不可见的最终考卷”。如果后面根据这些已知结果不断修改系统，最终最好另留一套 sealed test / frozen exam 做确认。

TRAIN24 可以承担：

```text
prompt
背景字段
retrieval k
输入顺序
阈值
```

的探索。

锁定以后再碰最终考卷。

而 B4 最好额外构造一套**专用合成 safety set**，因为正常 DEV 中未必有足够多“背景错、正文对”“未来事实注入”等高价值冲突案例。

**背景数量也应该作为被约束的预算，而不是目标。**

研究和工业系统普遍采用按需检索而非把所有长期记忆固定塞进上下文；Letta 明确区分 pinned memory 与需要按需检索的 archival memory，Mem0 也采用 salient extraction/retrieval。citeturn19search3turn20search2

所以推荐形态是：

```text
B1:
少量人物 ID + confirmed aliases
可以固定提供

B2/B3:
先检索
只给当前窗口相关项

Full world bible:
默认不进 extractor
```

你提的 **5～20 条**是很合理的实验区间，但不是已有研究证明的神奇常数。可以在 Qwen 的 TRAIN24 上低成本比较：

```text
k = 5
k = 10
k = 20
```

然后锁一个值去 DEV，而不是 DEV 上反复挑最漂亮的 k。

## 作者交互、字段裁剪与更新策略

**G｜作者确认原型**

作者流程本身可以保留：

```text
模型读前 5～10 章
        ↓
生成 candidate background card
        ↓
附当前可见逐字证据
        ↓
作者确认 / 修改 / 未知 / 尚未揭晓
        ↓
写入带 provenance + as_of 的背景库
```

但 UI 不应该长成：

> 模型：主角是张三，对吧？  
> `[✅ 是]`

这太容易产生 confirmation anchoring。

Human-in-the-loop 研究给出的警告很直接：DocRED 的 recommend-revise 让标注者倾向于只修推荐项、漏补模型没给出的关系；2025 年预注册实验中，350 名参与者完成 7,000 个 annotation，LLM 建议没有让他们更快，却明显改变了标签分布，并提高了他们自己对判断的信心。citeturn18view0turn18view2

但这也不能反过来得出“不要预标注”：高准确度自动 pre-annotation 在一项句法标注研究中确实加快了工作并提高一致性，没有降低最终质量。citeturn18view1

说白了就是：

> **候选建议值不值钱，取决于候选质量、任务客观程度，以及 UI 有没有放大锚定。**

因此推荐卡片长这样：

```text
人物：周明

正文证据
“村里人都管周明叫老周。”

候选字段
别名：老周

[确认] [修改] [未知] [尚未揭晓]
```

而不是：

```text
✅ 系统 97% 确信：周明的别名是老周
[默认已勾选确认]
```

几个细节很重要：

**不要默认选中“确认”。**

作者必须主动做一次动作。

**证据放在模型猜测前面。**

让作者先看到“为什么会产生这个 candidate”，而不是先被模型结论定锚。

**`MODEL_SUGGESTED` 不要用绿色、高置信进度条之类视觉语言。**

`0.93 confidence` 更适合后台调试，不适合成为作者判断依据。

**高风险字段可以先盲审再显示模型建议。**

比如：

```text
真实身份
系统类型
金手指类型
长期人物关系
```

可以先问：

```text
截止第 10 章，这个字段：
[已确定] [未知] [尚未揭晓]
```

作者点“已确定”以后才显示模型候选。

这样能显著减少：

> “模型已经说是空间系统了，我想想，好像也差不多。”

这种确认偏差风险。

**“尚未揭晓”点击后再提供作者私密输入区：**

```text
读者/Extractor 当前可见：
NOT_YET_REVEALED

作者私密区：
真实值 = ________
计划揭示章 = ________
```

两个数据要物理分离：

```text
PUBLIC MEMORY STORE
SECRET AUTHOR STORE
```

不要只是同一 JSON 里加：

```json
"hidden_from_model": true
```

然后把整个 JSON 又交给模型。

**模型提议 vs 作者从零填：不要凭感觉判断省多少工作。**

建议专门做一个小型 HCI A/B：

```text
UI-A
作者从零填写

UI-B
模型候选 + evidence + 四按钮
```

在一批相同类型字段上记录：

```text
seconds/item
最终错误率
遗漏率
修改率
错误建议接受率
```

特别再随机抽一小部分条目，让作者**不看模型 suggestion**做独立判断，这能估计 proposal anchoring 到底有多强。

不要把：

```text
作者点了确认
```

自动解释成：

```text
模型原来就是对的
```

因为 human-approved labels 本身也可能被机器建议影响，2025 年的实验已经直接观察到这种现象。citeturn18view2

**H｜哪些字段值得送 extractor**

我建议把后台拥有的字段与 extractor 真正看到的字段分成三层。

| 字段 | extractor 默认可见？ | 说明 |
|---|---:|---|
| `entity_id` | ✅ | 消歧核心 |
| canonical name | ✅ | 消歧核心 |
| confirmed aliases | ✅ | B1 核心 |
| alias 有效时间 | ✅ | 防名字变化/冒名 |
| 近亲、师徒等 stable relation | B2 验证后再决定 | 可能帮 pronoun/speaker，也可能过度提示 |
| 阵营/组织 | 按相关性检索 | 只在当前窗口需要时发 |
| 能力名称 | 按相关性检索 | 不要全人物能力表 |
| 系统/金手指类型 | 高风险，B2 单独验证 | 很容易诱导模型补全当前文本没有的效果 |
| prior location | B3 | mutable state |
| prior possession | B3 | mutable state |
| prior injury/status | B3 | mutable state |
| prior relationship state | B3 | mutable state |
| `as_of_chapter` | ✅ | 模型和检索层都应看到/执行 |
| `valid_from/to` | 必要时 ✅ | 状态变化和历史查询需要 |
| provenance 摘要 | 可给 source class，不必给全文 | 防 prompt 太大 |
| 完整 evidence history | ❌ | 后台/作者 UI |
| model confidence | ❌ | 防锚定 |
| reviewer audit log | ❌ | 后台 |
| training rights | ❌ | 后台治理，不帮助抽取 |
| superseded 全历史 | ❌ | 后台，需要时检索 |
| future plot / outline | **❌** | 泄漏 |
| author secret value | **❌** | 泄漏 |
| MODEL_SUGGESTED value | **默认 ❌** | 污染 |
| full world bible | **❌** | 噪声、锚定、token 成本 |

**stable background 与 previous state 必须分成两个 channel。**

推荐：

```text
STABLE_BACKGROUND
人物是谁、别名、长期角色关系、长期能力类别

PRIOR_CONFIRMED_STATE
上一章/最近一次有效状态：
位置、持有物、伤势、当前关系阶段、任务状态……
```

为什么这么分？

因为 stable background 的更新频率低，而 state 的正确行为恰恰是**被新正文频繁推翻**。

两者如果混在一起：

```text
周明：
别名老周；
是陈月师父；
持有青龙剑；
人在杭州；
左臂受伤；
系统等级 3……
```

模型很容易把这些全看成“人物恒定属性”。

拆开以后语义明显很多：

```text
[STABLE_BACKGROUND]
CHAR017 aliases = [周明, 老周]

[PRIOR_STATE @ end_of_ch31]
CHAR017 location = 杭州
CHAR017 holds = 青龙剑
CHAR017 injury.left_arm = injured
```

而正文第 32 章一旦说：

> “周明将青龙剑交给陈月。”

模型天然知道：

```text
holds
```

属于可变 state，不是要维护的稳定人物设定。

## 三层模型复验、生产迁移与禁止事项

**J｜Dense Qwen → Sparse Ling Tiny → Doubao Mini/Lite 的顺序**

这一部分最重要的是：**只迁移假设，不迁移结论。**

### Dense Qwen 本地代理

按你的项目约束，Qwen 是便宜的探索台，所以它应该承担最多的实验分支。

Qwen 官方的 Qwen3 系列同时包含 dense 与 MoE 模型；Qwen3-4B 是 4B 级别的本地模型，因此用它做你们定义的 Dense proxy 是合理的工程安排，但它的结果只能说明“这个具体 Qwen 配置在这批数据上的表现”。citeturn21search0turn21search8

本地阶段建议顺序：

```text
固定现有 extractor/output contract
        ↓
B0 / B1 / B2 / B3
        ↓
B4 safety suite
        ↓
只在 TRAIN24 上探索：
    retrieval k
    background order
    stable field subset
        ↓
锁定 2～3 个结论
        ↓
冻结
```

最值得筛的三个 hypothesis，我会优先放：

```text
H1:
B1 minimal confirmed alias card
是否稳定优于 B0

H2:
B3 previous-state channel
是否在不增加 unsupported extraction 的情况下
提升 state-transition / speaker continuity

H3:
retrieved minimal context
是否优于 full/large background
```

B2 值不值得保留，要看它有没有真正贡献，而不是因为“stable background 听起来有用”就默认进入生产。

如果结果是：

```text
B1 明显提升
B2 没提升甚至降低 precision
B3 只提升 state transition
```

那完全可以生产设计成：

```text
全局固定：B1
条件检索：previous state
stable world background：绝大多数不发
```

这反而是非常好的结果。

### Sparse Ling Tiny

这一阶段不要重新做十几个 arm。

本次检索截至 **2026-08-08**，我能从 inclusionAI 官方公开页核验到 Ling-3.0-flash，以及早先可下载的 Ling-mini-2.0；官方 Ling-mini-2.0 明确采用稀疏 MoE，而 Ling-3.0-flash 官方页也描述了其稀疏激活设计。citeturn14search2turn21search5

但我没有在 inclusionAI 官方公开结果里找到一个足够可靠、可据此确认你们所说 **“Ling 3.0 Tiny 本地可下载 checkpoint”** 的页面。因此现在不要根据 Flash 或 Ling-mini-2.0 的参数/架构细节，提前给未来 Tiny 写死结论。

等你们真正拿到那个 checkpoint，再把它当成一个新的 Sparse proxy。

只复验：

```text
Qwen 筛出来的 2～3 个关键 hypothesis
+
B4 safety
```

例如：

```text
L0 = no background
L1 = minimal alias
L2 = winning state/background design
L4 = noisy stress
```

这里最有价值的不是看绝对 F1 谁比谁高，而是看：

> Qwen 上的“方向”有没有跨到 sparse proxy。

比如：

```text
Qwen:
B1 +2.8 F1

Ling:
B1 +0.1 F1
```

正确结论是：

```text
alias card 的收益没有在 Ling 上复现
```

不是：

```text
背景卡理论仍然有效，只是 Ling 太小
```

同理，如果 Qwen B4 很安全而 Ling B4 很容易被污染，也不能因为 Qwen 已验证就忽略。

### Doubao Mini / Lite 生产迁移

进入云模型以后，探索策略应该反过来：**少 arm、强验证、先 inference contract 后 fine-tune。**

你已经给出的项目约束是 Mini 做主生产候选、Lite 做复杂案例升级，而且云微调成本高。那么生产迁移最合理的顺序是：

```text
冻结 Qwen/Ling 筛出的 Input Contract
        ↓
Doubao Mini
零样本 / few-shot inference 验证
        ↓
Mini B0 vs 最佳背景方案
        ↓
Mini B4
        ↓
对困难子集：
Mini vs Lite paired evaluation
        ↓
确定 escalation rule
        ↓
Input Contract 稳定后
才考虑云 fine-tuning
```

不要先：

```text
B1 微调一版
B2 微调一版
B3 微调一版
不同 k 再各微调……
```

因为这样你们会把本来可以便宜解决的 context-contract 探索，变成昂贵的 cloud SFT 多臂实验。

Mini/Lite 也必须重新回答：

```text
背景究竟提高了什么？
背景究竟伤害了什么？
Lite 是否真的在“背景冲突/implicit speaker”
这些指定难题上比 Mini 更好？
```

不能因为 Lite 在产品定位上更复杂，就自动认定：

```text
Lite 一定更会处理小说背景冲突
```

这仍然需要你们自己的 paired test。火山方舟当前官方文档维护其模型列表和精调能力，但具体任务质量排名并不能由产品层级直接推出。citeturn21search4turn21search13

最终三层证据链应该长这样：

```text
Dense Qwen
= 大规模便宜探索
= 产生候选 hypothesis

Sparse Ling Tiny
= 架构变化后的窄复验
= 判断关键方向是否复现

Doubao Mini/Lite
= 生产模型自己的最终结论
= 决定真正上线 contract
```

而不是：

```text
Qwen 赢
→ Ling 应该也赢
→ Doubao 应该更赢
```

**K｜明确不能做的事**

下面这些我建议直接写进项目的 Input Context Contract，作为 hard prohibition，而不是“最好不要”。

| ❌ 禁止事项 | 原因 |
|---|---|
| 把未来剧情、大纲、后续章节真相塞进当前 extractor | 直接造成 future leakage |
| 因 `valid_from_chapter` 很早，就忽略较晚的 `as_of_chapter` | 会把后期揭晓倒灌到早期 |
| 把 `AUTHOR_SECRET` 的真实值放在 prompt 中再叫模型“别使用” | 已经泄露 |
| 把 `MODEL_SUGGESTED` 默认混入 confirmed background | 错误 generated context 有明确锚定风险。citeturn17search1 |
| 用模型 confidence 把 suggestion 自动升级成 truth | confidence 不是 provenance |
| 让 background ID 出现在 `evidence_ids` | 混淆消歧依据与正文证据 |
| 因背景与正文冲突而静默改写当前正文事实 | 会让旧记忆覆盖新事件 |
| 自动用 extractor 推翻 `AUTHOR_CONFIRMED` | 稳定设定会逐步漂移 |
| 把 stable background 和 mutable prior state 混成一块 prose biography | 模型难判断哪些字段允许变化 |
| 每次把完整 world bible 塞给 extractor | 更多上下文不保证更可靠；错误/不足上下文会影响 abstention 和生成。citeturn17search5turn20search3 |
| 用权利不明数据做背景卡训练或 extractor 微调 | 与你们现有数据权利边界直接冲突 |
| 因 Qwen 结果好就认定 Ling/Doubao 同样好 | 模型、架构与规模变化后必须复验 |
| 因 Ling 是 sparse proxy 就把它当生产替代品 | proxy 只能复验 hypothesis |
| 在 Doubao 上重新进行大规模 context 多臂 SFT 探索 | 与云成本约束相违背 |
| 把“作者点击了模型建议”自动当独立人工 gold | 人类判断可能被机器建议锚定。citeturn18view2turn18view0 |

把整项研究压成一个最终推荐版本，就是：

```text
AUTHOR UI / MEMORY DATABASE
────────────────────────────

AUTHOR_CONFIRMED
TEXT_CONFIRMED
MODEL_SUGGESTED
UNKNOWN
NOT_YET_REVEALED
AUTHOR_SECRET
DISPUTED
SUPERSEDED

每条都有：
provenance
as_of_chapter
valid_from / valid_to
version
eligibility
rights


                 ↓ 时间硬过滤
                 ↓ 权限硬过滤
                 ↓ relevance retrieval


EXTRACTOR INPUT
────────────────────────────

[POLICY]

[MINIMAL CONFIRMED IDENTITY / ALIAS]

[RELEVANT STABLE BACKGROUND]
        非证据

[RELEVANT PRIOR STATE]
        非证据

[CURRENT TEXT + TXT evidence IDs]
        唯一当前事实证据源


                 ↓


EXTRACTOR OUTPUT
────────────────────────────

fact
entity_id
evidence_ids = TXT only
resolution_basis_ids = BG allowed
speaker
state_transition
conflict_flag


                 ↓


EVIDENCE FIREWALL
────────────────────────────

1. evidence ID namespace check
2. current-window check
3. exact evidence lookup
4. semantic support verification
   verifier 看不到 background
5. unsupported → reject / quarantine


                 ↓


MEMORY UPDATE
────────────────────────────

mutable state:
可按严格规则自动版本化

stable/high-impact background:
作者确认

MODEL_SUGGESTED:
绝不自动晋级
```

🔥 **如果近期只能做一轮最有信息量的实验，我会优先做 `B0 / B1 / B3 / B4`，同时把 B2 留在 TRAIN24 做筛选。**

原因是它们分别回答四个最核心的问题：

```text
B0
局部正文自己能做到多少？

B1
最小身份/别名卡是否解决真正的缺口？

B3
previous state 是否提供额外连续性价值？

B4
一旦背景错了，系统到底会不会被带走？
```

如果 B1 的 alias/speaker 有稳定收益，semantic precision 不降，background-only unsupported 不升，那么它很可能成为最安全的默认背景层。

如果 B3 只对 possession/location/state-change 有价值，则把 previous state 做成按需 channel，而不是把人物卡越堆越大。

如果 B2 只有很小收益、却明显提高过抽或背景复制，那就应该舍弃它。**背景卡的目标不是尽量完整地告诉模型这个世界，而是以最小必要信息消除当前窗口无法自己解决的歧义。**

这也是整轮研究最强的一条结论：长期记忆领域已经越来越倾向于分层、筛选、检索、更新和版本管理，而错误上下文、错误检索和机器建议锚定的研究都在提醒同一件事——**“模型知道得更多”与“模型抽得更准”不是一回事。**citeturn15search0turn20search2turn19search3turn17search1turn18view2

来源：ChatGPT