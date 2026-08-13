## 结论

你们的本地结果已经足以否定“固定短块优先”作为默认方案：

* 300 字非重叠块相对自然责任段的 F1 下降约 **60.3%**；117 条预测仅 14 TP，原始命中率约 **12.0%**。
* 若 Gold 必须由同一非重叠块完整承载，且没有跨块重建，那么 60 字切块在模型调用前就把结构性召回上限压到 **45.7%**；Stage1 八题只有 **42.4%**。
* 但 8 题仍不足以证明 760 字是跨小说通用最优值。620–923 字应视为你们当前最强的本地先验，而不是固定标准。

推荐默认方案是：

> **句子通常不可切；自然段是候选边界；对话轮和多句事实形成“不可断组”；再把这些组装箱到约 600–900 字。**
> 时间、地点、视角、人物集合和中心事件的联合变化帮助选切点；长度只负责在安全切点中择优。

简化成一条流水线：

```text
保留原文结构
→ 句子/对话轮原子
→ 两句事实与局部指代不可断组
→ 600–900 字软装箱
→ 风险边界添加只读邻域
→ 每条事实只有一个责任块
```

## 必须区分三种“块”

| 范围    | 解决的问题                 | 主要指标                |
| ----- | --------------------- | ------------------- |
| 检索块   | 哪段文本容易被搜到             | Recall@k、nDCG、QA    |
| 事实责任块 | 哪段原文有权产生这条事实          | Gold 完整率、唯一归属、抽取 F1 |
| 只读上下文 | 当前责任块怎样理解代词、说话人、时间与事件 | 先行词覆盖率、上下文泄漏率       |

RAG 论文里的短命题块、重叠百分比和 embedding 相似度，优化的是检索，不自动适合事实责任边界。例如，小说检索研究 LumberChunker 发现，先保留自然段再动态合并，优于递归固定切块；极短 proposition chunks 在叙事检索中反而较差。但它仍然只评估检索和 QA，不能证明某个块长适合抽取责任。[[LumberChunker](https://aclanthology.org/2024.findings-emnlp.377.pdf)](https://aclanthology.org/2024.findings-emnlp.377.pdf)

一项系统 RAG 评测则发现，semantic chunking 在真实文档上没有稳定胜过固定切块，收益高度依赖数据与检索任务。[[Qu et al. 2025](https://aclanthology.org/2025.findings-naacl.114.pdf)](https://aclanthology.org/2025.findings-naacl.114.pdf) Anthropic 的“给块补全文档背景”也显著改善的是检索失败率，而不是事实证据合法性。[[Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval)](https://www.anthropic.com/engineering/contextual-retrieval)

因此，RAG 资料可以借用“结构化边界、软硬长度上限、来源坐标、唯一 owner”，不能照搬块长和重叠率。

## 哪种边界最适合

没有一种单独的语言单位适合直接当最终责任块。最合适的是混合结构：

| 单位            | 推荐用途              | 不宜直接使用的原因                     |
| ------------- | ----------------- | ----------------------------- |
| 句子            | 默认不可机械切断的底层原子     | 大量关系、论元和纠正跨句                  |
| 自然段           | 最主要的软边界候选         | 小说微段落和对话会造成碎片                 |
| 对话轮           | 必须保留说话人归属的原子      | 整段长对话可能远超目标长度                 |
| 对话链           | 提高切断代价，保护问答和省略说话人 | 不能把所有长对话都硬粘成一块                |
| 事件单元          | 判断动作是否闭合、是否发生转场   | 自动事件边界本身不稳定                   |
| EDU／篇章小句      | 识别条件、原因、纠正等不可断关系  | 太细；中文 GCDT 平均仅 6.5 tokens/EDU |
| scene／场景      | 识别强时空、视角和人物集合变化   | 通常太长且边界模糊                     |
| embedding 语义段 | 只作低权重的候选切点排序      | 主题变化不等于事实闭合                   |

文档级关系抽取中，DocRED 有至少 **40.7%** 的关系事实需要综合多句；46.4% 的关系带有多于一句支持证据。[[DocRED](https://aclanthology.org/P19-1074.pdf)](https://aclanthology.org/P19-1074.pdf) 事件抽取 RAMS 的相关分析中，AIDA-1 有 **38.1%** 的事件至少一个论元不在触发句，五句窗口才能覆盖约 90% 的论元。[[RAMS](https://aclanthology.org/2020.acl-main.718.pdf)](https://aclanthology.org/2020.acl-main.718.pdf) 这些不是小说数据，但直接说明“句子是原子，不是充分的责任块”。

文学叙事证据更支持“自然段候选、对话和指代阻止切分”：

* Kauchak 的叙事分段实验里，74 个真实边界全部位于段落处，但另有 621 个段落位置并非边界；510 个 conversation 位置没有一个真实边界。段落是高召回候选，不是见段就切。[[Kauchak & Chen 2005](https://aclanthology.org/W05-0405.pdf)](https://aclanthology.org/W05-0405.pdf)
* 小说 scene 只约 43% 与段落边界对齐；场景由时间、地点、中心行动和人物集合共同定义，TextTiling 等主题方法表现很差。[[Zehe et al. 2021](https://aclanthology.org/2021.eacl-main.276.pdf)](https://aclanthology.org/2021.eacl-main.276.pdf)
* 后续 scene 研究发现，流动式转场可能延续约三句，模型还会因为换说话人而误切同一场对话。[[Guhr et al. 2025](https://aclanthology.org/2025.latechclfl-1.8.pdf)](https://aclanthology.org/2025.latechclfl-1.8.pdf)
* 中文 RST 数据中的 EDU 平均只有 6.5 tokens，而且还存在不连续 EDU；它更适合作依赖关系特征，而不是责任块。[[GCDT](https://aclanthology.org/2022.aacl-short.47.pdf)](https://aclanthology.org/2022.aacl-short.47.pdf)

## “咚”“嗯”“……”怎么处理

原则是：

> **合并容器，不合并说话人；保护换行、引号、原始坐标和 turn ID。**

例如：

```text
责任块 B17
  P41 / turn=A：“你见过他？”
  P42 / turn=B：“嗯。”
  P43 / turn=A：“在哪里？”
```

三个段可以进入同一个责任块，但不能拼成一句，也不能让“嗯”继承 P41 的说话人。

具体规则：

* 引号内的“嗯、哦、好、不”始终保留为独立对话轮。若它回应上一问句，把“问句—短答”设为不可断组。
* 未加引号的“咚、砰、沙沙”标为 `sound_effect`，不当成人物发言：

  * 前段给出撞击、敲击动作时，倾向与前段成组；
  * 后段解释声源或给出反应时，倾向与后段成组；
  * 两边都有时，三者形成局部事件闭包。
* 引语内部的“……”属于该说话轮。
* “……”独立成段且说话人不明时，保留 `speaker_unknown`，将前后话轮放入同一读取包，但不要靠 A/B 轮换强行定人。
* 长对话可以切，但应切在已经完成的问答、话题转折或有明确说话人重申的位置，并让下一块只读看到前一轮。
* 场景分隔符、明显时空转移、视角变化，或超过一个完整叙事段插入，可以结束对话链。

中文文学引语归属研究专门把“咚咚咚……”类声音作为特殊类别，并通过邻近段落恢复声源和说话人，支持这种做法。[[Yang & Wang 2024](https://aclanthology.org/anthology-files/pdf/sighan/2024.sighan-1.1.pdf)](https://aclanthology.org/anthology-files/pdf/sighan/2024.sighan-1.1.pdf) 英文小说研究也发现，同一自然段中不连续引语属于同一说话人的规则，违例少于 5%；超过一个叙事段才切断 conversation。[[Cuesta-Lazaro et al. 2022](https://aclanthology.org/2022.acl-long.400.pdf)](https://aclanthology.org/2022.acl-long.400.pdf)

## 怎样识别两句共同构成一个事实

建议对每个相邻句对计算 `must_link`。硬规则直接禁止切分；软规则累计到阈值后禁止切分。

| 结构          | 典型信号                           | 处理                 |
| ----------- | ------------------------------ | ------------------ |
| 前句给主体，后句给动作 | 后句有谓词但无显式主体；以“他、她、其、这、那、此事”开头  | 强不可断               |
| 误信—纠正       | “以为、误认、听说、声称”→“其实、原来、实际上、却、并非” | 强不可断；同时保留认知状态与现实状态 |
| 条件—结果       | “如果、若、一旦、除非、只要”→“就、才、便、那么”     | 强不可断               |
| 原因—结果       | “因为、由于”→“所以、因此、于是、结果”          | 成对标记时强不可断          |
| 问题—回答       | 问号后接短答、否定、确认或省略回答              | 强不可断               |
| 计划—执行／未执行   | “准备、打算、答应”→“随后、但最终、却没有”        | 中高强度               |
| 指代事件        | “此事、这样、那一幕、这才、对此”              | 中高强度               |
| 结构未闭合       | 未闭引号、冒号、分号、破折号、未完成补语           | 强不可断               |
| 连续动作        | 同一主体、地点和时间，后句以“又、仍、随即、随后”承接    | 软不可断               |

两个限制很重要：

* 软规则的传递闭包默认只保护 2–3 句，避免“于是……随后……又……”把整章粘起来。
* 单纯共享人物、单纯 embedding 相似、单纯换段，都不能独立触发不可断。

## 600–900 字动态装箱规则

建议参数从你们当前结果出发：

```text
min_len     = 600
target_len  = 760
soft_max    = 900
fallback_max = 1100～1200
```

具体决策：

* 未到 600：继续合并，除非遇到明确场景分隔或强时空／视角转移。
* 600–900：在候选边界里选择依赖最弱且最接近 760 的位置。
* 到 900 仍无安全边界：延长到下一个事实闭合点，最多先试 1100–1200。
* 强场景边界前只有 450 字：允许短块；不要为凑 600 穿过场景变化。
* 不可断组本身超过 900：允许成为超长块。
* 不可断组超过模型硬限制：

  * 优先进入一次“超长重试”；
  * 确实无法处理时，只在最弱句间关系处切，并标 `split_risk`；
  * 两侧添加完整邻句作为只读上下文，但不要声称这样已经恢复了合法完整证据。

边界分数可以很简单：

```text
切断代价 =
    指代/零主语依赖
  + 条件、因果、纠正、问答关系
  + 未闭合引号或补语
  + 未解决的对话归属
  - 明确场景分隔
  - 时间+地点+视角的联合变化
  - 已闭合事件后的新主体/新行动
```

embedding 语义距离最多作为同分时的辅助项。

## 是否允许重叠

建议允许少量重叠，但只放在**只读上下文**，责任核心仍然不重叠。

不要用固定 20% 字符重叠。使用完整语言单元：

* 块首出现代词、零主语、短答或反应句：向左加一个 protected group；
* 块尾有未解决说话人或事件承接：向右加一个 protected group；
* 初始上限可设为每侧一个自然段，或 2–4 句，先到者为准；
* 普通低风险边界不加重叠。

模型输入应显式区分：

```text
[READ_ONLY_LEFT]
...
[RESPONSIBILITY_CORE]
...
[READ_ONLY_RIGHT]
```

并要求每条事实返回绝对 `evidence_offsets`。任何证据跨度不完全位于 `RESPONSIBILITY_CORE` 的预测，都应拒收或标为 `context_leakage`。

DocOIE 正是“目标句负责输出、周边句帮助理解”的相关证据：加入上下文后 F1 上升，最佳上下文约为前后各 4–5 句，再增加则收益饱和。[[DocOIE](https://aclanthology.org/2021.findings-acl.210.pdf)](https://aclanthology.org/2021.findings-acl.210.pdf)

### 若实验物理重叠责任块

需要指定唯一 owner：

1. 只有完整包含最小证据跨度的块有资格；
2. 多个块都完整包含时，选择证据离两端最远的窗口；
3. 仍相同时固定选择较小 block ID。

去重分三层：

* 规范事实键相同、证据 offsets 相同：直接合并。
* 事实键相同、证据跨度重叠或紧邻：保留最短完整证据，合并 provenance。
* 仅语义相似：只作为人工或二次判定候选，不自动合并。

事实键至少包含：

```text
(subject_id, predicate, object/state,
 polarity, epistemic_status, modality,
 time, speaker/perspective)
```

否则会错误合并：

```text
张三以为李四已经死亡
李四实际上没有死亡
```

也不能把计划、承诺、尝试和真正执行合并成同一事实。

## 远距离姓名与代词

不建议把远处姓名到当前代词之间的全部文本吞进责任块。

中文小说 NovelCR 中，83% 的指代对跨至少三句，零代词约占标注 mention 的 27.2%。不过该数据集刻意强化长距离指代，不能据此把窗口直接定成五句或 184 tokens。[[NovelCR](https://aclanthology.org/2025.findings-acl.268.pdf)](https://aclanthology.org/2025.findings-acl.268.pdf)

推荐分层处理：

| 情况             | 处理                                                |
| -------------- | ------------------------------------------------- |
| 主体就在前一句，当前句省主语 | 两句直接不可断                                           |
| 先行词在前 1–2 个自然段 | 扩大只读上下文                                           |
| 姓名、别名、身份称呼相隔很远 | 章节级人物候选表／coreference sidecar                      |
| 指代高置信          | 给抽取模型 `surface_text + entity_id + support_offset` |
| 置信度不足          | 保留“他／师父／那女人”，输出 `unresolved_ref`                  |

推荐结构：

```json
{
  "surface_subject": "他",
  "resolved_entity_id": "CHAR_017",
  "coref_confidence": 0.91,
  "coref_support": ["CTX_P031"],
  "fact_evidence": ["CORE_P042"]
}
```

`CTX_P031` 只能解释“他是谁”，不能充当该事实的责任证据。

coreference 最好同时出现在抽取前后：

* 抽取前提供高置信人物候选，避免模型因“他”而漏掉事实；
* 抽取后统一实体 ID 和别名；
* 仅靠后处理无法恢复模型根本没有抽出的事实。

## 最小 Python 流程

下面的骨架不需要新训练一个切块模型；`annotate_units` 可先由正则、现有分句器和已有实体结果实现：

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Unit:
    uid: str
    start: int
    end: int
    text: str
    paragraph_id: int
    kind: str                 # narrative/dialogue/sound/pause
    turn_id: Optional[str]
    speaker: Optional[str]
    has_subject: Optional[bool]
    hard_before: bool = False
    features: set[str] = field(default_factory=set)

@dataclass
class Group:
    units: list[Unit]
    hard_before: bool = False
    cut_penalty_after: float = 0.0

    @property
    def length(self):
        return self.units[-1].end - self.units[0].start

def must_link(a: Unit, b: Unit) -> bool:
    f = a.features | b.features

    if a.turn_id and a.turn_id == b.turn_id:
        return True
    if "unclosed_quote" in a.features:
        return True
    if "missing_subject" in b.features and a.has_subject:
        return True
    if f & {
        "condition_result",
        "belief_correction",
        "question_short_answer",
        "cause_result",
        "reporting_complement",
    }:
        return True
    if b.kind in {"sound", "pause"} and "unresolved_source" in b.features:
        return True
    return False

def make_protected_groups(units: list[Unit]) -> list[Group]:
    groups: list[Group] = []

    for unit in units:
        if groups and must_link(groups[-1].units[-1], unit):
            groups[-1].units.append(unit)
        else:
            groups.append(Group([unit], hard_before=unit.hard_before))

    return groups

def choose_end(groups, i, target=760, soft_max=900,
               hard_max=1200):
    total = 0
    candidates = []

    for j in range(i, len(groups)):
        if j > i and groups[j].hard_before:
            break

        total += groups[j].length
        penalty = groups[j].cut_penalty_after

        if total <= hard_max:
            candidates.append((j + 1, total, penalty))
        else:
            break

    preferred = [
        c for c in candidates if 600 <= c[1] <= soft_max
    ]
    fallback = [
        c for c in candidates if c[1] <= hard_max
    ]

    pool = preferred or fallback
    if not pool:
        # 一个 protected group 本身超长：保持完整并标记回退
        return i + 1, "oversize"

    end, _, _ = min(
        pool,
        key=lambda c: abs(c[1] - target) + 180 * c[2]
    )
    return end, "normal"

def pack(groups):
    blocks = []
    i = 0

    while i < len(groups):
        end, status = choose_end(groups, i)
        members = groups[i:end]

        blocks.append({
            "core_start": members[0].units[0].start,
            "core_end": members[-1].units[-1].end,
            "unit_ids": [
                u.uid for g in members for u in g.units
            ],
            "status": status,
        })
        i = end

    return blocks
```

`annotate_units` 至少需要这些特征：

* 原文 SHA、绝对字符 offset、段落 ID、句子 ID；
* 引号开闭状态、对话轮、speaker 候选与置信度；
* `sound_effect`、短答、停顿段；
* 显式主体／零主语、句首代词；
* 条件、因果、纠正、问答、报告／信念作用域；
* 时间、地点、视角、人物集合和中心动作变化；
* `responsibility_core` 与 `read_only_context` 身份。

## 回退策略

* 引号不平衡：整段保留为原子，并增加邻段只读上下文。
* 说话人不明：输出 `speaker_unknown`，不靠位置硬猜。
* 900 字前没有安全边界：延长至 1100–1200。
* protected group 仍超长：进入超长重试，不做字符截断。
* 语义边界置信度低：退回自然段边界。
* coreference 低置信：保留表面称呼，不擅自换成人名。
* 任何机械回退都记录 `split_risk`，单独评估，不能悄悄混入正常样本。

## 应增加的评估指标

模型调用前：

* `gold_intact_in_core_rate`：完整 Gold 证据落在一个责任核心的比例；
* `gold_visible_in_any_read_window_rate`；
* `cross_core_gold_rate`；
* `zero_subject_split_rate`；
* `belief_correction_split_rate`；
* `condition_result_split_rate`；
* `question_answer_split_rate`；
* `short_turn_speaker_integrity`；
* 超长块率、回退率、只读上下文字符开销。

模型调用后：

* 总体语义 P/R/F1；
* 块内部事实 F1 与边界附近事实 F1；
* 单句／跨句／对话／误信纠正／条件结果分桶 F1；
* evidence offset 合法率；
* `context_leakage_rate`；
* 聚合前、聚合后的重复预测率；
* `wrong_merge_rate` 与 `missed_merge_rate`；
* unresolved coreference 比例及其精度；
* 每题调用数、输入 Unicode 字符数和 token 成本。

最小消融只需三个新旧方案：

* A：当前自然完整责任段基线；
* B：本文的 protected-group 动态装箱，不加只读邻域；
* C：B 加风险触发的只读邻域。

固定 300 字结果已经足够作为失败对照。比较时固定模型、提示词、解码参数、题集和去重逻辑，并同时报告聚合前、聚合后 F1。

最重要的优化目标不应是“平均块长最接近 760”，而应是：

> **在可接受调用成本下，最大化 Gold 完整落入唯一责任核心的比例，并压低边界事实与块内部事实之间的 F1 差距。**

来源：ChatGPT
