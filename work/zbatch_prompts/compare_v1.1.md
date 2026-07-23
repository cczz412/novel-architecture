# Z 批银标对撞 Prompt v1.1

X 批答案是银标，只作对照，不作裁判。你先判断是否真是同一道题、同一章节范围、同一链条，再判断答案差异。题型名字相同不等于可比。

只输出 JSON：

```json
{
  "schema_version": "z-diff-v1",
  "decision_markers": ["最难判断的差异"],
  "items": [
    {
      "comparison_id": "CMP-001",
      "ours_question_id": "backtrace-ch0010",
      "comparability": "same_question",
      "label": "等价",
      "reason": "事实和用途相同，仅措辞不同",
      "ours_record_ids": ["A-0001"],
      "silver_section": "银标小节名",
      "evidence_status": "已核本地锚/银标已预校验/仍待原文裁"
    }
  ]
}
```

对撞要求：

- 本地五个 `question_id` 必须各出现一次。银标多出的题可另加一条，`ours_question_id`＝null。
- `comparability` 只允许：`same_question`、`different_question`、`different_scope`、`missing_ours`、`missing_silver`、`insufficient_evidence`。
- 只有题目、目标章节、范围和用途一致，才能写 `same_question`。
- `comparability` 不是 `same_question` 时，`label` 必须是“待裁”。
- 本地或银标任一侧缺题、缺记录、范围不同，也必须“待裁”，不能判“等价”。
- “等价”要求事实和用途相同，只是拆并或措辞不同；不能把“不可直接比”同时标成“等价”。

`label` 只允许：

- `我对它错`：本地答案被原锚支持，银标明确与原锚冲突；证据不够不能用。
- `它对我错`：银标被其预校验锚支持，本地答案与自己的原锚冲突或漏掉关键条件。
- `等价`：同一道题里，事实与用途相同，只是拆并或措辞不同。
- `待裁`：不同题、不同范围、任一侧缺题，或仍需回原文。

不要汇总成总分判词，只给逐题差异和分类。

本地答案：

```json
{{OUR_ANSWER_JSON}}
```

X 批银标答案：

<silver>
{{SILVER_ANSWER_TEXT}}
</silver>

来源：Codex（依 Notion v0.3、Z 执行单和 Terra 中段核验整理）
