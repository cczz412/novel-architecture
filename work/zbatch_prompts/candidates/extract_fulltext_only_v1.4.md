# Z 批密候选提取 Prompt｜仅加连续全文候选 v1.4

你只看当前一章，不得使用本章之后的知识。下方“冻结证据目录”按原文顺序覆盖当前章全文，短引之间有少量重叠。你只选证据 ID，不手抄短引；程序会按 ID 展开成章号＋原文短引。

目标是“先密候选，宁多勿漏”。证据足够但分类有疑义时，用 `assertion`＝“推”或“存疑”，不要把有锚候选直接删掉。某类确实没有合格候选可以留空，但必须在四格清点里写明理由。

只输出一个 JSON 对象，不要代码围栏，不要解释。

## 输出外壳

```json
{
  "schema_version": "z-candidate-v1",
  "chapter": {{CHAPTER_NUMBER}},
  "decision_markers": ["本章最难的一处分类取舍，没有则空数组"],
  "coverage_audit": {
    "A": {"status": "emitted|none", "record_ids": [], "reason": "检查了哪些变化，为什么产出或不产出"},
    "B": {"status": "emitted|none", "record_ids": [], "reason": "检查了哪些触发，为什么产出或不产出"},
    "C": {"status": "emitted|none", "record_ids": [], "reason": "检查了哪些期待，为什么产出或不产出"},
    "D": {"status": "emitted|none", "record_ids": [], "reason": "检查了哪些规则，为什么产出或不产出"}
  },
  "records": []
}
```

`coverage_audit` 是空章自证，也是每章的防漏清点：

- 四类必须全部出现。
- 某类有记录：`status`＝`emitted`，`record_ids` 精确列出本类输出 ID。
- 某类无记录：`status`＝`none`，`record_ids`＝空数组，`reason` 写清为什么不成立。
- 全章 `records=[]` 可以，但 A/B/C/D 必须分别给出可核查理由；不能只写“无合格候选”。

## 四类记录

A 跨章因果：

```json
{
  "id": "A-C{{CHAPTER_PADDED}}-01",
  "type": "A",
  "story_line": "线名",
  "delta": "前态被什么改成后态",
  "direct_cause": "真正近因",
  "future_use": "以后哪条线会读取，未知就写待验",
  "status": "开",
  "type_state": "",
  "assertion": "明",
  "related_ids": [],
  "anchors": [{"anchor_id": "E0001"}]
}
```

B 故事内触发器：

```json
{
  "id": "B-C{{CHAPTER_PADDED}}-01",
  "type": "B",
  "trigger_condition": "故事内什么事件/时间/条件到达",
  "trigger_action": "条件到达后应触发什么",
  "status": "开",
  "type_state": "待",
  "assertion": "明",
  "related_ids": [],
  "anchors": [{"anchor_id": "E0002"}]
}
```

C 读者承诺：

```json
{
  "id": "C-C{{CHAPTER_PADDED}}-01",
  "type": "C",
  "reader_expectation": "正文已经让读者等待什么",
  "payoff_test": "发生什么才算还账",
  "status": "开",
  "type_state": "未兑现",
  "assertion": "明",
  "related_ids": [],
  "anchors": [{"anchor_id": "E0003"}]
}
```

D 世界规则：

```json
{
  "id": "D-C{{CHAPTER_PADDED}}-01",
  "type": "D",
  "condition": "如果什么条件成立",
  "consequence": "就会发生什么",
  "scope_exception": "适用范围或例外；原文没给就写无明示例外",
  "status": "开",
  "type_state": "有效",
  "assertion": "明",
  "related_ids": [],
  "anchors": [{"anchor_id": "E0004"}]
}
```

## 防漏检查顺序

按原文顺序扫完整个证据目录，再逐类清点：

- A：人物、组织、物件、调查、认知或故事线是否从前态进入可被后文读取的新状态；调查升级、限制行动、公开信息导致的认知变化都可入候选。
- B：正文是否公开了以后到达某事件、时间或条件就要执行的动作；已经说出口的后续任务也可入候选。
- C：正文是否明确吊起需要后文回答的期待；只收正文已公开承诺，不收普通未知。
- D：正文是否给出可重复适用的“如果—就会”规律；一次性场景、个人感叹不能硬写成 D。

## 硬纪律

- `anchors` 只交 `anchor_id`。ID 必须来自下方目录，不写 `chapter`，不写 `quote`，不拼两个目录项。
- 每条至少选一个真正支持该判断的 ID。一个短引不够时可以给多个 ID。
- `status` 只用“开/收/废”；`assertion` 只用“明/推/存疑”。
- A 一条只放一个可消费变化，不复述场景。
- B 必须有 `trigger_condition` 和 `trigger_action`，不得套用 A 字段。
- C 必须是正文已公开吊起的期待，小悬念和普通未知不凑数。
- D 必须是可重复适用的“如果—就会”，一次性事件不凑数。
- 同一个原始事实只存一处，其他类型只用 `related_ids` 引用。
- 某类没有合格候选就不输出，不为凑数编造；但真实发生的状态变化不能因为保守而全漏。
- ID 带类型、四位章号和两位序号，例如 `D-C0042-02`。

当前章号：`{{CHAPTER_NUMBER}}`

当前章文件名：`{{CHAPTER_FILENAME}}`

当前章全文（只帮助理解跨句关系，最终证据仍只能选择下方目录 ID）：

<chapter_text>
{{CHAPTER_TEXT}}
</chapter_text>

冻结证据目录（按原文顺序覆盖本章全文）：

```json
{{EVIDENCE_CATALOG_JSON}}
```

来源：Codex（单变量候选：相对 v1.3 只增加当前章连续全文）
