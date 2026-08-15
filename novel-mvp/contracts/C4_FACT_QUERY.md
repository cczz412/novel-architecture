# C4 · 事实查询（FACT_QUERY）

**版本：v0**（描述现状；要加字段先升版本并同步收发两端）

读法：`status` 只表示事实候选的审查处置，不表示计划是否发生、对账结果、收工或关章。`confirmed` 是审查状态；没有书稿证据或正式作者签字来源时，空 `quote` 不得冒充已承托事实。`quote` 是模型转抄、未校验，只能当定位线索。

一句话用途：事实账里一条事实的完整形态——候选、已确认、已拒绝都长这样；下游全部只读，谁也不许绕过 M4 改状态。

| 方向 | 模块 |
|---|---|
| 发 | M4 事实账（[store.py](../mvp/store.py) 的 `facts(project)` 返回全量列表；落盘 `data/<项目>/facts.json`） |
| 收 | M6 取证问答（[ask.py](../mvp/ask.py)）；M0 展示（status／confirm）；下一单 M7 一致性体检，以及未来 M8／M9 |

## 字段表

| 字段 | 类型 | 含义 | 必填 |
|---|---|---|---|
| id | str | 事实号，`f001` 格式，入账时按账内顺序分配 | 是 |
| chapter_id | str | 来源章节（C1 的 `id`） | 是 |
| text | str | 事实句（确认时可被作者改写，原候选句备档进 `note`） | 是 |
| quote | str | 原文依据片段（模型转抄，未做一致性校验） | 是（可空串） |
| status | str | `extracted`＝候选／`confirmed`＝已确认真值／`rejected`＝已拒绝；词表常量 `store.STATUS_*` | 是 |
| source | str | 候选来源：模型 ID 或候选文件名 | 是 |
| note | str | 备注；改写确认时存「原文候选：…」 | 是（可空串） |
| added_at | str | 入账时间 | 是 |
| seg | int | 来源责任段序号（对应 C2） | 否（外部载入的候选没有） |
| decided_at | str | 最近一次确认／拒绝时间 | 否（没审过就没有） |

语义规则：**只有 `confirmed` 是真值**。M6 只读 confirmed；上游只能投 `extracted` 候选，升降状态只走 M5 审查（现为 `cli.py confirm`）调 `store.set_status`。

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

## 已知缺口（v0 不含，升版本再加）

- 证据坐标粒度只有 `chapter_id`＋`seg`，无字符级锚点；`quote` 与原文的一致性未校验（M7 做矛盾定位时会先撞到这两条）。
- schema v0 整体是临时件，等研究仓 N16 语义合同定案后重建（见 [store.py](../mvp/store.py) 头注）。
