# C6 · 体检报告（HEALTH_REPORT）

**版本：v1**（增加来源 chapter revision 水位与 stale 身份；v0 报告作为 legacy）

读法：C6 是可覆盖投影，不是真值。v1 保存生成时消费的 chapter revision refs；读取时与 C11 current 比较，旧版报告派生 `STALE`，不得自动清灯、自动重跑或写回事实。`evidence.quote` 仍只是定位线索，只有带 VERIFIED C11 anchor 才是已核证据。

一句话用途：一致性体检的完整产出——矛盾、存疑、别名提示、账本完整性四本账分开记，每条都带涉事事实号和双方证据。它是事实账的投影快照：重跑覆盖、会过期作废，确认后的事实改动仍回审查台，绝不回写 facts.json。

| 方向 | 模块 |
|---|---|
| 发 | M7 一致性体检（[check.py](../mvp/check.py) 的 `run_check`；`save_report` 落盘 `data/<项目>/health_report.json`） |
| 收 | M0 展示（`cli.py check` 人读打印）；未来 M5 审查台的风险收件箱 |

## 顶层结构

| 字段 | 类型 | 含义 | 必填 |
|---|---|---|---|
| contract | str | 固定 `C6_HEALTH_REPORT` | 是 |
| version | str | 固定 `v1` | 是 |
| project / generated_at / model | str | 哪本书、何时体检、用什么模型 | 是 |
| chapter_revision_refs | list[obj] | 本报告实际消费的 chapter revisions，去重保存 | 是 |
| source_revision_state | enum | `CURRENT`／`STALE`／`LEGACY_REVISION_UNKNOWN`；由读取端与 C11 派生 | 是 |
| scan | obj | 扫描台账：扫了多少、分几组、花多少调用（字段见下） | 是 |
| conflicts | list | **矛盾账**：模型判「确实打架」的问题 | 是（可空） |
| insufficient | list | **存疑账**：可能矛盾但材料不足判不死的，**不算矛盾** | 是（可空） |
| alias_hints | list | **别名提示**：疑似同一实体，只提示不合并、不算矛盾 | 是（可空） |
| integrity | obj | **账本完整性**：事实账自身的数据事故（如重复事实号），不是小说矛盾 | 是 |
| summary | obj | 汇总计数：红/黄、按层、按类、各账条数 | 是 |

`scan` 里：`facts_total/confirmed/extracted` 实扫多少（rejected 不扫，条数记在 `rejected_excluded`；重复号副本记在 `duplicate_dropped`）；`api_calls/failed_calls/clean_groups/total_tokens/seconds` 花销与通过态；`groups` 每组一条（名字、类型 entity/timeline/leftover、条数、ok/failed/skipped_budget、发现数）。

## 矛盾条目（conflicts 一条；insufficient 同构，只是没有 severity）

| 字段 | 类型 | 含义 | 必填 |
|---|---|---|---|
| issue_id | str | 矛盾 `h001`、存疑 `n001`，本报告内唯一 | 是 |
| kind | str | `naming` 人名/称谓｜`timeline` 时间线｜`setting` 设定｜`event` 事项互斥 | 是 |
| severity | str | **灯，只管严重度**：`red` 硬矛盾（同一事项被无解释推翻/明说的设定被违反）；`yellow` 疑似或低置信。时间线 v0 封顶黄灯（无双序概念，倒叙全会误判） | 是（仅 conflicts） |
| layer | str | 按涉事事实状态分层：`confirmed` 全真值打架｜`mixed` 候选顶撞真值｜`candidate` 候选互撞。**真值矛盾 ≠ 候选矛盾** | 是 |
| fact_ids | list | 涉事事实号（C4 的 `id`，项目内唯一；不用 seg 当键） | 是 |
| note | str | 为何亮灯（模型一句话说明） | 是 |
| next_step | str | 下一步去哪（按 layer/verdict 生成的固定话术） | 是 |
| evidence | list | 双方证据；v1 追加 `chapter_revision_ref`，VERIFIED 时可追加 `anchor_ref` | 是 |
| found_by | list | 哪些扫描组发现的（合并去重后可能多个） | 是 |
| confidence / hard | str / bool | 模型自评（置信、是否铁矛盾），程序据此定灯，仅供追溯 | 是 |

灯（severity）、说明（note）、证据（evidence）、去向（next_step）是四个独立字段——灯只管红黄，为何亮、凭什么、怎么办各管各的。

## v0 真实示例（legacy）

取自 `data/万鬼伏藏/health_report.json`（2026-08-13 实跑；顶层其余字段略）：

```json
{
 "contract": "C6_HEALTH_REPORT v0",
 "project": "万鬼伏藏",
 "generated_at": "2026-08-13 03:02:11",
 "model": "doubao-seed-2-1-turbo-260628",
 "scan": {
  "facts_total": 223, "confirmed": 4, "extracted": 219,
  "rejected_excluded": 1, "duplicate_dropped": 0,
  "api_calls": 9, "failed_calls": 0, "clean_groups": 6,
  "total_tokens": 23674, "seconds": 113.0,
  "groups": [
   {"name": "李星燃·块1", "kind": "entity", "facts": 110, "status": "ok", "findings": 4}
  ]
 },
 "conflicts": [
  {
   "issue_id": "h003",
   "kind": "timeline",
   "severity": "yellow",
   "layer": "candidate",
   "fact_ids": ["f077", "f080"],
   "note": "f077称李星燃是天雷落下后穿越到这个世界，f080却称他来到这个世界已经一个月，时间线存在冲突。",
   "next_step": "双方都还是候选：先在审查台（confirm）核对真伪；都被确认时才升级为真值矛盾",
   "evidence": [
    {"fact_id": "f077", "chapter_id": "c01", "seg": 3, "status": "extracted",
     "text": "李星燃并非这个世界的人，那道天雷落下后，他穿越到了这个和自己同名同姓的倒霉蛋身上。",
     "quote": "他并非这个世界的人，那道天雷落下后，他穿越到了这个和自己同名同姓的倒霉蛋身上。"},
    {"fact_id": "f080", "chapter_id": "c01", "seg": 4, "status": "extracted",
     "text": "李星燃来到这个世界一个月，炼制了一根七星锁魂绳，画了一些符咒，前往驱鬼赚钱。",
     "quote": "李星燃来到这个世界也就一个月时间，只能是炼制了一根七星锁魂绳，画了一些符咒，前往驱鬼，先赚一笔钱。"}
   ],
   "found_by": ["李星燃·块1"],
   "confidence": "high",
   "hard": true
  }
 ],
 "summary": {
  "red": 2, "yellow": 1,
  "by_layer": {"confirmed": 0, "mixed": 1, "candidate": 2},
  "by_kind": {"naming": 1, "timeline": 1, "setting": 0, "event": 1},
  "insufficient": 2, "alias_hints": 0, "duplicate_ids": 0
 }
}
```

别名提示条目（`alias_hints` 一条；机械挖掘，字段值取自《1979西北往事》实测）：

```json
{
 "hint_id": "a001",
 "names": ["周卫军", "周新军"],
 "fact_ids_a": ["f002", "f003", "f004"],
 "fact_ids_b": ["f024", "f032", "f036"],
 "note": "写法只差一字，疑似同一实体；程序不自动合并、不算矛盾，请作者认"
}
```

完整性条目（`integrity.duplicate_ids` 一条；取自《三国》实跑，该账本有 50 个重复号）：

```json
{
 "problem": "duplicate_id",
 "id": "f274",
 "kept": {"chapter_id": "c03", "seg": 2, "text": "桃林庄到了。"},
 "dropped": [{"chapter_id": "c01", "seg": 1, "text": "刘瑁醒来时鼻子里全是药味，药味苦、潮，还带着一点发霉的木头味。"}]
}
```

`integrity` 还带一次性的 `note` 和 `next_step`（修账后重跑体检才算数）。

## 语义规则

1. **材料不足 ≠ 内容矛盾**：判不死的进 `insufficient`，永远不混进 `conflicts`；矛盾账已覆盖的问题不在存疑账里复读。
2. **别名不自动合并**：同名/疑似同人只进 `alias_hints`，由作者认；模型判出的「同一人写法冲突」才进矛盾账。
3. **数据事故不冒充剧情矛盾**：账本自身违约（重复事实号）由完整性预检机械拦下，坏号只认首次出现，副本不喂模型。
4. **只读投影**：本报告不改任何事实状态；`next_step` 都指回审查台或原文，不提供「就地修复」。
5. 证据定位只有 `chapter_id`＋`seg` 段级坐标；`quote` 是抽取时模型转抄、未回填校验（I-013），**不保证能在原文精确 find 到**。
6. v1 报告的任一 `chapter_revision_ref` 落后于 C11 current 时，整份报告的 `source_revision_state` 派生为 STALE；投影可以继续展示历史，但不能为高影响写操作提供依据。
7. 旧 v0 报告没有 revision ref，迁移时统一标 `LEGACY_REVISION_UNKNOWN`，重跑后才能成为 CURRENT。

## Backward compatibility

- v0 顶层组合字符串 `C6_HEALTH_REPORT v0` 不冒充 v1；旧 reader 遇到 v1 必须 fail closed。
- v1 不修改 conflicts／insufficient／alias／integrity 的故事语义，只增加来源版本水位。
- 产品 `check.py` 尚未施工 v1；本票只冻结正式合同。

## 仍未解决

- 无双序（故事顺序 vs 叙述顺序）：倒叙/回忆会触发时间线误报，故 v0 时间线封顶黄灯。
- 无豁免机制：作者「已阅，故意的」无处落笔，重跑会原样再报（零唠叨只管单次报告内去重）。
- 分组扫描有盲区：两条事实若不共享任何挖掘出的实体、又分属不同兜底块，就没机会同屏比对；设定类矛盾没有设定集材料架（M1 v1）对照，只能靠事实句互证。
- 模型自评 hard/confidence 运行间会漂移（同输入两跑，同一对事实在 conflict 和 insufficient 间翻转过一次）。
