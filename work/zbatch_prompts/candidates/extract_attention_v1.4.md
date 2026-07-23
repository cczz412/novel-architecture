# Z 批密候选提取｜注意力层序候选 v1.4

## 1. 任务与证据权限

你只分析当前一章，不得使用本章之后的知识。目标是先产“密候选”，宁多勿漏，但不能脑补。

- 当前章全文是唯一事实正文。
- 冻结证据目录与全文同源，只负责让你选择证据 ID；不得手抄引文。
- 本页的规则、例子和提醒只教你怎么判断，不能当小说事实。
- 候选不是最终裁决；证据够但分类有疑义时，用 `assertion`＝“推”或“存疑”，不要直接删掉。

## 2. 按 A→B→C→D 扫描

- A 跨章因果：人物、组织、物件、调查、认知或故事线从前态进入可被后文读取的新状态。一条只放一个变化。
- B 故事内触发器：正文已公开“某事件、时间或条件到达后，要执行某动作”。
- C 读者承诺：正文明确吊起需要后文回答的期待；普通未知和小悬念不收。
- D 世界规则：可重复适用的“如果—就会”；一次性场景和个人感叹不收。

同一个原始事实只存一处，其他类型只用 `related_ids` 关联。某类确实没有候选可以为空，但必须在输出末尾写清原因。

## 3. 三个微型边界例

下面都是分类示意，不是本章事实，示意文字和编号都不得复制进输出：

- 正例：正文若明确写出“调查尚未介入→警方正式介入并限制当事人离开”，这是可被后文读取的 A 状态变化；再从本章证据目录选真实 ID。
- 反例：角色一时害怕、惊讶或感叹，不等于可重复的 D 规则。
- 证据边界：全文帮助你理解跨句关系，最终 `anchors` 仍只能选择本章冻结目录里的真实 `E####`。

## 4. 当前章卡

- 当前章号：`{{CHAPTER_NUMBER}}`
- 当前章文件名：`{{CHAPTER_FILENAME}}`
- 可见范围：只限这一章

## 5. 当前章全文

<chapter_text>
{{CHAPTER_TEXT}}
</chapter_text>

## 6. 同章冻结证据目录

目录按原文顺序覆盖全文，短引之间有少量重叠。只选择 `anchor_id`，程序会回填章号和原文短引。

```json
{{EVIDENCE_CATALOG_JSON}}
```

## 7. JSON 输出契约

只输出一个 JSON 对象，不要代码围栏，不要解释。对象内先写 `records`，再写 `coverage_audit`。

```json
{
  "schema_version": "z-candidate-v1",
  "chapter": {{CHAPTER_NUMBER}},
  "decision_markers": ["本章最难的一处分类取舍，没有则空数组"],
  "records": [],
  "coverage_audit": {
    "A": {"status": "emitted|none", "record_ids": [], "reason": "检查了哪些变化，为什么产出或不产出"},
    "B": {"status": "emitted|none", "record_ids": [], "reason": "检查了哪些触发，为什么产出或不产出"},
    "C": {"status": "emitted|none", "record_ids": [], "reason": "检查了哪些期待，为什么产出或不产出"},
    "D": {"status": "emitted|none", "record_ids": [], "reason": "检查了哪些规则，为什么产出或不产出"}
  }
}
```

记录形状：

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

```json
{
  "id": "B-C{{CHAPTER_PADDED}}-01",
  "type": "B",
  "trigger_condition": "故事内什么事件、时间或条件到达",
  "trigger_action": "条件到达后应触发什么",
  "status": "开",
  "type_state": "待",
  "assertion": "明",
  "related_ids": [],
  "anchors": [{"anchor_id": "E0002"}]
}
```

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

`coverage_audit` 必须覆盖 A/B/C/D：有记录就写 `emitted` 并精确列本类输出 ID；没记录才写 `none`、空 ID 数组和具体理由。全章 0 条允许，但不能只写“无合格候选”。

## 8. 临交稿提醒

按 A→B→C→D 完整扫描。先把有锚候选写进 `records`，再为真正为空的类型写 `coverage_audit`。只输出 JSON；不猜测；不复制示意；所有 `anchor_id` 必须来自本章目录。

来源：Codex（只借小说101的注意力层序，字段仍用 Z 批 A/B/C/D）
