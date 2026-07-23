# Z 批银标对撞 Prompt v1

X 批答案是银标，只作对照，不作裁判。你要比较“本地答案”和“银标答案”，不能因为措辞不同就判错。

只输出 JSON：

```json
{
  "schema_version": "z-diff-v1",
  "decision_markers": ["最难判断的差异"],
  "items": [
    {
      "question_type": "回指",
      "label": "等价",
      "reason": "短理由",
      "ours_record_ids": [],
      "silver_section": "银标小节名",
      "evidence_status": "已核本地锚/银标已预校验/仍待原文裁"
    }
  ]
}
```

`label` 只允许：

- `我对它错`：本地答案被原锚支持，银标明确与原锚冲突；证据不够不能用。
- `它对我错`：银标被其预校验锚支持，本地答案与自己的原锚冲突或漏掉关键条件。
- `等价`：事实与用途相同，只是拆并或措辞不同。
- `待裁`：需要回更多原文，或两种解释都可能成立。

不要汇总成“总分判词”，只给逐题差异和分类。

本地答案：

```json
{{OUR_ANSWER_JSON}}
```

X 批银标答案：

<silver>
{{SILVER_ANSWER_TEXT}}
</silver>

来源：Codex（依 Notion v0.3 与 Z 执行单整理）
