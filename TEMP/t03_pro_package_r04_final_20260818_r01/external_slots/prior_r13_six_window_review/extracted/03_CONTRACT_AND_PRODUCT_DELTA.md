# 正式合同、R13 合同设计与产品设计稿｜差异候选

## 边界

本页只列“哪一句／哪个身份需要修订候选”，不重写整篇，不把建议写成已经生效。任何正式合同、R13 正文、产品代码或治理入口修改都标 `CZ_EXPLICIT_APPROVAL_REQUIRED`。

## A. 现行正式合同的原子差异候选

| Delta ID | 对象 | 当前证据造成的差异 | 推荐候选 | 明确不做 | 权限 |
|---|---|---|---|---|---|
| `DELTA-C10-01` | C10 adoption 状态 | D READY-02 看到合同文字仍说 Tags 产品 producer/consumer 未实现，而当前显式路径能保存 v4 Tags | 只对账“合同采用状态／运行时事实”，不改 Tags 真值地位；补一张 current adoption receipt 候选 | 不把 Tags 自动升 C1/M2，不借机扩材料语义 | `CZ_EXPLICIT_APPROVAL_REQUIRED`（正式合同） |
| `DELTA-C1-REV-01` | C1／上游章节证据合同 | A 证明当前 C1 只有追加 cXX，不能表达同章 revision | 在 C1 上游或独立章节版本合同中表达 stable lineage、append-only revision、current pointer；修订动作显式带 target chapter | 不用标题／章号自动替换；不把 `work_rev` 冒充 chapter revision | `CZ_EXPLICIT_APPROVAL_REQUIRED` |
| `DELTA-C2-WATERLINE-01` | C2 | D READY-01 证明 C2 可回拼，但自身不带 source/chapter revision | 正式消费者若需要持久锚，增加外层 run receipt／waterline，而不是让 C2 拥有版本链 | 不混用 C10 decoded offset、C2 normalized offset、quote | `CZ_EXPLICIT_APPROVAL_REQUIRED` |
| `DELTA-C3-UNRES-01` | C3 | T03 证明单段候选不足以表达非连续未决；D 只证明上游不能抬权 | 先在 TEMP 冻结“unresolved evidence bundle”候选：多个 source span＋命题边界＋闭合反证＋unknown 类型 | 不直接在 C3 v0 塞万能 `unresolved=true`；不让模型写真值／实体 | `CZ_EXPLICIT_APPROVAL_REQUIRED`（正式 C3） |
| `DELTA-C4-STALE-01` | C4 | A 证明旧证据消失后 confirmed 仍可查询；D 证明现行只有三态 | 冻结 stale/recheck 的业务语义、是否退出真值消费、重新确认动作与历史保留 | 不让 revision 自动改成 rejected；不让 rejected→confirmed 复活旧 RE | `CZ_EXPLICIT_APPROVAL_REQUIRED` |
| `DELTA-C4-UNRES-02` | C4 | T03 需要逐字送达多段未决；D 指出现行无 actuality/unresolved/entity scope | 先定义只读候选容器与 provenance；正式 C4 是否承载另行裁决 | 不把“缺少完成动作”写成否定事实 | `CZ_EXPLICIT_APPROVAL_REQUIRED` |
| `DELTA-C6-01` | C6 | D READY-04 证明只读，但无 source commit seq/chapter revision | 增加消费水位／过期回执候选；C6 继续只读 | 不把 C6 变成高影响 write action | `CZ_EXPLICIT_APPROVAL_REQUIRED` |
| `DELTA-PLAN-01` | PLAN_LEDGER / reconciliation | B 已统一 facts writer 与 RE stale；旧设计若仍描述旁路写入已过时 | 只更新 writer ownership 与事务边界说明；reconciliation facts admission 必须复用 M4 writer | 不把 B PASS 扩成暗稿、关章或 revision | `CZ_EXPLICIT_APPROVAL_REQUIRED` |
| `DELTA-C9-01` | C9 | C 只证明 R19 actuality＋R21 budget 候选；无正式 C9、无产品实现 | C9 设计必须分开四个规则族：actuality、budget、unresolved-current、evidence loading；每族独立证据与弃权 | 不把 7/7+6/7 写成正式通过；不把 TEST_ONLY normalizer 当产品 parser | `CZ_EXPLICIT_APPROVAL_REQUIRED` |
| `DELTA-PROTOCOL-01` | 共享页面调度合同 | 单 SHA 无法解释路径脱敏，状态机可死锁 | 增原件 SHA＋运输 SHA＋转换回执；TTL、epoch、capability matrix、route receipt | 不把页面回复当授权或执行票 | `CZ_EXPLICIT_APPROVAL_REQUIRED`（正式协议采用） |

## B. R13 合同设计稿 T01～T21 的最小滚动差异

旧设计稿：`04_external_reviews/r13_contract_design_baseline/R13_合同设计稿_模块并行测试审查_20260815.md`。不全量重写，只改受新证据触及的原子。

| 旧题 | 当前处理 | 新证据 | 差异候选 |
|---|---|---|---|
| T01｜M1-A | 修订 | A＋D | 保留 C10→C1 无损与非 Chapter 隔离；新增“同章 revision 不得自动 fork”为独立失败门；当前不是 Production Ready |
| T02｜M1-B | 保留＋窄修 | D READY-02 | 非 Chapter 0 C1/M2 可保留；Tags adoption 身份需对账，不扩产品语义 |
| T03｜M2 | 保留＋加水位缺口 | D READY-01＋A | 单次切窗机械可用；持久 anchor/revision 仍缺，不把 C2 当版本合同 |
| T04｜M3 | 重大修订 | T03＋D READY-03 | 权限不抬高已过机械门；未决发现／跨段聚合失败，不能写 M3 语义成熟 |
| T05｜M4 | 修订 | B＋A | 唯一 writer 已强固；revision stale/recheck 仍未定义，M4 不能自创语义 |
| T06｜M5 | 修订 | B | 作者 action→M4 writer 已窄通过；C5/UX/确认负担未建；暗稿/关章不在本票 |
| T07｜M6 | 修订 | A | 旧 confirmed fact 仍可查询，必须新增 source/revision waterline 与弃权候选 |
| T08｜M7 | 修订 | D READY-04＋A | 只读机械条款可保留；当前字节需重放；C6 无 revision/commit seq |
| T09/T10｜M8/planstore | 保留＋writer 身份修订 | B | 规划账与 facts 分权更清楚；B 不等于完整 M8；暗稿／关章仍开放 |
| T11｜M9 | 等待模块本体 | ARCHITECTURE | C5 和实现都不存在，不再只写“等接缝” |
| T12｜M10 | 等待模块本体 | ARCHITECTURE | C8 和实现都不存在；可在 plan object 稳定后独立推进 |
| T13｜M11 | 重大修订 | C＋A＋T03 | R19/R21 是实验规则候选；REAL-03 独立；C9 要等 revision/unresolved 身份，不正式化 |
| T14｜写作区/收工 | 等待 | B scope warning | 不由 writer PASS 推出暗稿签字、自动下一章或关章 |
| T21｜章节修订 | 从“补漏题”升为显式 blocker 候选 | A | 先做最小合同设计；owner、stale 语义、锚点、迁移和原子事务必须逐项冻结 |
| 其余 T15～T20 | 保留／按原证据等待 | 本轮无直接新结果票 | 不借本轮扩范围，不做全量重跑 |

## C. 产品设计稿差异候选

### `novel-mvp/ARCHITECTURE.md`

**需要改的不是整张架构图，而是身份句和排期句：**

1. M11 行“随 M8 第一单施工”已被现实证据穿透：M11 没有正式 C9，也不只服务 M8，M6/M7 同样是直接消费者。
2. 施工顺序里“M11 随 M8（唯一直接消费者）”应降为历史排期建议；正式接缝要按 M6/M7/M8 三消费方验收。
3. M4 行可保留“唯一 facts writer”，补充只限 confirmed facts，不能吸收 chapter revision owner。
4. D 4/4 不能写入架构“已验证”，除非当前字节重放通过。

正式修改：`CZ_EXPLICIT_APPROVAL_REQUIRED`。

### `CHAPTER_REVISION_DESIGN_R01.md`

当前稿是设计候选，不能直接施工。需要的最小差异：

- 把“C1 加 versions/current rev”从既定字段降为候选方案；
- 对齐当前 C10 v4、C1 v0-r01、C4 v0-r02 与 B 的 factstore writer；
- 明确章节 lineage owner 未拍；
- `needs_recheck` 只是推荐，不是现行 C4 enum；
- restore 改为“旧内容作为新 revision 追加”的候选；
- 加 M6/M7/M9/M10/M11 消费水位和 fail-closed 表；
- 加现存数据迁移与 rollback，不只画新项目路径。

正式设计稿改版：`CZ_EXPLICIT_APPROVAL_REQUIRED`。

### `CONTEXT_PACKER_DESIGN_R01.md`

需要的最小差异：

- 显式写 `formal C9 = false / runtime = false`；
- 把 100 章 3–4k、5–15 条约束等数字标为未验证预算假设；
- 消费方从“主要 M8”改为 M6/M7/M8，分别列任务合同；
- 增 revision/source waterline、unresolved bundle、coverage/omission receipt、按需回捞；
- R19 actuality 与 R21 budget 可以作为实验候选引用，R20 unresolved 和 R18 evidence 保持独立；
- 豆包 fence／DeepSeek bare JSON 差异列为运输风险；
- 删除或降级任何把 M4 `irreversible` 等候选字段写成已定的句子。

正式设计稿与 C9：`CZ_EXPLICIT_APPROVAL_REQUIRED`。

### `M8_PLANNING_DESIGN_R04.md`

当前主要方向与 B 兼容：计划不等于事实、选择动作经 planstore、对账不自动写真值。只需防两种误读：

- “选定那一刻规划账改完”必须指 C7 selection action→planstore，不是 M8 直接改文件；
- B writer 统一只解决 facts/RE，不批准暗稿、关章或自动下一章。

不建议重写整稿。

### `REVIEW_OVERVIEW_DESIGN_R03.md`

- C5 仍是候选，M9 未建；
- M5 动作链已更新，应引用 FACT_REVIEW v1＋M4 writer；
- revision 后的投影 stale 只能标候选，不能引用 CHAPTER_REVISION R01 当正式合同；
- 概览可改、进真值须作者确认保持不动。

### `SCENE_CARD_EXPORT_DESIGN_R01.md`

- C8 仍未开工；
- 它是投影出口，不应等待 T03 所有未决研究完成才做任何 V0；
- 但正式导出必须带 plan/fact/revision 来源与版本回执；
- 不得反写真源。

### `design/INDEX.md`

索引中“暗稿默认已发生、仍是事实不动；只剩签字与下一章开放”与本轮硬边界存在高风险语义碰撞。外审不改判 R13，只建议把它标成：

`R13_SEMANTIC_CLAIM__FORMAL_ACTION_AUTHORITY_AND_CHAPTER_TRANSITION_STILL_OPEN`

不能因 B writer PASS 把“默认已发生”解释成事实写入已获作者授权。正式改字：`CZ_EXPLICIT_APPROVAL_REQUIRED`。

## D. 不建议改的内容

- R13 “计划≠已发生”“投影可改、进真值须作者确认”“M4 是 confirmed facts 唯一写域”的上位边界；
- B 已落的唯一 writer 与 atomic RE stale 纪律；
- D 机械测试里 extracted-only、rejected 排除、facts 0 回写等负权限条款候选；
- C 的冻结 R19/R21 实验产物；
- T03 的原始失败账、部分覆盖与负控结果。

## E. 变更生效规则

本页所有 `DELTA-*` 均为外审候选。采用顺序应是：

`CZ 明字 → 指定 owner/写集 → 独立合同改版 → 收发两端施工 → 定向回归 → 跨接缝回归 → 当前入口更新`。

任何一步都不能由“外审建议”“某窗 PASS”或“没有人反对”替代。

来源：当前正式合同／设计稿、R13、A/B/C/D/T03 最新回执。
