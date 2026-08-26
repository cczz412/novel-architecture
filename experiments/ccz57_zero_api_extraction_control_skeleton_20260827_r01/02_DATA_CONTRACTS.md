# 02｜数据合同

## 对象关系

```text
InputSnapshot
     │
     └── Attempt（原始请求和回复，不可变）
            │
            ├── Diagnostic
            ├── ResultVersion v0
            │       │
            │       └── PatchProposal
            │              │
            │              └── ResultVersion v1
            │
            └── RelationCandidate（旁路，不写 facts）

ReplayCase → ReplayReport（只说明机械重放是否符合预注册预期）
ControllerState（只决定下一动作或停止，不修改内容）
```

## 八个设计合同

| 对象 | 主要用途 | 不能冒充什么 |
|---|---|---|
| `InputSnapshot` | 冻结题面、背景卡、Prompt、Schema、模型目录和授权引用 | 新运行许可 |
| `Attempt` | 冻结一次真实请求、响应、身份、Token、耗时和结果状态 | 可用版本或正确答案 |
| `Diagnostic` | 说明哪一轴、哪个位置、由谁检查、哪些没检查 | 总体 PASS |
| `PatchProposal` | 提交最小修改单，绑定基线、稳定事实 ID 和允许字段 | 已经合并的结果 |
| `ResultVersion` | 保存父子版本、内容哈希、diff 和分轴状态 | Gold 或作者确认事实 |
| `RelationCandidate` | 旁路保存因果等关系候选 | v2.1 `facts` 的正式字段 |
| `ReplayCase／ReplayReport` | 预注册真实回件应命中什么机械错误，并保存重放结果 | 模型准确率或语义评分 |
| `ControllerState` | 保存错误指纹、版本哈希、进展和停止原因 | 内容修改器或模型调度许可 |

对应 Schema 在 [`schemas/`](schemas/)；它们都是实验设计合同，不修改现行产品 Schema。

## 稳定身份怎么生成

### Attempt ID

同一请求和同一原始回复必须得到同一 ID：

```text
attempt_id = "att_" + first24(
  sha256(request_sha256 + ":" + raw_response_sha256 + ":" + retry_index)
)
```

任何重试、预算变体或回复字节变化都会生成新 Attempt，不能覆盖旧记录。

### Fact ID

事实 ID 只要求在同一 Attempt 的派生链里稳定：

```text
fact_id = "fact_" + first24(
  sha256(attempt_id + ":" + source_order + ":" + fact + ":" + evidence)
)
```

Patch 先指向 `fact_id + field`，程序确认基线哈希后，才解析成当时的 JSON Pointer。禁止把 `/facts/3` 当成长期身份。

如果 Patch 改了 `fact` 或 `evidence`，子版本必须生成新的 fact ID，并用 `parent_fact_id` 指回旧事实；不能让内容变了、身份却没变。

### Version ID

```text
version_id = "ver_" + first24(
  sha256(parent_version_id + ":" + content_sha256 + ":" + applied_patch_hashes)
)
```

内容回到旧哈希时，控制器能据此发现 `A→B→A`。

## 不可变规则

- Attempt 的请求、原始 stdout／stderr、响应模型、usage 和原始 SHA 只读。
- 安全围栏剥除生成新的 `ResultVersion`，不能把派生 JSON写回原始 `.bin`。
- Patch 必须保存基线版本和基线内容 SHA；不一致就拒绝。
- MergeGate 只能创建子版本；父版本永远保留。
- RelationCandidate 不能出现在 v2.1 `facts` 里。

## Patch 的最小作用域

0 API 第一版只允许人工冻结的测试 Patch，不自动生成语义修改。每张 Patch 都必须包含：

- 触发它的 Diagnostic；
- 基线版本和 SHA；
- 允许的稳定事实 ID 与字段；
- 实际触碰的稳定事实 ID 与字段；
- 修改前置条件；
- 修改后必须重跑的机械检查；
- Patch 自身 SHA。

安全格式派生不走 Patch，它属于原始内容的白名单派生，必须另存叶子不变量报告。

## 分轴状态

ResultVersion 不提供一个笼统的 `passed=true`。它至少分别保存：

```text
transport
identity
json
schema
evidence_location
value_semantics
speaker
causal
coverage
regression
```

每一轴只能是：

```text
PASS | FAIL | NOT_CHECKED | HUMAN_REQUIRED
```

比如“Schema PASS、evidence 8/8 精确命中、因果 NOT_CHECKED”，不能缩成“结果通过”。

## 仓内路径规则

- 所有证据引用使用仓库相对路径；不保存 `<LOCAL_HOME>` 这类主机路径。
- 上游证据只引用 `work/ccz57_agentic_extraction_pipeline_candidate_20260827_r01/`。
- 设计和后续程序只写自己的实验目录。
- SHA 使用小写 64 位十六进制。
- reasoning 若在原始回包中存在，只作为原始字节保留，不进入事实证据或正确性判断。

来源：Codex
