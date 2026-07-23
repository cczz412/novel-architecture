# 原样复述 Prompt v1.0

你只做逐字复制，不做总结、改写、纠错、补充或分类。

输入对象里的每个 `source_text` 必须原样放进对应输出项的 `text`。项目顺序、`item_id` 和 `source_sha256` 也必须保持一致。标点、空格、换行和大小写都不能改变。

只输出一个 JSON 对象，不要代码围栏，不要解释：

```json
{
  "schema_version": "z-verbatim-restatement-v1",
  "items": [
    {
      "item_id": "ITEM-0001",
      "source_sha256": "输入中的同一值",
      "text": "输入中的 source_text，逐字不变"
    }
  ]
}
```

输入：

```json
{{INPUT_JSON}}
```

来源：Codex
