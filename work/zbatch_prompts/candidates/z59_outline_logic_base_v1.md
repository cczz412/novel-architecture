# 第59道大纲／逻辑句最小试验组件 v1

你只处理当前章已经落盘的中性事件池，不补写正文里没有的事实，也不调用本章之后的知识。

把中性事件编排成便于后续大纲组件读取的逻辑句。每条应尽量回答：谁发生了什么、前因或触发是什么、产生了什么状态转变。没有独立状态转变时，明确写“本条无独立状态转变”，不要沉默省略。

要求：

- 每条至少引用一个输入 `event_id`，引用只能来自下方事件池。
- 可以把同一逻辑链上的多个输入事件合成一条，但不得捏造新人物、新地点或新结果。
- `logic_sentence` 用完整句说明主体、动作和结果；有明确因果才写因果，没有就只写发生关系。
- `state_change` 只写事件前后发生的状态变化；没有则写固定句“本条无独立状态转变”。
- 输出顺序跟随输入事件的最早原文顺序。

只输出一个 JSON 对象，不要代码围栏，不要解释：

```json
{
  "schema_version": "z59-outline-logic-v1",
  "chapter": {{CHAPTER_NUMBER}},
  "outline_items": [
    {
      "item_id": "OL-C{{CHAPTER_PADDED}}-01",
      "source_event_ids": ["EV-C{{CHAPTER_PADDED}}-01"],
      "logic_sentence": "谁在什么条件下做了什么，并产生什么结果",
      "state_change": "状态从什么变成什么；没有则写固定句"
    }
  ]
}
```

当前章号：`{{CHAPTER_NUMBER}}`

已落盘中性事件池：

```json
{{NEUTRAL_EVENTS_JSON}}
```

来源：Codex
