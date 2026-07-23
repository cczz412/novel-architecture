# Z 批五题四型答题 Prompt v1.3

只能依据事件级主账和折叠视图作答，不读取银标。你只列使用过的主账记录 ID，程序按 ID 展开原锚，并重算目标章、宏来源和梯度步距。

只输出一个 JSON 对象，不要代码围栏。顶层结构：

```json
{
  "schema_version": "z-answer-v1",
  "decision_markers": ["选题和取舍短记"],
  "items": []
}
```

必须交下面五个题目对象，`question_id` 一个不能少、不能改名、不能重复。每个对象都必须带 `question`、`status`、`not_applicable_reason`、`answer_markdown`、`record_ids`；梯度题也不能省这些通用字段。

## 1. 第 10 章回指

```json
{
  "question_id": "backtrace-ch0010",
  "question_type": "回指",
  "target_chapter": 10,
  "question": "第10章发生的哪件事由什么前因造成，对后续有什么用？",
  "status": "answered",
  "not_applicable_reason": "",
  "answer_markdown": "因什么事件→导致第10章当前情景→对后续有什么用",
  "record_ids": ["A-0010"]
}
```

引用的记录中必须至少有一条第 10 章原锚。不能写 `not_applicable`。

## 2. 第 20 章回指

```json
{
  "question_id": "backtrace-ch0020",
  "question_type": "回指",
  "target_chapter": 20,
  "question": "第20章发生的哪件事由什么前因造成，对后续有什么用？",
  "status": "answered",
  "not_applicable_reason": "",
  "answer_markdown": "因什么事件→导致第20章当前情景→对后续有什么用",
  "record_ids": ["A-0020"]
}
```

引用的记录中必须至少有一条第 20 章原锚。不能写 `not_applicable`。

## 3. 转线

```json
{
  "question_id": "cross-line",
  "question_type": "转线",
  "target_chapter": null,
  "question": "哪一个折叠视图标出的跨线出口可以承接后续？",
  "status": "answered",
  "not_applicable_reason": "",
  "answer_markdown": "因何而来／当前情景／可续动作／必验问题／对主线用途",
  "record_ids": ["A-0007"]
}
```

有真实样本时，`record_ids` 必须包含折叠视图 `cross_line_exits` 里的真实 ID。折叠视图确实没有跨线出口时才可写 `not_applicable`。

## 4. 伸缩

```json
{
  "question_id": "compression",
  "question_type": "伸缩",
  "target_chapter": null,
  "question": "一个已成立的宏节点怎样从事件记录折成压缩视图？",
  "status": "answered",
  "not_applicable_reason": "",
  "macro_id": "M-001",
  "answer_markdown": "折叠前的真实记录→折叠后的宏；按实际条数写比例",
  "record_ids": ["A-0001", "A-0002"]
}
```

`record_ids` 必须与所选 `macro_id` 的 `source_record_ids` 完全一致。折叠视图确实没有宏时才可写 `not_applicable`，并把 `macro_id` 写成 null。

## 5. 梯度

```json
{
  "question_id": "gradient",
  "question_type": "梯度",
  "target_chapter": 20,
  "question": "以样本末章为当前，各步距档有哪些真实结构落点？",
  "status": "answered",
  "not_applicable_reason": "",
  "answer_markdown": "逐档列出实际落点；没有真实落点的档写无样本",
  "current_chapter": 20,
  "gradient_points": [
    {"bucket": "0-1", "status": "sample", "chapter": 20, "distance": 0, "record_ids": ["A-0014"]},
    {"bucket": "2-5", "status": "sample", "chapter": 17, "distance": 3, "record_ids": ["A-0012"]},
    {"bucket": "6-20", "status": "sample", "chapter": 4, "distance": 16, "record_ids": ["A-0003"]},
    {"bucket": "21-50", "status": "no_sample", "chapter": null, "distance": null, "record_ids": []},
    {"bucket": "50+", "status": "no_sample", "chapter": null, "distance": null, "record_ids": []}
  ],
  "record_ids": ["A-0014", "A-0012", "A-0003"]
}
```

梯度步距＝样本末章减去落点章号。`record_ids` 必须等于各档样本记录 ID 的并集。整题不能写 `not_applicable`。

## 共同纪律

- 有真实材料可答时：`status`＝`answered`，`not_applicable_reason` 留空，必须给 `record_ids`。
- 只引用主账里存在的 ID；不输出 `anchors`。
- 推断要标明，不能把建议动作、期待或可能性写成已发生事实。
- 不要凭心算写比例、章距或宏来源，直接按输入 ID 和章号计算。

事件级主账：

```json
{{THIN_LEDGER_JSON}}
```

折叠视图：

```json
{{FOLD_VIEW_JSON}}
```

来源：Codex（依 Notion v0.3、Z 执行单、Z00g 答题失败与 Terra 核验整理）
