# LEDGER_ENTRY_ENVELOPE · 十本账共同条目信封

**正式版本：`ledger-entry-envelope-v2`；兼容读取：`ledger-entry-envelope-v1`**

一句话用途：给人物、地点、物品、势力、体系、世界规则六本设定账及其后续长线对象提供同一套来源、确认、证据、时间与修订身份；落盘方是 `settingstore`，本合同只冻字段，不实现文件布局。

## 1. Owner 与边界

| 项 | 正式规则 |
|---|---|
| 合同 owner | `LEDGER_ENTRY_ENVELOPE` |
| 适用范围 | 人物、地点、物品、势力、体系、世界规则六本设定账。L5 长线三对象（卷 `VOL-`／人物命运 `DESTINY-`／灵感 `INS-`）已登记：住规划账、复用规划账公共字段，另在各自合同内本地校验 `confirm_status`／`evidence_refs` 语义（`AUTHOR_ATTESTATION` 判定规则同本合同）；三前缀由 planstore `id_counters` 发号，不进本合同 §3 前缀表 |
| 提出者 | 作者直接编辑、M4／M5 已确认事实后的投影、题材包预填、模型候选 |
| 唯一落盘者 | `settingstore`；必须复用 planstore 的事务、`id_counters` 与原子提交样式，见 [SETTING_LEDGER_STORAGE.md](SETTING_LEDGER_STORAGE.md) |
| 读取者 | L2～L5 内容合同、M7、M9、M10、M11 |
| 本票不做 | L1 当时不实现 runtime writer；落盘现由 `SETTING_LEDGER_STORAGE`／`settingstore` 承接。本合同仍不定义六本账各自业务字段 |

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
| `pack_prefilled` | 题材包预填 | v1 必须停在 `candidate`；v2 可由作者退役，但不能因此变成 `confirmed` |

**新增语义正式成文：**作者编辑 `pack_prefilled` 的业务正文后，新的 `source_identity` 必须转为 `author_declared`，并在 `evidence_refs` 写入 `AUTHOR_ATTESTATION`。只退役、不改正文的操作不走这条转正路径。`pack_ref` 属于各内容合同的业务字段，不在共同信封内；作者修改后必须保留原 `pack_ref` 作为来源留痕。

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
- 含 `AUTHOR_ATTESTATION` 的条目可以是 `confirm_status=confirmed` 或 `retired`；退役保留“曾经确认”的历史签字，不产生新签字；
- 程序、模型、题材包、投影过程都不能自行生成该枚举；
- 作者对题材包预填定义卡的直接编辑，必须走“来源转 author_declared＋保留 pack_ref＋写 AUTHOR_ATTESTATION”的完整迁移。

### 2.4 `story_time`

`story_time` 只描述故事世界内的有效时段。它与 `created_at`、`updated_at`、提交时间、日志时间完全不同。

- 定义卡：必须为 `null`。
- 变化／状态条目：可以是非空对象；精确锚形状由 L2～L4 内容合同继续收窄。
- 禁止在 `story_time` 中使用 `created_at`、`updated_at`、`recorded_at`、`committed_at`、`system_time`、`timestamp` 等系统时间键。
- 系统时间不能代替故事时间，故事时间也不能反推系统提交顺序。

## 2b. v2 标签与标签组

v1 条目继续按原九个共同字段校验；v2 条目在此基础上必须带 `tags` 和 `tag_groups`。标签只是命名空间化的描述，不能代替作者确认，也不能自己授予权限。

标签组规则版本固定写成 `tag-group-rules-v1`。每个 v2 标签都必须属于至少一个组；每组的 `members` 必须来自本条目的 `tags`，组 ID 不得重复，`targets` 必须命中宿主内容合同列出的字段，未知规则、未知字段、缺少必要组成员时拒绝。作者界面只让作者选择组并查看限制说明，底层仍保留完整规则对象，不能为了页面清爽把规则藏回口头解释。

四种 `mutation` 的含义固定为：`editable` 可按本组写入权限修改；`write_once` 首次写入后不可改；`frozen` 不允许普通修改；`transition_only` 只能按 `transition_rule` 指定的状态机变化。第一版唯一允许的规则名是 `confirmation_forward_v1`；缺少规则或填入未知规则都拒绝。

v2 必须有下列三个合同内置组。成员标签与组名相同；管理方必须为合同（`managed_by=CONTRACT`）。目标、修改方式、转换规则和写入方必须与下表一致，不能靠改名、搬走字段或改成作者组解除保护。读取方和屏蔽受众可进一步收紧，但不能自行授权。普通修订不能改变已有合同内置组；规则升版另走显式迁移。

| 必要组 | 保护字段 | 修改方式 | 转换规则 | 可请求写入方 |
|---|---|---|---|---|
| `core:identity` | `/id`、`/created_at` | `write_once` | `null` | `SYSTEM` |
| `core:confirmation` | `/confirm_status` | `transition_only` | `confirmation_forward_v1` | `AUTHOR` |
| `core:revision` | `/rev`、`/updated_at` | `editable` | `null` | `SYSTEM` |

修订组的“可编辑”只允许受信 writer 推进系统字段：创建时修订号为 1，更新时恰好加 1，更新时间严格前进。普通请求不能指定结果，也不能用另一个组放宽这条宿主限制。合同校验器核对前后版本；实际写盘拦截留给第二刀。插件不能创建或管理 `core:` 命名空间内的组。

实际权限按交集计算：受信账号权限 ∩ 本次任务许可 ∩ 内容合同限制 ∩ 所有命中组限制。`access` 只是上限，不是授权凭证；真正写入仍必须经过原 writer。自动屏蔽发生在送出前，不能留下秘密字段的外壳。

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
- 新号必须由 `settingstore` 在同一次原子提交内读取、递增并落盘；
- **不得由各模块私自发号**；
- 失败事务不得消耗或重复使用已经对外承诺的 ID；
- 已分配 ID 永不回收、永不改写、永不跨账复用。

L1 只冻结合同和校验规则；统一 writer 现由 `settingstore` 实现。

## 4. 真实示例

以下保留 v1 示例形状，供旧版读取对照；v2 完整样例见 [v2 校验样例](LEDGER_ENTRY_ENVELOPE.v2.fixtures.jsonl)，必须包含标签和三个必要组。

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
5. 禁止作者编辑题材包业务正文后仍把来源写成 `pack_prefilled`，或删除／改写原 `pack_ref` 留痕；仅退役不触发业务编辑转正。
6. 禁止定义卡携带非空 `story_time`。
7. 禁止把系统时间字段塞进 `story_time`，或把系统提交时间当故事时间。
8. 禁止物理删除 `retired` 条目的历史身份。
9. 禁止把信封合同当成落盘方；文件布局与原子提交只认 `SETTING_LEDGER_STORAGE`／`settingstore`。

## 6. 确认流程与退役

`confirmation_forward_v1` 只允许向前走：`candidate → confirmed` 需要作者和证据，`candidate → retired` 可以由作者放弃，`confirmed → retired` 保留已有签字但不改正文、不新增或撤销 `AUTHOR_ATTESTATION`；`confirmed → candidate` 和 `retired → candidate/confirmed` 都拒绝。v1 仍按旧规则拒绝带签字的 retired；只有 v2 才保留“曾经确认”的 retired 历史语义。失败事务可以回滚到“本次写入未发生”，读取旧版也不是把 current 指针拨回去。人物故事里的死亡／复活是独立故事时间条目，不属于系统回退。

## 7. 迁移

退役只允许改变 `confirm_status`、`rev` 和 `updated_at`；来源、证据、备注、标签及其余信封字段必须保留。调用确认流程校验时，退役必须提供前后完整业务正文快照；任一快照缺失就拒绝，不能把“未比较”当作正文未变。题材包候选转作者确认时，无论使用专用编辑入口还是通用确认入口，都必须新增作者签字并核对前后题材包来源（`pack_ref`）一致。v2 退役保留根字段和业务子项中的历史签字；子项如别名、状态记录、成员、关系仍要求作者声明来源。v1 的嵌套签字规则不变。

v1 记录保留原文和原版本；迁移必须显式生成 v2，不能静默改写。迁移程序可以机械补入 `id`、`created_at` 和修订纪律对应的保护组，但不能猜作者私密组、扩大可见范围、伪造 `AUTHOR_ATTESTATION` 或自动把候选转正。缺少私密标记时按旧可见范围保守处理。

题材包候选不能先换成另一种候选来源，再用普通确认绕过签字和来源留痕。保持 `pack_prefilled/candidate` 的修订也须提供前后快照 `{record: 完整宿主记录, pack_ref: 题材包来源}`，其中 `record` 含信封、合同名和版本，按六账内容合同校验并绑定各自信封后再比较业务正文；局部对象不能作为快照，正文与 `pack_ref` 均未变才可保留候选；作者编辑正文须一次完成上述签字迁移。v2 条目只要是 `confirmed`，来源就必须为 `author_declared`；六本内容合同共用此检查，世界规则的红灯资格不能接纳其他来源的已确认条目。v1 静态校验行为保留。

两个版本的 Schema 同时注册时，v1 保留原 `$id`（`https://local.novel-mvp/contracts/LEDGER_ENTRY_ENVELOPE.schema.json`），v2 使用独立 `$id`（`https://local.novel-mvp/contracts/LEDGER_ENTRY_ENVELOPE.v2.schema.json`）。v2 文件仍为下方 `LEDGER_ENTRY_ENVELOPE.schema.json`，标识用于版本解析，不改变文件路径。

退役转换的 `business_before`／`business_after` 必须传入六本宿主内容合同之一的完整前后记录，不能传空对象或裁剪过的正文字段。校验器按记录的合同与版本检查完整内容，并将其中的信封逐字段绑定到本次转换的 before／after，再自行剥离信封比较正文；合同身份和内容版本也不得在退役时变化。缺字段、未知宿主或信封不一致均拒绝。记录是否来自当前持久版本，仍由第二刀宿主读取与修订检查保证，调用方不能用手造副本代替实际旧记录。

普通候选不能通过修订把来源改成 `pack_prefilled`，也不能借此添加题材包出处；该来源应在真实题材包首次接纳时建立。已有题材包候选的原样修订与合法作者签字转换仍按既有规则处理。

通用确认转换与题材包签字转换必须显式传入 `contract_version`，前后快照按同一声明版本校验；不能因为缺少 `tags/tag_groups` 就降为 v1。内容合同调用方从已校验的宿主版本传递信封版本。旧 fixture 未声明版本时固定按历史 v1 解释，v2 fixture 必须声明 v2，夹具入口原样转交该声明。

## 8. 开放问题

以下四项只留位，不在 L1 定义：

- 知情边字段枚举（T3）；
- ADD-043 规则／能力／例外是否拆条；
- READER 侧数据结构；
- 新账申请流程。

## 9. 机器件

- Schema：[LEDGER_ENTRY_ENVELOPE.schema.json](LEDGER_ENTRY_ENVELOPE.schema.json)
- v1 兼容 Schema：[LEDGER_ENTRY_ENVELOPE.v1.schema.json](LEDGER_ENTRY_ENVELOPE.v1.schema.json)
- Validator：[validate_ledger_entry_envelope.py](validate_ledger_entry_envelope.py)
- Fixtures：[LEDGER_ENTRY_ENVELOPE.fixtures.jsonl](LEDGER_ENTRY_ENVELOPE.fixtures.jsonl)
- v2 Fixtures：[LEDGER_ENTRY_ENVELOPE.v2.fixtures.jsonl](LEDGER_ENTRY_ENVELOPE.v2.fixtures.jsonl)
- 定向测试：`tests/test_novel_mvp_ledger_entry_envelope_contract.py`

## 8. 实现状态

`UNIFIED_WRITER_SETTINGSTORE_V1`

本合同通过只证明字段与迁移规则已经冻结，并且六本设定账已有唯一落盘方 `settingstore`。不证明作者界面或端到端主循环已经能用。
