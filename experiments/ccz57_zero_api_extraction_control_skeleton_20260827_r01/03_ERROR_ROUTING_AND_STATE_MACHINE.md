# 03｜错误路由与状态机

## 路由顺序

错误检查必须按下面顺序执行。前面已经阻断时，后面没有执行的轴写 `NOT_CHECKED`，不能补写成 PASS。

```text
文件与 SHA
  → 运输状态
  → 模型身份
  → 空回复／截断
  → 外壳 JSON
  → content 重复键扫描
  → content JSON
  → v2.1 Schema
  → evidence 精确定位
  → 关系／说话人／覆盖候选提示
  → Patch 作用域与版本门
```

## 第一版错误表

| 代码 | 怎样发现 | 程序允许做什么 | 停止或下一步 |
|---|---|---|---|
| `SOURCE.MISSING` | 引用文件不存在 | 什么都不改 | `STOP_SOURCE_MISSING` |
| `SOURCE.HASH_MISMATCH` | 当前 SHA 与冻结值不同 | 什么都不改 | `STOP_SOURCE_DRIFT` |
| `TRANSPORT.EMPTY_RESPONSE` | stdout 或任务内容为空 | 只记原件和回执 | `STOP_EMPTY_RESPONSE` |
| `TRANSPORT.TRUNCATED` | finish reason、incomplete 状态或输出顶满预算且未完成 | 只记截断 | `STOP_TRUNCATED` |
| `IDENTITY.REQUEST_MODEL_MISSING` | 冻结请求 ID 不在保存的目录快照 | 禁止换号 | `STOP_IDENTITY_MISMATCH` |
| `IDENTITY.RESPONSE_MODEL_MISMATCH` | 返回 ID 不符合冻结绑定 | 禁止静默 fallback | `STOP_IDENTITY_MISMATCH` |
| `JSON.OUTER_FENCE` | content 被一层完整围栏包住 | 可走白名单格式派生 | 派生后重新检查；叶子变化则 `STOP_UNSAFE_DERIVATION` |
| `JSON.DUPLICATE_KEY` | 保留顺序的原始键扫描发现同一对象重复键 | 禁止交普通解析器静默覆盖 | `STOP_UNSAFE_JSON` |
| `JSON.PARSE_ERROR` | content 不能正常解析 | 保存错误位置，不猜修 | `STOP_UNSAFE_JSON` |
| `SCHEMA.EMPTY_OPTIONAL` | 可选字段出现空字符串并违反 Schema | 只记录目标事实和字段 | `STOP_HUMAN_REQUIRED` |
| `SCHEMA.MISSING_REQUIRED` | 必填字段缺失 | 不补默认值 | `STOP_HUMAN_REQUIRED` |
| `SCHEMA.INVALID_ENUM` | 状态等字段不在冻结枚举 | 不猜正确值 | `STOP_HUMAN_REQUIRED` |
| `EVIDENCE.NOT_FOUND` | evidence 不是正文连续子串 | 不改 evidence | `STOP_EVIDENCE_NOT_FOUND` |
| `EVIDENCE.MULTIPLE_MATCHES` | 同一证据命中多处且没有唯一锚 | 保存所有位置 | `STOP_HUMAN_REQUIRED` |
| `CAUSAL.REVIEW_CANDIDATE` | 正文有明确因果提示，而结果没有可表示的关系；只作候选提示 | 生成旁路 RelationCandidate | `STOP_HUMAN_REQUIRED` |
| `PATCH.BASE_HASH_MISMATCH` | Patch 绑定的基线不是当前版本 | 拒绝 Patch | `STOP_BASE_HASH_MISMATCH` |
| `PATCH.SCOPE_VIOLATION` | 实际修改超出稳定事实 ID 和允许字段 | 拒绝 Patch | `STOP_PATCH_SCOPE_VIOLATION` |
| `REGRESSION.UNTOUCHED_CHANGED` | 未触碰字段发生变化 | 拒绝 Patch | `STOP_REGRESSION` |
| `CONTROL.NO_PROGRESS` | 同一错误和同一策略重复，严重度没下降 | 不再继续 | `STOP_NO_PROGRESS` |
| `CONTROL.OSCILLATION` | 版本哈希或字段值出现 A→B→A | 不再继续 | `STOP_OSCILLATION` |
| `CONTROL.ZERO_API_BOUNDARY` | 下一步需要模型、网络或未批准语义处理器 | 什么都不发 | `STOP_ZERO_API_BOUNDARY` |

## 状态机

```text
PLANNED
  ↓
ATTEMPT_IMPORTED
  ↓
SOURCE_VERIFIED
  ↓
TRANSPORT_CHECKED
  ↓
IDENTITY_CHECKED
  ↓
RAW_JSON_CHECKED
  ├── 可安全剥围栏 → DERIVED_FORMAT_CREATED → RAW_JSON_CHECKED
  ├── 重复键／坏 JSON ──────────────────────────────→ STOPPED
  ↓
SCHEMA_CHECKED
  ├── 合同阻断 ─────────────────────────────────────→ HUMAN_PENDING
  ↓
EVIDENCE_LOCATED
  ├── 找不到／歧义 ─────────────────────────────────→ HUMAN_PENDING 或 STOPPED
  ↓
DIAGNOSED
  ├── 需要模型／作者 ───────────────────────────────→ HUMAN_PENDING
  ├── 无待处理机械错误 ─────────────────────────────→ READY_FOR_HUMAN
  ↓
PATCH_PROPOSED（只接人工冻结测试 Patch）
  ↓
PATCH_VERIFIED
  ├── 失败 ─────────────────────────────────────────→ STOPPED
  ↓
VERSION_CREATED
  ├── 无进展／震荡／回归 ───────────────────────────→ STOPPED
  └── 仍有人工轴 ───────────────────────────────────→ HUMAN_PENDING
```

`READY_FOR_HUMAN` 只表示机械门已经完成，不能直接进入 M4 已确认区。

## 状态转移硬条件

- 任何状态只能追加事件，不回写历史事件。
- `Attempt` 一经导入，原始请求和回复 SHA 不再变化。
- `RAW_JSON_CHECKED` 必须同时保存外壳状态和 content 状态。
- 有 `JSON.DUPLICATE_KEY` 时，不得生成普通解析后的 CandidateVersion。
- `SafeFormatDeriver` 只有在叶子值、键值、数组顺序全部相同时才能生成派生版本。
- `PatchProposal` 必须先通过基线哈希和作用域，再预览修改后结果。
- `MergeGate` 只能创建子版本。
- 任何语义轴没检查，就必须留在 `NOT_CHECKED` 或 `HUMAN_REQUIRED`。

## 错误指纹

```text
error_signature = sha256(
  axis + code + stable_target_ids + normalized_evidence_anchor + checker_version
)
```

指纹不包含 Attempt ID。否则同一个问题换一次重试就会被误认成新问题。

整个状态还保存：

```text
state_fingerprint = sha256(
  current_version_sha256 + sorted(open_error_signatures)
)
```

## 无进展、震荡和回归

下面任意一条成立就停：

- 同一错误指纹和同一策略已经出现两次，严重度没有下降；
- 两张连续 Patch 的规范化操作完全相同；
- 最近四个版本里出现当前内容哈希；
- 同一字段历史为 A→B→A；
- Patch 是最近 Patch 的反向操作；
- 正确项被改错；
- 未触碰字段变化；
- Schema 错误、矛盾或重复数量增加；
- 继续需要 API、模型或未批准语义判断。

当前四题不是 Gold，所以“正确项回归”在这一轮只能对机械不变量和人工冻结测试断言生效，不能假装有正式语义 Gold。

## 没有总 PASS

每次输出都要像下面这样写范围：

```text
运输 PASS；身份 PASS；JSON PASS；Schema PASS；
evidence 8/8 精确命中；说话人 NOT_CHECKED；
因果 HUMAN_REQUIRED；覆盖 NOT_CHECKED。
```

不能只输出“通过”。

来源：Codex
