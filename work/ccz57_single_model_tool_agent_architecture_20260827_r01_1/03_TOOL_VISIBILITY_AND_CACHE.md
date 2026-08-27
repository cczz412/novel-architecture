# 工具开放与缓存策略

## 修订结论

R01.1 采用“分阶段固定工具包”。一个阶段内工具定义和顺序保持不变；状态切换到另一个工具包时，允许缓存不命中，不伪装成同一稳定前缀。

完整 32 项目录只保留为目标能力地图，不等于 A 票要把 32 项都做成模型可调用工具。

## 三种能力必须分开

| 类型 | 谁决定调用 | 是否发给模型 | 例子 |
|---|---|---:|---|
| 模型可调用工具 | 模型在当前阶段选择 | 是 | 读当前 C2、提交 baseline、列诊断、请求人工 |
| 控制器固定服务 | 程序按固定次序自动运行 | 否 | 保存原件、外壳解析、Schema、evidence、预算、checkpoint |
| 人工处置动作 | 作者／CZ 明确选择 | 否 | 接受语义 Patch、确认因果边、扩大预算 |

把机械门也伪装成模型工具，只会增加模型选错工具的机会，还会让权限和缓存更难控制。

## 候选工具包

### `baseline-r01.1`

- `read_current_c2_segment`
- `submit_baseline_candidate`
- `request_human_review`
- `declare_no_progress`

### `diagnose-r01.1`

- `read_current_c2_segment`
- `read_c1_range`
- `list_open_diagnostics`
- `query_story_memory` 暂不进入 A／C；等查询字段拆成可验证的窄 Schema 后再加入
- `request_human_review`
- `declare_no_progress`

### `patch-r01.1`

- 局部字段 Patch
- 新增事实 Patch
- 因果提示提案
- Patch 预览读取
- 请求干净复核
- 请求人工

### `finalize-r01.1`

- 预览 C3
- 标记责任段完成
- 请求人工
- 声明无进展

A 票只冻结 `baseline-r01.1` 以及控制器固定服务。B 才讨论 diagnose／patch／finalize；C 只使用 baseline 的四个工具。

## 缓存身份

每个工具包单独冻结：

```json
{
  "tool_bundle_id": "baseline-r01.1",
  "tool_bundle_sha256": "64位小写hex",
  "prompt_prefix_sha256": "64位小写hex",
  "provider_protocol": "openrouter_chat_completions|ark_responses",
  "exact_model_identity": {},
  "cache_policy": "MEASURE_ONLY_NOT_AUTHORITY"
}
```

规则：

- 同一工具包内，system、合同摘要、工具定义和工具顺序尽量逐字不变。
- run ID、时间、预算、C2、Diagnostic 和工具结果放在动态部分。
- 切换工具包时重新计算缓存身份；不把旧命中率沿用过来。
- provider cache、session ID、previous response ID 都只是加速器。
- 本地 Attempt、工具账、候选版本和 checkpoint 才能恢复任务。
- 响应缓存默认关闭，避免状态变化后重放旧 tool call。
- 没有真实 usage 回执时，只能写“未验证”，不能写“缓存已生效”。

## 实验要回答什么

- 同一工具包第二轮是否出现真实 cached read／write；
- 工具包切换后缓存损失是多少；
- 缓存命中是否改变工具调用参数；
- 断开供应商续接后，仅靠本地账本是否能重建同一状态；
- 缓存省下的钱，是否抵得上分阶段工具包的额外调用。

来源：Codex
