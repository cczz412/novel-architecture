# C4 · 事实查询（FACT_QUERY）

**版本：v1**（增加 chapter revision、正式 anchor 与 needs-recheck；v0-r02 保留为迁移前运行时）

读法：`status` 只表示事实候选的审查处置，不表示计划是否发生、对账结果、收工或关章。`confirmed` 只有在 current chapter revision 上仍有合法证据时才属于 current truth；`needs_recheck` 已退出当前真值消费。普通 `quote` 仍只是模型转抄，不能冒充 VERIFIED anchor。

一句话用途：事实账里一条事实的完整形态——候选、已确认、已拒绝都长这样；下游全部只读，确认／驳回／改判只走 M5 作者动作和 M4 事务 writer。

| 方向 | 模块 |
|---|---|
| 发 | M4 事实账（[store.py](../mvp/store.py) 的 `facts(project)` 返回全量列表；落盘 `data/<项目>/facts.json`） |
| 收 | M6 取证问答（[ask.py](../mvp/ask.py)）；M0 展示（status／confirm）；下一单 M7 一致性体检，以及未来 M8／M9 |

## 字段表

| 字段 | 类型 | 含义 | 必填 |
|---|---|---|---|
| contract | str | 固定 `C4_FACT_QUERY` | 是 |
| version | str | 固定 `v1` | 是 |
| id | str | 事实号，`f001` 格式，入账时按账内顺序分配 | 是 |
| chapter_id | str | 来源章节（C1 的 `id`） | 是 |
| text | str | 事实句（确认时可被作者改写，原候选句备档进 `note`） | 是 |
| quote | str | 原文依据片段（模型转抄，未做一致性校验） | 是（可空串） |
| status | str | `extracted`／`confirmed`／`rejected`／`needs_recheck`；最后一项不属于 current truth | 是 |
| source | str | 候选来源：模型 ID 或候选文件名 | 是 |
| note | str | 备注；改写确认时存「原文候选：…」 | 是（可空串） |
| added_at | str | 入账时间 | 是 |
| seg | int | 来源责任段序号（对应 C2） | 否（外部载入的候选没有） |
| decided_at | str | 最近一次确认／拒绝时间 | 否（没审过就没有） |
| chapter_revision_ref | obj | `{chapter_id, revision_no, revision_text_sha256}`；必须与本事实证据版本一致 | 是 |
| anchor_ref | obj/null | VERIFIED 时为 C11 revision anchor；legacy 未核时为 null | 是 |
| anchor_state | enum | `VERIFIED`／`LEGACY_UNVERIFIED` | 是 |
| recheck | obj/null | needs_recheck 时记录 previous status、原因、from/target revision、时间 | 是 |

`recheck.reason` 只允许：`evidence_gone`、`anchor_ambiguous`、`legacy_anchor_unverified`。

语义规则：**只有 current revision 上仍可回验的 `confirmed` 是当前真值**。M6／M8／M11 只读这些记录；M7 不把 needs_recheck 当 confirmed 或普通 candidate 扫描。普通上游只能投 `extracted` 候选，作者审查仍走 M5；程序不得把 needs_recheck 自动改回 confirmed。

章节 revision 提交前，事务协调器必须对本章全部事实预计算 anchor effects。verified slice 在新版唯一命中时，保持 status 并把 ref/anchor 前进；0 次、多次或 legacy 无法双边唯一验证时转 needs_recheck。facts effects、C11 current、C1 view 与受影响 RE stale 必须同事务提交，任何一边失败都恢复 all-before。

普通 M5 确认、驳回、改判与“改写后采纳”统一使用 [FACT_REVIEW_ACTION.md](FACT_REVIEW_ACTION.md)。旧 `cli.py confirm`、`store.set_status` 和 `store.edit_fact_text` 只保留兼容调用面，不能再直接替换 `facts.json`。底层由 [factstore.py](../mvp/factstore.py) 复用 planstore 的文件锁、prepare／commit、恢复底稿与 operation ID；“改写后采纳”必须是一个事务，不能留下“文本已改、状态未确认”的半状态。

若 current RE 正在引用被改判或改写的事实，事务必须同时把旧 RE 转为 stale，使旧 actual support 当场失效。以后把事实重新改回 confirmed 也不会复活旧边；恢复支持必须重新对账。该规则不增加新的 C4 状态，也不把计划或模型意见变成事实。

已交棒 C1 的计划—书稿对账可以使用 [RECONCILIATION_FACT_ADMISSION_ACTION.md](RECONCILIATION_FACT_ADMISSION_ACTION.md) 走同一份 M4／M5 权限：模型仍只交 C3 与六态观察，作者逐条确认后，提交协调器才可以在同一事务把候选按现有 C4 字段写成 `confirmed`，并把内部 f 引用接回 planstore RE。这个事务路径不增加第二种事实状态、不允许模型指定 f／F-，也不允许 PE 因已安排而生成事实。

该路径在 v2 action 中还必须绑定 current `chapter_revision_ref`。`quote` 逐字存在且唯一命中后，confirmed C4 v1 同时生成 VERIFIED anchor；C1 SHA、revision ref、RE rev、planned rev 任一不 current 时 facts 与 planstore 都保持 0 变化。

M6 回答时会在记录上附加 `chapter_title`（章节标题，内存态补充，不落盘、不属于本合同字段）。

## 真实示例

`data/万鬼伏藏/facts.json` 的 f001（已确认，带全部可选字段）：

```json
{
  "id": "f001",
  "chapter_id": "c01",
  "text": "市医院精神科的陈医生询问李星燃有什么症状。",
  "quote": "“你叫李星燃对吧，说说看吧，你都有什么症状。”",
  "status": "confirmed",
  "source": "doubao-seed-2-1-turbo-260628",
  "note": "",
  "added_at": "2026-08-13 00:55:19",
  "seg": 1,
  "decided_at": "2026-08-13 00:55:31"
}
```

## Backward compatibility

### 合同扩展：保存可回取的原章片段（尚未接入运行）

[C2_C1_TEXT_MAP v1](C2_C1_TEXT_MAP.md) 定义跨自然段引文的离线验证证据。第二刀由 M4 在同一 current revision 与可信责任范围下重放映射，保存原章实际连续片段及其 UTF-8 SHA-256，另保留候选原文和规范化匹配内容。现役 C4 v1 字段表、确认权限、C11 anchor 形状及事务规则不变；本刀的返回值只是拟保存片段，不等于正式 anchor、已入账事实或 confirmed。运行 writer、并发复核及失败零写入接线另批，不允许旧 reader 忽略扩展后降级消费。

- v0-r02 迁移到 v1 时，能唯一回验的 quote 生成 VERIFIED anchor；不能回验的历史记录可以暂存 `LEGACY_UNVERIFIED`。
- legacy confirmed 不因迁移本身自动撤销；但所属章节第一次 revision 时必须双边唯一验证，否则转 needs_recheck。
- 旧 C4 reader 遇到 v1 必须 fail closed，不能只看 `status=confirmed` 就继续问答、规划或体检。
- 现役 `FACT_REVIEW_ACTION v1` 与统一 fact writer 仍是 v0-r02 产品面；revision-aware 产品迁移另开施工票，本票不修改产品代码。

## 仍未解决

- 证据坐标粒度只有 `chapter_id`＋`seg`，无字符级锚点；`quote` 与原文的一致性未校验（M7 做矛盾定位时会先撞到这两条）。
- schema v0 整体是临时件，等研究仓 N16 语义合同定案后重建（见 [store.py](../mvp/store.py) 头注）。
