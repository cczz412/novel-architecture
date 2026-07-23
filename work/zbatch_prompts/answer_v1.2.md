# Z 批五题四型答题 Prompt v1.2

只能依据事件级主账和折叠视图作答，不读取银标。你只列使用过的主账记录 ID，程序按 ID 展开原锚，并重算目标章和梯度步距。

只输出 JSON：

```json
{
  "schema_version": "z-answer-v1",
  "decision_markers": ["选题和取舍短记"],
  "items": [
    {
      "question_id": "backtrace-ch0010",
      "question_type": "回指",
      "target_chapter": 10,
      "question": "第10章回指问题",
      "status": "answered",
      "not_applicable_reason": "",
      "answer_markdown": "因什么事件→导致第10章当前情景→对后续有什么用",
      "record_ids": ["A-0001"]
    }
  ]
}
```

必须交五道题，`question_id` 一个不能少、不能改名、不能重复：

- `backtrace-ch0010`：题型“回指”，`target_chapter`＝10。答案引用的记录中必须至少有一条第 10 章原锚。
- `backtrace-ch0020`：题型“回指”，`target_chapter`＝20。答案引用的记录中必须至少有一条第 20 章原锚。
- `cross-line`：题型“转线”，`target_chapter`＝null。找一个真实故事线切换点，给“因何而来／当前情景／可续动作／必验问题／对主线用途”。
- `compression`：题型“伸缩”，`target_chapter`＝null。选一段已成立的因果，展示折叠前后；比例由实际条数计算，不要心算。
- `gradient`：题型“梯度”，`target_chapter`＝样本末章，并额外输出 `current_chapter` 和 `gradient_points`。

梯度题结构：

```json
{
  "question_id": "gradient",
  "question_type": "梯度",
  "target_chapter": 20,
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

- 梯度步距＝样本末章减去落点章号。`record_ids` 必须等于各档样本记录 ID 的并集。
- 有真实材料可答时：`status`＝`answered`，`not_applicable_reason` 留空，必须给 `record_ids`。
- 两道回指和梯度必须真答，不能写 `not_applicable`。
- 当前范围确实没有真实转线点或已闭环因果段时：转线/伸缩保留题目，`status`＝`not_applicable`，写清原因，`record_ids` 为空数组。
- 只引用主账里存在的 ID；不输出 `anchors`。推断要标明，不能把建议动作、期待或可能性写成已发生事实。

事件级主账：

```json
{{THIN_LEDGER_JSON}}
```

折叠视图：

```json
{{FOLD_VIEW_JSON}}
```

来源：Codex（依 Notion v0.3、Z 执行单和 Terra 中段核验整理）
