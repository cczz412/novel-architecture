# chatgpt

# **✅ 总判断**

不要在“厚描”和“薄切片”里二选一。

**唯一真相层用厚描，薄切片全部由系统按需生成。**

你们的大纲不该继续做成一张平铺 JSON 表，而应升级成一套可回放的叙事账本：

> **发生了什么的事件流**
> 
> 
> ＋ **人物、关系、规则现在怎样的状态账**
> 
> ＋ **读者正在等什么、爽点兑现到哪的体验账**
> 
> ＋ **未来必须检查什么的 Hook 账**
> 
> ＋ **每条判断来自正文哪里的证据**
> 

下游仍然只认“大纲”，但它们拿到的不是同一坨字段：

- 续写拿“下一章创作视图”
- 分镜拿“场景与高光视图”
- 互动叙事拿“状态机视图”
- 作者工作台拿“长线与 Hook 视图”

这些都是同一份权威大纲生成的**派生视图**，不能各自成为第二套真相。

🔥 当前最优先的三件事：

1. **厚描做权威数据，薄片只做查询和上下文压缩。**
2. **把期待、兑现、爽点、规则、Hook 放进固定核心，不要等适配层补救。**
3. **弱模型只负责提出候选判断，程序负责路由、校验、合并和落库。**

---

# **一｜中枢形态**

## **结论**

**“章末快照＋章内变化流＋章间交接”更适合做中枢；“入场／出场／中段概要”适合做它的派生视图。**

原因很直接：

- 续写真正需要的不是“谁进来了、谁出去了”，而是**为什么发生、发生过程中什么变了、下一章接什么压力**。
- 分镜真正需要的是**动作、反应、转折、高光、空间与情绪变化**，薄切片通常只剩结果。
- 纯对话、回忆、信息揭示、心理决策这类章节，人物可能原地没动，但知识、立场、期待和关系已经大变。薄切片很容易把它们误判成“无事发生”。

事件流负责保存变化，快照负责快速查询历史状态，这与事件溯源系统的常见做法一致；长篇故事研究也常把事实拆成前置状态、后置状态和有效时间，而不是只保留一段摘要。([martinfowler.com](https://martinfowler.com/eaaDev/EventSourcing.html?utm_source=chatgpt.com))

## **可操作方案**

一章的权威结构可以收成这样：

```
chapter:
  chapter_id:CH_0081
  entry_snapshot_ref:SNAP_0080_END

  beat_flow:
    -beat_id:B01
      narration_order:1
      story_time:DAY_17_20_10
      scene_ref:SCENE_01

      event:
        actor:E_LIN
        action:challenge
        target:E_ZHAO

      preconditions:
        -RANK_LIN < RANK_ZHAO
        -CROWD_EXPECTS_LIN_TO_LOSE

      deltas:
        world_state: []
        knowledge:
          -subject:CROWD
            learns:LIN_HAS_HIDDEN_SKILL
        relationship:
          -subject:ZHAO
            toward:LIN
            change:contempt_to_fear
        rule:
          -rule_id:RULE_SKILL_COOLDOWN
            change:demonstrated

      reader_effect:
        promise_progress:P_019
        payoff_refs: [PAY_031]
        emotion_shift:repression_to_release
        visual_highlight:high

      evidence_refs:
        -paragraph_18_to_26

  end_snapshot:
    character_states: {}
    relationship_states: {}
    rule_states: {}
    promise_states: {}

  handoff:
    unresolved_promises: [P_020, P_023]
    active_pressure:ZHAO_SECT_RETALIATION
    must_preserve:
      -LIN_SKILL_COOLDOWN_3_DAYS
    next_chapter_options:
      -PUBLIC_REACTION
      -ENEMY_ESCALATION
```

这里有几个关键约束。

### **1. 入场状态不要重复抄**

`entry_snapshot_ref` 指向上一章结束快照即可。

只有出现下面情况时，才单独记录“入场修正”：

- 跳时
- 转线
- 换视角
- 回忆插叙
- 章间有未展示事件
- 上一章结束状态后来被证明不完整或错误

否则每章重复保存一套入场状态，很容易互相打架。

### **2. 章内不要只留一个 `middle_summary`**

中间概要是有损压缩，一压就容易丢：

- 谁导致了变化
- 变化的先后顺序
- 规则是何时展示的
- 爽点是怎样铺垫和兑现的
- 哪个动作适合拆镜头
- 读者在哪个节点改变预期

建议权威层保存 `beat_flow`，再由程序生成：

- 一句话章概
- 入场／出场关键帧
- 场景卡
- 人物时间线
- 高光镜头候选
- 下一章上下文包

### **3. 章间交接不是摘要，而是“续写合同”**

交接至少要回答四件事：

- **还欠读者什么**
- **现在最大的压力是什么**
- **下一章不能忘记什么规则**
- **下一章有哪些可选方向，哪些方向不能走**

这样续写模型拿到的不是“上一章发生了什么”，而是“下一章为什么值得继续读”。

### **4. 一个“时刻”必须区分三种状态**

长篇里问“第 617 章时某人知不知道秘密”，可能有三种答案：

**查询口径含义**世界真实状态秘密在故事世界里是否已经成立角色认知状态某个角色当时相信什么读者已知状态连载到这一章，读者已经被告知什么

这三种状态必须分开。否则回忆、误导、身份揭示、信息差爽点都会乱。

建议固定支持三个查询：

```
world_truth_at(story_time)
character_belief_at(character_id, story_time)
reader_knowledge_by(chapter_id)
```

## **代价与风险**

厚描的成本不在数据库容量，而在：

- 提取字段更多
- 合并逻辑更复杂
- 模型容易欠产出
- 检索时不能把整本账本塞进上下文
- 同一事件可能被重复抽取

对应控制手段：

- 每个变化必须带 `evidence_refs`
- 每个事实有稳定 `fact_id`
- 重复事件按证据区间和语义签名去重
- 旧章节保留原子事实，低价值语言描述可以压缩
- 快照是缓存，不是独立真相；与事件流不一致时，以经过确认的事件为准
- 下游默认拿查询视图，禁止扫描全书 JSON

## **反面核查：千章检索会不会崩**

**会崩，但不是因为“厚”，而是因为没有索引、快照和双时间。**

真正危险的形态是：

```
查第 800 章人物状态
→ 从第一章开始回放所有事件
→ 再把几百章文本交给模型判断
```

预防方式：

1. 给每个实体建立独立时间线索引：

```
entity_id + state_field + story_time
entity_id + state_field + narration_order
```

1. 每个小剧情段或每 10～20 章生成一次实体快照。
2. 单次查询最多回放最近 100～200 条变化；超出就自动补快照。
3. 高频查询直接保存物化状态：

```
current_character_state
current_relationship_state
current_rule_state
active_reader_promises
active_future_hooks
```

1. 回忆和倒叙同时记录：

```
story_time       # 事情在世界中何时发生
narration_order  # 读者何时看到它
```

上面的 10～20 章、100～200 条是工程起步值，不是行业定律。

**需补材料：平均每章事件数、活跃实体数、千章作品的查询类型、目标查询延迟、主力模型实际上下文预算。**

---

# **二｜Schema 三层切法**

## **结论**

三层不该按“常用字段／不常用字段”切，而要按下面的规则切：

- **固定核心：任何题材、任何下游都不能失去的叙事含义**
- **题材可选池：只有特定世界规则才需要的专用字段**
- **适配层：同一叙事含义在不同媒介里怎样被消费**

最容易犯的错，是把固定核心做得过薄，只留下人物、地点、事件摘要；然后把爽点、期待、金手指和规则全部塞进标签扩展。那样看似灵活，实际上把产品最重要的东西降成了可有可无。

## **可操作方案**

### **固定核心建议保留九类对象**

**对象主要解决什么**`narrative_units`卷、剧情段、章、场景、节拍的层级和顺序`entities`人物、组织、地点、物品、能力、任务等稳定身份`events`谁在何时做了什么，导致什么`state_facts`人物、关系、资源、知识、规则当前怎样`rules`条件、限制、代价、例外、违规后果`reader_promises`读者正在期待什么`payoffs`哪个期待得到怎样的兑现`future_obligations`未来事件 Hook、伏笔、作者暗稿`provenance`每条记录来自哪里、置信度如何、是否确认

建议的顶层结构：

```
outline_package:
  meta:
    core_schema_version:
    module_versions:
    source_hash:
    extraction_run_id:

  narrative_units: {}
  entities: {}
  events: {}
  state_facts: {}
  rules: {}
  reader_experience:
    promises: {}
    payoffs: {}
    hooks: {}
    emotion_curve: {}
  future_obligations: {}
  provenance: {}

  extensions:
    xuanhuan: {}
    esports: {}
    urban: {}

  derived_views:
    continuation_v2: {}
    storyboard_v1: {}
    interactive_v1: {}
```

`derived_views` 可以缓存，但必须能从核心重新生成，不能反过来修改核心事实。

### **题材可选池不要做成杂物箱**

用命名空间隔离：

```
extensions:
  xuanhuan:
    cultivation_realms:
    bloodlines:
    tribulation_rules:
    artifact_grades:

  esports:
    match_state:
    economy:
    skill_cooldowns:
    draft_bans:
    tournament_bracket:

  urban:
    wealth:
    social_identity:
    evidence_chain:
    legal_risk:

  rule_horror:
    rules:
    exceptions:
    violation_history:
    safe_zones:
```

金手指不应只属于玄幻模块。

固定核心里保存通用结构：

```
capability:
  trigger:
  input:
  output:
  cost:
  limit:
  cooldown:
  growth_path:
  known_by:
```

题材模块再补充“修为境界”“系统积分”“电竞技能冷却”等专用解释。

### **适配层只改消费口径，不改事实**

例如同一个“主角公开击败宿敌”的事件：

**续写视图需要：**

- 前因
- 当前实力规则
- 宿敌后续反应
- 未兑现承诺
- 下一章升级压力

**分镜视图需要：**

- 场景位置
- 动作顺序
- 人物站位
- 视觉反差
- 群体反应
- 高光瞬间
- 连续性锚点

**互动叙事视图需要：**

- 可选行动
- 前置条件
- 状态修改
- 失败分支
- 不可逆后果

事实只存一遍，视图各取所需。

## **字段演化与版本化**

建议同时记录三种版本：

```
core_schema_version:2.1.0
module_versions:
  xuanhuan:1.4.0
  esports:1.1.0
view_contract_versions:
  continuation:3.0.0
  storyboard:2.2.0
```

版本规则可以这样定：

- 加可选字段：小版本升级
- 改字段含义、删除字段、改变必填规则：大版本升级
- 校验规则修正、文档补充：修订版本升级
- 已发布字段永不改作其他含义
- 已删除字段的编号或 ID 永不复用
- 同一个大版本中，不突然新增必填字段

JSON Schema 支持明确声明所用规范版本；Protobuf 的兼容规则也强调不要复用字段编号、不要随意更改类型或新增会破坏旧数据的必填要求。([JSON Schema](https://json-schema.org/blog/posts/stable-json-schema?utm_source=chatgpt.com))

### **空值不能只有 `null`**

你们现在 F1 低，部分问题可能正是“没有”与“没抽出来”混在一起。

建议统一：

```
field_status:
  value:
  status:
    -present
    -absent_confirmed
    -unknown
    -not_applicable
    -not_extracted
    -conflicted
  confidence:
  evidence_refs:
```

这样能区分：

- 正文明确没有变化
- 这个题材不适用
- 模型没找到
- 两处文本互相冲突
- 金标没有标，但模型抽到了

这会直接改善错误分析，避免把所有空字段都算成同一种失败。

## **下游取数合同**

下游不要直接写：

```
outline.reader_experience.payoffs[3].xxx
```

而应请求具名视图：

```
get_outline_view(
  view="storyboard_scene_v2",
  scope="chapter_81",
  max_tokens=8000
)
```

每份合同明确：

```
consumer:storyboard_scene_v2

requires:
  core_schema:">=2.1,<3.0"
  mandatory:
    -scene.location
    -scene.participants
    -beats.action
    -beats.reader_effect
  optional:
    -visual_highlight
    -crowd_reaction

fallback:
  missing_visual_highlight:infer_from_payoff
  missing_location:return_blocked

output_limit:
  max_scenes:12
  max_beats_per_scene:8
```

还要给每个下游保存一组“消费者合同测试”：

- 旧大纲升级后，续写视图是否仍可生成
- 新字段加入后，分镜是否仍能读取
- 某可选模块缺失时，互动叙事是否有降级方案
- 必填数据不全时，是阻断还是允许推断

消费者合同测试的思路，就是只检查某个消费者真正依赖的那部分接口，而不是要求所有调用方一起理解整套大纲。([docs.pact.io](https://docs.pact.io/?utm_source=chatgpt.com))

## **代价与风险**

- 固定核心太大：每次提取都很重，弱模型漏字段更多。
- 固定核心太小：核心含义散落到题材模块和下游私有逻辑里。
- 扩展字段无限增长：同一概念出现五种写法。
- 派生视图可被人工修改：产生多个互相冲突的版本。
- 版本只写数字、不提供迁移程序：版本号等于摆设。

建议建立“字段入核心”的硬门槛：

> 至少两个题材需要，至少两个下游消费，缺失会造成叙事含义损失，而不仅是表现细节损失。
> 

## **反面核查：固定核心定错的典型案例**

最典型的错法是：

> 固定核心只记录“客观世界发生的动作和结果”，没有角色认知、读者认知、期待与兑现。
> 

后果会全线扩散：

- 纯对话章被判定成“低变化”
- 身份揭示只记成“说了一句话”
- 续写模型不知道读者已经知道、角色还不知道
- 建议层错误要求“增加事件”
- 分镜错过震惊反应和信息揭示高光
- Hook 系统不知道哪个谜底已经对读者兑现
- 互动分支让角色使用自己尚不知道的信息

预防手段：

1. 用你们的八类难章做“核心表示验收”，不只做提取 F1。
2. 每类章节都问：**重要叙事变化能否完全落到正式字段，而不是塞进备注？**
3. 新核心先影子运行，不直接替换生产版。
4. 保留临时的 `unmodeled_claims`，但统计使用率；高频内容必须转正式字段。
5. 每次核心改动都跑所有下游的合同测试。
6. 迁移期双写旧字段和新字段，对比输出差异。

# **三｜多遍提取流水线**

## **结论**

建议做成**八个逻辑阶段，但不要固定八次大模型调用**。

正常章节应是：

- 两个程序阶段
- 三到四个模型阶段
- 一个条件式核查阶段

难章再增加定向复查。

对于 DeepSeek 档执行模型，最稳的原则是：

> **流程决定它什么时候做什么；模型只在局部语义判断上拥有选择权。**
> 

不要让模型自己决定“整章下一步该做什么”，也不要每一遍都把上一遍的自然语言总结当成真相继续传下去。研究和工程经验都表明，固定工作流适合边界清楚的任务；模型没有外部证据时反复自我反思，不但未必纠错，还可能把正确答案改坏。([Anthropic](https://www.anthropic.com/engineering/building-effective-agents))

## **开工前先处理 F1 口径**

F1 只有 0.22，不宜直接得出“单轮一定不行，改八遍就行”。

先把错误拆成五类：

**错误类型要回答的问题**金标口径两名标注者会不会对同一字段给不同答案Schema 覆盖正确答案是否根本无处可填欠产出正文有、金标有，模型没输出误产出模型输出了正文不支持的内容对齐错误内容抽到了，但实体、时间、字段或粒度错了

建议抽八章中的一部分做双人复标和裁决，并分别统计：

- 各字段 Precision、Recall、F1
- 各章型指标
- “未提取”比例
- 无证据输出比例
- 实体对齐错误
- 时间对齐错误

否则多遍流水线可能只是在更高成本地迎合一个不稳定金标。

## **八个逻辑阶段**

### **P0｜程序预处理**

不调用模型。

做这些事：

- 清洗章节文本
- 保留段落、句子、对白编号
- 识别章节边界和明显场景分隔
- 计算文本哈希，支持缓存
- 拉取上一章结束快照
- 拉取当前活跃 Hook、规则和期待
- 给每一段建立 `span_id`

输出：

```
source_packet:
  chapter_id:
  source_hash:
  paragraphs:
  prior_snapshot_ref:
  active_promises:
  active_future_hooks:
```

### **P1｜结构地图与章型识别**

模型只判断：

- 场景如何分
- 叙述视角
- 正叙、倒叙、回忆还是梦境
- 主要时间锚点
- 章节属于哪些难章类型
- 哪些段落是动作、对白、信息说明、内心判断

不让它抽完整账本。

输出：

```
structure_map:
  scenes:
  narration_mode:
  time_shifts:
  chapter_type_tags:
  risky_spans:
```

### **P2｜实体、指代与时间对齐**

专门处理：

- “他”“队长”“老者”分别是谁
- 同名人物
- 伪装身份
- 组织、地点、物品
- 事情发生的故事时间
- 读者看到它的叙述顺序

这一遍的结果必须允许“不确定候选”，不能逼模型胡选：

```
alias_resolution:
  mention:"黑衣人"
  candidates:
    -entity_id:E_17
      confidence:0.63
    -entity_id:UNKNOWN_NEW_ENTITY
      confidence:0.37
```

### **P3｜原子事件与事实候选**

把正文拆成最小可验证陈述：

```
claim:
  claim_id:
  type:event | state | knowledge | relationship | rule
  subject:
  predicate:
  object:
  valid_from:
  evidence_refs:
  confidence:
```

这一遍只负责“正文说了什么”，不要同时要求模型概括、诊断和写章末总结。

### **P4｜变化归并与因果检查**

程序先把 P3 候选应用到上一章快照：

```
上一状态 + 候选变化 → 新状态
```

自动检查：

- 同一时刻两个互斥状态
- 死亡角色突然行动
- 物品同时被两人持有
- 实力规则超限
- 角色使用未知情报
- 回忆事件错误覆盖当前状态

只有发生冲突时，再调用模型读取对应原文片段裁决。

### **P5｜读者体验提取**

与 P4 可以并行，不必等待完整状态归并。

专门提取：

- 这章让读者期待什么
- 哪些旧期待得到推进或兑现
- 爽点依赖了什么铺垫
- 金手指展示了哪条规则
- 情绪由什么转向什么
- 章末留下了什么具体问题
- 哪些段落适合作为漫剧高光

这一遍必须同时看到原文和 P1 的结构地图，不能只看 P3 摘要。

### **P6｜覆盖核查与定向补抽**

这里不是让模型自由说“请反思”。

程序先生成明确问题，例如：

```
第 41～53 段存在 4 个新专有名词，但 P3 没有规则事实。
请只检查这些段落是否包含：
1. 新规则
2. 新能力限制
3. 角色认知变化
```

核查方式采用“草稿—生成核查问题—独立查证—合并”的思路，比让同一模型看着自己的答案泛泛反思更稳。([arXiv](https://arxiv.org/abs/2309.11495?utm_source=chatgpt.com))

简单章节、高置信章节可跳过这一阶段。

### **P7｜程序组装与派生视图**

程序负责：

- 生成章末快照
- 生成章间交接
- 更新实体时间线
- 更新期待／兑现账
- 更新 Hook 状态
- 生成续写视图
- 生成分镜视图
- 记录差异补丁

模型最多负责写一段供作者阅读的自然语言概览，不能负责最终落库。

## **难章型专用核查**

**章型必查项目**转线新旧线交接、未兑现期待、地点与人物状态高潮连续事件顺序、规则使用、围观反应、余波纯对话知识、立场、决策、关系权力变化回忆插叙故事时间与叙述顺序分离弱变化期待是否加压、情绪是否沉淀、是否为后续铺垫信息倾泻哪些是规则、哪些是角色听说、哪些是世界真相开篇核心欲望、第一期待、金手指承诺、初始限制卷末大期待兑现情况、未清债务、新卷压力与 Hook

这张表应直接进入流程路由，不要只写在提示词说明里。

## **遍间传什么**

不要传一段段自然语言总结。

统一传“工件信封”：

```
artifact:
  artifact_type:
  schema_version:
  chapter_id:
  producer_stage:
  source_hash:

  claims:
  evidence_refs:
  unresolved_questions:
  coverage:
  confidence:
  validation_errors:
```

所有重要判断都能回到原文证据。上一遍错了，下一遍才有机会重新读取原文纠正，而不是继承错误摘要。

## **主动与被动怎么拿捏**

建议大约九成流程由程序强制：

**程序决定：**

- 哪个阶段运行
- 允许读取什么
- 允许写哪些字段
- 何时重试
- 何时升级模型
- 何时阻断
- 如何合并
- 如何写入权威账本

**模型可以决定：**

- 某句话对应哪个候选实体
- 一个事件应拆成几个原子变化
- 是否存在语义歧义
- 在限定列表中选择一次定向复查动作
- 提交“无法判断，需要原文补证据”

可以给模型一个很小的下一步枚举：

```
next_action:
  -accept
  -request_source_span
  -propose_new_entity
  -mark_conflict
  -ask_targeted_recheck
```

禁止：

- 任意跳过阶段
- 自己反复循环
- 直接改权威状态
- 自己删除冲突证据
- 无限制调用其他 Tool

## **代价与风险**

成本控制手段：

- 按章节文本哈希缓存 P1～P5
- P4、P7尽量程序化
- P5与P4并行
- 简单章节跳过 P6
- 只把冲突片段送去复查，不重读整章
- 新增一遍前，必须证明它修正了哪类错误
- 每遍记录“新增正确项、引入错误项、净收益”

## **反面核查：什么时候多遍更差**

出现下面任一情况，多遍可能比单轮还差：

- 每遍只看到上一遍总结，看不到原文
- 每遍都重新改写全部 JSON
- 合并器靠模型自由判断，没有稳定规则
- 同一个错误被复制到所有后续阶段
- 简单章也强制跑完整流程
- 金标不接受额外正确事实，召回提升反而被算成误报
- 章内细节被过早压成一句话
- 同一模型既生成又裁判，没有独立证据
- 加一遍只增加字段数量，没有提高最终下游效果

**需补材料：八章逐字段错误表、标注一致率、模型每阶段 token 成本、平均冲突率、当前 JSON 中最常欠产出的字段。**

---

# **四｜作者建议层**

## **结论**

建议层应该是**有证据的诊断与修改选项**，不是自动改稿器。

默认输出：

> 这章最伤追读的 1～3 个问题
> 
> 
> → 证据在哪里
> 
> → 为什么伤害读者体验
> 
> → 最小怎么改
> 
> → 改动会影响哪些长线内容
> 

不要默认输出一篇“更好的重写稿”。

现有研究显示，大模型能给出具体反馈，但经常漏掉故事中最大的那个问题，也会把正面和负面反馈判断反；让大模型单独做裁判，还会受到位置、篇幅和偏好自身写法等偏差影响。([arXiv](https://arxiv.org/abs/2507.16007))

## **可操作方案**

### **建议对象固定成可验证结构**

```
diagnostic:
  issue_id:
  issue_type:weak_payoff | slow_pace | rule_confusion | weak_hook
  severity:
  confidence:

  evidence_refs:
  counter_evidence_refs:

  reader_harm:
    -expected_payoff_delayed_without_progress
    -first_value_arrives_too_late

  affected_promises:
  affected_rules:
  affected_future_hooks:

  recommendation:
    goal:
    minimal_patch:
    stronger_option:
    visual_adaptation_option:

  preserve:
    -character_voice
    -hidden_identity_timing

  tradeoffs:
  verification_test:
```

`counter_evidence_refs` 很重要。诊断模型必须主动找“也许这段并不拖”的证据，减少一看到安静段落就喊删。

### **一次只提最重要的问题**

商业连载最怕建议层平均用力：

- 台词可以更精练
- 环境描写可以更生动
- 人物动机可以更明确
- 节奏可以更紧凑
- 冲突可以更激烈

这种话看起来全面，实际无法执行。

建议固定：

- 一个主问题
- 最多两个次问题
- 每个问题最多两个修改方向
- 明确“不建议动”的亮点

### **先诊断，再选择是否生成改稿**

工作台分三档：

1. **只诊断**：指出问题和证据。
2. **给改法**：提供最小改动与强改方案。
3. **生成补丁**：作者明确选择后，才生成局部文本差异。

不要一上来重写整章。创作研究发现，过早给出完整 AI 方案可能让创作者被现成思路黏住，降低后续方案的多样性；许多创作者也更希望自己决定 AI 在何时、以何种方式介入。([arXiv](https://arxiv.org/html/2403.11164v1))

### **建议质量怎么立秤**

分四层评价。

#### **A. 诊断有没有找对**

- Top-1 问题命中率
- 证据是否真的支持判断
- 是否漏掉更严重的问题
- 是否把正常铺垫误判成拖沓
- 是否识别了规则、期待和长线影响

#### **B. 建议能不能执行**

- 作者能否在十分钟内理解改什么
- 修改范围是否清楚
- 是否给出可选择的强弱档
- 是否保留作者原来的亮点和风格
- 是否会破坏后续 Hook

#### **C. 作者是否认可**

工作台记录：

```
接受
部分接受
拒绝
稍后撤销
改成作者自己的方案
```

“稍后撤销率”比当场点击接受更有价值，因为很多建议看起来合理，写进去才发现伤长线。

#### **D. 读者结果有没有改善**

可以观察：

- 章节读完率
- 下一章进入率
- 追更／加书架变化
- 评论中的困惑、爽点反馈
- 同类章型的历史表现

但不能看到数据下跌，就认定是这一条建议造成的。流量来源、推荐人群、更新时间、作品阶段都会干扰。更稳的做法是同类章节对照、作者盲评、小流量实验和长期撤销率一起看。番茄官方创作内容也建议结合章节完成曲线、后续追读等数据定位掉点，而不是只凭主观感觉。([番茄小说网](https://fanqienovel.com/writer/zone/article/7626644363652644889))

## **代价与风险**

建议层会天然倾向于：

- 更强冲突
- 更短铺垫
- 更早揭密
- 更多反转
- 更多章末危险

短期可能刺激，长期会导致所有书一个味道。

所以建议层必须读取：

- 作者意图
- 本卷计划
- 当前节奏位置
- 已经连续用了哪些爽点模式
- 哪些人物设定不可动
- 哪些伏笔尚不能揭开
- 当前章节承担的是铺垫、兑现还是余波

## **反面核查：哪些建议会伤害作者**

高风险建议包括：

- “每章都加一个大高潮”
- “这一段没有事件，建议全部删除”
- “把谜底提前说清楚”
- “把人物对白改得更直接”，却毁掉人物声音
- 为了章末钩子强行制造误会
- 为了爽点让角色违反既定智商和规则
- 只优化当前章，导致三十章后的大兑现失效
- 给所有都市文都加打脸，给所有玄幻文都加越级战斗
- 直接把作者方案替换成模型最熟悉的套路

拦截规则：

- 没有正文证据，不允许进入高置信建议
- 涉及多章、角色核心动机、主线结局时，必须标记“高影响”
- 建议破坏作者锁定项时直接阻断
- 大爽点提前、人物死亡、身份揭示、能力规则修改，必须人工确认
- 同一种建议在连续章节频繁出现时触发“模板疲劳”警报
- 建议无法说清“对哪个读者期待有帮助”，降级为普通润色意见

---

# **五｜未来事件 Hook**

## **结论**

未来事件 Hook 要做成**有触发条件、有生命周期、有冲突规则的未来义务对象**，不能只是一条备注。

还要把两种 Hook 分开：

- `reader_hook`：章末让读者点下一章的悬念
- `future_hook`：未来某个条件成立时，系统要检查的规划事项

它们可以通过同一个 `promise_id` 连接，但不能混成一张表。

## **可操作方案**

### **Hook 登记结构**

```
future_hook:
  hook_id:FH_009

  title:某人进入天渊副本后触发旧敌追杀
  origin_ref:CH_035_B07
  linked_promise_ids: [P_044]

  visibility:
    -author_only
    -reader_seeded
    -character_known

  trigger:
    type:compound
    all:
      -event.type == enter_instance
      -event.actor == E_LIN
      -event.target == INSTANCE_ABYSS

  check_keys:
    -entity:E_LIN
    -event:enter_instance
    -location:INSTANCE_ABYSS

  preconditions:
    -E_LIN.level >= REALM_3
    -E_ENEMY.status == alive

  desired_effect:
    -escalate_main_conflict
    -pay_off_old_enemy_seed

  minimum_payoff:
    -old_enemy_identity_confirmed

  allowed_variants:
    -direct_ambush
    -proxy_attack
    -false_ally_betrayal

  hardness:hard
  priority:high

  active_window:
    earliest_story_time:
    latest_story_time:

  dependencies:
  conflicts:
  fallback:

  status:dormant
  last_checked_at:
  resolution_ref:
```

### **“有机会就检查”怎样运行**

每当一章正式写入权威大纲，程序生成变化键：

```
change_keys:
  -entity:E_LIN
  -location:INSTANCE_ABYSS
  -event:enter_instance
  -story_time:DAY_30
  -inventory:ARTIFACT_07
```

Hook 系统不扫描全部 Hook，只从索引里取匹配项：

```
变化键
→ 找到候选 Hook
→ 检查前置条件
→ 标记 eligible / blocked / expired
→ 交给章节规划器排序
```

排序后只向创作模型提供少量候选：

```
eligible_hooks:
  -hook_id:FH_009
    fit_reason:当前正在进入目标副本
    urgency:high
    conflict_risk:low
```

这与耐久工作流中“计时器、条件、外部信号触发”的处理很接近：条件先登记，状态变化时再恢复检查，而不是靠人工到处翻备注。([docs.temporal.io](https://docs.temporal.io/develop/typescript/workflows/timers?utm_source=chatgpt.com))

### **Hook 生命周期**

```
idea
→ dormant
→ eligible
→ scheduled
→ partially_paid
→ paid
```

异常分支：

```
blocked
expired
deferred
cancelled
superseded
```

任何取消和延期都要保留原因，不能直接删除，否则作者以后会不知道某个伏笔是忘了，还是主动放弃了。

### **与逐章账本怎样联动**

章前：

- 章节规划器读取活跃期待
- 查询本章可能触发的未来 Hook
- 选择本章推进、兑现或继续隐藏的项目

章后：

- 提取流水线判断是否已经触发
- 检查是否真正兑现最低要求
- 更新 Hook 状态
- 更新关联期待
- 生成新的余波或后续 Hook

例如：

```
FH_009 触发
→ 旧敌现身
→ P_044 从“等待旧敌回归”变为“已兑现”
→ 新建 P_052：“旧敌背后的宗门是谁”
→ 新建 reader_hook：“宗门使者已在出口等候”
```

## **代价与风险**

- Hook 登记太细，作者像在维护项目管理软件。
- 条件写得太死，会限制自由生长。
- Hook 全部暴露给生成模型，会让剧情机械兑现。
- 隐藏计划与读者已知承诺混在一起，裁决优先级错误。
- 回忆中出现“进入副本”，可能错误触发当前 Hook。

因此：

- 条件尽量写“效果义务”，不要写死具体场面
- 同时保留多个允许方案
- Hook 检查必须使用 `story_time`，不能只看章节顺序
- 生成模型只拿当前相关候选，不拿全部暗稿
- 作者可设置硬承诺、软计划、灵感种子三档

## **反面核查：Hook 太多且冲突怎么办**

裁决顺序建议这样定：

1. 世界规则、作者锁定内容不可违反。
2. 已经让读者看见的承诺，优先于作者私下灵感。
3. 已投入大量铺垫的承诺，优先于刚登记的新点子。
4. 主线和当前卷目标，优先于支线装饰。
5. 临近兑现窗口的 Hook，优先于没有期限的 Hook。
6. 爽点机制近期重复过多时，降低优先级。
7. 同章容量不足时，只激活少量主 Hook，其余延期。

系统可以给 Hook 建冲突图：

```
FH_09 与 FH_12 不能同时发生
FH_09 依赖 FH_03
FH_14 可与 FH_09 合并
FH_17 会提前暴露 P_21
```

处理动作只有五种：

- 合并
- 延期
- 降为软计划
- 改用替代方案
- 取消并留痕

两个“读者已知＋硬承诺”的 Hook 发生不可调和冲突时，不让模型偷偷选一个，直接交给作者裁决。

# **六｜Tool 拆分与网页画布**

## **结论**

内部可以有十几个 Tool，但作者界面不应展示十几个按钮。

**内部按可测试的业务动作拆；外部按作者目标组合成五到七条工作流。**

作者关心的是：

- 导入这本书
- 继续写下一章
- 检查这章哪里有问题
- 拆成漫剧
- 管理未来剧情
- 做一个互动分支

他不该先理解 `resolve_alias`、`materialize_snapshot`、`reconcile_patch` 分别是什么。

## **可操作方案**

### **内部 Tool 分三类**

#### **纯读取，不改权威数据**

```
query_outline_view
query_entity_state
inspect_active_promises
inspect_future_hooks
validate_consistency
diagnose_chapter
```

#### **生成候选补丁**

```
extract_chapter_outline
plan_next_chapter
generate_chapter_draft
adapt_storyboard
generate_interactive_branch
propose_hook
propose_revision
```

#### **明确写入**

```
apply_outline_patch
register_future_hook
resolve_future_hook
migrate_outline_schema
import_source
```

写入类 Tool 数量要少，而且只有它们能改权威大纲。

### **推荐的内部边界**

一个 Tool 最好同时满足：

- 只有一个清楚的业务结果
- 只有一种主要副作用
- 成功与失败能被程序判断
- 可以单独重试
- 输入输出边界稳定
- 权限要求明确

例如：

`extract_chapter_outline` 的职责是产出候选补丁，不直接写入。

`apply_outline_patch` 的职责是校验并落库，不重新理解正文。

这样提取错了，可以重新提取；落库失败，可以修补丁；不会一个 Tool 既读正文、又改状态、又生成分镜、又登记 Hook。

### **Tool 自描述模板**

```
name:extract_chapter_outline

purpose:
  从一章正文中提取事件、状态变化和读者体验候选，
  输出大纲补丁，不直接修改权威大纲。

use_when:
  -新章节正文已导入
  -修改正文后需要重新提取

do_not_use_when:
  -只想查询已有大纲
  -只想生成下一章
  -没有原始正文

reads:
  -source_chapter
  -prior_snapshot
  -active_promises

writes:
  -none

returns:
  -candidate_outline_patch

preconditions:
  -source_hash_present
  -core_schema_version_supported

side_effects:
  -none

idempotency:
  同一 source_hash 与同一模型版本应返回语义等价结果

failure_codes:
  -SOURCE_MISSING
  -SCHEMA_UNSUPPORTED
  -AMBIGUOUS_TIMELINE
```

描述中必须写清“什么时候不要用”。官方工具调用建议也强调，函数用途和参数说明越明确，模型越不容易选错；真实工具评测中，重复调用、误调用往往能反推工具边界或描述存在问题。([OpenAI 开发者](https://developers.openai.com/api/docs/guides/function-calling))

### **不要一次把全部 Tool 塞给 Agent**

按照当前工作流只开放相关 Tool：

**导入阶段：**

```
import_source
extract_chapter_outline
validate_consistency
apply_outline_patch
```

**续写阶段：**

```
query_outline_view
plan_next_chapter
generate_chapter_draft
diagnose_chapter
```

**漫剧阶段：**

```
query_outline_view
adapt_storyboard
validate_visual_continuity
```

工具数量太多会占用上下文，也会增加选错工具和参数的概率；渐进式发现、按阶段暴露工具更稳。([Model Context Protocol](https://modelcontextprotocol.io/llms-full.txt))

## **网页端画布怎么摆**

### **左侧：故事树**

```
作品
├─ 卷
│  ├─ 剧情段
│  │  ├─ 章节
│  │  │  ├─ 场景
│  │  │  └─ 节拍
```

可以按人物线、时间线、期待线切换。

### **中间：当前任务画布**

作者看到的是目标卡：

- 导入并整理
- 规划下一章
- 诊断当前章
- 改成漫剧分镜
- 安排未来事件
- 创建互动分支

每一步展示：

```
选择范围
→ 查看系统准备使用的数据
→ 运行
→ 查看大纲差异
→ 勾选接受项
→ 写入
```

### **右侧：持续上下文**

固定显示：

- 当前核心期待
- 尚未兑现的承诺
- 金手指规则和冷却
- 当前人物状态
- 即将到期的 Hook
- 最近重复过的爽点模式
- 一致性警告

### **底部：运行记录**

作者能看到：

- 哪个 Tool 运行过
- 读取了哪些章节
- 改了哪些字段
- 为什么失败
- 是否可撤销

## **代价与风险**

### **Tool 切太碎的死法**

- 一个任务要调用十几次
- 中途一次失败，后面全断
- Agent 把上一步 ID 传错
- 同一状态被多个小 Tool 重复写
- 上下文全被工具说明占满
- 作者无法理解系统在干什么
- 评测只看到单 Tool 成功，整体任务却失败

### **Tool 切太粗的死法**

- 一个 `write_novel` 包办所有事情
- 出错时不知道错在提取、规划还是生成
- 无法局部重试
- 每次都重读全书
- 权限和副作用混在一起
- 不能单独评测某项能力
- 用户只改一个 Hook，也被迫重跑整章

## **反面核查：怎么判断粒度对不对**

给每个 Tool 过七道检查：

1. 能不能用一句话说明成功结果？
2. 失败后能不能只重试它，而不重跑无关步骤？
3. 它是否只有一个权威写入责任？
4. 它是否需要独立权限或作者确认？
5. 两个 Tool 是否超过七成场景总是一起出现？是的话考虑组合。
6. 一个 Tool 的不同能力是否经常被独立调用？是的话考虑拆开。
7. 给 100 个真实作者意图让模型选 Tool，误选是否集中在同一对 Tool？集中就说明边界或描述不清。

“七成”和“100 个样本”是团队可先采用的评测起点，不是固定标准。

---

# **七｜爽点、规则与追读结构化**

## **结论**

**爽点不能只记“类型＋强度”，更不能只统计一章有几个爽点。**

真正该记的是一条完整链：

> **读者想要什么**
> 
> 
> → **为什么越来越想要**
> 
> → **规则允许怎样兑现**
> 
> → **发生了什么反转或胜利**
> 
> → **谁看见、谁受影响**
> 
> → **世界状态有什么真实改变**
> 
> → **兑现后又产生什么新期待**
> 

所以建议把这部分建成六本互相连接的账：

1. 期待账
2. 铺垫与压力账
3. 兑现／爽点账
4. 章末钩子账
5. 金手指与规则账
6. 情绪与疲劳账

番茄官方创作内容反复强调开篇期待、金手指对后续期待的牵引、章末悬念和剧情推进；微短剧相关行业材料也强调冲突集中、反转密集、节奏快，同时警惕公式滥用带来的审美疲劳。([番茄小说网](https://fanqienovel.com/writer/zone/article/7605818896267870270))

## **固定核心该记什么**

### **1. 期待账 `promise_ledger`**

不是只有“伏笔”，而是所有让读者继续看的未完成欲望。

```
reader_promise:
  promise_id:P_019
  opened_at:CH_003_B04

  desire:
    type:status_reversal
    description:主角公开证明自己不是废物

  target:
    character:E_LIN
    opponent:E_ZHAO

  reader_visibility:explicit
  salience:high

  expected_window:
    earliest:CH_010
    latest:CH_030

  progress:
    -chapter:CH_008
      change:获得初步能力
    -chapter:CH_016
      change:第一次小范围证明

  status:
    -open
    -progressing
    -partially_paid
    -paid
    -subverted
    -deferred
    -abandoned

  payoff_refs:
```

期待来源可以是：

- 主角目标
- 敌人压迫
- 金手指承诺
- 身份谜团
- 规则悬念
- 感情关系
- 宝物或副本
- 读者知道但角色不知道的信息差
- 已经种下的报复、证明、救援、晋级

### **2. 铺垫与压力账**

爽点不是单独出现的烟花。

```
pressure_unit:
  pressure_id:
  linked_promise_id:
  source:
  intensity:
  reader_visibility:
  escalation_type:
  repetition_signature:
  consequence_if_unresolved:
```

例如“主角亮出身份，全场震惊”是否爽，取决于：

- 之前有没有真实压制
- 压制持续多久
- 读者是否明确想看反转
- 对手是否值得被打败
- 身份规则是否可信
- 反转后是否真的改变地位

没有压力和期待，单纯“全场震惊”只是模板动作。

### **3. 兑现／爽点账 `payoff_ledger`**

```
payoff:
  payoff_id:PAY_031
  linked_promises: [P_019]
  beat_ref:CH_021_B06

  type:
    -competence
    -status_reversal
    -justice
    -gain
    -reveal
    -protection
    -strategic_win
    -emotional_validation
    -spectacle
    -relationship

  mechanism:
    主角依照已展示规则，以隐藏技能反杀高阶对手

  setup_refs:
  rule_refs:
  gold_finger_refs:

  intensity:
  earnedness:
  novelty:
  surprise:
  clarity:

  witness:
    scope:public
    entities: [CROWD, MASTER, RIVAL]

  reactions:
    -fear
    -regret
    -admiration

  state_consequences:
    -reputation_increased
    -enemy_faction_escalated
    -tournament_seed_changed

  cost_paid:
  aftershock_refs:

  signature:
    type:status_reversal
    mechanism:hidden_power_reveal
    target:arrogant_rival
    witness:public_crowd
```

`signature` 用来识别套路重复。

例如连续三次都是：

```
被轻视
→ 主角亮隐藏实力
→ 对手震惊
→ 围观者改口
```

即使每章都有高强度爽点，读者也可能开始疲劳。

### **4. 章末钩子账 `reader_hook_ledger`**

一个有效章末钩子至少应有下面一种具体东西：

- 一个明确未回答的问题
- 一个即将发生的行动
- 一个迫近的危险
- 一个新机会
- 一个需要立即选择的两难
- 一个被部分揭开的秘密
- 一个有期限的倒计时

字段：

```
reader_hook:
  hook_id:
  chapter_end_ref:

  hook_type:
    -question
    -danger
    -opportunity
    -reveal
    -countdown
    -choice
    -reversal

  concrete_object:
  next_expected_action:
  cost_or_stakes:
  deadline:
  linked_promises:
  specificity:
  click_impulse:
```

“更大的危险正在靠近”通常是弱钩子。

“宗门执法使已经拿着主角的追杀令抵达城门”才是具体钩子。

### **5. 金手指与规则账**

金手指如果没有规则，就会从爽点发动机变成作者随意改答案。

```
gold_finger:
  capability_id:
  owner:
  acquired_at:

  trigger:
  inputs:
  outputs:

  costs:
  cooldown:
  limits:
  exceptions:

  growth_path:
  current_level:
  unlock_conditions:

  reader_disclosure:
  known_by_characters:

  usage_history:
  exploit_history:
  failure_history:

  related_rules:
```

每次使用要记：

- 是否满足触发条件
- 消耗了什么
- 是否进入冷却
- 是否暴露给他人
- 是否产生长期后果
- 是否展示了新规则
- 是否违反了旧规则

规则对象建议带测试例：

```
rule:
  rule_id:
  statement:
  scope:
  conditions:
  expected_result:
  exceptions:
  violation_consequence:
  known_by:
  reader_known_from:
  positive_examples:
  negative_examples:
```

这样一致性校验不是问模型“合不合理”，而是让它比对规则实例。

### **6. 情绪与疲劳账**

必须把**角色情绪**与**读者情绪**分开。

主角可能非常痛苦，但读者正在期待反击；主角可能非常得意，但读者已经觉得重复。

```
emotion_point:
  beat_ref:

  protagonist_emotion:
  reader_emotion:

  reader_valence:negative_to_positive
  arousal:low_to_high

  function:
    -pressure
    -anticipation
    -release
    -payoff
    -afterglow
    -recovery
    -new_tension

  linked_promise:
```

对 Wattpad 大规模章节的研究表明，读者对后续发展的期待、期待的不确定性以及最终惊讶程度，可以帮助解释读者对叙事的反应；这支持把“期待—兑现”当成结构对象，而不是只做情绪标签。([arXiv](https://arxiv.org/html/2412.15239v1))

## **提取端怎么诊断“爽点不足”**

不要只看 `payoff_count`。

### **爽点不足的可靠信号**

- 高显著期待连续多章没有任何推进
- 铺垫强，兑现弱或没有兑现
- 发生了强事件，却没有连接任何读者欲望
- 大胜之后没人反应、地位不变、资源不变
- 金手指突然给答案，没有规则展示或代价
- 同一种爽点签名近期连续出现
- 大量压力积累，但没有阶段性小兑现
- 兑现发生得太轻，读者还没意识到它的重要性
- 爽点只存在于作者解释里，场景中没有可感知结果

### **节奏拖的可靠信号**

“字多”不等于拖，“没推进”才更接近拖。

每个节拍检查是否至少改变一项：

```
行动局势
人物目标
人物决策
知识
关系权力
资源
规则理解
期待压力
危险程度
```

连续多个节拍都没有变化，同时也没有加强期待，就很可能在原地踏步。

信息说明也不一定拖。它若立刻改变了人物选择，或者让读者重新理解危险，就有叙事价值。

### **钩子弱的可靠信号**

- 只说“事情还没结束”，没有具体对象
- 没有下一步行动
- 没有代价、危险或机会
- 读者不知道下一章能看到什么
- 钩子与本章核心期待无关
- 每章都用“门被推开了”“电话响了”式假悬念

## **生成端怎么保证爽点与追读**

不要给模型下死指标：

```
本章必须有 3 个爽点、2 个反转、1 个打脸
```

它一定会刷数量。

给它“读者体验合同”：

```
experience_plan:
  primary_promise_to_advance:P_019

  required_progress:
    type:partial_payoff
    result:主角第一次在公开场合证明实力

  setup_to_use:
    -PRESSURE_011
    -RIVAL_CONTEMPT_004

  rule_to_demonstrate:
    -SKILL_COOLDOWN_RULE

  desired_pattern:
    -pressure
    -apparent_failure
    -rule_based_reversal
    -public_reaction
    -lasting_consequence
    -new_hook

  avoid_recent_signatures:
    -hidden_identity_public_reveal
    -elder_suddenly_rescues

  ending_hook:
    type:enemy_escalation
    linked_promise:P_025

  must_preserve:
    -主角尚不能连续使用技能
    -师父不知道主角真实身份
```

这里控制的是**功能与因果**，不是固定套路台词。

章节位置不同，体验合同也不同：

**章型体验要求**开篇尽快给核心欲望、危险或金手指承诺过渡余波、关系变化、新压力，不能只搬场景信息章信息必须改变理解、选择或危险高潮兑现、规则运用、反应和真实后果高潮后给余韵和收益确认，再开启新期待卷末结算主要承诺，同时抛出更大方向

## **分镜与漫剧怎么直接挑高光**

爽点记录里增加派生的视觉评价：

```
visual_payoff_profile:
  frameability:
  before_after_contrast:
  action_clarity:
  spatial_clarity:
  transformation:
  spectacle:
  public_witness:
  reaction_value:
  continuity_cost:
```

挑镜头时，不只挑爆炸最大的那一帧，而是挑三连：

1. **反转前**：主角被压制、众人轻视
2. **峰值**：能力发动或局势翻转
3. **反应与余波**：对手、围观者、环境和状态改变

没有反转前，峰值不够爽；没有反应和余波，爽点像一张独立海报。

视觉故事系统还要额外维护人物、场景、道具和空间连续性，因为逐帧单独生成很容易出现角色外观、站位和环境不一致。([arXiv](https://arxiv.org/html/2604.13452v1))

## **网文与 AI 漫剧口径差多少**

**语义核心差得不大，表现和权重差得很大。**

共同固定核心：

- 读者期待
- 压力与铺垫
- 兑现
- 金手指规则
- 情绪转折
- 章／集末钩子
- 后果与新期待

网文适配层更看重：

- 内心判断
- 战术解释
- 信息差
- 语言气势
- 章节字数内的推进密度
- 章末下一点击
- 规则说明是否容易理解

AI 漫剧适配层更看重：

- 能否外化成动作
- 视觉反差
- 变身、技能、道具和身份展示
- 群体反应
- 场景是否容易生成
- 镜头内人物数量
- 空间连续性
- 单集时长和镜头预算
- 台词能否压短
- 每隔较短时间是否有可见变化

所以这块的切法是：

> **期待、兑现、规则、情绪变化放固定核心；视觉潜力、镜头预算、台词压缩、画面连续性放适配层。**
> 

不要给网文和漫剧各做一套独立爽点账，否则同一事件会产生两套互相冲突的定义。

**需补材料：目标漫剧单集时长、平均镜头数、画面模型能稳定维持的人物数量、平台常见掉点位置。**

## **代价与风险**

把爽点结构化后，模型会立刻学会刷表面指标：

- 多写“全场震惊”
- 多写越级反杀
- 每章安排反派嘲讽
- 频繁发奖励
- 强行制造章末危险
- 所有兑现都越来越大
- 规则不断临时开例外

所以不能给爽点一个公开的总分，让生成模型直接最大化。

## **反面核查：怎么防指标被刷**

### **1. 不用单一总分**

内部可以计算：

```
有效兑现
≈ 强度
× 与期待的相关性
× 铺垫充分度
× 规则可信度
× 新鲜度
× 后果真实性
－ 套路疲劳
－ 情绪透支
－ 规则破坏
```

但生成模型不直接看到这条公式，只看到定性的创作合同。

### **2. 大爽点必须连接期待**

没有 `linked_promise` 的高强度事件，默认只能算“刺激事件”，不能自动算有效兑现。

### **3. 大兑现必须消耗铺垫信用**

系统检查：

- 是否有前期压力
- 是否有明确欲望
- 是否有规则支持
- 是否付出代价
- 是否产生后果

没有这些，就标记为“空降爽点”。

### **4. 对近期套路做签名去重**

签名可以由这些部分组成：

```
爽点类型
+ 触发机制
+ 被打击对象
+ 围观者
+ 结果
+ 章末接法
```

近一段剧情连续相似，自动降低推荐权重。

### **5. 检查余波**

高强度事件后，如果人物关系、地位、资源、敌我局势和新期待都没改变，大概率是“烟花爽点”。

### **6. 做删除测试**

把这个爽点节拍删掉，再问：

- 期待是否仍然同样推进
- 世界状态是否完全不变
- 人物关系是否完全不变
- 下一章是否照样成立

如果全都不变，它很可能只是装饰。

### **7. 允许低谷，但低谷必须有功能**

持续高刺激会透支。

低谷可以承担：

- 确认收益
- 展示代价
- 改变关系
- 让规则变清楚
- 埋下新威胁
- 给下一次兑现蓄压

系统不应把所有低唤醒章节都判成拖沓。

### **8. 生成器与评估器分开**

- 生成器按体验合同写
- 评估器看隐藏的重复度、规则破坏和空降爽点
- 评估器必须引用正文证据
- 关键样本加入人工裁决
- 保留一批“爽点数量高但阅读体验差”的对抗样本

### **9. 真实读者数据只用于校准，不直接当指令**

读完率下降可以提示问题，但不能自动推导出“下一章多加两个打脸”。

更合理的是：

```
某题材
+ 某作品阶段
+ 某章型
+ 某期待状态
```

一起比较，再调整诊断阈值。

---

# **建议的落地顺序**

## **第 1 阶段：先把真相层立稳**

只做四个最小对象：

```
beat_event
state_fact
reader_promise
future_hook
```

同时加入：

```
evidence_ref
story_time
narration_order
field_status
```

这一步还不要急着做十几个 Tool。

## **第 2 阶段：重做八章评测**

把八类难章重新标成：

- 事件变化
- 状态变化
- 认知变化
- 期待与兑现
- 规则变化
- 章末交接

分别算指标，不再只看一个总 F1。

## **第 3 阶段：上八阶段流水线**

先影子运行：

- 旧单轮继续服务生产
- 新流水线同时运行
- 比较两者对续写、诊断和分镜的实际帮助
- 不只比较 JSON 字段命中率

## **第 4 阶段：接入爽点与 Hook**

先服务两个最有价值的场景：

- 下一章规划
- 当前章诊断

跑稳后再给分镜和互动叙事使用。

## **第 5 阶段：把内部 Tool 包成作者工作流**

作者只看到：

```
导入
规划
续写
诊断
改编
未来事件
```

内部再按阶段调用工具。

---

# **🔥 一句话收口**

你们要做的不是“更复杂的大纲模板”，而是：

> **一套能保存叙事变化、回放人物状态、管理读者期待、约束金手指规则、安排未来义务，并向不同下游生成专用视图的商业连载叙事操作系统。**
> 

厚描负责不丢东西，快照和薄片负责取数快；固定核心保存跨题材叙事含义，适配层处理网文与漫剧的表现差异；模型负责理解，程序负责可信地把理解变成长期可用的数据。

来源：ChatGPT