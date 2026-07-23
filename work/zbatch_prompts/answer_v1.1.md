# Z 批四型答题 Prompt v1.1

只能依据事件级主账和折叠视图作答，不读取银标。你只列使用过的主账记录 ID，程序按 ID 展开原锚。

只输出 JSON：

```json
{
  "schema_version": "z-answer-v1",
  "decision_markers": ["选题和取舍短记"],
  "items": [
    {
      "question_type": "回指",
      "question": "具体问题",
      "status": "answered",
      "not_applicable_reason": "",
      "answer_markdown": "答案",
      "record_ids": ["A-0001"]
    }
  ]
}
```

必须覆盖四型：

- 回指：第 10 章与第 20 章各选一处，回答“因什么事件→导致当前情景→对后续有什么用”。
- 转线：找一个真实故事线切换点，给“因何而来／当前情景／可续动作／必验问题／对主线用途”。
- 伸缩：选一段已闭环因果，展示折叠前后。
- 梯度：以样本末章为当前，展示线内步距 0-1／2-5／6-20／21-50／50+ 的实际落点；当前样本跨度不足的档位写“无样本”，不能凑数。

- 有真实材料可答时：`status`＝`answered`，`not_applicable_reason` 留空，必须给 `record_ids`。
- 回指和梯度必须真答，`status` 只能是 `answered`。梯度里跨度不够的个别档位可在正文写“无样本”，但整题不能跳过。
- 当前 20 章确实没有真实转线点或已闭环因果段时：转线/伸缩仍保留题型，`status`＝`not_applicable`，写清 `not_applicable_reason`，`record_ids` 为空数组。不能为了过题编造样本。
- 只引用主账里存在的 ID；不输出 `anchors`。推断要标明，不能把建议动作写成已发生事实。

事件级主账：

```json
{{THIN_LEDGER_JSON}}
```

折叠视图：

```json
{{FOLD_VIEW_JSON}}
```

来源：Codex（依 Notion v0.3、Z 执行单和 Z00c 冒烟结果整理）
