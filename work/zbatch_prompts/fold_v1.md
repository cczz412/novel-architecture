# Z 批折叠视图 Prompt v1

输入是事件级主账。你只生成视图，不删除、不改写底账。

只输出 JSON：

```json
{
  "schema_version": "z-fold-v1",
  "decision_markers": ["折叠时最难的一两处取舍"],
  "macros": [
    {
      "id": "M-001",
      "summary": "根因→最大转折→结果→开放口",
      "status": "收",
      "source_record_ids": ["A-0001"],
      "kept_reasons": ["根因", "跨线出口"],
      "anchors": [
        {"chapter": 1, "quote": "起点锚"},
        {"chapter": 5, "quote": "转折锚"},
        {"chapter": 9, "quote": "落点锚"}
      ]
    }
  ],
  "open_record_ids": [],
  "cross_line_exits": [],
  "compressed_view_markdown": "两三千字目标的压缩视图"
}
```

折叠安全四条：

1. 段内节点都收，或未收部分另列为开放项。
2. 宏节点保留最早根因、最大转折、最终结果。
3. 跨故事线出口全保留。
4. 每个宏节点尽量保留起/转/落三锚；锚只能原样取自输入。

压缩视图只留：仍开节点、高扇出节点、故事线交叉口、已收束宏节点。压缩预算跟开放因果口走，不为达到固定字数删断因果。

事件级主账：

```json
{{THIN_LEDGER_JSON}}
```

来源：Codex（依 Notion v0.3 与 Z 执行单整理）
