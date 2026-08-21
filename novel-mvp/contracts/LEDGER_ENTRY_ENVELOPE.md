# LEDGER_ENTRY_ENVELOPE · 十本账共同条目信封

**正式版本：`ledger-entry-envelope-v1`**

一句话用途：给人物、地点、物品、势力、体系、世界规则六本设定账及其后续长线对象提供同一套来源、确认、证据、时间与修订身份；它只冻结合同层，不实现落盘 writer。

## 1. Owner 与边界

| 项 | 正式规则 |
|---|---|
| 合同 owner | `LEDGER_ENTRY_ENVELOPE` |
| 适用范围 | 人物、地点、物品、势力、体系、世界规则六本设定账；L5 长线三对象复用时另行登记 |
| 提出者 | 作者直接编辑、M4／M5 已确认事实后的投影、题材包预填、模型候选 |
| 唯一落盘者 | 后续“设定账统一 writer”；必须复用 planstore 的事务、`id_counters` 与原子提交样式 |
| 读取者 | L2～L5 内容合同、M7、M9、M10、M11 |
| 本票不做 | 不新增 runtime writer，不改变 planstore，不定义六本账各自业务字段 |

来源真值：
- `work/ledger_content_contract_20260822_r01/00_DECIDED_DRAFT_R01.md`
- `work/ledger_content_contract_20260822_r01/01_REVIEW_R01.md`

冲突时以复核注记为准。

## 2. 六组共同字段

“六字段”按产品语义分组六组，机器对象实际有 9 个键。

| 语义组 | 机器字段 | 类型 | 规则 |
|---|---|---|---|
| 永久身份 | `id` | str | 只允许本合同前缀表；永久、不可回收、不可改号 |
| 来源身份 | `source_identity` | enum | `author_declared`／`draft_inferred`／`model_suggested`／`pack_prefilled` |
| 确认状态 | `confirm_status` | enum | `candidate`／`confirmed`／`retired` |
| 证据 | `evidence_refs` | list[str] | `f001` 形事实账内部 ID，或正式枚举 `AUTHOR_ATTESTATION` |
| 故事时间 | `story_time` | object/null | 只有变化／状态类条目可以非空；定义卡必须为 null |
| 系统修订 | `created_at`／`updated_at`／`rev`／`note` | str/str/int/str | 系统登记与修订信息；不是故事时间；`note` 即使为空也必须存在 |

### 2.1 `source_identity`

| 值 | 含义 | 硬规则 |
|---|---|---|
| `author_declared` | 作者明确声明或直接编辑后的内容 | 可以在有合法证据时进入 `confirmed` |
| `draft_inferred` | 从草稿／正文机械提取或推断 | 默认停在 `candidate`，不得自动冒充作者声明 |
| `model_suggested` | 模型建议 | 默认停在 `candidate`，不得自动确认 |
| `pack_prefilled` | 题材包预填 | 必须停在 `candidate`；作者可改可删 |

**新增语义正式成文：**作者修改 `pack_prefilled` 条目后，新的 `source_identity` 必须转为 `author_declared`，并在 `evidence_refs` 写入 `AUTHOR_ATTESTATION`。`pack_ref` 属于各内容合同的业务字段，不在共同信封内；作者修改后必须保留原 `pack_ref` 作为来源留痕。

### 2.2 `confirm_status`

- `candidate`：候选，不进入已确认真值读取。
- `confirmed`：作者已经确认；`evidence_refs` 不得为空。
- `retired`：条目保留历史身份，但不再作为当前有效定义／状态读取。退役不是物理删除。

模型和题材包铺入的内容不能直接写 `confirmed`。

### 2.3 `evidence_refs` 与 `AUTHOR_ATTESTATION`

合法元素只有两类：

1. 事实账内部永久 ID：`f001`、`f002`……；
2. 枚举值：`AUTHOR_ATTESTATION`。

`AUTHOR_ATTESTATION` 是本合同新增语义。判定规则固定为：

> 作者在定义卡上的直接编辑＝签字。

机械含义：
- 含 `AUTHOR_ATTESTATION` 的条目必须是 `source_identity=author_declared`；
- 含 `AUTHOR_ATTESTATION` 的条目必须是 `confirm_status=confirmed`；
- 程序、模型、题材包、投影过程都不能自行生成该枚举；
- 作者对题材包预填定义卡的直接编辑，必须走“来源转 author_declared＋保留 pack_ref＋写 AUTHOR_ATTESTATION”的完整迁移。

### 2.4 `story_time`

`story_time` 只描述故事世界内的有效时段。它与 `created_at`、`updated_at`、提交时间、日志时间完全不同。

- 定义卡：必须为 `null`。
- 变化／状态条目：可以是非空对象；精确锚形状由 L2～L4 内容合同继续收窄。
- 禁止在 `story_time` 中使用 `created_at`、`updated_at`、`recorded_at`、`committed_at`、`system_time`、`timestamp` 等系统时间键。
- 系统时间不能代替故事时间，故事时间也不能反推系统提交顺序。

## 3. ID 前缀与统一发号

| 账 | 前缀 |
|---|---|
| 人物账 | `CH-` |
| 地点账 | `LOC-` |
| 物品账 | `IT-` |
| 势力账 | `FA-` |
| 体系账 | `SY-` |
| 世界规则账 | `RU-` |

ID 形状为“前缀＋十进制数字”，例如 `CH-0001`、`LOC-12`。前导零只影响显示，不改变永久身份。

发号纪律：

- 复用 planstore `id_counters` 的统一计数与同事务提交样式；
- 新号必须由后续统一 writer 在同一次原子提交内读取、递增并落盘；
- **不得由各模块私自发号**；
- 失败事务不得消耗或重复使用已经对外承诺的 ID；
- 已分配 ID 永不回收、永不改写、永不跨账复用。

本票只冻结合同和校验规则，不实现统一 writer。

## 4. 真实示例

### 4.1 作者直接编辑的人物定义卡信封

```json
{
  "id": "CH-0001",
  "source_identity": "author_declared",
  "confirm_status": "confirmed",
  "evidence_refs": ["AUTHOR_ATTESTATION"],
  "story_time": null,
  "created_at": "2026-08-22T09:00:00+08:00",
  "updated_at": "2026-08-22T09:00:00+08:00",
  "rev": 1,
  "note": ""
}
```

### 4.2 题材包预填的体系定义卡信封

```json
{
  "id": "SY-0001",
  "source_identity": "pack_prefilled",
  "confirm_status": "candidate",
  "evidence_refs": [],
  "story_time": null,
  "created_at": "2026-08-22T09:05:00+08:00",
  "updated_at": "2026-08-22T09:05:00+08:00",
  "rev": 1,
  "note": "来自题材包，尚未由作者确认"
}
```

其业务内容必须另存 `pack_ref`。作者修改后，信封转为 `author_declared`／`confirmed`，新增 `AUTHOR_ATTESTATION`，但业务内容里的 `pack_ref` 保持不变。

## 5. 明确禁止

1. 禁止任何 M 模块、插件、题材包或模型绕过统一 writer 私自发号。
2. 禁止 `pack_prefilled`、`draft_inferred`、`model_suggested` 直接写成 `confirmed`。
3. 禁止 `confirmed` 条目没有证据。
4. 禁止程序伪造 `AUTHOR_ATTESTATION`。
5. 禁止作者修改题材包条目后仍把来源写成 `pack_prefilled`，或删除／改写原 `pack_ref` 留痕。
6. 禁止定义卡携带非空 `story_time`。
7. 禁止把系统时间字段塞进 `story_time`，或把系统提交时间当故事时间。
8. 禁止物理删除 `retired` 条目的历史身份。
9. 禁止在本票顺手实现统一 writer、文件布局或模块业务字段。

## 6. 开放问题

以下四项只留位，不在 L1 定义：

- 知情边字段枚举（T3）；
- ADD-043 规则／能力／例外是否拆条；
- READER 侧数据结构；
- 新账申请流程。

## 7. 机器件

- Schema：[LEDGER_ENTRY_ENVELOPE.schema.json](LEDGER_ENTRY_ENVELOPE.schema.json)
- Validator：[validate_ledger_entry_envelope.py](validate_ledger_entry_envelope.py)
- Fixtures：[LEDGER_ENTRY_ENVELOPE.fixtures.jsonl](LEDGER_ENTRY_ENVELOPE.fixtures.jsonl)
- 定向测试：`tests/test_novel_mvp_ledger_entry_envelope_contract.py`

## 8. 实现状态

`CONTRACT_ONLY__UNIFIED_WRITER_PENDING`

本合同通过只证明字段与迁移规则已经冻结，不证明六本设定账已经有正式落盘方、作者界面或端到端主循环。
