# 交件合同｜30章干净故事真值候选

任务：`GEN-CONSUMER-STAGE0-FIXTURE-20260802`  
合同版本：`story-truth-candidate.v1`  
状态：**下一位明确接单的故事 Agent 可以执行**

## 只交三个业务文件

故事 Agent 在本目录新建 `truth_candidate/`，只交：

```text
truth_candidate/
  story_truth_candidate.json
  OPEN_DECISIONS.md
  README.md
```

- `story_truth_candidate.json`：机器读取的30章干净故事真值候选；必须通过 [story_truth_candidate.schema.json](story_truth_candidate.schema.json)。
- `OPEN_DECISIONS.md`：仍需 CZ 选择的故事问题，不能偷偷选完再写进真值。
- `README.md`：给 CZ 看的故事概要、四条故事线、主要变化和自查结果。

不得修改 Schema 来迁就自己的数据。Schema 真有冲突时停下，在 `OPEN_DECISIONS.md` 说明。

ChatGPT 回传 ZIP 时，可以在这三个业务文件之外附加 `MANIFEST.json` 和 `SHA256SUMS` 两个运输封套文件。因此回传 ZIP 是**三个业务文件＋两个运输文件，共五个普通文件**；这不算增加业务交件。

## 读取顺序

1. [REVISION_PLAN.md](REVISION_PLAN.md)：已拍修改方向；
2. [STORY_AGENT_BRIEF.md](STORY_AGENT_BRIEF.md)：可调整的30章骨架、身份合同和角色模板；
3. [STORY_CONCEPT_CANDIDATE_v0.1.md](STORY_CONCEPT_CANDIDATE_v0.1.md)：原始故事材料。

上层与下层打架时，上层优先。不得从聊天摘要猜字段。

## 必须满足的规模

- 正好30章，章节号为1～30，不缺号、不重复；
- 正好4条主要故事线；
- 6名核心角色，辅助角色不超过4名；
- 4～6次“七日后果”预测；
- 至少2条跨越3章以上的因果链；
- 第9章必须发生七家商户撤回退租、改签三十天联合经营承诺；
- 第30章只保留“外部资金来源不明”这一条系列开放 Hook。

## 数据身份不能混

- `WF-`：真实发生或成立的世界事实；
- `ST-`：有有效期、会被新值替代的状态；
- `PRED-`：周野通过能力看见的条件预测；
- `BL-`：某个具体人物的知情、怀疑或误信；
- `HK-`：开放、触发、解决或延期的 Hook；
- `OB-`：债务、承诺、义务或期限；
- `RULE-`：已经确认或仍属推测的世界规则；
- `CE-`：连接原因、行动和后果的因果边；
- `EXIT-`：每章结束时给下一章使用的出口状态。

体验说明只放 `experience_notes`。爽点、羞辱感和镜头动作不能冒充世界事实。

## 仍待拍的问题怎么处理

赵万海是否授权伤人、父亲是否有历史污点、许清禾的职业损失是否永久，目前都不是已拍事实。

故事 Agent可以：

- 在 `OPEN_DECISIONS.md` 给2～3个候选；
- 在 JSON 的 `open_decisions` 登记同一个问题；
- 使用不依赖该答案的章节骨架继续施工。

故事 Agent不可以：

- 擅自选一个答案写入 `world_facts`；
- 为了让30章看起来完整而假装 CZ 已拍；
- 把角色猜测写成世界真相。

这些问题若挡住某一章的唯一写法，就在该章使用候选占位并明确引用决定编号，不能伪造正式事实。

## 提交前自查

- JSON 能解析并通过 Schema；
- 所有 ID 唯一；
- 所有引用的 ID 都真实存在；
- 状态有效期没有倒置；
- 被替代状态能找到新记录；
- 预测在触发章前不可用；
- 已失效预测仍保留原始记录和失效原因；
- 角色认知只属于具体人物，不使用“众人都知道”；
- 条件预测没有复制成世界事实；
- 开放 Hook 没有虚构幕后答案；
- 30个章节出口与章节一一对应；
- 模型/API调用次数为0。

## 停点

三个文件交齐并自查后立即停下，回传 CZ。不得继续制作污染库、查询题、编包器、对照组或成绩表。

来源：Codex
