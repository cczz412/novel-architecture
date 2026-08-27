# 供应商回合与 Agent 动作协议

## 修订结论

🔥 旧抽取回包和新 Agent 回合是两种不同东西，不能再用同一个 `final content JSON` 解析规则处理。

### A. 旧抽取回包

这是 L1 探针里已经保存的供应商响应。候选事实可能放在普通 `content`／final text 里。

固定处理顺序：

```text
保存原始响应字节
→ 检查 HTTP、模型身份、完成状态和截断
→ 解析供应商外壳
→ 提取普通 content 原文
→ 重复键扫描
→ 解析事实 JSON
→ internal v2.1 Schema
→ evidence 定位
```

这一条只用于离线重放旧证据，不是新 Agent 的动作协议。

### B. 新 Agent 回合

Agent 必须通过原生工具调用表达动作。候选内容放在工具参数里，例如 `submit_baseline_candidate.arguments`，不放在普通正文里。

控制器先把不同供应商响应规范化成统一回合：

```json
{
  "schema_version": "m3-provider-turn-v1",
  "provider_protocol": "openrouter_chat_completions|ark_responses",
  "provider_response_id": "opaque string",
  "exact_model_identity": {},
  "completion_kind": "TOOL_CALLS|PLAIN_TEXT|EMPTY|TRANSPORT_ERROR",
  "tool_calls": [
    {
      "call_id": "opaque string",
      "name": "read_current_c2_segment",
      "arguments_raw": "{}"
    }
  ],
  "plain_text": null,
  "reasoning_artifact_ref": null,
  "usage": {},
  "truncation": {}
}
```

## 机械接收顺序

```text
run 身份和 current revision
→ 请求／响应原件追加保存
→ HTTP、完成状态、截断、精确模型身份
→ 供应商外壳解析
→ 规范化 ProviderTurn
→ tool call 数量、调用编号、工具名
→ arguments 原始字符串重复键扫描
→ arguments JSON 解析
→ 当前阶段允许工具检查
→ 已打包工具 Schema 校验
→ 才执行本地工具
```

## 必须写死的规则

- 有合法 `tool_calls` 时，普通正文可以为空；不能报 `FINAL_MISSING`。
- 工具参数只能从供应商的原生工具字段读取，不能从正文、代码围栏或隐藏 reasoning 里捞。
- R01.1 每回合最多执行一个工具；多个调用直接记为阻断错误，不挑一条偷偷执行。
- `call_id`／`tool_call_id` 是供应商给出的不透明值，控制器保存并原样回送，模型不能自己填写。
- OpenRouter Chat Completions 回送工具结果时，使用与调用匹配的工具结果消息和 `tool_call_id`。
- Ark Responses 续接时，供应商的 response ID、function call ID 和工具结果由适配器保存、回送；本地消息账本仍是恢复真源。
- 隐藏 reasoning 可以按供应商续接要求保存成不透明 artifact，但不能作为事实证据、动作或自动放行理由。
- 普通正文永远不当动作。第一次没有工具调用时，控制器追加一次固定短提醒；连续第二次仍没有工具调用，停止为 `NO_TOOL_SELECTED`。
- 完成、认输、请求人工也必须走结构化工具，不能靠一句“我完成了”。

## 供应商适配器的输出责任

适配器只做外壳映射，不做语义修补：

| 输入 | 统一输出 |
|---|---|
| OpenRouter `message.tool_calls[]` | `ProviderTurn.tool_calls[]` |
| Ark Responses function-call output | `ProviderTurn.tool_calls[]` |
| 普通 assistant content | `plain_text`，只保存，不执行 |
| reasoning／reasoning details | 不透明 artifact ref |
| usage／cache 字段 | 标准用量回执，保留原币种和原字段 |

## 0 API 负例

- 有一条合法 tool call、正文为空：必须通过回合外壳门。
- 正文里伪造 `<tool_call>`、原生字段为空：不得执行。
- 两条并行工具调用：拒绝且不执行任何一条。
- arguments 有重复键：拒绝。
- 工具名存在，但当前阶段不可见：拒绝。
- `call_id` 与回送结果不一致：拒绝。
- 模型输出“已经完成”但没有终止工具：第一次提醒，第二次停止。

来源：Codex
