# 工具 Schema 打包合同

## 为什么要加这一层

R01 的 47 个 JSON 代码块都能解析，但有 21 个工具片段引用 `#/$defs/...`，片段自身没有对应的 `$defs`。这只能证明 Markdown 里的 JSON 语法没坏，不能证明某个工具可以单独交给 Doubao 或 OpenRouter。

R01.1 把 Schema 分成两层：

- **内部标准 Schema**：供本地验证和文档复用，可以使用 `$defs`；
- **供应商工具 Schema**：每个工具都必须是独立、完整、冻结的发送对象，不能依赖文档另一段里的定义。

## 打包器的确定性输入和输出

输入：

- 工具名、说明和内部参数 Schema；
- 共享 `$defs`；
- 精确供应商协议；
- 精确模型身份；
- 工具包身份与允许工具名单；
- 明确登记的供应商兼容变换版本。

输出：

```json
{
  "bundle_contract": "M3_TOOL_SCHEMA_BUNDLE",
  "bundle_version": "r01.1",
  "provider_protocol": "openrouter_chat_completions|ark_responses",
  "exact_model_identity": {},
  "tool_bundle_id": "baseline-r01.1",
  "canonical_internal_schema_sha256": "64位小写hex",
  "provider_payload_sha256": "64位小写hex",
  "compatibility_transform_version": "none-or-explicit-version",
  "tool_names": [],
  "validation_receipt_ref": "artifact://..."
}
```

## 固定打包顺序

```text
读取内部工具 Schema
→ 解析所有本地 $ref
→ 检查循环引用和缺失引用
→ 为当前供应商内联必要定义
→ 按明确白名单做兼容变换
→ canonical JSON
→ 计算内部与供应商版本 SHA
→ 本地 Schema 自检
→ 冻结为不可变工具包
```

## 禁止静默做的事

- 不能因为供应商不认识某个关键字，就悄悄删除后继续发。
- 不能把可选字段偷偷改成必填或 `null`，除非兼容变换合同写明并有差异回执。
- 不能把 `additionalProperties: false` 删除。
- 不能把失败的 `$ref` 当成开放对象。
- 不能只保存内部 Schema hash，不保存真正发给供应商的 payload hash。
- 不能从某一家通过，外推另一家也支持。

## R01.1 的保守发送形状

在 C 票真实预检以前，供应商工具参数优先采用完全内联的基础形状：

- `type`、`properties`、`required`、`additionalProperties`；
- 简单 `enum`、`items`、长度和数值边界；
- 不依赖远程引用；
- 不发送 `$schema`、`$id`；
- `$ref`／`$defs` 只有精确端点预检证明接受后才可保留。

这不是宣称供应商一定不支持高级 Schema，而是避免 A 票在没有真实预检时先押注。

## A 票机械验收

- 所有内部 Schema 均可解析；
- 所有本地引用都能解析到确定对象；
- 每个供应商工具参数是独立完整 JSON；
- 相同输入重复打包得到相同字节和 SHA；
- 任一兼容变换都有 before／after diff；
- 21 个当前悬空引用用例全部转为完整对象或明确失败；
- 全程网络调用 0。

## C 票真实预检

每个精确端点单独登记：

- HTTP 是否接受工具 Schema；
- 是否产生原生工具调用；
- arguments 是否符合冻结 Schema；
- 是否出现供应商悄悄替换模型或 provider；
- 不支持哪个关键字；
- 失败时原始错误和请求 SHA 是什么。

来源：Codex
