# 轮次停点日志｜30章干净故事真值候选

任务：`GEN-CONSUMER-STAGE0-FIXTURE-20260802` 的下一段  
上游拍板：[../REVISION_PLAN.md](../REVISION_PLAN.md)（已 APPROVED_FOR_NEXT_STORY_AGENT）  
原案：[../STORY_CONCEPT_CANDIDATE_v0.1.md](../STORY_CONCEPT_CANDIDATE_v0.1.md)  
目标：只做**30章干净故事真值候选**，做完停，回 CZ 审。不注入坑、不写编包器、不调模型、不建羞辱真值表。

## 纪律红线（来自修改单，子 Agent 必读）
- 四类身份物理隔离：①条件预测 PRED / ②真实事实 WF / ③知情误信 BL / ④后文事实 FF。
- 已失效预测仍合法可见，不算过期资料、不算未来泄漏。
- 系列钩子只留"外部资金不明"开放 Hook，不得虚构幕后人当事实。
- 不建混合羞辱真值表；爽点/镜头只进体验层或漫剧层，不反向污染事实层。
- 能力已确认规则五条；未确认推测（来源/代价上限/他人是否有）不进事实。

## 轮子规划
| 轮 | 产物文件 | 负责 | 停点 |
|---|---|---|---|
| R1 | 01_characters.md | 角色补全（六角色四项+辅助角色） | 角色落定 |
| R2 | 02_chapter_skeleton.md | 30章骨架（事实/钩/战争归属） | 骨架落定 |
| R3 | 03_truth_schema.md | 真值表结构+隔离枚举 | 结构落定 |
| R4 | 04_story_truth_candidate.md | 汇总 30 章真值候选（引用 R1-R3） | 候选完成待审 |
| R5 | README_draft.md | 给 CZ 的审读说明 | 交件 |

## 当前停点
- R1 完成：`01_characters.md` 已落定（六角色四项+辅助角色+隔离接口）。
- R2 完成：`02_chapter_skeleton.md` 已落定（30章骨架+四战落位+第9章切分样例）。
- R3 完成：`03_truth_schema.md` 已落定（四类隔离表+失效预测判例+系列钩子登记+能力七字段）。
- R4 完成：`04_story_truth_candidate.md` 已落定（30章真值候选汇总，待审）。
- R5 完成：`README_draft.md` 审读说明已落定。
- R6 完成：`05_grounding.md` 落定；02/03/04 已回写下沉事件替换、公开化章号、exit_snapshot、三层取数边界、下沉可信纪律。
- **整体仍停此待 CZ 审。** 未经授权不进入污染库/编包器/评测阶段。

## 本轮新增待 CZ 确认项（R6）
1. 悬浮点替换（伪造债务→冒签借条、股权→铺面分红等）是否采用，或保留更原案化表达。
2. exit_snapshot 八项固定字段是否纳入真值结构（波次B建议，不改表结构只加 chapters 字段）。
3. reader_baseline_from_chapter 公开化章号表是否认可（第一幕内完毕原则）。
4. 下沉可信纪律条文是否写进 REVISION_PLAN.md（"钱数证据合同流水须可核查，夸张仅限EN-*"）。

## R6 新需求（CZ 2026-08-02 补充）
CZ 要求贴合下沉市场：事件要读者熟悉、可信、离自己近；情绪/反应可夸张但事件要真可感；任何一章切入都能看懂个大概（低门槛）。
新增讨论轮次：波次A下沉事件库 / 波次B低门槛切入 / 波次C可信度纪律。结论落 `05_grounding.md`，并回写 02/03/04 的相关标注。

## 交付清单（story_truth_draft/）
- 00_ROUND_LOG.md（轮次停点）
- 01_characters.md（角色四项+辅助角色）
- 02_chapter_skeleton.md（30章骨架）
- 03_truth_schema.md（真值表结构+隔离）
- 04_story_truth_candidate.md（30章真值候选汇总）
- README_draft.md（给 CZ 审读说明）

注：子 Agent 无写入权限，R1-R5 实际由主 Agent 依据各波次讨论结论落盘。
