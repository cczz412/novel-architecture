# PACK_02 现行合同｜novel-mvp/contracts 34 份原文

本分册收录 commit 当时 `novel-mvp/contracts/` 下全部 34 个 `.md`，原文不删节。

排列只为方便人读：信封／存储 → 内容合同 → C 层对象 → 动作与回执。排列不是权力顺序，合同正文自己说了算。


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/LEDGER_ENTRY_ENVELOPE.md git_blob=05adab4b392eb9aac54ceb6dd5cde7185c37f685 bytes=8043 -->

# 源文件：`novel-mvp/contracts/LEDGER_ENTRY_ENVELOPE.md`

- Git blob：`05adab4b392eb9aac54ceb6dd5cde7185c37f685`
- 字节：8043
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# LEDGER_ENTRY_ENVELOPE · 十本账共同条目信封

**正式版本：`ledger-entry-envelope-v1`**

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
- 新号必须由 `settingstore` 在同一次原子提交内读取、递增并落盘；
- **不得由各模块私自发号**；
- 失败事务不得消耗或重复使用已经对外承诺的 ID；
- 已分配 ID 永不回收、永不改写、永不跨账复用。

L1 只冻结合同和校验规则；统一 writer 现由 `settingstore` 实现。

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
9. 禁止把信封合同当成落盘方；文件布局与原子提交只认 `SETTING_LEDGER_STORAGE`／`settingstore`。

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

`UNIFIED_WRITER_SETTINGSTORE_V1`

本合同通过只证明字段与迁移规则已经冻结，并且六本设定账已有唯一落盘方 `settingstore`。不证明作者界面或端到端主循环已经能用。


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/LEDGER_RECALL_CODE.md git_blob=b3535dc634cd2e8b8ed0e64470b574590ed67756 bytes=3773 -->

# 源文件：`novel-mvp/contracts/LEDGER_RECALL_CODE.md`

- Git blob：`b3535dc634cd2e8b8ed0e64470b574590ed67756`
- 字节：3773
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# LEDGER_RECALL_CODE · 取件码扩十本合同

**正式版本：`ledger-recall-code-v1`**

一句话用途：拿一枚钉死版本的取件码，从十本账中的任何一本取回「那条条目的那个版本」；过期或无权被拒并说明原因；条目改判／退役后旧码仍取旧版，回执标明身份（题 7 已拍，AE-M11-N01）。

## 1. 码的形状（C11 revision ref 同族）

```json
{
  "contract": "LEDGER_RECALL_CODE",
  "version": "ledger-recall-code-v1",
  "ledger_name": "事实账",
  "entry_id": "f0007",
  "rev": 1,
  "sha": "aaaaaaaa…（64 位十六进制）",
  "expires_at": null
}
```

| 字段 | 类型 | 规则 |
|---|---|---|
| `ledger_name` | enum | 只允许户籍十本中文名：章节账／事实账／人物账／地点账／物品账／势力账／体系账／世界规则账／长线账／规划账 |
| `entry_id` | str | 该账内的稳定条目 ID（`f0007`、`PE-0412`、`CH-0001`、`DESTINY-0001`……） |
| `rev` | int | 钉死的条目修订号，≥1 |
| `sha` | str | 该版本内容 SHA-256，64 位十六进制 |
| `expires_at` | str/null | 可选过期时刻；非空时解析必须提供当前时刻，否则拒绝判定 |

长线账没有自己的落盘文件：`ledger_name=长线账` 的码解析到规划账里的长线对象（卷／命运／灵感／故事线／伏笔）。不存在第十一本物理账。

## 2. 解析语义

| 情形 | 回执 |
|---|---|
| 有效码 | `{"status":"OK", …, "rev":钉死的那版}` |
| 码过期 | `{"status":"REJECTED","reason":"CODE_EXPIRED"}` |
| 无权 | `{"status":"REJECTED","reason":"UNAUTHORIZED"}` |
| 条目不存在 | `{"status":"REJECTED","reason":"ENTRY_NOT_FOUND"}` |
| 版本不存在 | `{"status":"REJECTED","reason":"REVISION_NOT_FOUND"}` |
| SHA 对不上 | `{"status":"REJECTED","reason":"SHA_MISMATCH"}` |

**题 7 条款**：条目 `confirmed→retired`（改判／退役）后，旧码仍取回旧版本；回执必须带
`"retired_notice": true` 与 `"notice": "此条已改判／退役"`。历史可回是全仓一贯纪律，标明身份就不误导。

## 3. 两种形状并存的边界（复核注记 4，本票不迁移）

**本票选择：不迁移现役行为，两种形状并存。**

| | 形状 A（现役） | 形状 B（本合同） |
|---|---|---|
| 载体 | `rh_` 不透明 handle（`recall_handle_workspace.py`） | `{ledger_name, entry_id, rev, sha}` 明码 |
| 覆盖 | 事实／规划／章节三账 | 户籍十本 |
| 源版本前进 | **STALE 拒收**（`RecallHandleStaleError`） | 不受影响——码钉死那一版，照常取回 |
| 条目退役 | 不适用 | 旧码仍取旧版＋回执标注 |
| 测试 | `tests/test_novel_mvp_recall_handle_workspace.py`，本票一字不改 | `tests/test_novel_mvp_ledger_recall_code_contract.py` |

- 形状 A 的「源一前进就 STALE」语义继续锁死，不迁移到 rev-pinned；
- 题 7 的「旧码仍取旧版」只适用于形状 B；
- 未来若要迁移形状 A，必须另开票、同票改其测试并显式声明，禁止静默改现役行为。

## 4. 明确禁止

1. 禁止发明十本之外的 `ledger_name` 或用英文名。
2. 禁止有效码返回「当前版」代替钉死的那版。
3. 禁止无理由拒绝：REJECTED 必须带 reason。
4. 禁止退役条目的旧码被拒收，或回执不带改判／退役标注。
5. 禁止本票改动 `recall_handle_workspace.py`、packer 一族或其测试。
6. 禁止本票实现十本账取件 runtime 接线（M11 接线另开票）。

## 5. 机器件与状态

- `LEDGER_RECALL_CODE.schema.json`
- `validate_ledger_recall_code.py`
- `LEDGER_RECALL_CODE.fixtures.jsonl`
- `tests/test_novel_mvp_ledger_recall_code_contract.py`

实现状态：`CONTRACT_ONLY__M11_TEN_LEDGER_WIRING_PENDING`。


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/SETTING_LEDGER_STORAGE.md git_blob=d46a1bdbaba7995618dbf12421ef16cb022eb1bd bytes=5930 -->

# 源文件：`novel-mvp/contracts/SETTING_LEDGER_STORAGE.md`

- Git blob：`d46a1bdbaba7995618dbf12421ef16cb022eb1bd`
- 字节：5930
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# SETTING_LEDGER_STORAGE · 设定账统一落盘

**版本：`setting-ledger-storage-v1`**

一句话用途：六本设定账只从一个落盘方写入。它照规划账 `planstore` 的锁、跨文件原子提交、统一发号和失败回滚来干活；不改 L1～L5 字段表，也不回答人物现在穿什么。

| 方向 | 模块 |
|---|---|
| 唯一落盘 | [mvp/settingstore.py](../mvp/settingstore.py)；事务协调器仍是 [mvp/planstore.py](../mvp/planstore.py) |
| 读 | 内容合同校验器、后续 M7／M9／M10／M11；本票只保证能读已提交记录 |
| 禁止写入 | 查询页、导出、检查报告、题材包、模型、各模块私写 JSON |

机制细节（prepare／commit／rolled_back、恢复扫描）仍看 [PLAN_LEDGER_STORAGE.md](PLAN_LEDGER_STORAGE.md) §20。字段读法以各本内容合同为准。

来源：拍板题 3（六本设定账共用一个落盘方）；样板是 planstore 通用事务和 factstore 第二本账接法。

## 1. Owner 与边界

| 项 | 正式规则 |
|---|---|
| 合同 owner | `SETTING_LEDGER_STORAGE` |
| 管哪些账 | 人物、地点、物品、势力、体系、世界规则 |
| 不管哪些账 | 章节账、事实账、规划账、长线账。长线真值住规划账，读取面不是本 writer |
| 谁能提出 | 作者直接编辑、M4／M5 已确认事实后的投影、题材包预填、模型候选 |
| 谁落盘 | 只有 settingstore。提出方不能自己改文件或私自发号 |
| 本票不做 | 不实现作者界面、M7 红灯 runtime、M10 as-of 查询页、题材包一键铺账、取件码接线 |

开放事项只留位：知情边字段枚举（T3）、ADD-043 规则拆条、READER 侧数据结构、新账申请流程。

## 2. 落盘文件

```text
data/<项目>/
├─ characters.json
├─ locations.json
├─ items.json
├─ factions.json
├─ systems.json
├─ world_rules.json
├─ plan.json              # 只为复用 id_counters；设定账不另放第二套发号器
├─ plan_history.jsonl     # 跨账共用流水，与规划／事实同一条
├─ commit_log.jsonl
└─ blobs/
```

- 六本主文件各自是**记录数组**，和 `facts.json` 同族，不是再包一层 `id_counters`。
- 缺文件或空文件按空数组读。第一次成功提交才写出合法 JSON 数组。
- `.planstore.lock`、`.planstore_txn/` 仍是 planstore 护栏，不是业务账。

| 账 | 机器名 | 主文件 | 发号键 | ID 前缀 |
|---|---|---|---|---|
| 人物账 | `character` | `characters.json` | `CH` | `CH-` |
| 地点账 | `location` | `locations.json` | `LOC` | `LOC-` |
| 物品账 | `item` | `items.json` | `IT` | `IT-` |
| 势力账 | `faction` | `factions.json` | `FA` | `FA-` |
| 体系账 | `system` | `systems.json` | `SY` | `SY-` |
| 世界规则账 | `world_rule` | `world_rules.json` | `RU` | `RU-` |

## 3. 发／收模块

| 角色 | 模块 | 权限 |
|---|---|---|
| 发起修改 | 作者、确认事实投影、题材包、模型 | 只交候选或作者已签的定义卡 |
| 唯一落盘者 | settingstore | 校验内容合同、发号、写主文件、改 `id_counters`、追加流水、走同一 `commit_log` |
| 事务协调器 | planstore | 持锁、prepare／commit／回滚／恢复；settingstore 不得另起第二套 journal |
| 读取者 | 校验器与后续模块 | 只读已 commit 版本 |
| 禁止写入者 | 查询、导出、检查、题材包、模型直写 | 不得旁路改 JSON，也不得私增 `id_counters` |

## 4. 原子提交

复合动作名固定 `setting_ledger_write`。一次提交只写一本设定账的一条记录，但必须把这些文件放进同一事务：

1. 该本主文件（替换）；
2. `plan.json`（替换，写入该本 `id_counters`）；
3. `plan_history.jsonl`（追加一行）；
4. `blobs/`（内容寻址，存改前快照）。

`files[]` 只许三种形状，与规划账 §20 相同：替换、追加、内容寻址 blob。

失败怎么收：

- 写前护栏失败：不得出现 prepare 行，不得消耗 ID。
- 全部 target 已写成：恢复时补 commit。
- 只写一部分：按底稿还原主文件和 `plan.json`、截断流水、删未引用 blob，再写 `rolled_back`。
- 文件既不是 before 也不是 target：`NEEDS_MANUAL_RECOVERY`，不准猜。

同一 `operation_id`：同载荷已 commit 则幂等回放、不重复发号；不同载荷写前拒绝；`rolled_back` 后必须换新号。

## 5. 发号与 `rev`

- 新号只由 settingstore 在持锁后、同一次原子提交内从 `plan.json.id_counters` 读取、递增并落盘。
- 调用方创建时不得自带 ID；自带且账上没有这条，一律拒绝。
- 已分配 ID 永不回收、永不改号、永不跨账复用。退役只改 `confirm_status`，号仍占着。
- 失败事务回滚后计数器回到提交前；不得留下“号已对外承诺、文件却没有”的空洞。
- 载入时核对：该本最大已用号必须等于计数器；对不上就拒绝写入。
- `rev`：新建为 1，每次成功更新 +1。流水里的 `rev` 与主文件一致。
- 系统字段 `created_at`／`updated_at`／`rev`／`id` 由 writer 填写；`AUTHOR_ATTESTATION` 仍只能由作者签字语义带来，程序不得伪造。

## 6. 明确禁止

1. 禁止给每本设定账各写一个 writer，或绕过 settingstore 直写六本主文件。
2. 禁止模块私自发号、手改 `id_counters`、把发号器再复制进 `characters.json`。
3. 禁止本 writer 写长线、规划、事实、章节。
4. 禁止物理删除 `retired` 条目来“腾号”。
5. 禁止在本票定义知情边、READER 结构、ADD-043 拆条、新账申请流程。
6. 禁止把本票写成 M1～M11 已具备完整作者能力。

## 7. 实现状态

`UNIFIED_WRITER_SETTINGSTORE_V1`

通过本合同只证明六本设定账有了唯一落盘方和原子提交。不证明作者界面、查询 runtime 或端到端主循环已经能用。


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/PLAN_LEDGER_STORAGE.md git_blob=afdc31e62c8c0a60996397be649e712945194731 bytes=71935 -->

# 源文件：`novel-mvp/contracts/PLAN_LEDGER_STORAGE.md`

- Git blob：`afdc31e62c8c0a60996397be649e712945194731`
- 字节：71935
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# PLAN_LEDGER_STORAGE · 规划账存储

**版本：`plan-v2-candidate-r08`**（r07 语义不变；L5 冻结卷／人物命运／灵感三个长线对象的内容合同与 `expected_at` 三种锚；落盘中的 schema 仍为 `plan-v2`；planstore 对三对象的写动作仍未施工）

一句话用途：保存作者未来准备怎样写，以及计划与书稿怎样对照。它不是事实账，不证明故事已经发生。

| 方向 | 模块 |
|---|---|
| 唯一落盘 | planstore 事务协调器；handover 见 [mvp/planstore.py](../mvp/planstore.py)，对账见 [mvp/reconcile.py](../mvp/reconcile.py)，facts 变更统一入口见 [mvp/factstore.py](../mvp/factstore.py)；六本设定账经同一协调器、由 [mvp/settingstore.py](../mvp/settingstore.py) 写入，见 [SETTING_LEDGER_STORAGE.md](SETTING_LEDGER_STORAGE.md)；其他规划动作仍待施工 |
| 读 | M8、M9、M11、对账、关章检查 |
| 跨账只读 | C1 章节书稿 ID、C4 事实内部 ID |
| 禁止写入 | C6、C7、C8、C9、概览卡、导出文件 |

机制细节（提交护栏、恢复扫描、影响传播）仍看设计稿 [PLAN_LEDGER_STORAGE_DESIGN_R04.md](../design/PLAN_LEDGER_STORAGE_DESIGN_R04.md)。字段读法以本稿为准。

来源：SI-016 回包 B1／B2，对照 R13 与存储稿 R03／R04。收费数字仍冻。暗稿 K3 不动；开口只剩算不算签字、能不能开下一章。关章六道门不在本账。

## 合同正文

### 合同名与版本

**合同名**：`PLAN_LEDGER_STORAGE`
**版本**：`plan-v2-candidate-r08`
**落盘中的 schema 值**：`"plan-v2"`
**状态**：r06 handover／对账／M5 统一 writer 产品接缝已实现；r07 chapter revision 接缝正式冻结、产品实现待下一票；r08 卷／人物命运／灵感三对象合同层冻结（L5），planstore 写动作与长线视图投影待后续 runtime 票；通用 planstore 其他动作未完成

### 一句话用途

保存作者未来准备怎样写，以及计划与实际书稿怎样对照；它不是事实账，不证明故事已经发生。

### 发／收模块

| 角色       | 模块                              | 权限                                       |
| ---------- | --------------------------------- | ------------------------------------------ |
| 发起修改   | 作者通过 M8／大纲画布／设置页     | 提出或确认规划修改                         |
| 候选生产   | M8、模型、反向剧情图管线          | 只能产生候选；模型不能直接替作者签真值     |
| 唯一落盘者 | planstore                         | 校验、发号、写 `plan.json`、流水和提交日志 |
| 读取者     | M8、M9、M11、关章检查器、对账流程 | 只读当前已提交版本                         |
| 跨账只读   | C1、C4                            | 规划账只保存其内部永久 ID，不写对方文件    |
| 禁止写入者 | C6、C7、C8、C9、概览卡、导出文件  | 均为投影或执行材料，不得直写规划账         |

### 落盘文件

```text
data/<项目>/
├─ plan.json
├─ plan_history.jsonl
├─ commit_log.jsonl
└─ blobs/
```

- `plan.json`：当前规划态。
- `plan_history.jsonl`：对象级纯追加流水。
- `commit_log.jsonl`：跨文件动作的 prepare／commit／rolled_back 回执及 `story_commit_seq`。
- `blobs/`：对象旧版完整快照。

当前 handover writer 还会使用两个实现内护栏：`.planstore.lock` 是跨进程互斥锁，`.planstore_txn/` 是 prepare 到 terminal 之间的瞬时恢复底稿。两者都不是业务账、投影或第二真源；动作 commit／rolled_back 后恢复底稿必须删除。正式业务状态仍只认上面四类文件与 C1 `chapters.json`。

### 来源标注

| 标记          | 含义                                         |
| ------------- | -------------------------------------------- |
| `STORAGE R03` | 字段形状来自存储设计稿；现行人读稿是 R04，字段权威以本合同为准 |
| `R13 已拍`    | R13 已确认语义                               |
| `C1／C4／C7`  | 已落合同的当前代码现实                       |
| `M8 R04`      | `M8_PLANNING_DESIGN_R04.md`                  |
| `WRITING R04` | `WRITING_DESK_DESIGN_R04.md`                 |
| `本轮候选`    | 为消除歧义做的收窄；不得冒充已拍             |
| `接缝微改`    | C7 选择动作固定 9 题通过后转正的最小差异     |
| `章纲版本微改` | 章纲 checkpoint 固定 9 题通过后转正的最小差异 |
| `工作稿交棒微改` | 工作稿生命周期固定 14 题通过后转正的最小接收顺序 |
| `槽位映射微改` | slot mapping 固定 14 题通过后转正的最小身份、类型与引用规则 |
| `对账准入微改` | 六态候选固定反例与正式 writer 回归通过后的最小身份、stale 与 facts 准入字段 |
| `M5 事务微改` | 旧确认／驳回／改判入口统一后，facts 与 RE stale 共用提交协调器的最小对齐 |

### 十五条总规则

1. `ledger` 恒为 `"plan"`；PE、场、槽、伏笔安排都不是 F 事实。
2. 只有 planstore 能写 `plan.json`；模型只能提候选。
3. 新书稿入库默认不改 `handover_parts`、`slot_status` 或 `truth_bearing`。
4. 只有作者明确选择「以这篇为准」，才执行交棒。
5. 对账不以交棒为前置；对账和交棒互不代替。
6. 收工不得修改 `slot_status`；收工不是关章。
7. `truth_bearing` 只挂章槽、场、计划事件、伏笔、必写承接五类对象。
8. 跨账事实引用只存 `f001` 这类内部 ID；`F-0001` 只用于界面显示。
9. C7 与选择动作都不能直接写账；选择动作必须先经过 planstore 的引用、修订、来源和停点校验。
10. 章纲整体版本只挂现有章槽；旧版沿用规划流水与 blob，禁止新建章纲库、章纲 ID 或第二套提交链。
11. 工作稿保存、检测与收工都不能写规划账；只有 C1 已合法产生章节身份后，作者显式交棒才可进入 `handover_parts`。
12. `slot_mappings=[]` 只表示映射尚未完成；完整交棒必须产生带稳定 `MAP-` 身份的 `active` 映射，实际章节不承接叙事规划时使用 `non_narrative`。
13. 六态模型输出先是短命观察候选；RE 只有接到 current confirmed C4 引用并通过作者 facts 准入后，才可能支持 actual 派生。
14. M5 改变被 RE 引用的事实状态或文本时，facts 与 RE stale 必须同事务提交；事实重新 confirmed 不得静默复活旧 RE。
15. stable slot mapping 只绑定 `chapter_id`；RE 额外绑定 `chapter_revision_ref`。章节修订不改 mapping，但必须让引用旧 revision 或受影响 fact 的 active RE stale。

------

## 1. 顶层骨架

| 英文名                 | 类型      | 必填 | 人话                 | 枚举／约束                             | 来源                     |
| ---------------------- | --------- | ---- | -------------------- | -------------------------------------- | ------------------------ |
| `schema`               | str       | 是   | 规划账格式版本       | 固定 `"plan-v2"`                       | STORAGE R03              |
| `ledger`               | str       | 是   | 这本账的身份         | 固定 `"plan"`                          | STORAGE R03＋R13 已拍    |
| `book`                 | obj       | 是   | 书核                 | 见书核表                               | STORAGE R03              |
| `slot_sequence`        | list[str] | 是   | 规划槽位顺序         | 只放 `S-` ID，数组顺序即顺序           | STORAGE R03              |
| `volumes`              | list[obj] | 是   | 卷                   | 本候选只允许空数组，见开放项           | STORAGE R03＋本轮候选    |
| `slots`                | list[obj] | 是   | 章槽／章纲           | 见章槽表                               | STORAGE R03              |
| `scenes`               | list[obj] | 是   | 场安排               | 见场表                                 | STORAGE R03              |
| `events`               | list[obj] | 是   | 计划事件             | 见 PE 表                               | STORAGE R03＋WRITING R03 |
| `storylines`           | list[obj] | 是   | 故事线               | 见故事线表                             | STORAGE R03              |
| `hooks`                | list[obj] | 是   | 伏笔安排             | 见伏笔表                               | STORAGE R03              |
| `widgets`              | list[obj] | 是   | 写法挂件             | 见挂件表                               | STORAGE R03              |
| `pins`                 | list[obj] | 是   | 依据引脚             | 见引脚表                               | STORAGE R03              |
| `must_carries`         | list[obj] | 是   | 必写承接             | 见承接表                               | STORAGE R03              |
| `option_records`       | list[obj] | 是   | 选择留痕             | 见选择记录表                           | STORAGE R03              |
| `slot_mappings`        | list[obj] | 是   | 规划槽与实际章的映射 | 空数组只表示 pending；有值时见 §14      | STORAGE R03＋槽位映射微改 |
| `reconciliation_edges` | list[obj] | 是   | 计划与书稿的对账结果 | 见对账边表                             | STORAGE R03              |
| `stop_points`          | obj       | 是   | 停点偏好             | 当前按兼容对象保存，不授予收费或真值权 | STORAGE R03              |
| `id_counters`          | obj       | 是   | 各已有前缀最大发号值 | 不得由各模块私自发号                   | STORAGE R03              |

------

## 2. 公共字段

除书核以外，各规划对象均带以下公共字段；书核同样按对象处理。

| 英文名            | 类型 | 必填 | 人话           | 枚举／约束                                             | 来源        |
| ----------------- | ---- | ---- | -------------- | ------------------------------------------------------ | ----------- |
| `id`              | str  | 是   | 内部永久门牌号 | 已有前缀＋数字；永不回收、永不重写                     | STORAGE R03 |
| `source_identity` | enum | 是   | 这条安排从哪来 | `author_declared`／`draft_inferred`／`model_suggested` | STORAGE R03 |
| `created_at`      | str  | 是   | 系统登记时间   | 不表示故事内时间                                       | STORAGE R03 |
| `updated_at`      | str  | 是   | 最近修订时间   | 不表示叙述释放位置                                     | STORAGE R03 |
| `rev`             | int  | 是   | 对象修订号     | 建档为 1，每次提交 +1                                  | STORAGE R03 |
| `note`            | str  | 是   | 备注           | 无内容写空串，不省略字段                               | STORAGE R03 |

### 谁写谁读

| 对象                                             | 谁能提出               | 谁落盘                            | 主要读取者                   |
| ------------------------------------------------ | ---------------------- | --------------------------------- | ---------------------------- |
| 书核／卷／章槽／场／计划事件／故事线／伏笔／承接 | 作者、M8 候选          | planstore；改变方向必须有作者动作 | M8、M9、M11、关章检查        |
| 写法挂件                                         | 作者、插件候选         | planstore                         | M8、M11、写作区              |
| 依据引脚                                         | 作者或程序建立只读引用 | planstore                         | M8、M7、影响扫描             |
| 选择记录                                         | M8 生成选项；作者选择或策略层合规自动放行 | planstore             | M8、审计、撤销               |
| 槽位映射                                         | 系统建议，作者决定     | planstore                         | 开章、时间轴、战报           |
| 对账边                                           | 模型写观察，作者写处置 | planstore                         | M8、伏笔／状态派生、关章检查 |
| 停点设置                                         | 作者设置               | planstore／设置模块               | 各模块只读                   |

------

## 3. 书核 `book_core`

| 英文名            | 类型      | 必填 | 人话               | 枚举／约束                                 | 来源        |
| ----------------- | --------- | ---- | ------------------ | ------------------------------------------ | ----------- |
| `premise`         | str       | 是   | 一句话故事前提     | 不得写成书稿成文                           | STORAGE R03 |
| `genre_promise`   | str\|null | 是   | 题材与主要阅读承诺 | 暂无写 null                                | STORAGE R03 |
| `main_beats`      | list[obj] | 是   | 全书大节拍         | 子项固定 `{key:str, text:str}`；key 不重编 | STORAGE R03 |
| `ending_anchor`   | str\|null | 是   | 结局锚             | 未定写 null                                | STORAGE R03 |
| `volumes_enabled` | bool      | 是   | 是否启用卷层       | 默认 false                                 | STORAGE R03 |

书核不带 `truth_bearing`。

------

## 4. 卷 `volume`

字段表已由 L5 正式冻结，形状权威见 [PLAN_VOLUME_CONTENT.md](PLAN_VOLUME_CONTENT.md)（`volume-plan-content-v1`，前缀 `VOL-`，复用 `id_counters.VOL` 统一发号）。STORAGE R03 点名的七个业务字段全部收口：

| 英文名 | 类型 | 必填 | 人话 | 来源 |
|---|---|---|---|---|
| `order` | int | 是 | 卷序，≥1 | STORAGE R03＋L5 |
| `title` | str | 是 | 卷名，非空 | STORAGE R03＋L5 |
| `goal` | str | 是 | 本卷目标；无内容写空串 | STORAGE R03＋L5 |
| `main_conflict` | str\|null | 是 | 主冲突，未定写 null | STORAGE R03＋L5 |
| `entry_state` | str\|null | 是 | 入卷状态，未定写 null | STORAGE R03＋L5 |
| `exit_state` | str\|null | 是 | 出卷状态，未定写 null | STORAGE R03＋L5 |
| `summary` | str | 是 | 卷摘要；无内容写空串，不省略 | STORAGE R03＋L5 |

运行时边界（L5 不改 runtime）：

- planstore 与长线视图 runtime 仍只接受 `volumes=[]`（现役硬停 `VOLUMES_NOT_SUPPORTED` 不动）；
- `book.volumes_enabled=false` 时 `volumes=[]`，章槽 `volume_ref` 必须为 null；
- `volumes_enabled=true` 的写路径挂后续 runtime 票；届时章槽 `volume_ref` 只能指已有 `VOL-` 或 null；
- 卷纲只留节奏与骨架级约束，过细内容应下沉章计划或人物卡（M8-N02 语义，提示器不在合同层）。

## 4b. 人物命运 `destiny` 与灵感 `inspiration`（L5 新对象）

长线真值全住规划账（题 1 已拍）；长线账是按长线视角取数的读取面，不是第二真源。L5 新增两个规划账对象，形状权威见各自合同：

- 人物命运：[PLAN_DESTINY_CONTENT.md](PLAN_DESTINY_CONTENT.md)（`destiny-plan-content-v1`，前缀 `DESTINY-`，人物账 `destiny_ref` 的目标对象，存在性校验随 L5 收口）；
- 灵感：[PLAN_INSPIRATION_CONTENT.md](PLAN_INSPIRATION_CONTENT.md)（`inspiration-plan-content-v1`，前缀 `INS-`，`placements[]` 多实例，录入零门槛）。

两对象共用预计时机 `expected_at` 三种锚（章槽锚／故事时间锚／模糊锚）；模糊锚对账只提醒、不报警。条目永远住账不动窝，写章取料带走的是引用；兑现／未兑现／改挂由对账边推进。取件码扩十本见 [LEDGER_RECALL_CODE.md](LEDGER_RECALL_CODE.md)。planstore 对两对象的写动作、长线视图投影仍未施工。

------

## 5. 章槽位 `chapter_slot`

| 英文名           | 类型      | 必填 | 人话                       | 枚举／约束                                     | 来源                  |
| ---------------- | --------- | ---- | -------------------------- | ---------------------------------------------- | --------------------- |
| `volume_ref`     | str\|null | 是   | 所属卷                     | 卷未启用写 null                                | STORAGE R03           |
| `title_hint`     | str\|null | 是   | 章名建议                   | 不是实际章节标题                               | STORAGE R03           |
| `goal`           | str       | 是   | 本章要完成什么             | 计划身份                                       | STORAGE R03＋R13 已拍 |
| `summary`        | str       | 是   | 本章计划梗概               | 不冒充已写成内容                               | STORAGE R03＋R13 已拍 |
| `entry_state`    | str\|null | 是   | 开章前的计划入口说明       | 硬依据另挂引脚                                 | STORAGE R03           |
| `storyline_refs` | list[str] | 是   | 本章涉及哪些故事线         | 存 L- ID                                       | STORAGE R03           |
| `scene_refs`     | list[str] | 是   | 本章场序                   | 只存 SCN- ID；数组顺序即场序                   | STORAGE R03           |
| `exit_condition` | str\|null | 是   | 章尾计划达到的条件         | 不表示已达到                                   | STORAGE R03           |
| `exit_hook`      | str\|null | 是   | 计划章末钩子               | 不表示已写出                                   | STORAGE R03           |
| `must_not`       | list[str] | 是   | 不得违反的硬边界           | 来自设定／事实的引用应另挂 PIN                 | STORAGE R03           |
| `risks`          | list[str] | 是   | 已知风险                   | 不是 C6 体检结果                               | STORAGE R03           |
| `target_length`  | int\|null | 是   | 目标字数                   | 估计，不是关章通过证明                         | STORAGE R03           |
| `outline_checkpoint` | obj\|null | 是 | 当前落位章纲的整体版本与编译基线 | 未有消费就绪章纲写 null；有值时见下表 | 章纲版本微改 |
| `slot_status`    | enum      | 是   | 槽位交棒进度               | `planned`／`partial`／`handed_over`／`dropped` | STORAGE R03＋R13 已拍 |
| `handover_parts` | list[obj] | 是   | 作者明确交棒的覆盖记录     | 默认空；入库不能自动追加                       | STORAGE R03＋R13 已拍 |
| `truth_bearing`  | enum      | 是   | 当前计划在工作中的真值方向 | `primary`／`shadow`／`handed_over`             | STORAGE R03           |

### `outline_checkpoint`

| 英文名 | 类型 | 必填 | 人话 | 约束 | 来源 |
|---|---|---|---|---|---|
| `outline_rev` | int | 是 | 同一章当前落位章纲的整体修订号 | 首版为 1；同章新章纲成功落位严格 +1；与内部对象 `rev` 分开 | 章纲版本微改 |
| `source_slot_ref` | str | 是 | 这份章纲属于哪个稳定规划槽位 | 必须是承载它的 `chapter_slot.id`；不得跨章 | 章纲版本微改 |
| `source_commit_seq` | int | 是 | 编译本版章纲时，该章最近的 planning 输入提交水位 | 引用已 commit 的现有 `story_commit_seq`；不得自造 future 水位 | 章纲版本微改 |

checkpoint 只由 planstore 在合法 `outline_land` 中生成：M8／模型可以提交章纲候选、`source_slot_ref` 与 `source_commit_seq`，但不能自己发 `outline_rev`、宣布 current 或改写 checkpoint。

章纲可读身份是 `chapter_slot.id` 与 `outline_rev` 的派生组合，例如 `S-0001@outline-r2`。它不是持久化 `outline_id`，不进入 `id_counters`。`outline_checkpoint` 也不带 `source_identity`、作者签字、`current` 或 `stale` 可写位。

#### 章内 planning baseline

planstore 用现有 `commit_log.jsonl`、`plan_history.jsonl`、对象 blob 和对象归属关系，按 `source_slot_ref` 机械计算：

```text
current_source_commit_seq(source_slot_ref)
```

它表示最近一次真正改变该章**章纲编译输入**的已提交规划动作水位。章槽、该章场、该章 PE、该章选择记录或其他正式规划输入发生有效改变时，该章水位前进；另一章变化不推进本章水位。单纯把编译结果落回 `plan.json` 的 `outline_land` 动作不属于新的 planning 输入，不推进该值，避免章纲落位后立即把自己判 stale。这个按章水位由现有提交链派生，不新增 `chapter_commit_seq`、缓存账本或第二套提交链。

合法章纲落位前，planstore 必须逐项校验：

1. 上游候选满足既有 `consumer_ready=true` 与等价消费条件；
2. 候选章号、目标章槽和 `source_slot_ref` 完全相同；
3. `source_commit_seq` 指向真实已 commit 水位，且等于当前章的 `current_source_commit_seq`；
4. 新 `outline_rev` 是当前版 +1，首版为 1；
5. 同一 `operation_id` 已 commit 时直接返回原结果，不再升版或重复创建章槽、场、PE；
6. 未消费就绪、跨章、future、不存在或已过期 baseline 全部在写 `plan.json`、流水和提交日志前拒绝。

当前章纲必须同时满足：checkpoint 位于当前 `plan.json` 的目标章槽；`source_slot_ref` 等于章槽 ID；`source_commit_seq` 等于该章当前 planning 输入水位；它满足消费条件且未被更新 `outline_rev` 取代。任一条件不满足即失去 current 消费资格，其中 planning 输入水位前进时旧版派生为 stale。

stale 只改变消费资格。不得删除旧版本、静默改旧 checkpoint、把旧 baseline 自动抬到新水位或让旧版重新夺回 current。旧章纲继续按同一 `operation_id` 从 `plan_history.jsonl` 与 `blobs/` 追溯，不增加 `outline_history[]` 或完整章纲副本。`slot_status=partial` 仍只表示书稿部分交棒，不能代替章纲 blocked／partial 状态；未消费就绪的章纲投影不得获得 checkpoint 或写作区 current 身份。

### `handover_parts[]`

| 英文名               | 类型      | 必填 | 人话                   | 约束                | 来源                  |
| -------------------- | --------- | ---- | ---------------------- | ------------------- | --------------------- |
| `part_no`            | int       | 是   | 本槽第几次交棒         | 从 1 递增           | STORAGE R03           |
| `chapter_id`         | str       | 是   | 交棒所依据的 C1 章节   | 必须是章节书稿 ID   | STORAGE R03＋C1       |
| `covered_scene_refs` | list[str] | 是   | 这次覆盖了哪些场       | 只存 SCN- ID        | STORAGE R03           |
| `covered_pe_refs`    | list[str] | 是   | 这次覆盖了哪些计划事件 | 只存 PE- ID         | STORAGE R03           |
| `handed_at`          | str       | 是   | 作者交棒时间           | 系统时间            | STORAGE R03           |
| `decided_by`         | enum      | 是   | 谁决定交棒             | 当前只允许 `author` | STORAGE R03＋R13 已拍 |

### 交棒动作

书稿入库时：

```text
handover_parts 不变
slot_status 不变
truth_bearing 不变
```

作者明确选择「以这篇为准」后，才允许在同一个 `operation_id` 内：

1. 确定覆盖的场与 PE；
2. 追加一条 `handover_parts`；
3. 将被覆盖的场／PE 改为 `truth_bearing=handed_over`；
4. 全覆盖时 `slot_status=handed_over`，部分覆盖时为 `partial`；
5. 写槽位映射；
6. 写 `handover` 流水。

交棒不自动改写原计划文字，也不自动生成对账边。

来自写作区工作稿的交棒必须先经过 [WORK_DRAFT_HANDOVER_ACTION.md](WORK_DRAFT_HANDOVER_ACTION.md) 与 [C1_CHAPTER_DOC.md](C1_CHAPTER_DOC.md) 的接收边界：

```text
current work revision
  → 作者显式交棒命令
  → AWAITING_C1_ACCEPTANCE
  → C1 校验并产生合法 chapter_id
  → planstore 才可执行上面的 handover_parts 写入
```

planstore 不直接消费工作稿全文，也不能根据交棒命令伪造 C1。工作稿保存、检测结果、[WRITING_DESK_CLOSEOUT_ACTION.md](WRITING_DESK_CLOSEOUT_ACTION.md) 或文件存在，都不能替代作者交棒命令和 C1 成功回执。任一前置条件缺失时，`handover_parts`、`slot_status` 与 `truth_bearing` 必须保持不变。

------

## 6. 场 `scene`

| 英文名           | 类型      | 必填 | 人话               | 枚举／约束                         | 来源                  |
| ---------------- | --------- | ---- | ------------------ | ---------------------------------- | --------------------- |
| `slot_ref`       | str       | 是   | 属于哪个章槽       | S- ID                              | STORAGE R03           |
| `goal`           | str       | 是   | 这场要解决什么     | 计划身份                           | STORAGE R03           |
| `summary`        | str       | 是   | 这场的计划胶囊     | 不冒充已发生                       | STORAGE R03           |
| `location`       | str\|null | 是   | 计划地点           | 推荐以后指共享实体；当前仍是旧形   | STORAGE R03           |
| `characters`     | list[str] | 是   | 计划在场人物       | 只存 CH- ID                        | STORAGE R03           |
| `pe_refs`        | list[str] | 是   | 本场计划事件顺序   | 数组顺序即叙述顺序                 | STORAGE R03           |
| `mood_in`        | str\|null | 是   | 入场情绪要求       | 写法供料，不是真值                 | STORAGE R03           |
| `mood_out`       | str\|null | 是   | 出场情绪要求       | 写法供料，不是真值                 | STORAGE R03           |
| `visual_hint`    | str\|null | 是   | 画面提示           | 不得自动变成书稿                   | STORAGE R03           |
| `dialogue_hints` | list[str] | 是   | 对白需要释放的信息 | 只写目的／信息点，不写完整台词     | STORAGE R03＋R13 已拍 |
| `resistance`     | str\|null | 是   | 场内阻力           | 计划身份                           | STORAGE R03           |
| `turn`           | str\|null | 是   | 转折发生什么       | 禁止保存完成对白                   | STORAGE R03＋本轮纠错 |
| `pov`            | str\|null | 是   | 计划视角人物       | CH- ID                             | STORAGE R03           |
| `spoiler_notes`  | list[str] | 是   | 防泄底提示         | 不改变伏笔真值                     | STORAGE R03           |
| `word_estimate`  | int\|null | 是   | 预计字数           | 估计值                             | STORAGE R03           |
| `truth_bearing`  | enum      | 是   | 工作真值方向       | `primary`／`shadow`／`handed_over` | STORAGE R03           |

------

## 7. 计划事件 `planned_event`

| 英文名            | 类型       | 必填 | 人话                         | 枚举／约束                                       | 来源                  |
| ----------------- | ---------- | ---- | ---------------------------- | ------------------------------------------------ | --------------------- |
| `text`            | str        | 是   | 准备让谁做什么／发生什么变化 | 永远是计划，不得叫事实                           | STORAGE R03＋R13 已拍 |
| `scene_ref`       | str\|null  | 是   | 安排在哪一场                 | SCN- ID；未落场写 null                           | STORAGE R03           |
| `storyline_ref`   | str\|null  | 是   | 属于哪条线                   | L- ID                                            | STORAGE R03           |
| `purpose`         | enum       | 是   | 剧情用途                     | `setup`／`advance`／`reveal`／`payoff`／`repair` | STORAGE R03           |
| `hook_links`      | list[obj]  | 是   | 与伏笔的计划关系             | 子项 `{hook_ref, role}`；role=`plant`／`payoff`  | STORAGE R03           |
| `story_time_hint` | str\|null  | 是   | 故事内时间提示               | 题 16 机器判据仍开放                             | STORAGE R03＋R13 开放 |
| `digest_status`   | enum       | 是   | 是否已安排进计划             | `pending`／`digested`／`voided`                  | STORAGE R03           |
| `digest_ref`      | str\|null  | 是   | 由哪次选择消化               | OPT- ID                                          | STORAGE R03           |
| `origin_ref`      | str\|null  | 是   | 从哪拆出                     | 指稳定规划对象                                   | STORAGE R03           |
| `repair_ref`      | str\|null  | 是   | 要修的旧问题                 | 仅 purpose=repair 时使用                         | STORAGE R03           |
| `deviation_note`  | str\|null  | 是   | 作者看的偏差备注             | 不代替对账边                                     | STORAGE R03           |
| `defer_count`     | int        | 是   | 被延期次数                   | ≥0                                               | STORAGE R03           |
| `truth_bearing`   | enum       | 是   | 工作真值方向                 | `primary`／`shadow`／`handed_over`               | STORAGE R03           |
| `prose_status`    | enum       | 是   | 这项计划的成文／暗稿状态     | `unwritten`／`written`／`dark_draft`             | WRITING R04＋R13 已拍 |
| `prose_basis`     | enum\|null | 是   | 成文覆盖的判定来源           | `verified`／`self_reported`／null                | WRITING R03           |
| `impact`          | enum       | 是   | 暗稿是否高影响               | `normal`／`high`                                 | WRITING R03           |

### 三个字段不能被误读

- `digest_status=digested`：只表示已安排，不表示发生。
- `prose_status=dark_draft`：表示已发生、未描写、仍是事实；它仍住规划账，不发 F 号。
- `prose_basis`：只说明“谁判断它写没写”，不能推出暗稿已经完成关章签字，也不能推出可以开下一章。

暗稿算不算完整签字、能不能开下一章，继续保持开放。

------

## 8. 故事线 `storyline`

| 英文名           | 类型      | 必填 | 人话               | 枚举／约束                                | 来源             |
| ---------------- | --------- | ---- | ------------------ | ----------------------------------------- | ---------------- |
| `name`           | str       | 是   | 线名               | 人话名称                                  | STORAGE R03      |
| `alias`          | str\|null | 是   | 展示短名           | 不作永久 ID                               | STORAGE R03      |
| `priority`       | int       | 是   | 当前优先级         | 数字越小越高                              | STORAGE R03      |
| `members`        | list[str] | 是   | 与这条线有关的人物 | CH- ID；不要求线必须有人                  | STORAGE R03＋R13 |
| `line_status`    | enum      | 是   | 当前规划状态       | `active`／`paused`／`converged`／`merged` | STORAGE R03      |
| `last_scene_ref` | str\|null | 是   | 上次现场           | SCN- ID                                   | STORAGE R03      |

故事线不带 `truth_bearing`。

------

## 9. 伏笔 `hook`

| 英文名            | 类型      | 必填 | 人话               | 枚举／约束                                  | 来源        |
| ----------------- | --------- | ---- | ------------------ | ------------------------------------------- | ----------- |
| `content`         | str       | 是   | 作者知道的伏笔底牌 | 未揭示时不得送读者视图                      | STORAGE R03 |
| `plant_refs`      | list[obj] | 是   | 计划埋点           | 子项 `{ref, note}`                          | STORAGE R03 |
| `payoff_slot_ref` | str\|null | 是   | 计划回收槽位       | S- ID                                       | STORAGE R03 |
| `hook_status`     | enum      | 是   | 规划层回收安排     | `open`／`paid`／`voided`；paid 只表示已安排 | STORAGE R03 |
| `paid_by_ref`     | str\|null | 是   | 计划由哪条 PE 回收 | PE- ID                                      | STORAGE R03 |
| `defer_count`     | int       | 是   | 被改期次数         | ≥0                                          | STORAGE R03 |
| `revealed`        | bool      | 是   | 计划是否安排揭示   | 不表示读者实际已知                          | STORAGE R03 |
| `revealed_at`     | str\|null | 是   | 计划揭示位置       | S- 或 SCN- ID                               | STORAGE R03 |
| `safety_summary`  | str       | 是   | 可送下游的脱敏说明 | 不含底牌                                    | STORAGE R03 |
| `truth_bearing`   | enum      | 是   | 工作真值方向       | `primary`／`shadow`／`handed_over`          | STORAGE R03 |

实际兑现不写回 `hook_status`，只能从 `exact／variant` 对账边现算。

------

## 10. 写法挂件 `craft_widget`

| 英文名       | 类型 | 必填 | 人话               | 约束               | 来源        |
| ------------ | ---- | ---- | ------------------ | ------------------ | ----------- |
| `key`        | str  | 是   | 挂件类别           | 开放词表，不进真值 | STORAGE R03 |
| `anchor_ref` | str  | 是   | 挂在哪个规划对象上 | 稳定规划 ID        | STORAGE R03 |
| `payload`    | obj  | 是   | 写法提示内容       | 由宿主插件解释     | STORAGE R03 |

挂件不带 `truth_bearing`。

------

## 11. 依据引脚 `basis_pin`

| 英文名         | 类型      | 必填 | 人话                 | 枚举／约束                        | 来源                  |
| -------------- | --------- | ---- | -------------------- | --------------------------------- | --------------------- |
| `owner_ref`    | str       | 是   | 依据挂在哪个规划对象 | 稳定规划 ID                       | STORAGE R03           |
| `target_kind`  | enum      | 是   | 依据类型             | `fact`／`setting`／`author_quote` | STORAGE R03           |
| `target_ref`   | str\|null | 条件 | 所指事实或设定       | fact 时必须是 `f001` 形内部 ID    | STORAGE R03＋本轮纠错 |
| `quote`        | str\|null | 条件 | 作者原话             | 仅 author_quote 时使用            | STORAGE R03           |
| `purpose_note` | str       | 是   | 为什么引用           | 可空串                            | STORAGE R03           |
| `pin_status`   | enum      | 是   | 引用是否需重查       | `ok`／`needs_recheck`             | STORAGE R03           |

引脚只有规划→事实单向只读权限。

------

## 12. 必写承接 `must_carry`

| 英文名            | 类型      | 必填 | 人话           | 枚举／约束                         | 来源        |
| ----------------- | --------- | ---- | -------------- | ---------------------------------- | ----------- |
| `text`            | str       | 是   | 后续必须还什么 | 计划身份                           | STORAGE R03 |
| `target_slot_ref` | str\|null | 是   | 计划在哪个槽还 | S- ID                              | STORAGE R03 |
| `origin_ref`      | str\|null | 是   | 这笔承接从哪来 | H／PE／其它规划 ID                 | STORAGE R03 |
| `mc_status`       | enum      | 是   | 规划层处理状态 | `pending`／`digested`／`voided`    | STORAGE R03 |
| `digest_ref`      | str\|null | 是   | 由哪次选择安排 | OPT- ID                            | STORAGE R03 |
| `defer_count`     | int       | 是   | 延期次数       | ≥0                                 | STORAGE R03 |
| `truth_bearing`   | enum      | 是   | 工作真值方向   | `primary`／`shadow`／`handed_over` | STORAGE R03 |

`mc_status=digested` 只表示已经安排，不表示已写成。

------

## 13. 选择记录 `option_record`

| 英文名           | 类型      | 必填 | 人话                     | 枚举／约束          | 来源             |
| ---------------- | --------- | ---- | ------------------------ | ------------------- | ---------------- |
| `slot_ref`       | str       | 是   | 在哪个章槽出的题         | S- ID               | STORAGE R03      |
| `question`       | str       | 是   | 当时问了什么             | 说明腔              | STORAGE R03      |
| `options`        | list[obj] | 是   | 当时全部候选             | 未选项也保留        | STORAGE R03      |
| `chosen_key`     | str\|null | 是   | 选了哪个稳定选项号       | 选定时指向 `options[].key`；整组驳回为 null | STORAGE R03＋接缝微改 |
| `decided_by`     | enum      | 是   | 谁作选择                 | `author`／`auto`；禁止 `model` | STORAGE R03＋R13＋接缝微改 |
| `decided_at`     | str\|null | 是   | 选择或明确驳回时间       | 未决定写 null       | STORAGE R03      |
| `digest_applied` | list[str] | 是   | 这次在规划层消化了什么   | 只存规划 ID         | STORAGE R03      |
| `variant_note`   | str\|null | 是   | 作者混合输入后的变体说明 | 无则 null           | STORAGE R03      |
| `card_ref`       | str       | 是   | 这次选择属于哪张稳定主架卡 | AC 号或完整沙箱卡引用；不得保存 C7 局部卡号 | 接缝微改 |
| `recommended_key` | str     | 是   | 当时的稳定主推荐号       | 必须指向本记录一个真实 `options[].key` | 接缝微改 |
| `group_status`   | enum      | 是   | 题组是否被明确驳回       | `active`／`discarded` | M8 R04＋接缝微改 |

### `options[]`

| 英文名        | 类型      | 必填 | 人话               | 来源             |
| ------------- | --------- | ---- | ------------------ | ---------------- |
| `key`         | str       | 是   | 本组内选项号       | STORAGE R03 示例 |
| `summary`     | str       | 是   | 选项一句话         | STORAGE R03 示例 |
| `why_fit`     | str       | 是   | 为什么适合         | STORAGE R03 示例 |
| `changes`     | str       | 是   | 选它会怎样改规划   | STORAGE R03 示例 |
| `risks`       | str       | 是   | 风险               | STORAGE R03 示例 |
| `digest_refs` | list[str] | 是   | 将消化哪些规划对象 | STORAGE R03 示例 |

选择记录不带 `truth_bearing`。模型生成选项，不等于模型作决定。

三种状态只有下面一种读法：

| 人话状态 | 规划账表达 |
|---|---|
| 选择某项 | 有 `option_record`；`group_status=active`；`chosen_key` 非空 |
| 作者明确整组驳回 | 有 `option_record`；`group_status=discarded`；`chosen_key=null`；`digest_applied=[]` |
| 尚未处理／被停点挡住 | 没有 `option_record`；C7 快照与停点回执继续可见 |

`decided_by=auto` 只允许由 [C7_SELECTION_ACTION.md](C7_SELECTION_ACTION.md) 中通过 P1 `auto_pass` 校验的动作产生，并且只能采用当时的 `recommended_key`。它不能填写作者签字、整组驳回或获得 Canon／actual／事实账写权。

planstore 消费选择动作时，必须在写入前校验：稳定规划卡存在且 rev 未过期；C7 的推荐号和选择号都指向真实 option；动作来源只为 `author`／`auto`；`auto` 没有伪造作者签字且当前停点允许；`discarded` 不带 `chosen_key` 或规划消化；全部规划目标存在且 rev 相符。任一项失败都不得写 `plan.json`、流水或提交日志，也不得回退到首个选项、按标题找替身或静默新建对象。

------

## 14. 槽位映射 `slot_mapping`

映射表只记已经形成的映射或写成前的明确预调整。`slot_mappings=[]` 只表示映射尚未完成／pending，不表示作者明确决定“无映射”。实际 C1 章节若不承接叙事规划，使用既有 `non_narrative`；本合同不增加 `unmapped`／`none`／`discarded` 状态。

| 英文名 | 类型 | 必填 | 人话 | 约束 | 来源 |
|---|---|---|---|---|---|
| `id` | str | 是 | 稳定映射身份 | `MAP-0001` 形状，由 planstore 复用 `id_counters.MAP` 发号；不得回收或按数组位置引用 | 槽位映射微改 |
| `slot_ref` | str\|null | 是 | 被映射的规划槽 | `as_written`／`split`／`merge` 必须引用真实 S-；`inserted`／`non_narrative` 不承接叙事规划时为 null | STORAGE R03＋槽位映射微改 |
| `chapter_id` | str\|null | 是 | 实际 C1 章节 | 写成后必须引用真实 C1；仅预调整时可以 null | STORAGE R03＋C1 |
| `expected_chapter_no` | int\|null | 是 | 预计物理章号 | 非空时为正整数；`chapter_id=null` 的预调整必须提供 | STORAGE R03 |
| `mapping_kind` | enum | 是 | 映射类型 | `as_written`／`split`／`merge`／`inserted`／`non_narrative` | STORAGE R03 |
| `reason` | str | 是 | 为什么这样映射 | 可以为空串，不得为 null | STORAGE R03 |
| `decided_by` | enum | 是 | 谁决定映射 | `author`／`auto`；`auto` 仍须通过既有停点权限，不因此获得作者签字 | STORAGE R03＋槽位映射微改 |
| `mapping_status` | enum | 是 | 映射是否仍现行 | `active`／`superseded` | STORAGE R03 |
| `superseded_by` | str\|null | 是 | 被哪条新映射顶替 | `active` 必须为 null；`superseded` 必须引用真实存在、非自身的 `MAP-` | STORAGE R03＋槽位映射微改 |

planstore 写入前必须逐项校验：MAP 号是本次计数器下一号且全账唯一；非空章槽和 C1 引用真实存在；类型、枚举与空值组合合法；`auto` 获得当前停点授权；`superseded_by` 指向真实现行替代映射；相同 `operation_id`＋相同载荷只返回原结果，不重复发号或写行，相同动作号携带不同载荷则拒绝。

完整 handover 还必须得到与本次 C1 `chapter_id`、目标章槽相符的 `active` 映射，并与 `handover_parts`、槽位状态、覆盖对象真值方向和 handover 流水在同一事务提交。不得只写 `handover_parts`、跳过映射后冒充交棒成功，也不得用 `slot_status` 代替映射对象。

------

## 15. 对账边 `reconciliation_edge`

| 英文名             | 类型      | 必填 | 人话                 | 枚举／约束                                                   | 来源            |
| ------------------ | --------- | ---- | -------------------- | ------------------------------------------------------------ | --------------- |
| `id`               | str       | 是   | 稳定对账边身份       | `RE-0001` 形状，由 planstore 复用 `id_counters.RE` 发号       | STORAGE R03＋对账准入微改 |
| `planned_ref`      | str\|null | 是   | 被对照的 PE／H／MC   | 书稿有新增、计划没有时为 null                                | STORAGE R03     |
| `planned_rev`      | int\|null | 是   | 对账时的计划对象修订 | 与 current 对象一致；`planned_ref=null` 时为 null             | 对账准入微改    |
| `actual_fact_refs` | list[str] | 是   | 已确认成文事实       | 只存 C4 内部 ID，如 `f044`                                   | STORAGE R03＋C4 |
| `actual_fact_basis_sha256` | str\|null | 是 | 所引 confirmed facts 的基线摘要 | 未接入事实时为 null；有引用时按稳定顺序对完整 C4 记录做 canonical SHA-256 | 对账准入微改 |
| `chapter_ref`      | str       | 是   | 对照哪一章书稿       | 必须是 C1 章节书稿 ID                                        | STORAGE R03＋C1 |
| `chapter_revision_ref` | obj   | r07 是 | 对照的是该章哪一版 current 正文 | `{chapter_id, revision_no, revision_text_sha256}`；chapter_id 必须等于 `chapter_ref` | C11 v1 |
| `slot_ref`         | str       | 是   | 对账属于哪个规划槽   | 必须由 current active mapping 连接到 `chapter_ref`            | 对账准入微改    |
| `chapter_text_sha256` | str    | 是   | 对账看到的 C1 原文字节摘要 | current C1 文本变化后旧边 stale                            | 对账准入微改    |
| `source_run_id`    | str       | 是   | 观察候选动作号       | 对应 `RECONCILIATION_CANDIDATE.reconcile_run_id`；不是对象 ID | 对账准入微改    |
| `source_item_key`  | str       | 是   | 候选里的局部项       | 与 source run 组合唯一；不复制候选内容                       | 对账准入微改    |
| `outcome`          | enum      | 是   | 机器观察结果         | `exact`／`variant`／`unrealized`／`contradicted`／`unplanned`／`ambiguous` | STORAGE R03     |
| `coverage`         | enum      | 是   | 覆盖完整程度         | `full`／`partial`                                            | STORAGE R03     |
| `variant_note`     | str\|null | 条件 | 变体说明             | outcome=variant 时必填                                       | STORAGE R03     |
| `author_decision`  | obj\|null | 是   | 作者怎样处置         | 未处置为 null                                                | STORAGE R03     |
| `basis_commit_seq` | int       | 是   | 对账时看到的账本水位 | `story_commit_seq`                                           | STORAGE R03     |
| `decided_by`       | enum      | 是   | 当前结果由谁定       | `auto`／`author`                                             | STORAGE R03     |
| `edge_status`      | enum      | 是   | 边的生命周期         | `active`／`superseded`／`stale`                              | STORAGE R03     |
| `superseded_by`    | str\|null | 是   | 被哪条新边接替       | RE- ID 或 null                                               | STORAGE R03     |
| `rev`              | int       | 是   | 边自身修订号         | 创建为 1；facts 准入、作者处置或 stale 迁移时严格 +1          | 对账准入微改    |

### `author_decision`

| 英文名       | 类型 | 必填 | 人话     | 枚举                                                  |
| ------------ | ---- | ---- | -------- | ----------------------------------------------------- |
| `action`     | enum | 是   | 作者处置 | `accept_as_is`／`defer`／`void_plan`／`rewrite_draft` |
| `decided_at` | str  | 是   | 处置时间 | 系统时间                                              |
| `note`       | str  | 是   | 作者说明 | 可空串                                                |

### 写权限

- 模型／程序可以写 `outcome`、`coverage`、`variant_note`，此时 `decided_by=auto`、`author_decision=null`。
- 作者改判或处置后，写入 `author_decision`，并将 `decided_by=author`。
- `rewrite_draft` 的作者界面词为“修改书稿”，内部旧枚举暂保留。
- 对账边可以在未交棒状态下产生。
- 普通对账观察 writer 不能改 C4，也不能改冻结书稿；跨账 facts 准入事务中仍由 M4 规则写 C4，planstore 只负责同事务接回 RE 引用。
- `outcome=exact／variant` 可以支持实际兑现派生，但不能自动等于关章通过。

### 观察候选、facts 准入与 actual 支持

[RECONCILIATION_CANDIDATE.md](RECONCILIATION_CANDIDATE.md) 先读 current C1、当前 planning 对象和冻结 C3 候选。候选通过机械覆盖与证据校验后，planstore 可以创建 RE；创建时 `actual_fact_refs=[]`、`actual_fact_basis_sha256=null`，只保存六态观察，不获得 actual 支持权。

只有作者提交 [RECONCILIATION_FACT_ADMISSION_ACTION.md](RECONCILIATION_FACT_ADMISSION_ACTION.md)，M4 规则在同一事务把逐字有据的 C3 候选接纳成 confirmed C4 后，planstore 才能把内部 f 引用与事实基线摘要接回 current RE。模型、PE 的 digested 状态、文件存在或 handover 本身都不能代替这次作者动作。

actual 派生支持必须同时满足：RE 为 active；outcome 为 exact／variant；`actual_fact_refs` 非空；所引 C4 全部仍是 current confirmed；事实基线摘要、C1 文本 SHA、`chapter_revision_ref`、planned rev 与 mapping 全部 current。任一不满足即不得支持 actual，并应由 stale 扫描把旧边转为 `edge_status=stale`。actual 是带 `support_set=[RE-…]` 的派生结果，不在 PE、C4 或别处写裸布尔位。

六态观察 writer 只写 plan；facts 准入事务同时写 `facts.json`、`plan.json`、history、blob 与 commit log。跨文件事务继续复用同一 `.planstore.lock`、`.planstore_txn/` 和 operation ID；不能新建 reconciliation ledger 或第二 facts 真源。

### C11 chapter revision 接缝（r07）

- `slot_mapping.chapter_id` 是稳定映射，不复制 revision truth，章节 r1→r2 时保持 active。
- 新建 RE 必须保存 current `chapter_revision_ref`；r06 旧 RE 没有该字段，只能按 legacy fail-closed 读取，不能支持 revision-aware actual。
- revision commit 在 C11 current pointer 翻转前，必须预计算本章 active RE：引用旧 revision、旧 C1 SHA 或转 needs_recheck fact 的边进入同一事务 stale，edge rev +1，旧引用保留审计。
- planstore 原计划文字、stable mapping、PE digest 与 slot status 不因章节修订自动改变。
- ledger／C1／facts／RE／history／blob／receipt 复用现有统一 transaction coordinator；任何一边写失败都恢复 all-before。

### r06 backward compatibility

r06 plan-v2 可以继续由现役 handover／对账／fact writer 读取。升级到 r07 后，旧非空 RE 必须通过显式迁移补 `chapter_revision_ref`；不得只拿 `chapter_text_sha256` 猜 revision，也不得静默填 current。旧 reader 遇到带 r07 revision ref 的 RE 只能 fail closed，不能忽略新字段继续提供 actual 支持。

------

## 16. 停点设置 `stop_points`

当前来源只给出：

```text
preset / P1 / P2 / P3 / P4 / P5
```

并给出过一个兼容示例：

```json
{
  "preset": "novice",
  "P1": "auto_pass",
  "P2": "auto_pass",
  "P3": "remind",
  "P4": "remind",
  "P5": "remind"
}
```

本候选只冻结四条边界：

1. P3 不允许无提示自动搬剧情；
2. 停点设置不能改变真值签字权；
3. 停点设置不能表示收费等级；
4. 英文 P 号不进入作者界面。

完整 preset 和各 P 值域仍需现行 R01 字段表或独立合同补齐。

------

## 17. `truth_bearing` 的唯一读法

只允许出现在：

```text
chapter_slot
scene
planned_event
hook
must_carry
```

枚举：

| 值            | 唯一含义                                       |
| ------------- | ---------------------------------------------- |
| `primary`     | 当前仍由规划账承担工作真值                     |
| `shadow`      | 从已有书稿反推的规划影子                       |
| `handed_over` | 作者已明确选择书稿接棒，该计划成为“当初的打算” |

它不能表示：

- 已经发生；
- 已经收工；
- 已经关章；
- 已经通过质检；
- 可以开下一章。

------

## 18. 收工动作与规划账边界

历史 WRITING R03 曾提议在槽位上增加：

```text
closeout = {
  mode: full_check / self_report / no_prose,
  closed_at,
  dark_count,
  prose_disposition: stored / exported / discarded
}
```

正式 [WRITING_DESK_CLOSEOUT_ACTION.md](WRITING_DESK_CLOSEOUT_ACTION.md) 已把 `full_check`、`skip_check`、`no_prose` 收窄为短命作者命令。它不等于上面的长期 `closeout` 对象，也不进入本账 schema。

长期落点仍存在一个不能硬猜的缺口：

- `mode=no_prose` 时根本没有书稿，`prose_disposition` 应该写什么；
- 是否允许 null／省略，来源没有决定；
- `closed_at` 还容易被误读为关章时间；
- 暗稿是否算签过字、是否允许开下一章仍开放。

因此：

- `closeout` **不进入本候选必填 schema**；
- 不得退而使用 `slot_status=closed`；
- 收工动作可以正式表达，但不能给其它模块提供关章／开章权力；
- `no_prose` 的“规划进度 +1”长期 owner 仍未正式化，不能写进 planstore、written、actual 或新进度账；
- `prose_status=dark_draft` 仍可正常记录，不受这个缺口影响。

------

## 19. `plan_history.jsonl`

每行字段：

| 英文名         | 类型 | 必填 | 人话               | 约束                      | 来源             |
| -------------- | ---- | ---- | ------------------ | ------------------------- | ---------------- |
| `ts`           | str  | 是   | 操作时间           | 系统时间                  | STORAGE R03      |
| `op`           | str  | 是   | 所属复合动作       | operation_id              | STORAGE R03      |
| `actor`        | enum | 是   | 谁发起了落盘变化   | `author`／`model`／`auto` | STORAGE R03      |
| `action`       | enum | 是   | 做了什么           | 见下                      | STORAGE R03      |
| `object_id`    | str  | 是   | 改了哪个对象       | 稳定对象 ID               | STORAGE R03      |
| `rev`          | int  | 是   | 修改后的对象修订号 | 与主文件一致              | STORAGE R03      |
| `changes`      | obj  | 是   | 字段前后值         | 不得只写自然语言          | STORAGE R03      |
| `content_hash` | str  | 是   | 修改前完整对象快照 | 指向 blob                 | STORAGE R03      |
| `note`         | str  | 是   | 人话说明           | 可空串                    | STORAGE R03 示例 |

允许动作：

```text
create
update
void
digest
reschedule
remap
handover
reconcile
fact_basis_stale
undo
```

`claim` 在 STORAGE R03 中出现但没有定义，当前禁止写入。

`WRITING_DESK_CLOSEOUT_ACTION v1` 是规划账外的短命命令，不加入本动作词表。`dark_mark` 仍只存在于 WRITING 设计，等它自己的正式写入边界补齐后再决定是否加入。

### actor 纪律

- `actor=model` 只能记录模型候选对象的创建；
- 作者选择候选后对正式规划造成的变化，`actor=author`；
- P1 设置允许的主推荐自动放行，以及机械水位、过期或恢复处理，可用 `actor=auto`；
- 不允许用 `model` 表示模型替作者决定剧情。

合法示例：

```json
{
  "ts": "2026-08-15 09:10:00",
  "op": "op-20260815-a1b2",
  "actor": "author",
  "action": "digest",
  "object_id": "PE-0412",
  "rev": 2,
  "changes": {
    "digest_status": ["pending", "digested"],
    "digest_ref": [null, "OPT-0001"]
  },
  "content_hash": "sha256:9f2c...",
  "note": "作者选择 OPT-0001 的 B"
}
```

------

## 20. `commit_log.jsonl`

### prepare 行

| 英文名             | 类型      | 必填 | 人话                   |
| ------------------ | --------- | ---- | ---------------------- |
| `op`               | str       | 是   | operation_id           |
| `phase`            | enum      | 是   | 固定 `prepare`         |
| `story_commit_seq` | int       | 是   | 本次权威提交水位       |
| `request_sha256`   | str       | 是   | 本次正式输入载荷摘要；跨进程重放同 op 时必须完全相同 |
| `receipt`          | obj       | 否   | v2 通用事务的无正文结果回执；只供已 commit 动作幂等回放 |
| `files`            | list[obj] | 是   | 会改哪些文件及预期版本 |
| `action`           | str       | 是   | 复合动作名             |
| `ts`               | str       | 是   | 时间                   |

`files[]` 不再使用没有 owner 的裸 `expected_rev=0` 占位。现有 JSON writer 只允许三种机械形状：

- 原子替换文件：`path + expected_sha256 + target_sha256`；
- 纯追加文件：`path + append=true + expected_size + append_sha256`；
- 内容寻址 blob：`path + content_addressed=true + target_sha256`。

prepare 写入前先生成瞬时恢复底稿；prepare 之后每一步都按上面的 before／target 指纹核对。恢复扫描遇到全部 target 已写成时补 commit；只写一部分时按底稿恢复原字节、截断未提交流水并追加 rolled_back；任何文件既不匹配 before 也不匹配 target 时进入 `NEEDS_MANUAL_RECOVERY`，不得猜测。

### 完成／回滚行

| 英文名  | 类型 | 必填 | 人话                    |
| ------- | ---- | ---- | ----------------------- |
| `op`    | str  | 是   | 与 prepare 相同         |
| `phase` | enum | 是   | `commit`／`rolled_back` |
| `ts`    | str  | 是   | 时间                    |

合法示例：

```json
{"op":"op-20260815-a1b2","phase":"prepare","story_commit_seq":108,
 "request_sha256":"…",
 "files":[{"path":"plan.json","expected_sha256":"…","target_sha256":"…"},
          {"path":"plan_history.jsonl","append":true,"expected_size":2401,"append_sha256":"…"}],
 "action":"handover","ts":"2026-08-15 09:20:00"}
{"op":"op-20260815-a1b2","phase":"commit","ts":"2026-08-15 09:20:01"}
```

handover writer 的公开运行状态只有：`NOT_HAPPENED`、`PENDING_RECOVERY`、`COMMITTED`、`NEEDS_MANUAL_RECOVERY`。rolled_back 是 `NOT_HAPPENED` 的终态证据；同一 operation_id 不得在 rolled_back 后静默复用。已 commit 的同 op＋同载荷直接回放成功，不重复创建 C1、handover part、MAP 或 commit；同 op＋不同载荷写前拒绝。

------

## 21. 合法 `plan.json` 示例

以下示例处于“计划已选定，但书稿尚未交棒、尚未对账”的状态：

```json
{
  "schema": "plan-v2",
  "ledger": "plan",
  "book": {
    "id": "BK-0001",
    "premise": "抬棺匠陈九棺发现祖传阴棺正在逐步抹去他与至亲之间的关系。",
    "genre_promise": "悬疑灵异；每次开棺都会带来更重的代价。",
    "main_beats": [
      {
        "key": "beat-2",
        "text": "每开一口禁棺，世上多一个忘记他的人。"
      }
    ],
    "ending_anchor": "开尽十二棺时，陈九棺必须决定是否保留自己的名字。",
    "volumes_enabled": false,
    "source_identity": "author_declared",
    "created_at": "2026-08-15 08:00:00",
    "updated_at": "2026-08-15 08:00:00",
    "rev": 1,
    "note": ""
  },
  "slot_sequence": [
    "S-0004"
  ],
  "volumes": [],
  "slots": [
    {
      "id": "S-0004",
      "volume_ref": null,
      "title_hint": "归家",
      "goal": "让开棺的代价第一次直接落到陈九棺身上。",
      "summary": "陈九棺回家报平安，却发现爷爷已经无法认出他；他据此确认开棺代价正在兑现。",
      "entry_state": "首棺已开；爷爷仍健在。",
      "storyline_refs": [
        "L-0001"
      ],
      "scene_refs": [
        "SCN-0007"
      ],
      "exit_condition": "陈九棺确认遗忘与开棺有关。",
      "exit_hook": "棺中出现第二次异常心跳。",
      "must_not": [
        "爷爷可以遗忘陈九棺，但不能在本章死亡。"
      ],
      "risks": [
        "遗忘规则的作用范围仍未完全确定。"
      ],
      "target_length": 2600,
      "outline_checkpoint": {
        "outline_rev": 2,
        "source_slot_ref": "S-0004",
        "source_commit_seq": 108
      },
      "slot_status": "planned",
      "handover_parts": [],
      "truth_bearing": "primary",
      "source_identity": "author_declared",
      "created_at": "2026-08-15 08:05:00",
      "updated_at": "2026-08-15 08:30:00",
      "rev": 2,
      "note": ""
    }
  ],
  "scenes": [
    {
      "id": "SCN-0007",
      "slot_ref": "S-0004",
      "goal": "让读者和陈九棺同时意识到爷爷已经忘了他。",
      "summary": "陈九棺回到老屋，爷爷用对待陌生访客的方式招呼他，原本亲近的关系转为疏离。",
      "location": "陈家老屋堂屋",
      "characters": [
        "CH-0001",
        "CH-0002"
      ],
      "pe_refs": [
        "PE-0412"
      ],
      "mood_in": "归家的短暂放松",
      "mood_out": "确认代价后的不安",
      "visual_hint": "昏黄堂屋；老人背光削苹果。",
      "dialogue_hints": [
        "爷爷最后才问出陈九棺的身份，不写完整台词。"
      ],
      "resistance": "爷爷的其他行为完全正常，使陈九棺一开始误以为老人只是开玩笑。",
      "turn": "爷爷以待客动作确认自己把陈九棺当成陌生人。",
      "pov": "CH-0001",
      "spoiler_notes": [
        "不得提前解释遗忘会扩散到哪些人。"
      ],
      "word_estimate": 900,
      "truth_bearing": "primary",
      "source_identity": "author_declared",
      "created_at": "2026-08-15 08:10:00",
      "updated_at": "2026-08-15 08:30:00",
      "rev": 2,
      "note": ""
    }
  ],
  "events": [
    {
      "id": "PE-0412",
      "text": "爷爷无法认出陈九棺，并把他当成第一次上门的陌生人。",
      "scene_ref": "SCN-0007",
      "storyline_ref": "L-0001",
      "purpose": "payoff",
      "hook_links": [
        {
          "hook_ref": "H-0003",
          "role": "payoff"
        }
      ],
      "story_time_hint": "首棺开启后的次日清晨",
      "digest_status": "digested",
      "digest_ref": "OPT-0001",
      "origin_ref": "BK-0001#beat-2",
      "repair_ref": null,
      "deviation_note": null,
      "defer_count": 0,
      "truth_bearing": "primary",
      "prose_status": "unwritten",
      "prose_basis": null,
      "impact": "high",
      "source_identity": "model_suggested",
      "created_at": "2026-08-15 08:20:00",
      "updated_at": "2026-08-15 08:30:00",
      "rev": 2,
      "note": ""
    }
  ],
  "storylines": [
    {
      "id": "L-0001",
      "name": "十二禁棺主线",
      "alias": "禁棺线",
      "priority": 1,
      "members": [
        "CH-0001",
        "CH-0002"
      ],
      "line_status": "active",
      "last_scene_ref": "SCN-0007",
      "source_identity": "author_declared",
      "created_at": "2026-08-15 08:00:00",
      "updated_at": "2026-08-15 08:10:00",
      "rev": 1,
      "note": ""
    }
  ],
  "hooks": [
    {
      "id": "H-0003",
      "content": "每开一口禁棺，至少一名至亲会遗忘开棺者。",
      "plant_refs": [
        {
          "ref": "PE-0203",
          "note": "老仵作曾警告开棺会失去重要之物。"
        }
      ],
      "payoff_slot_ref": "S-0004",
      "hook_status": "paid",
      "paid_by_ref": "PE-0412",
      "defer_count": 0,
      "revealed": true,
      "revealed_at": "SCN-0007",
      "safety_summary": "爷爷一线存在尚未向读者完全解释的遗忘规则。",
      "truth_bearing": "primary",
      "source_identity": "author_declared",
      "created_at": "2026-08-15 08:00:00",
      "updated_at": "2026-08-15 08:30:00",
      "rev": 2,
      "note": ""
    }
  ],
  "widgets": [
    {
      "id": "WG-0001",
      "key": "writing_guidance",
      "anchor_ref": "SCN-0007",
      "payload": {
        "instruction": "先让爷爷表现得一切正常，再通过身份误认确认关系变化。"
      },
      "source_identity": "model_suggested",
      "created_at": "2026-08-15 08:25:00",
      "updated_at": "2026-08-15 08:25:00",
      "rev": 1,
      "note": ""
    }
  ],
  "pins": [
    {
      "id": "PIN-0001",
      "owner_ref": "S-0004",
      "target_kind": "fact",
      "target_ref": "f001",
      "quote": null,
      "purpose_note": "入口状态依据：首棺已经开启。",
      "pin_status": "ok",
      "source_identity": "author_declared",
      "created_at": "2026-08-15 08:05:00",
      "updated_at": "2026-08-15 08:05:00",
      "rev": 1,
      "note": ""
    }
  ],
  "must_carries": [
    {
      "id": "MC-0011",
      "text": "让开棺代价第一次落到陈九棺的至亲关系上。",
      "target_slot_ref": "S-0004",
      "origin_ref": "H-0003",
      "mc_status": "digested",
      "digest_ref": "OPT-0001",
      "defer_count": 0,
      "truth_bearing": "primary",
      "source_identity": "author_declared",
      "created_at": "2026-08-15 08:05:00",
      "updated_at": "2026-08-15 08:30:00",
      "rev": 2,
      "note": ""
    }
  ],
  "option_records": [
    {
      "id": "OPT-0001",
      "slot_ref": "S-0004",
      "question": "首棺已开，这一章怎样让代价第一次落到陈九棺身上？",
      "options": [
        {
          "key": "A",
          "summary": "先让旁系亲属认不出他，再递进到爷爷。",
          "why_fit": "铺垫更充分。",
          "changes": "需要增加一场过渡。",
          "risks": "本章可能装不下。",
          "digest_refs": []
        },
        {
          "key": "B",
          "summary": "直接让爷爷无法认出他。",
          "why_fit": "最亲关系带来的冲击最直接。",
          "changes": "爷爷线进入陌生人状态。",
          "risks": "规则边界尚未完全交代。",
          "digest_refs": [
            "H-0003",
            "MC-0011"
          ]
        }
      ],
      "chosen_key": "B",
      "decided_by": "author",
      "decided_at": "2026-08-15 08:30:00",
      "digest_applied": [
        "PE-0412",
        "H-0003",
        "MC-0011"
      ],
      "variant_note": null,
      "card_ref": "SB-0001#d-ac-1",
      "recommended_key": "B",
      "group_status": "active",
      "source_identity": "model_suggested",
      "created_at": "2026-08-15 08:25:00",
      "updated_at": "2026-08-15 08:30:00",
      "rev": 2,
      "note": ""
    }
  ],
  "slot_mappings": [],
  "reconciliation_edges": [],
  "stop_points": {
    "preset": "novice",
    "P1": "auto_pass",
    "P2": "auto_pass",
    "P3": "remind",
    "P4": "remind",
    "P5": "remind"
  },
  "id_counters": {
    "BK": 1,
    "VOL": 0,
    "S": 4,
    "SCN": 7,
    "PE": 412,
    "L": 1,
    "H": 3,
    "WG": 1,
    "PIN": 1,
    "MC": 11,
    "OPT": 1,
    "MAP": 0,
    "RE": 0,
    "DESTINY": 0,
    "INS": 0
  }
}
```

### 明确禁止

- 不能把 PE、场、槽或 hook 写进 C4 冒充已发生事实；
- 不能因书稿保存或入库自动追加 `handover_parts`；
- 不能将 `slot_status` 扩成 `closed`；
- 不能把收工写成关章；
- 不能把 C6 无红灯写成关章通过；
- 不能用 `digested`／`paid` 表示实际发生或实际兑现；
- 不能把 `prose_basis=self_reported` 读成“已完成关章签字”；
- 不能让模型直接写 `author_decision`；
- 不能把自动放行写成 `author`，也不能让 `auto` 夹带作者签字；
- 不能把不存在的推荐号退回为 `options[0]`；
- 不能按标题猜规划卡，或在引用不存在／rev 过期时先写账；
- 不能把整组驳回写成选中主推荐，也不能把未处理和明确驳回混为一条记录；
- 不能把 `F-0001` 显示号写进跨账引用；
- 不能把 C7／C9／概览卡的内容回写为规划真值；
- 不能在计划字段中保存完整小说对白；
- 不能在合同中加入付费档或免费额度。

### 开放问题

仅保留 R13 或 ZIP 已经开口的部分：

1. 暗稿算不算完整签字；
2. 暗稿／无书稿收工能不能开下一章；
3. 题 16 的触发字段、枚举与组合判据；
4. ADD-043：规则／能力／例外是否拆条；
5. ADD-044：读者承诺是否单开；
6. 作者旧大纲什么时候从原稿区变成规划对象；
7. 写完的章节在规划画布上显示哪张卡；
8. 卷对象完整字段；
9. 停点设置完整枚举；
10. 是否需要长期保存独立 closeout 结果；当前正式动作本身不落规划账；
11. `no_prose` 收工的“规划进度 +1”由哪个长期 owner 保存；
12. `defer_count` 强制升级阈值是否固定为 3。

------

## 接线表

| 工件           | 落盘                 | 谁写                           | 谁读                          | 什么时候过期                        | 能不能写真值                   |
| -------------- | -------------------- | ------------------------------ | ----------------------------- | ----------------------------------- | ------------------------------ |
| C1 章节文档    | `chapters.json`      | M1／章节版本管理               | M2、M3、M6、M7、对账          | 新章版本产生时旧版本仍保留          | 只保存书稿及来源；不能写计划   |
| C4 事实账      | `facts.json`         | M4；状态改变必须走 M5 作者确认 | M6、M7、M8、M9、M11           | 不作为投影，不因读取过期            | 只能写已确认事实；不写计划     |
| 规划账         | `plan.json`          | planstore                      | M8、M9、M11、对账、关章检查   | 当前文件永远是最新提交态            | 写未来安排；不能冒充事实       |
| 规划流水       | `plan_history.jsonl` | planstore 纯追加               | 审计、撤销、恢复              | 永不过期、永不改写                  | 不单独裁决当前真值             |
| 跨账提交日志   | `commit_log.jsonl`   | 提交协调器                     | planstore、恢复扫描、投影水位 | 永不过期                            | 不保存故事内容真值             |
| C7 v1 出题快照 | `plan_latest.json`   | M8 覆盖写                      | 展示、选择／停点动作层        | plan、fact 或当前出题输入改变即失效 | 不能写任何账                   |
| C7 选择动作 v1 | 不落盘；消费后丢弃   | 作者动作层／停点策略层         | planstore                     | C7 SHA、规划卡或目标 rev 变化即 stale | 只能请求规划写入，自己不能写账 |
| 工作稿 v1 | 写作区当前工作资产；物理保存属实现细节 | 作者经写作区保存 | 写作区、检测侧、收工／交棒动作层 | 新 work revision 产生后旧 revision stale | 不能产生 C1、facts、actual 或交棒 |
| 收工动作 v1 | 不落 planstore；短命命令 | 作者动作层 | 写作区收工流程 | 相同 operation 走幂等；引用旧 work rev 拒绝 | 只区分三路收工，不能关章或写真值 |
| 工作稿交棒动作 v1 | 不落盘；C1 接收后丢弃 | 作者动作层 | C1 接收边界 | work revision 变化即 stale | 只能请求 C1 接收，不能直写 planstore |
| C6 体检报告    | `health_report.json` | M7                             | 收件箱、M5、作者              | `source_commit_seq` 落后即 stale    | 只能报告问题，不能修事实或关章 |
| C5 概览卡候选  | 本候选不落盘         | M9                             | M5、项目概览                  | 来源提交变化即 stale                | 投影可改；进 C4 必须作者确认   |
| C8 场景卡候选  | 尚未冻结             | M10                            | 外部视频／分镜消费者          | 来源规划提交变化即 stale            | 产品内可纠错；不能反写真源     |
| C9 前提包候选  | 尚未冻结             | M11                            | M8                            | 任一来源提交变化即重编              | 只读执行材料；不能回写         |

### C4 与规划账的边界

- C4 只读给规划账；
- `basis_pin.target_ref` 和 `reconciliation_edge.actual_fact_refs` 只保存 C4 内部 ID；
- 规划账不能更改 C4；
- C4 的事实状态或 chapter revision 归属改变后，引用它的引脚、对账边及投影进入 stale／重查；
- 暗稿不发 F 号，不塞进 C4；它以 `planned_event.prose_status=dark_draft` 继续住规划账。

### C7 的边界

- C7 v1 只回答“这一次 M8 出了什么题和候选”，只比 v0 多稳定推荐、规划卡引用和规划卡 rev；
- C7 v1 不提供 plan.json 查询；
- 作者选择、合规自动放行或整组驳回先形成短命 [C7_SELECTION_ACTION.md](C7_SELECTION_ACTION.md)，再由 planstore 校验并按选择记录写规划账；
- C7 的局部 card ID 不得进入长期账；
- C7 过期可覆盖，不留作事实历史。

### C6 的边界

- C6 只报告质检；
- C6 的 red／yellow 不表示关章；
- C6 不得就地改事实；
- 投影界面可以让作者纠错，但确认动作仍落 M5／C4；
- 当前 C6 v0 没有 `source_commit_seq`，升 v1 前不得用于高影响写操作。

------


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/CHARACTER_LEDGER_CONTENT.md git_blob=ba6cd88cb156a1d7f6683dd2947f378af13d1b94 bytes=9729 -->

# 源文件：`novel-mvp/contracts/CHARACTER_LEDGER_CONTENT.md`

- Git blob：`ba6cd88cb156a1d7f6683dd2947f378af13d1b94`
- 字节：9729
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# CHARACTER_LEDGER_CONTENT · 人物账内容合同

**正式版本：`character-ledger-content-v1`**

一句话用途：用一张可直接编辑的人物定义卡，配一组有证据、有故事时间锚的状态与轻量关系读取面，回答“这个人是谁、在某个故事时点是什么状态”；没有记录时必须明说，不能拿最新状态冒充历史。

## 1. Owner、发／收模块与边界

| 角色 | 模块／对象 | 权限与边界 |
|---|---|---|
| 作者定义 | 作者通过人物卡直接编辑 | 直接编辑按 `LEDGER_ENTRY_ENVELOPE` 记作 `AUTHOR_ATTESTATION`；这是作者签字，不是模型证据 |
| 候选提出 | M4／M5 已确认事实后的投影、模型候选 | 只能提出候选或投影；不得绕过作者与统一 writer 改写真值 |
| 唯一落盘 | `settingstore` | 复用 planstore 的原子提交、`id_counters` 与恢复样式；见 [SETTING_LEDGER_STORAGE.md](SETTING_LEDGER_STORAGE.md) |
| 读取 | M7、M9、M10、M11 | 只读合同内已确认记录及其证据、故事时间锚 |
| 跨账只读 | 事实账、规划账、章节版本账 | 只保存稳定 ID／revision ref，不复制对方真值 |
| 禁止写入 | 查询页、上下文包、导出、检查报告 | 都是投影，不得反写人物账 |

真值来源：

- `work/ledger_content_contract_20260822_r01/00_DECIDED_DRAFT_R01.md`
- `work/ledger_content_contract_20260822_r01/01_REVIEW_R01.md` 第三节
- `novel-mvp/contracts/LEDGER_ENTRY_ENVELOPE.md`
- `novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md`

冲突时以复核注记优先。本合同只定内容形状；落盘走 `settingstore`，人物页和 as-of 查询 runtime 仍待后续票。

## 2. 根对象与共同信封

每条人物账记录是一个 `CHARACTER_LEDGER_CONTENT` 对象。它复用 L1 的共同信封：

```text
id/source_identity/confirm_status/evidence_refs/story_time/
created_at/updated_at/rev/note
```

人物定义卡自身是定义类条目，因此根 `story_time` 必须为 `null`。变化时间只存在于 `state_timeline[]`、`aliases[]` 和 `relationships[]` 的故事时间区间里。

## 3. 人物卡七字段

| 字段 | 类型 | 规则 |
|---|---|---|
| `id` | str | `CH-` 永久 ID；来自共同信封，改名不改 ID |
| `canonical_name` | str | 正名，非空；人称与显示名是渲染层 |
| `aliases` | list[obj] | 每项含 `name`、故事时间区间、非空证据 |
| `role_tag` | str/null | 主角、男配等是开放值，不硬编码枚举 |
| `profile` | str | 作者可编辑背景卡；帮助识别，不能替书稿补事实 |
| `visibility` | enum | `AUTHOR`／`READER_RELEASED`；READER 侧完整数据结构仍开放 |
| `destiny_ref` | str/null | 指向规划账人物命运条目 `PLAN_DESTINY_CONTENT`；非空时必须匹配官方前缀 `^DESTINY-[0-9]+$`，提供命运目录时必须命中已登记条目 |

存在性校验已随 L5 收口（复核注记 3）：校验器 `validate_record(..., destiny_ids=...)` 收到命运目录时，悬空 `destiny_ref` 必须失败（`DESTINY_REF_NOT_FOUND`）；非官方前缀无论有无目录都失败（`DESTINY_REF_PREFIX_INVALID`）。目标对象合同见 [PLAN_DESTINY_CONTENT.md](PLAN_DESTINY_CONTENT.md)。

## 4. 状态时间线五字段

`state_timeline[]` 是从事实账与作者签字派生的读取面，不是第二事实库。

| 字段 | 类型 | 规则 |
|---|---|---|
| `ch_ref` | str | 必须等于根人物 `id` |
| `state_key` | str | 多值键，例如 `injury:left_arm`、`outfit`、`location`、`alive` |
| `value` | str | 该键在该故事区间内的值 |
| `story_time` | obj | 起锚必填、止锚可空；形状见 §6 |
| `evidence_refs` | list[str] | 至少一项，只允许 `f001` 形事实 ID 或 `AUTHOR_ATTESTATION` |

同一人物、同一 `state_key`、同一起锚只能有一项。伤势等不同键互不覆盖；例如 `injury:left_arm` 与 `poisoned` 可以同时存在。

`state_key=alive` 的值只允许 `alive` 或 `dead`。死亡与复活必须是两个不同故事时间点的独立条目，而且每一项都必须含 `AUTHOR_ATTESTATION`，对应 M5 高影响决定单条签字纪律。

## 5. 轻量关系条目

`relationships[]` 只承载轻量关系读取面：

| 字段 | 类型 | 规则 |
|---|---|---|
| `target_ref` | str | 另一人物的 `CH-` ID；不得等于自己 |
| `kind` | str | 开放词表，例如 `ally`、`rival`、`mentor` |
| `story_time` | obj | 故事时间区间 |
| `evidence_refs` | list[str] | 非空，规则同状态时间线 |

重要、不对称、需要独立历史的关系以后可以升独立对象；L2 不提前定义升级协议。

**知情边（知道／怀疑／误信／不知）只留位，不定义字段、枚举或对象形状。** `knowledge_edges` 等未拍字段在 v1 中必须被拒绝。

## 6. 故事时间锚

页面把章 revision ref 简写为 `chapter_id/revision_no/text_sha256`。为避免产生影子合同，机器字段严格沿用现役 C11：

```json
{
  "chapter_revision_ref": {
    "chapter_id": "c12",
    "revision_no": 3,
    "revision_text_sha256": "64位小写sha256"
  },
  "story_order": 120
}
```

- `story_order` 可选；它是明确的故事序，不是系统提交序。
- 区间形状为 `{start, end}`；`start` 必填，`end` 可以为 `null`。
- 同一可比较坐标下，`end` 必须严格晚于 `start`。
- `created_at`、`updated_at`、`committed_at` 等系统时间不得进入故事时间锚。

## 7. 查询语义三条硬规矩

1. `as-of` 查询没有命中时返回 `NOT_RECORDED`；不得编造值。
2. 不得拿当前最新状态冒充历史时点；晚于查询点的条目不能倒灌。
3. 缺少可比较故事序时，程序不得猜章顺序；只能精确匹配 revision ref，或返回 `STORY_TIME_NOT_COMPARABLE`。

死亡与复活保留两条独立时间线，不覆盖旧条目。

## 8. 真实示例

```json
{
  "contract": "CHARACTER_LEDGER_CONTENT",
  "version": "character-ledger-content-v1",
  "id": "CH-0001",
  "source_identity": "author_declared",
  "confirm_status": "confirmed",
  "evidence_refs": ["AUTHOR_ATTESTATION"],
  "story_time": null,
  "created_at": "2026-08-22T09:00:00+08:00",
  "updated_at": "2026-08-22T09:30:00+08:00",
  "rev": 2,
  "note": "",
  "canonical_name": "沈砚",
  "aliases": [
    {
      "name": "小砚",
      "story_time": {
        "start": {
          "chapter_revision_ref": {
            "chapter_id": "c01",
            "revision_no": 1,
            "revision_text_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
          },
          "story_order": 1
        },
        "end": null
      },
      "evidence_refs": ["f001"]
    }
  ],
  "role_tag": "主角",
  "profile": "出身北城，擅长拆解机关。",
  "visibility": "AUTHOR",
  "destiny_ref": "DESTINY-0001",
  "state_timeline": [
    {
      "ch_ref": "CH-0001",
      "state_key": "injury:left_arm",
      "value": "fractured",
      "story_time": {
        "start": {
          "chapter_revision_ref": {
            "chapter_id": "c12",
            "revision_no": 3,
            "revision_text_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
          },
          "story_order": 120
        },
        "end": null
      },
      "evidence_refs": ["f023"]
    }
  ],
  "relationships": [
    {
      "target_ref": "CH-0002",
      "kind": "ally",
      "story_time": {
        "start": {
          "chapter_revision_ref": {
            "chapter_id": "c04",
            "revision_no": 1,
            "revision_text_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
          },
          "story_order": 40
        },
        "end": null
      },
      "evidence_refs": ["f008"]
    }
  ]
}
```

## 9. 明确禁止

1. 禁止改名时重发 `CH-` ID。
2. 禁止把 `profile`、模型建议或题材包内容当书稿事实。
3. 禁止根人物定义卡携带非空 `story_time`。
4. 禁止状态、别名或关系条目没有证据。
5. 禁止 `ch_ref` 指向根人物以外的 ID。
6. 禁止拿最新状态回答较早的 `as-of` 查询。
7. 禁止死亡／复活合并成一个覆盖式值，或省略作者单签。
8. 禁止把非官方前缀或悬空的 `destiny_ref` 当合法引用（L5 起：前缀必须 `DESTINY-`＋数字；有命运目录时必须命中）。
9. 禁止在本票定义知情边字段、READER 侧数据结构、新账申请流程或 ADD-043 拆条答案。
10. 禁止绕过 `settingstore` 直写人物账，或把内容合同、validator、fixture 当成落盘方。

## 10. 开放问题与后续接缝

- `destiny_ref` 的存在性与目标对象合同：已随 L5 收口（`PLAN_DESTINY_CONTENT.md`）。
- 知情边字段枚举（T3）：只留位。
- READER 侧数据结构：只留位。
- 新账申请流程：只留位。
- ADD-043 规则／能力／例外拆条：与人物账无关，保持开放。
- 统一设定账 writer 已由 `settingstore` 承接；人物页、as-of 查询 runtime 仍待后续票。

## 11. 机器件

- Schema：[CHARACTER_LEDGER_CONTENT.schema.json](CHARACTER_LEDGER_CONTENT.schema.json)
- Validator：[validate_character_ledger_content.py](validate_character_ledger_content.py)
- Fixtures：[CHARACTER_LEDGER_CONTENT.fixtures.jsonl](CHARACTER_LEDGER_CONTENT.fixtures.jsonl)
- 定向测试：`tests/test_novel_mvp_character_ledger_content_contract.py`

## 12. 实现状态

`UNIFIED_WRITER_SETTINGSTORE_V1__DESTINY_EXISTENCE_CLOSED`

通过本合同只证明人物内容形状、证据纪律、时间锚与查询边界已经冻结，且 `destiny_ref` 的前缀与存在性校验已随 L5 收口；落盘走 `settingstore`。不证明人物页、as-of 查询或完整接入 M10/M11。


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/LOCATION_LEDGER_CONTENT.md git_blob=68dd37dd6026941dd88186e0bab50bde456ea5fd bytes=3535 -->

# 源文件：`novel-mvp/contracts/LOCATION_LEDGER_CONTENT.md`

- Git blob：`68dd37dd6026941dd88186e0bab50bde456ea5fd`
- 字节：3535
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# LOCATION_LEDGER_CONTENT · 地点账内容合同

**正式版本：`location-ledger-content-v1`**

一句话用途：保存地点定义卡和有证据、有故事时间锚的状态读取面，按故事时点回答地点是否存在、是否损毁、归属哪个势力；没记录必须返回 `NOT_RECORDED`，不能拿最新状态冒充历史。

## 1. 发／收模块与边界

| 角色 | 模块／对象 | 权限与边界 |
|---|---|---|
| 作者定义 | 作者直接编辑地点卡 | 按共同信封记录作者签字 |
| 候选提出 | M4／M5 已确认事实投影 | 只能产生候选或读取面 |
| 唯一落盘 | `settingstore` | 复用 planstore 原子提交和统一发号；见 [SETTING_LEDGER_STORAGE.md](SETTING_LEDGER_STORAGE.md) |
| 读取 | M9、M10、M11 | 只读已确认内容、证据和故事时间锚 |

真值来源：拍板页 5.2、复核页第三节、`LEDGER_ENTRY_ENVELOPE`、L2 人物账样板。冲突时复核注记优先。

## 2. 根对象与字段表

根对象复用共同信封，定义卡根 `story_time=null`。

| 字段 | 类型 | 规则 |
|---|---|---|
| `id` | str | `LOC-` 永久 ID |
| `name` | str | 地点正名 |
| `aliases` | list[obj] | 名称、故事时间区间、证据 |
| `loc_type` | str | 开放词表，例如城、国、秘境、门派驻地 |
| `parent_ref` | str/null | 可指另一 `LOC-`；不强制形成树 |
| `profile` | str | 作者可编辑定义卡正文，不替书稿补事实 |
| `state_timeline` | list[obj] | `loc_ref/state_key/value/story_time/evidence_refs`；存在、损毁、归属势力等只做读取面 |

## 3. 故事时间锚与查询

机器锚原样沿用 L2：

```json
{"chapter_revision_ref":{"chapter_id":"c08","revision_no":2,"revision_text_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},"story_order":80}
```

区间为 `{start,end}`，`end` 可为 null。查询没有该键记录返回 `NOT_RECORDED`；存在记录但故事坐标不可比较返回 `STORY_TIME_NOT_COMPARABLE`。不得用系统时间、文件顺序或最新状态猜历史。

## 4. 真实示例

```json
{"contract":"LOCATION_LEDGER_CONTENT","version":"location-ledger-content-v1","id":"LOC-0001","source_identity":"author_declared","confirm_status":"confirmed","evidence_refs":["AUTHOR_ATTESTATION"],"story_time":null,"created_at":"2026-08-22T09:00:00+08:00","updated_at":"2026-08-22T09:00:00+08:00","rev":1,"note":"","name":"北城","aliases":[],"loc_type":"城","parent_ref":null,"profile":"北境商路枢纽。","state_timeline":[{"loc_ref":"LOC-0001","state_key":"control:faction","value":"FA-0002","story_time":{"start":{"chapter_revision_ref":{"chapter_id":"c08","revision_no":2,"revision_text_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},"story_order":80},"end":null},"evidence_refs":["f081"]}]}
```

## 5. 明确禁止

1. 禁止把层级强制成树。
2. 禁止状态读取面成为第二事实库。
3. 禁止状态缺证据或缺故事时间区间。
4. 禁止拿最新状态回答更早时点。
5. 禁止把内容合同当成落盘方；落盘只走 `settingstore`。
6. 禁止在 L3 定义知情边、ADD-043、READER、新账申请、取件码、hardness 红灯或 handle 迁移。

## 6. 开放问题

知情边字段枚举、ADD-043、READER 侧结构、新账申请流程、取件码扩十本、hardness 红灯资格、handle 迁移全部只留位。

## 7. 机器件与状态

Schema、validator、fixtures 与定向测试同名配套。实现状态：`UNIFIED_WRITER_SETTINGSTORE_V1`。


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/ITEM_LEDGER_CONTENT.md git_blob=6f4d6add4f3919ef1fd8faa49ba7cccb05495836 bytes=3164 -->

# 源文件：`novel-mvp/contracts/ITEM_LEDGER_CONTENT.md`

- Git blob：`6f4d6add4f3919ef1fd8faa49ba7cccb05495836`
- 字节：3164
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# ITEM_LEDGER_CONTENT · 物品账内容合同

**正式版本：`item-ledger-content-v1`**

一句话用途：保存物品定义卡、初次出现锚、归属时间线和状态读取面；“宝物易手”的变化真值住事实账，物品账只按故事时点投影谁持有它。

## 1. 发／收模块与边界

| 角色 | 模块／对象 | 权限与边界 |
|---|---|---|
| 作者定义 | 作者直接编辑物品卡 | 按共同信封记录作者签字 |
| 候选提出 | M4／M5 已确认事实投影 | 易手、损毁等变化真值仍住事实账 |
| 唯一落盘 | `settingstore` | 见 [SETTING_LEDGER_STORAGE.md](SETTING_LEDGER_STORAGE.md) |
| 读取 | M6、M7、M10、M11 | 只读定义、归属／状态投影、证据和锚 |

## 2. 字段表

| 字段 | 类型 | 规则 |
|---|---|---|
| `id` | str | `IT-` 永久 ID |
| `name` | str | 物品正名 |
| `item_type` | str | 开放词表，例如法宝、丹药、信物 |
| `first_seen` | obj/null | L2 同形故事时间锚 |
| `ownership` | list[obj] | `owner_ref/story_time/evidence_refs`；owner 只允许 `CH-` 或 `FA-` |
| `item_status` | list[obj] | `it_ref/state_key/value/story_time/evidence_refs`，例如损毁、下落不明 |

## 3. 锚与查询

```json
{"chapter_revision_ref":{"chapter_id":"c05","revision_no":1,"revision_text_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},"story_order":50}
```

查询没有记录返回 `NOT_RECORDED`；故事坐标不可比返回 `STORY_TIME_NOT_COMPARABLE`。物品账不根据更新时间、文件顺序或“当前 owner”倒推历史。

## 4. 真实示例

```json
{"contract":"ITEM_LEDGER_CONTENT","version":"item-ledger-content-v1","id":"IT-0001","source_identity":"author_declared","confirm_status":"confirmed","evidence_refs":["AUTHOR_ATTESTATION"],"story_time":null,"created_at":"2026-08-22T09:00:00+08:00","updated_at":"2026-08-22T09:00:00+08:00","rev":1,"note":"","name":"玄铁令","item_type":"信物","first_seen":{"chapter_revision_ref":{"chapter_id":"c05","revision_no":1,"revision_text_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},"story_order":50},"ownership":[{"owner_ref":"CH-0001","story_time":{"start":{"chapter_revision_ref":{"chapter_id":"c05","revision_no":1,"revision_text_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},"story_order":50},"end":null},"evidence_refs":["f050"]}],"item_status":[]}
```

## 5. 明确禁止

1. 禁止把 ownership 当成易手变化真值；变化住事实账。
2. 禁止 owner_ref 使用 `CH-`／`FA-` 之外的未拍前缀。
3. 禁止归属或状态条目缺证据、缺故事时间。
4. 禁止拿最新归属冒充历史。
5. 禁止把内容合同当成落盘方；落盘只走 `settingstore`。不在本票实现取件码或 handle 迁移。
6. 禁止定义知情边、ADD-043、READER、新账申请或 hardness 红灯。

## 6. 开放问题

知情边、ADD-043、READER、新账申请、取件码、hardness 红灯、handle 迁移全部只留位。

## 7. 机器件与状态

Schema、validator、fixtures 与定向测试同名配套。实现状态：`UNIFIED_WRITER_SETTINGSTORE_V1`。


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/FACTION_LEDGER_CONTENT.md git_blob=d7610b573e09876268a1b273a4e524e32a867f56 bytes=3241 -->

# 源文件：`novel-mvp/contracts/FACTION_LEDGER_CONTENT.md`

- Git blob：`d7610b573e09876268a1b273a4e524e32a867f56`
- 字节：3241
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# FACTION_LEDGER_CONTENT · 势力账内容合同

**正式版本：`faction-ledger-content-v1`**

一句话用途：保存势力定义卡，以及成员和势力关系的故事时间读取面；每个成员／关系条目必须带区间和证据。

## 1. 发／收模块与边界

| 角色 | 模块／对象 | 权限与边界 |
|---|---|---|
| 作者定义 | 作者直接编辑势力卡 | 按共同信封记录作者签字 |
| 候选提出 | M4／M5 已确认事实投影 | 成员变化、结盟／敌对变化真值仍住事实账 |
| 唯一落盘 | `settingstore` | 见 [SETTING_LEDGER_STORAGE.md](SETTING_LEDGER_STORAGE.md) |
| 读取 | M9、M10、M11 | 只读定义、成员／关系投影、证据和锚 |

## 2. 字段表

| 字段 | 类型 | 规则 |
|---|---|---|
| `id` | str | `FA-` 永久 ID |
| `name` | str | 势力正名 |
| `aliases` | list[obj] | 名称、故事时间区间、证据 |
| `fac_type` | str | 开放词表，例如国家、门派、组织 |
| `members` | list[obj] | `ch_ref/role/story_time/evidence_refs` |
| `relations` | list[obj] | `target_ref/kind/story_time/evidence_refs`；target 为另一 `FA-` |
| `profile` | str | 作者可编辑定义卡正文 |

## 3. 锚与查询

```json
{"chapter_revision_ref":{"chapter_id":"c11","revision_no":4,"revision_text_sha256":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"},"story_order":110}
```

查询没有成员／关系记录返回 `NOT_RECORDED`；故事坐标不可比返回 `STORY_TIME_NOT_COMPARABLE`。不得拿当前成员表或当前关系冒充历史。

## 4. 真实示例

```json
{"contract":"FACTION_LEDGER_CONTENT","version":"faction-ledger-content-v1","id":"FA-0001","source_identity":"author_declared","confirm_status":"confirmed","evidence_refs":["AUTHOR_ATTESTATION"],"story_time":null,"created_at":"2026-08-22T09:00:00+08:00","updated_at":"2026-08-22T09:00:00+08:00","rev":1,"note":"","name":"白鹤盟","aliases":[],"fac_type":"组织","members":[{"ch_ref":"CH-0001","role":"盟主","story_time":{"start":{"chapter_revision_ref":{"chapter_id":"c11","revision_no":4,"revision_text_sha256":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"},"story_order":110},"end":null},"evidence_refs":["f110"]}],"relations":[{"target_ref":"FA-0002","kind":"alliance","story_time":{"start":{"chapter_revision_ref":{"chapter_id":"c11","revision_no":4,"revision_text_sha256":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"},"story_order":110},"end":null},"evidence_refs":["f111"]}],"profile":"北境商盟。"}
```

## 5. 明确禁止

1. 禁止 members／relations 缺故事时间或证据。
2. 禁止 relation 指向自己。
3. 禁止把当前成员表、当前关系当历史真值。
4. 禁止本合同成为第二事实库。
5. 禁止把内容合同当成落盘方；落盘只走 `settingstore`。不在本票实现取件码或 handle 迁移。
6. 禁止定义知情边、ADD-043、READER、新账申请或 hardness 红灯。

## 6. 开放问题

知情边、ADD-043、READER、新账申请、取件码、hardness 红灯、handle 迁移全部只留位。

## 7. 机器件与状态

Schema、validator、fixtures 与定向测试同名配套。实现状态：`UNIFIED_WRITER_SETTINGSTORE_V1`。


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/SYSTEM_LEDGER_CONTENT.md git_blob=0e2a12e9a26021e48d9a477f3c0ed76f0050d14d bytes=3717 -->

# 源文件：`novel-mvp/contracts/SYSTEM_LEDGER_CONTENT.md`

- Git blob：`0e2a12e9a26021e48d9a477f3c0ed76f0050d14d`
- 字节：3717
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# SYSTEM_LEDGER_CONTENT · 体系账内容合同

**正式版本：`system-ledger-content-v1`**

一句话用途：保存体系定义卡、同类排序和有方向的体系关系；题材包预填必须保留来源，作者改写后 pack_ref 原样留痕，仍能回溯原包。

## 1. 发／收模块与边界

| 角色 | 模块／对象 | 权限与边界 |
|---|---|---|
| 作者定义 | 作者直接编辑体系卡 | 直接编辑按共同信封的 `AUTHOR_ATTESTATION` 处理 |
| 预填提出 | 题材包／插件 | 只能写 `pack_prefilled + candidate + pack_ref` |
| 唯一落盘 | `settingstore` | 复用 planstore 原子提交与统一发号；见 [SETTING_LEDGER_STORAGE.md](SETTING_LEDGER_STORAGE.md) |
| 读取 | 题材包、插件、M7、M11 | 只读已登记定义、方向和来源 |

真值来源：拍板页 5.5、题 3／题 8，复核页第三节六条施工注记，`LEDGER_ENTRY_ENVELOPE`。冲突时复核注记优先。

## 2. 字段表

根对象复用共同信封，定义卡根 `story_time=null`。

| 字段 | 类型 | 规则 |
|---|---|---|
| `id` | str | `SY-` 永久 ID |
| `name` | str | 体系或体系项名称 |
| `category` | str | 开放词表，例如等级体系、技能、种族、功法、货币 |
| `rank_order` | int/null | 同一 category 内的序；没有顺序就留空 |
| `relations` | list[obj] | `target_ref` 指另一 `SY-`，`kind` 为开放文本 |
| `scope` | str/null | 适用范围 |
| `pack_ref` | str/null | 题材包来源；`pack_prefilled` 时必须非空 |

## 3. 有向关系

关系从本条指向 `target_ref`，不会自动补反向边。`relations[]` 只含：

```json
{"target_ref":"SY-0002","kind":"进阶"}
```

禁止指向自己。关系是定义卡上的有向边，不带故事时间区间。

## 4. 题材包预填与作者改写

- 预填条目必须是 `source_identity=pack_prefilled`、`confirm_status=candidate`，且 `pack_ref` 非空。
- 作者改写后必须转成 `author_declared + confirmed + AUTHOR_ATTESTATION`。
- 改写前后 `id` 不变、`rev` 加一、`pack_ref` 原样留痕。
- 校验器直接调用 L1 `validate_pack_prefilled_author_edit`，不重定义该语义。

## 5. 真实示例

```json
{
  "contract":"SYSTEM_LEDGER_CONTENT",
  "version":"system-ledger-content-v1",
  "id":"SY-0001",
  "source_identity":"author_declared",
  "confirm_status":"confirmed",
  "evidence_refs":["AUTHOR_ATTESTATION"],
  "story_time":null,
  "created_at":"2026-08-22T10:00:00+08:00",
  "updated_at":"2026-08-22T10:00:00+08:00",
  "rev":1,
  "note":"",
  "name":"炼气",
  "category":"等级体系",
  "rank_order":1,
  "relations":[{"target_ref":"SY-0002","kind":"进阶"}],
  "scope":"东陆修士",
  "pack_ref":null
}
```

## 6. 明确禁止

1. 禁止各模块私自发 `SY-` 号。
2. 禁止 `pack_prefilled` 缺 `pack_ref` 或直接成为 confirmed。
3. 禁止作者改写后清空或更换 `pack_ref`。
4. 禁止关系自动补反向边。
5. 禁止关系指向自己。
6. 禁止给定义卡关系强加故事时间区间。
7. 禁止把开放 category／kind 固化成封闭枚举。
8. 禁止绕过 `settingstore` 私写体系账；不在本票实现取件码或 handle 迁移。
9. 禁止本票定义知情边、ADD-043 拆条、READER 结构或新账申请流程。

## 7. 开放问题

知情边字段枚举、ADD-043 规则拆条、READER 侧数据结构、新账申请流程只留位。取件码扩十本和现役 handle 迁移留 L5，不在 L4 定义。

## 8. 机器件与状态

- `SYSTEM_LEDGER_CONTENT.schema.json`
- `validate_system_ledger_content.py`
- `SYSTEM_LEDGER_CONTENT.fixtures.jsonl`
- `tests/test_novel_mvp_system_ledger_content_contract.py`

实现状态：`UNIFIED_WRITER_SETTINGSTORE_V1`。


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/WORLD_RULE_LEDGER_CONTENT.md git_blob=969e5c3c146ac730f33b97c9adb1a4f9518a9d51 bytes=3644 -->

# 源文件：`novel-mvp/contracts/WORLD_RULE_LEDGER_CONTENT.md`

- Git blob：`969e5c3c146ac730f33b97c9adb1a4f9518a9d51`
- 字节：3644
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# WORLD_RULE_LEDGER_CONTENT · 世界规则账内容合同

**正式版本：`world-rule-ledger-content-v1`**

一句话用途：保存独立完整的世界规则句、适用范围、强度和例外；只有 hard 且 confirmed 的记录具备进入 M7 红灯判断的机械资格。

## 1. 发／收模块与边界

| 角色 | 模块／对象 | 权限与边界 |
|---|---|---|
| 作者定义 | 作者直接编辑规则卡 | 可用 `AUTHOR_ATTESTATION` 签字 |
| 候选提出 | M4／M5 已确认事实投影、模型建议 | 未确认只能停在 candidate |
| 唯一落盘 | `settingstore` | 复用 planstore 原子提交与统一发号；见 [SETTING_LEDGER_STORAGE.md](SETTING_LEDGER_STORAGE.md) |
| 读取 | M7、M8、M11 | M7 只能把满足本合同资格的规则送入冲突判断 |

真值来源：拍板页 5.6、题 6／题 8，复核页第三节六条施工注记，`LEDGER_ENTRY_ENVELOPE`。冲突时复核注记优先。

## 2. 字段表

根对象复用共同信封，定义卡根 `story_time=null`。

| 字段 | 类型 | 规则 |
|---|---|---|
| `id` | str | `RU-` 永久 ID |
| `rule_text` | str | 一句规则，独立完整、主语明确，沿用 C3 事实句纪律 |
| `scope` | str/null | 全书、某体系或某地域等适用范围 |
| `hardness` | enum | `hard`／`advisory` |
| `exceptions` | list[str] | v1 例外做子字段；每项是非空例外说明 |

## 3. M7 红灯资格

机械前提是：

```text
hardness=hard 且 confirm_status=confirmed
```

校验器提供 `m7_red_light_eligibility()`：

- 两项同时满足：返回 `ELIGIBLE`；
- 非 hard：返回 `HARDNESS_NOT_HARD`；
- 未 confirmed：返回 `CONFIRM_STATUS_NOT_CONFIRMED`。

这只是**资格门**，不等于 M7 已经判出冲突，也不实现 M7 runtime。AI 推断或题材包候选不能直接亮红灯。

## 4. 例外与 ADD-043 边界

`exceptions` 在 v1 只是一组字符串子字段。是否把规则、能力和例外拆成独立条目继续保持开放；本票不创建能力对象、例外对象或拆条流程。

## 5. 真实示例

```json
{
  "contract":"WORLD_RULE_LEDGER_CONTENT",
  "version":"world-rule-ledger-content-v1",
  "id":"RU-0001",
  "source_identity":"author_declared",
  "confirm_status":"confirmed",
  "evidence_refs":["AUTHOR_ATTESTATION"],
  "story_time":null,
  "created_at":"2026-08-22T10:00:00+08:00",
  "updated_at":"2026-08-22T10:00:00+08:00",
  "rev":1,
  "note":"",
  "rule_text":"东陆修士突破金丹时必须经历雷劫。",
  "scope":"东陆修士",
  "hardness":"hard",
  "exceptions":["持有天雷赦令者可延后一日"]
}
```

## 6. 明确禁止

1. 禁止各模块私自发 `RU-` 号。
2. 禁止把 advisory 规则送入 M7 红灯判断。
3. 禁止把未 confirmed 的 hard 规则送入 M7 红灯判断。
4. 禁止把资格通过写成冲突已经成立。
5. 禁止 `rule_text` 使用空串、多行清单或缺主语的残句。
6. 禁止把 `exceptions` 偷换成独立对象或能力对象。
7. 禁止抢答 ADD-043 的拆条问题。
8. 禁止本票实现 M7 runtime、取件码或 handle 迁移；落盘只走 `settingstore`。
9. 禁止本票定义知情边、READER 结构或新账申请流程。

## 7. 开放问题

知情边字段枚举、ADD-043 规则拆条、READER 侧数据结构、新账申请流程只留位。取件码扩十本和现役 handle 迁移留 L5。

## 8. 机器件与状态

- `WORLD_RULE_LEDGER_CONTENT.schema.json`
- `validate_world_rule_ledger_content.py`
- `WORLD_RULE_LEDGER_CONTENT.fixtures.jsonl`
- `tests/test_novel_mvp_world_rule_ledger_content_contract.py`

实现状态：`UNIFIED_WRITER_SETTINGSTORE_V1__M7_RUNTIME_PENDING`。


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/PLAN_VOLUME_CONTENT.md git_blob=5b1ad04ec871f35d467faf5ecb7238d5610d7f7f bytes=3780 -->

# 源文件：`novel-mvp/contracts/PLAN_VOLUME_CONTENT.md`

- Git blob：`5b1ad04ec871f35d467faf5ecb7238d5610d7f7f`
- 字节：3780
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# PLAN_VOLUME_CONTENT · 卷对象内容合同

**正式版本：`volume-plan-content-v1`**

一句话用途：把规划账卷对象的字段正式冻结——STORAGE R03 点名的七个业务字段从「空数组、不得猜类型」升级为可校验的合同；卷真值住规划账（题 1 已拍：长线真值全住规划账，长线账＝读取面）。

## 1. Owner、发／收模块与边界

| 角色 | 模块／对象 | 权限与边界 |
|---|---|---|
| 提出 | 作者、M8 候选 | 改变方向必须有作者动作 |
| 唯一落盘 | planstore | 复用 `id_counters.VOL` 统一发号与原子提交；本票不实现写动作 |
| 读取 | M8、M9、M11、关章检查、长线读取面 | 只读已提交版本 |
| 禁止写入 | C6、C7、C8、C9、概览卡、导出文件 | 均为投影，不得直写规划账 |

真值来源：`work/ledger_content_contract_20260822_r01/00_DECIDED_DRAFT_R01.md` §5.7／题 1／题 8，
复核页第三节注记，`PLAN_LEDGER_STORAGE.md`（STORAGE R03 七字段名单与 `VOL` 计数器）。冲突时复核注记优先。

## 2. 字段表

STORAGE R03 点名的七个业务字段全部收口，禁止改名、禁止删：

| 字段 | 类型 | 规则 |
|---|---|---|
| `id` | str | `VOL-` 永久 ID，`id_counters.VOL` 统一发号 |
| `order` | int | 卷序，≥1 |
| `title` | str | 卷名，非空、去首尾空白 |
| `goal` | str | 本卷目标；无内容写空串 |
| `main_conflict` | str/null | 主冲突，未定写 null |
| `entry_state` | str/null | 入卷状态，未定写 null |
| `exit_state` | str/null | 出卷状态，未定写 null |
| `summary` | str | 卷摘要；无内容写空串，不省略字段 |

另带规划账公共字段 `source_identity`（`author_declared`／`draft_inferred`／`model_suggested`）、
`created_at`／`updated_at`／`rev`／`note`，以及 L5 登记的 `confirm_status`＋`evidence_refs`
（`confirmed` 必须有证据；`AUTHOR_ATTESTATION` 只许 `author_declared+confirmed`）。

## 3. 与现役规划账的边界（本票不改 runtime）

- planstore 与长线视图 runtime 仍只接受 `volumes=[]`；现役硬停 `VOLUMES_NOT_SUPPORTED` 一字不动。
- `book.volumes_enabled=false` 时 `volumes=[]`，章槽 `volume_ref` 必须为 null（现役纪律保持）。
- `volumes_enabled=true` 的写路径挂后续 runtime 票；届时章槽 `volume_ref` 只能指已有 `VOL-` 或 null。
- 卷纲只留节奏与骨架级约束，过细内容应下沉到章计划或人物卡（M8-N02 语义）；提示器实现不在本票。

## 4. 真实示例

```json
{
  "contract": "PLAN_VOLUME_CONTENT",
  "version": "volume-plan-content-v1",
  "id": "VOL-0001",
  "source_identity": "author_declared",
  "confirm_status": "confirmed",
  "evidence_refs": ["AUTHOR_ATTESTATION"],
  "created_at": "2026-08-22T10:00:00+08:00",
  "updated_at": "2026-08-22T10:00:00+08:00",
  "rev": 1,
  "note": "",
  "order": 1,
  "title": "北城起势",
  "goal": "主角接管拆解行会",
  "main_conflict": "行会旧派阻挠",
  "entry_state": "主角初到北城",
  "exit_state": "主角掌握行会话语权",
  "summary": "第一卷交代主角进入北城并接管行会。"
}
```

## 5. 明确禁止

1. 禁止改名或删除 STORAGE R03 的七个业务字段。
2. 禁止各模块私自发 `VOL-` 号。
3. 禁止本票实现 planstore 卷写动作、M8 提示器或长线视图投影。
4. 禁止 `pack_prefilled` 进入卷对象（题材包不铺卷纲）。
5. 禁止拿卷对象冒充已发生事实或写进 C4。

## 6. 机器件与状态

- `PLAN_VOLUME_CONTENT.schema.json`
- `validate_plan_volume_content.py`
- `PLAN_VOLUME_CONTENT.fixtures.jsonl`
- `tests/test_novel_mvp_plan_volume_content_contract.py`

实现状态：`CONTRACT_ONLY__PLANSTORE_VOLUME_WRITE_PENDING`。


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/PLAN_DESTINY_CONTENT.md git_blob=d1e627f861894b6c813e1813340d9a7a6a281c2b bytes=4220 -->

# 源文件：`novel-mvp/contracts/PLAN_DESTINY_CONTENT.md`

- Git blob：`d1e627f861894b6c813e1813340d9a7a6a281c2b`
- 字节：4220
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# PLAN_DESTINY_CONTENT · 人物命运条目内容合同

**正式版本：`destiny-plan-content-v1`**

一句话用途：给人物账 `destiny_ref` 一个真实存在的目标对象——人物命运条目住规划账（题 1 已拍），本合同把 L2 占位示例里的 `DESTINY-` 正式冻结为官方前缀，并随本票补齐人物账的存在性校验（复核注记 3 收口）。

## 1. Owner、发／收模块与边界

| 角色 | 模块／对象 | 权限与边界 |
|---|---|---|
| 提出 | 作者、M8 候选 | 模糊未来内容经 M8 放置路由落到这里（M8-N01） |
| 唯一落盘 | planstore | 复用 `id_counters` 统一发号（`DESTINY` 计数器）；本票不实现写动作 |
| 读取 | M8、长线读取面、人物账存在性校验 | 只读已提交版本 |
| 跨账只读 | 人物账 | 人物账只保存 `destiny_ref` 稳定 ID，不复制命运正文 |

真值来源：拍板页 §5.7／题 1，复核页注记 3，`CHARACTER_LEDGER_CONTENT.md`。冲突时复核注记优先。

## 2. 字段表

| 字段 | 类型 | 规则 |
|---|---|---|
| `id` | str | `DESTINY-` 官方前缀＋十进制数字；L2 示例 `DESTINY-0001` 自本票起为正式形状 |
| `ch_ref` | str | 指向哪个人物，`CH-` ID |
| `destiny_text` | str | 命运正文，非空、去首尾空白 |
| `expected_at` | obj/null | 预计时机，三种锚之一，见 §3 |

另带规划账公共字段与 `confirm_status`＋`evidence_refs`（规则同 PLAN_VOLUME_CONTENT §2）。
`confirmed→retired` 后条目保留历史身份；取件码旧码仍可取旧版并标注（见 LEDGER_RECALL_CODE）。

## 3. 预计时机 `expected_at` 三种锚（题 1 已拍）

tagged union，`kind` 三选一；条目永远住账不动窝，写章取料带走的是引用：

1. `slot_anchor`：挂计划章槽 `{"kind":"slot_anchor","slot_ref":"S-0003"}`——写快写慢改槽位映射，条目不动窝；
2. `story_time_anchor`：挂故事内时间 `{"kind":"story_time_anchor","anchor":{"chapter_revision_ref":{…},"story_order":120}}`——锚坐标复用 L2 已冻的章 revision 三元组＋可选故事序；缺记录答 `NOT_RECORDED`，不可比答 `STORY_TIME_NOT_COMPARABLE`；禁止 `story_sequence`、禁止扁平 `text_sha256`；
3. `fuzzy_anchor`：只说「本卷内」「三卷内」`{"kind":"fuzzy_anchor","scope":"本卷内"}`——对账只提醒、不报警（`expected_at_alarm_policy` 恒答 `REMIND_ONLY`）。

配套语义（合同层声明，机器实现挂对账票）：写完由对账边标兑现／未兑现／改挂新落点；「先加两章铺垫再挂后面」＝插新槽＋改挂，必要时登记承接。

## 4. 与人物账的存在性闭环（复核注记 3，本票收口）

- 人物账 `destiny_ref` 非空时必须匹配 `^DESTINY-[0-9]+$`；
- 统一 writer／校验方提供命运目录时，`destiny_ref` 必须命中一个已登记的命运条目 `id`；
- L2 时代「只做形状校验」的开口自本票关闭，人物账合同、校验器与测试同票更新。

## 5. 真实示例

```json
{
  "contract": "PLAN_DESTINY_CONTENT",
  "version": "destiny-plan-content-v1",
  "id": "DESTINY-0001",
  "source_identity": "author_declared",
  "confirm_status": "confirmed",
  "evidence_refs": ["AUTHOR_ATTESTATION"],
  "created_at": "2026-08-22T10:00:00+08:00",
  "updated_at": "2026-08-22T10:00:00+08:00",
  "rev": 1,
  "note": "",
  "ch_ref": "CH-0001",
  "destiny_text": "他最终会为守住北城而死。",
  "expected_at": {"kind": "fuzzy_anchor", "scope": "三卷内"}
}
```

## 6. 明确禁止

1. 禁止另发明 `DY-` 等第二套命运前缀。
2. 禁止 `expected_at` 三种锚平铺混写或发明第四种 `kind`。
3. 禁止模糊锚触发报警（只提醒）。
4. 禁止在故事时间锚里使用 `story_sequence` 或扁平 `text_sha256`。
5. 禁止本票实现 planstore 写动作、对账推进或 M8 路由 runtime。
6. 禁止把命运条目写进 C4 冒充已发生事实。

## 7. 机器件与状态

- `PLAN_DESTINY_CONTENT.schema.json`
- `validate_plan_destiny_content.py`
- `PLAN_DESTINY_CONTENT.fixtures.jsonl`
- `tests/test_novel_mvp_plan_destiny_content_contract.py`

实现状态：`CONTRACT_ONLY__PLANSTORE_DESTINY_WRITE_PENDING`。


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/PLAN_INSPIRATION_CONTENT.md git_blob=12ad8c66d4264a8bf617012ce8860e2a3e033439 bytes=3430 -->

# 源文件：`novel-mvp/contracts/PLAN_INSPIRATION_CONTENT.md`

- Git blob：`12ad8c66d4264a8bf617012ce8860e2a3e033439`
- 字节：3430
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# PLAN_INSPIRATION_CONTENT · 灵感条目内容合同

**正式版本：`inspiration-plan-content-v1`**

一句话用途：一句话灵感不设格式门槛就能存进规划账（M8-N04），带 `placements[]` 多实例——一个灵感可以安放多处（ADD-030 第 5 条），到相关章出题或线收束前被点名提醒。

## 1. Owner、发／收模块与边界

| 角色 | 模块／对象 | 权限与边界 |
|---|---|---|
| 提出 | 作者、M8 候选 | 录入零门槛：任何非空一句话即可入账 |
| 唯一落盘 | planstore | 复用 `id_counters` 统一发号（`INS` 计数器）；本票不实现写动作 |
| 读取 | M8、长线读取面 | 只读已提交版本；存而不喂＋内化要作者签（M8-E06）不在本票 |

真值来源：拍板页 §5.7／题 1，R14 ADD-030（「实际兑现」第二轴：灵感 `placements[]` 多实例，书稿没写时可干净回滚）。冲突时复核注记优先。

## 2. 字段表

| 字段 | 类型 | 规则 |
|---|---|---|
| `id` | str | `INS-` 官方前缀＋十进制数字 |
| `content` | str | 灵感正文，非空即可，零格式门槛 |
| `placements` | list[obj] | 安放实例；空数组＝已收录未安放；子项 `{placement_ref, note}` |
| `expected_at` | obj/null | 预计时机三种锚，形状与 PLAN_DESTINY_CONTENT §3 完全一致 |

`placements[].placement_ref` 是稳定 ID（`S-`、`VOL-`、`CH-`、`H-` 等「前缀＋数字」形），同一条目内不得重复；`note` 说明这一处怎么用，可空串。另带规划账公共字段与 `confirm_status`＋`evidence_refs`（规则同 PLAN_VOLUME_CONTENT §2）。

## 3. 多实例与两层状态轴（ADD-030）

- 一个灵感安放三处＝`placements[]` 三个子项，条目本身只有一条、住账不动窝；
- 安放只是规划层安排，「实际兑现」另有一层，只能由对账边或作者签字推进——本合同不设 `paid`／`digested` 之类的兑现字段，防止把安排冒充发生；
- 书稿没写时撤掉一个 placement 即干净回滚，不影响其余安放。

## 4. 真实示例

```json
{
  "contract": "PLAN_INSPIRATION_CONTENT",
  "version": "inspiration-plan-content-v1",
  "id": "INS-0001",
  "source_identity": "author_declared",
  "confirm_status": "confirmed",
  "evidence_refs": ["AUTHOR_ATTESTATION"],
  "created_at": "2026-08-22T10:00:00+08:00",
  "updated_at": "2026-08-22T10:00:00+08:00",
  "rev": 1,
  "note": "",
  "content": "结尾让守门老人再出现一次。",
  "placements": [
    {"placement_ref": "S-0001", "note": "开篇埋一句"},
    {"placement_ref": "VOL-0002", "note": "卷中回收"},
    {"placement_ref": "CH-0002", "note": "挂到配角线"}
  ],
  "expected_at": {"kind": "fuzzy_anchor", "scope": "三卷内"}
}
```

## 5. 明确禁止

1. 禁止给 `content` 加格式门槛（模板、字段、最小长度都不许）。
2. 禁止「一个灵感只能挂一个落点」；`placements[]` 天然多实例。
3. 禁止同一条目内重复 `placement_ref`。
4. 禁止设置兑现／消化字段冒充实际发生。
5. 禁止本票实现提醒时机 runtime、M8 喂料或内化签字流程。

## 6. 机器件与状态

- `PLAN_INSPIRATION_CONTENT.schema.json`
- `validate_plan_inspiration_content.py`
- `PLAN_INSPIRATION_CONTENT.fixtures.jsonl`
- `tests/test_novel_mvp_plan_inspiration_content_contract.py`

实现状态：`CONTRACT_ONLY__PLANSTORE_INSPIRATION_WRITE_PENDING`。


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/C1_CHAPTER_DOC.md git_blob=5ae20dc1882e1e8b7cc1e06ff7e0fdf94e6be69e bytes=4774 -->

# 源文件：`novel-mvp/contracts/C1_CHAPTER_DOC.md`

- Git blob：`5ae20dc1882e1e8b7cc1e06ff7e0fdf94e6be69e`
- 字节：4774
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# C1 · 章节文档（CHAPTER_DOC）

**版本：v1**（正式增加 stable chapter revision 引用；v0-r01 保留为迁移前旧读法）

读法：v1 只表示章节书稿，是 [C11_CHAPTER_REVISION_LEDGER.md](C11_CHAPTER_REVISION_LEDGER.md) current revision 的物化视图。`chapters.json` 不保存第二份 revision history；大纲继续留在材料架／规划侧。现役产品仍输出 v0-r01，必须经过正式迁移后才可声称写出 v1。

一句话用途：给 M2 与 current chapter 消费者提供某个 stable chapter 的当前标题和逐字正文。

| 方向 | 模块 |
|---|---|
| 发 | 首次合法 M1 接收或章节 revision commit 协调器；写作区工作稿只在作者显式 handover 后进入接收边界 |
| 收 | M4 事实账（落盘 `data/<项目>/chapters.json`）；M2 切窗器（只吃 `text`）；M0 展示（status） |

## 字段表

| 字段 | 类型 | 含义 | 必填 |
|---|---|---|---|
| contract | str | 固定 `C1_CHAPTER_DOC` | 是 |
| version | str | 固定 `v1` | 是 |
| id | str | stable chapter id，`c01` 格式；正文修订时保持不变 | 是 |
| title | str | 章节标题（导入时指定，默认取文件名） | 是 |
| kind | str | 固定 `draft`；Outline 不进入 v1 C1 | 是 |
| text | str | 原文全文，原样保存、未清洗 | 是 |
| added_at | str | 导入时间，`YYYY-MM-DD HH:MM:SS` 本地时间 | 是 |
| chapter_revision_ref | obj | `{chapter_id, revision_no, revision_text_sha256}`；必须等于 C11 current revision | 是 |

章节顺序仍由 `chapters.json` 数组顺序表达。修订只替换同一 id 的 current 视图，不新增第二条 current chapter，也不改变数组位置。

## v1 形状示例

```json
{
  "contract": "C1_CHAPTER_DOC",
  "version": "v1",
  "id": "c01",
  "title": "第一章 雨夜",
  "kind": "draft",
  "text": "沈砚放下铜钥匙。",
  "added_at": "2026-08-18 04:30:00",
  "chapter_revision_ref": {
    "chapter_id": "c01",
    "revision_no": 2,
    "revision_text_sha256": "0aeb78621f82e724f19a56e01f2dc9bfcdec630b1748e2fb2c78edb0b0e47cfc"
  }
}
```

## v0-r01 真实示例（legacy）

取自 `data/万鬼伏藏/chapters.json` 第 1 条（`text` 截断展示，实际 3928 字）：

```json
{
  "id": "c01",
  "title": "第1章 李星燃",
  "kind": "draft",
  "text": "“你叫李星燃对吧，说说看吧，你都有什么症状。”\n　　市医院精神科的陈医生，四十岁出头，戴着眼镜，穿着干净整洁的白大褂，脸…",
  "added_at": "2026-08-13 00:53:41"
}
```

## 附：导入损失报告（M1 返回值，v0 最小版，不落盘）

`ingest.ingest_files(...)` 每批导入返回一份：

| 字段 | 类型 | 含义 |
|---|---|---|
| count | int | 本次导入章数 |
| total_chars | int | 本次导入总字数 |
| warnings | list[str] | 空章警告（正文全空白时一条） |
| chapters | list | 本次导入的 C1 章节文档 |

## 写作区工作稿的接收边界（v0-r01）

[WRITING_DESK_WORK_DRAFT.md](WRITING_DESK_WORK_DRAFT.md) 中的工作稿不是 C1。自动保存、修改、检测、收工或文件存在，都不能创建章节书稿。

只有作者显式发出 [WORK_DRAFT_HANDOVER_ACTION.md](WORK_DRAFT_HANDOVER_ACTION.md)，且动作仍指向 current work revision 时，C1 接收端才可以：

1. 用 `work_ref + work_rev` 从写作区工作稿 owner 取得作者原文；
2. 复核动作中的 `slot_ref`、`source_outline_ref` 与 current 工作稿一致；
3. 只接受 `WORK_DRAFT_HANDOVER_ACTION v2` 中作者明确确认的 `chapter_title`，不用文件名或 `slot.title_hint` 猜标题；
4. 首次入库经 C11 建 r1，标题从此由 C11 current revision 长期持有，再生成带 `chapter_revision_ref` 的 C1 v1 current view；
5. 原文逐字进入 `text`，不得由接收端润色、补写或改标点；
6. 成功返回合法 C1 `chapter_id` 与 current revision ref，供后续 planstore 交棒使用。

动作处于 `AWAITING_C1_ACCEPTANCE`、C1 校验失败或章节身份尚未产生时，planstore 不得先写 `handover_parts`。这段只增加接收顺序，不给 C1 增加 planstore、facts、actual、对账或关章权力，也不改变上面的 v0 字段表。

## Backward compatibility

- v0-r01 `id/title/kind/text/added_at` 可以迁移为 C11 r1；正文 bytes 不得改变。
- 旧只读展示可以在明确声明 legacy-display-only 时读取 v1 `title/text`；抽取、重导、问答、事实确认和 stale 判断必须升级后才可消费。
- 未知版本、缺 `chapter_revision_ref`、ref 与 `id/text` 不一致时 fail closed。
- Outline 不迁。

## 仍未解决

- 无来源文件名、无清洗损失明细；章序校验、缺章检测、水印剥离未做（台账 I-001／I-002／I-003／I-006）。


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/C2_SEGMENT.md git_blob=c193ad57afaf6badee80e28ba49ac4420852266b bytes=2733 -->

# 源文件：`novel-mvp/contracts/C2_SEGMENT.md`

- Git blob：`c193ad57afaf6badee80e28ba49ac4420852266b`
- 字节：2733
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# C2 · 责任段（SEGMENT）

**版本：v1**（增加输入章节 revision 身份；v0 作为迁移前内存态）

一句话用途：从一份明确的 C1 current revision 切出责任段＋左右只读背景，是一次模型调用的输入单位。内存态合同，不落盘。

| 方向 | 模块 |
|---|---|
| 发 | M2 切窗器（[segment.py](../mvp/segment.py) 的 `segment_chapter`） |
| 收 | M3 抽取器（[extract.py](../mvp/extract.py) 的 `build_user_content`／`extract_segment`） |

## 字段表

| 字段 | 类型 | 含义 | 必填 |
|---|---|---|---|
| contract | str | 固定 `C2_SEGMENT` | 是 |
| version | str | 固定 `v1` | 是 |
| chapter_revision_ref | obj | 必须逐字段复制输入 C1 v1 的 current revision ref | 是 |
| seg | int | 段序号，本章内从 1 起 | 是 |
| text | str | 责任段正文（若干完整自然段，用 `\n` 连接） | 是 |
| start | int | 段起点字符偏移（见下「偏移基准」） | 是 |
| end | int | 段终点字符偏移（`start + len(text)`） | 是 |
| halo_before | str | 前文只读背景，最多 `halo_chars` 字；开篇段为空串 | 是（可空串） |
| halo_after | str | 后文只读背景，最多 `halo_chars` 字；末段为空串 | 是（可空串） |

⚠️ 偏移基准：`start`／`end` 相对「规范化拼接文本」——各自然段去首尾空白后用单个 `\n` 连接——**不是**原始文件里的偏移。

因此 C2 `start/end` 只服务本次切窗，不能保存成 C11 章节证据 anchor。正式 anchor 一律回到 revision 逐字正文并使用 `CHAPTER_REVISION_TEXT_UNICODE_CODEPOINT_0_BASED_HALF_OPEN`。

切窗参数在 [config.json](../config.json)：`seg_min_chars` 620／`seg_max_chars` 923／`halo_chars` 180（研究仓 T5_R04 守擂冠军配方），由调用方（M0）读配置传入。

## 真实示例

《万鬼伏藏》c01 切出 4 段，这是第 2 段（长字段截断展示，实际 `text` 948 字、halo 各 180 字）：

```json
{
  "contract": "C2_SEGMENT",
  "version": "v1",
  "chapter_revision_ref": {
    "chapter_id": "c01",
    "revision_no": 2,
    "revision_text_sha256": "0aeb78621f82e724f19a56e01f2dc9bfcdec630b1748e2fb2c78edb0b0e47cfc"
  },
  "seg": 2,
  "text": "听着李星燃的描述，陈医生开始在问诊单上写下：患者意识清，仪态整齐，接触尚可，被动合作。思维连贯，语速…",
  "start": 941,
  "end": 1889,
  "halo_before": "…然后找她家要了十斤大米，这才把她的魂魄给超度。”\n",
  "halo_after": "\n他被吓得双腿发软，真从医院高楼跌落惨死。\n…"
}
```

v0 reader 遇到 v1 不得剥掉 revision ref 后继续抽取；产品完成 revision-aware 升级前必须 fail closed。


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/C3_FACT_CANDIDATE.md git_blob=a7a6c1080f5050c7a193e33eda3e74c889bf9a9d bytes=2303 -->

# 源文件：`novel-mvp/contracts/C3_FACT_CANDIDATE.md`

- Git blob：`a7a6c1080f5050c7a193e33eda3e74c889bf9a9d`
- 字节：2303
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# C3 · 事实候选（FACT_CANDIDATE）

**版本：v1**（增加来源章节 revision 身份；quote 仍只是未核定位线索）

一句话用途：抽取器（或外部 JSON 文件）产出的候选事实句，投给事实账之前的传输形态；入账后由 M4 补齐记录字段变成 C4。

| 方向 | 模块 |
|---|---|
| 发 | M3 抽取器（[extract.py](../mvp/extract.py) 的 `extract_segment`；备用入口 `load_candidates_file`） |
| 收 | M4 事实账（[store.py](../mvp/store.py) 的 `add_fact_candidates`） |

## 字段表（传输条目，`items` 数组里的一条）

| 字段 | 类型 | 含义 | 必填 |
|---|---|---|---|
| contract | str | 固定 `C3_FACT_CANDIDATE` | 是 |
| version | str | 固定 `v1` | 是 |
| chapter_revision_ref | obj | 必须等于产生本候选的 C2/C1 revision ref | 是 |
| text | str | 事实句，独立完整、主语明确 | 是（空白条目入账时被丢弃） |
| quote | str | 责任段内的原文依据片段（模型转抄，未做一致性校验） | 否（可空串） |
| seg | int | 来源责任段序号（对应 C2 的 `seg`） | 否（extract 路径必带；外部候选文件通常没有） |

批次级参数（不在条目里，随调用传）：

| 参数 | 类型 | 含义 |
|---|---|---|
| chapter_id | str | 兼容调用参数；必须等于每条 `chapter_revision_ref.chapter_id` |
| source | str | 候选来源：模型 ID（extract 路径）或候选文件名（candidates 路径），入库时打在每条上 |

## 真实示例

《万鬼伏藏》c01 第 1 段抽出的一条（入账后成为 f001）：

```json
{
  "contract": "C3_FACT_CANDIDATE",
  "version": "v1",
  "chapter_revision_ref": {
    "chapter_id": "c01",
    "revision_no": 2,
    "revision_text_sha256": "0aeb78621f82e724f19a56e01f2dc9bfcdec630b1748e2fb2c78edb0b0e47cfc"
  },
  "text": "市医院精神科的陈医生询问李星燃有什么症状。",
  "quote": "“你叫李星燃对吧，说说看吧，你都有什么症状。”",
  "seg": 1
}
```

外部候选文件进入 v1 时也必须携带 revision ref 与 seg；旧 v0 无 revision 的候选只能走显式 legacy migration，不能直接进入 C4 v1。

## 仍未解决

- 无置信分（I-008 置信分层依赖它）；无字符级坐标，证据定位只能到段粒度。


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/C4_FACT_QUERY.md git_blob=15d0869894ad61854e357ff60fff792ee53b7614 bytes=6256 -->

# 源文件：`novel-mvp/contracts/C4_FACT_QUERY.md`

- Git blob：`15d0869894ad61854e357ff60fff792ee53b7614`
- 字节：6256
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# C4 · 事实查询（FACT_QUERY）

**版本：v1**（增加 chapter revision、正式 anchor 与 needs-recheck；v0-r02 保留为迁移前运行时）

读法：`status` 只表示事实候选的审查处置，不表示计划是否发生、对账结果、收工或关章。`confirmed` 只有在 current chapter revision 上仍有合法证据时才属于 current truth；`needs_recheck` 已退出当前真值消费。普通 `quote` 仍只是模型转抄，不能冒充 VERIFIED anchor。

一句话用途：事实账里一条事实的完整形态——候选、已确认、已拒绝都长这样；下游全部只读，确认／驳回／改判只走 M5 作者动作和 M4 事务 writer。

| 方向 | 模块 |
|---|---|
| 发 | M4 事实账（[store.py](../mvp/store.py) 的 `facts(project)` 返回全量列表；落盘 `data/<项目>/facts.json`） |
| 收 | M6 取证问答（[ask.py](../mvp/ask.py)）；M0 展示（status／confirm）；下一单 M7 一致性体检，以及未来 M8／M9 |

## 字段表

| 字段 | 类型 | 含义 | 必填 |
|---|---|---|---|
| contract | str | 固定 `C4_FACT_QUERY` | 是 |
| version | str | 固定 `v1` | 是 |
| id | str | 事实号，`f001` 格式，入账时按账内顺序分配 | 是 |
| chapter_id | str | 来源章节（C1 的 `id`） | 是 |
| text | str | 事实句（确认时可被作者改写，原候选句备档进 `note`） | 是 |
| quote | str | 原文依据片段（模型转抄，未做一致性校验） | 是（可空串） |
| status | str | `extracted`／`confirmed`／`rejected`／`needs_recheck`；最后一项不属于 current truth | 是 |
| source | str | 候选来源：模型 ID 或候选文件名 | 是 |
| note | str | 备注；改写确认时存「原文候选：…」 | 是（可空串） |
| added_at | str | 入账时间 | 是 |
| seg | int | 来源责任段序号（对应 C2） | 否（外部载入的候选没有） |
| decided_at | str | 最近一次确认／拒绝时间 | 否（没审过就没有） |
| chapter_revision_ref | obj | `{chapter_id, revision_no, revision_text_sha256}`；必须与本事实证据版本一致 | 是 |
| anchor_ref | obj/null | VERIFIED 时为 C11 revision anchor；legacy 未核时为 null | 是 |
| anchor_state | enum | `VERIFIED`／`LEGACY_UNVERIFIED` | 是 |
| recheck | obj/null | needs_recheck 时记录 previous status、原因、from/target revision、时间 | 是 |

`recheck.reason` 只允许：`evidence_gone`、`anchor_ambiguous`、`legacy_anchor_unverified`。

语义规则：**只有 current revision 上仍可回验的 `confirmed` 是当前真值**。M6／M8／M11 只读这些记录；M7 不把 needs_recheck 当 confirmed 或普通 candidate 扫描。普通上游只能投 `extracted` 候选，作者审查仍走 M5；程序不得把 needs_recheck 自动改回 confirmed。

章节 revision 提交前，事务协调器必须对本章全部事实预计算 anchor effects。verified slice 在新版唯一命中时，保持 status 并把 ref/anchor 前进；0 次、多次或 legacy 无法双边唯一验证时转 needs_recheck。facts effects、C11 current、C1 view 与受影响 RE stale 必须同事务提交，任何一边失败都恢复 all-before。

普通 M5 确认、驳回、改判与“改写后采纳”统一使用 [FACT_REVIEW_ACTION.md](FACT_REVIEW_ACTION.md)。旧 `cli.py confirm`、`store.set_status` 和 `store.edit_fact_text` 只保留兼容调用面，不能再直接替换 `facts.json`。底层由 [factstore.py](../mvp/factstore.py) 复用 planstore 的文件锁、prepare／commit、恢复底稿与 operation ID；“改写后采纳”必须是一个事务，不能留下“文本已改、状态未确认”的半状态。

若 current RE 正在引用被改判或改写的事实，事务必须同时把旧 RE 转为 stale，使旧 actual support 当场失效。以后把事实重新改回 confirmed 也不会复活旧边；恢复支持必须重新对账。该规则不增加新的 C4 状态，也不把计划或模型意见变成事实。

已交棒 C1 的计划—书稿对账可以使用 [RECONCILIATION_FACT_ADMISSION_ACTION.md](RECONCILIATION_FACT_ADMISSION_ACTION.md) 走同一份 M4／M5 权限：模型仍只交 C3 与六态观察，作者逐条确认后，提交协调器才可以在同一事务把候选按现有 C4 字段写成 `confirmed`，并把内部 f 引用接回 planstore RE。这个事务路径不增加第二种事实状态、不允许模型指定 f／F-，也不允许 PE 因已安排而生成事实。

该路径在 v2 action 中还必须绑定 current `chapter_revision_ref`。`quote` 逐字存在且唯一命中后，confirmed C4 v1 同时生成 VERIFIED anchor；C1 SHA、revision ref、RE rev、planned rev 任一不 current 时 facts 与 planstore 都保持 0 变化。

M6 回答时会在记录上附加 `chapter_title`（章节标题，内存态补充，不落盘、不属于本合同字段）。

## 真实示例

`data/万鬼伏藏/facts.json` 的 f001（已确认，带全部可选字段）：

```json
{
  "id": "f001",
  "chapter_id": "c01",
  "text": "市医院精神科的陈医生询问李星燃有什么症状。",
  "quote": "“你叫李星燃对吧，说说看吧，你都有什么症状。”",
  "status": "confirmed",
  "source": "doubao-seed-2-1-turbo-260628",
  "note": "",
  "added_at": "2026-08-13 00:55:19",
  "seg": 1,
  "decided_at": "2026-08-13 00:55:31"
}
```

## Backward compatibility

- v0-r02 迁移到 v1 时，能唯一回验的 quote 生成 VERIFIED anchor；不能回验的历史记录可以暂存 `LEGACY_UNVERIFIED`。
- legacy confirmed 不因迁移本身自动撤销；但所属章节第一次 revision 时必须双边唯一验证，否则转 needs_recheck。
- 旧 C4 reader 遇到 v1 必须 fail closed，不能只看 `status=confirmed` 就继续问答、规划或体检。
- 现役 `FACT_REVIEW_ACTION v1` 与统一 fact writer 仍是 v0-r02 产品面；revision-aware 产品迁移另开施工票，本票不修改产品代码。

## 仍未解决

- 证据坐标粒度只有 `chapter_id`＋`seg`，无字符级锚点；`quote` 与原文的一致性未校验（M7 做矛盾定位时会先撞到这两条）。
- schema v0 整体是临时件，等研究仓 N16 语义合同定案后重建（见 [store.py](../mvp/store.py) 头注）。


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/C6_HEALTH_REPORT.md git_blob=d5f3d3d3d3bb25893c15ed0e5c1f8f53ed1005f6 bytes=9025 -->

# 源文件：`novel-mvp/contracts/C6_HEALTH_REPORT.md`

- Git blob：`d5f3d3d3d3bb25893c15ed0e5c1f8f53ed1005f6`
- 字节：9025
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# C6 · 体检报告（HEALTH_REPORT）

**版本：v1**（增加来源 chapter revision 水位与 stale 身份；v0 报告作为 legacy）

读法：C6 是可覆盖投影，不是真值。v1 保存生成时消费的 chapter revision refs；读取时与 C11 current 比较，旧版报告派生 `STALE`，不得自动清灯、自动重跑或写回事实。`evidence.quote` 仍只是定位线索，只有带 VERIFIED C11 anchor 才是已核证据。

一句话用途：一致性体检的完整产出——矛盾、存疑、别名提示、账本完整性四本账分开记，每条都带涉事事实号和双方证据。它是事实账的投影快照：重跑覆盖、会过期作废，确认后的事实改动仍回审查台，绝不回写 facts.json。

| 方向 | 模块 |
|---|---|
| 发 | M7 一致性体检（[check.py](../mvp/check.py) 的 `run_check`；`save_report` 落盘 `data/<项目>/health_report.json`） |
| 收 | M0 展示（`cli.py check` 人读打印）；未来 M5 审查台的风险收件箱 |

## 顶层结构

| 字段 | 类型 | 含义 | 必填 |
|---|---|---|---|
| contract | str | 固定 `C6_HEALTH_REPORT` | 是 |
| version | str | 固定 `v1` | 是 |
| project / generated_at / model | str | 哪本书、何时体检、用什么模型 | 是 |
| chapter_revision_refs | list[obj] | 本报告实际消费的 chapter revisions，去重保存 | 是 |
| source_revision_state | enum | `CURRENT`／`STALE`／`LEGACY_REVISION_UNKNOWN`；由读取端与 C11 派生 | 是 |
| scan | obj | 扫描台账：扫了多少、分几组、花多少调用（字段见下） | 是 |
| conflicts | list | **矛盾账**：模型判「确实打架」的问题 | 是（可空） |
| insufficient | list | **存疑账**：可能矛盾但材料不足判不死的，**不算矛盾** | 是（可空） |
| alias_hints | list | **别名提示**：疑似同一实体，只提示不合并、不算矛盾 | 是（可空） |
| integrity | obj | **账本完整性**：事实账自身的数据事故（如重复事实号），不是小说矛盾 | 是 |
| summary | obj | 汇总计数：红/黄、按层、按类、各账条数 | 是 |

`scan` 里：`facts_total/confirmed/extracted` 实扫多少（rejected 不扫，条数记在 `rejected_excluded`；重复号副本记在 `duplicate_dropped`）；`api_calls/failed_calls/clean_groups/total_tokens/seconds` 花销与通过态；`groups` 每组一条（名字、类型 entity/timeline/leftover、条数、ok/failed/skipped_budget、发现数）。

## 矛盾条目（conflicts 一条；insufficient 同构，只是没有 severity）

| 字段 | 类型 | 含义 | 必填 |
|---|---|---|---|
| issue_id | str | 矛盾 `h001`、存疑 `n001`，本报告内唯一 | 是 |
| kind | str | `naming` 人名/称谓｜`timeline` 时间线｜`setting` 设定｜`event` 事项互斥 | 是 |
| severity | str | **灯，只管严重度**：`red` 硬矛盾（同一事项被无解释推翻/明说的设定被违反）；`yellow` 疑似或低置信。时间线 v0 封顶黄灯（无双序概念，倒叙全会误判） | 是（仅 conflicts） |
| layer | str | 按涉事事实状态分层：`confirmed` 全真值打架｜`mixed` 候选顶撞真值｜`candidate` 候选互撞。**真值矛盾 ≠ 候选矛盾** | 是 |
| fact_ids | list | 涉事事实号（C4 的 `id`，项目内唯一；不用 seg 当键） | 是 |
| note | str | 为何亮灯（模型一句话说明） | 是 |
| next_step | str | 下一步去哪（按 layer/verdict 生成的固定话术） | 是 |
| evidence | list | 双方证据；v1 追加 `chapter_revision_ref`，VERIFIED 时可追加 `anchor_ref` | 是 |
| found_by | list | 哪些扫描组发现的（合并去重后可能多个） | 是 |
| confidence / hard | str / bool | 模型自评（置信、是否铁矛盾），程序据此定灯，仅供追溯 | 是 |

灯（severity）、说明（note）、证据（evidence）、去向（next_step）是四个独立字段——灯只管红黄，为何亮、凭什么、怎么办各管各的。

## v0 真实示例（legacy）

取自 `data/万鬼伏藏/health_report.json`（2026-08-13 实跑；顶层其余字段略）：

```json
{
 "contract": "C6_HEALTH_REPORT v0",
 "project": "万鬼伏藏",
 "generated_at": "2026-08-13 03:02:11",
 "model": "doubao-seed-2-1-turbo-260628",
 "scan": {
  "facts_total": 223, "confirmed": 4, "extracted": 219,
  "rejected_excluded": 1, "duplicate_dropped": 0,
  "api_calls": 9, "failed_calls": 0, "clean_groups": 6,
  "total_tokens": 23674, "seconds": 113.0,
  "groups": [
   {"name": "李星燃·块1", "kind": "entity", "facts": 110, "status": "ok", "findings": 4}
  ]
 },
 "conflicts": [
  {
   "issue_id": "h003",
   "kind": "timeline",
   "severity": "yellow",
   "layer": "candidate",
   "fact_ids": ["f077", "f080"],
   "note": "f077称李星燃是天雷落下后穿越到这个世界，f080却称他来到这个世界已经一个月，时间线存在冲突。",
   "next_step": "双方都还是候选：先在审查台（confirm）核对真伪；都被确认时才升级为真值矛盾",
   "evidence": [
    {"fact_id": "f077", "chapter_id": "c01", "seg": 3, "status": "extracted",
     "text": "李星燃并非这个世界的人，那道天雷落下后，他穿越到了这个和自己同名同姓的倒霉蛋身上。",
     "quote": "他并非这个世界的人，那道天雷落下后，他穿越到了这个和自己同名同姓的倒霉蛋身上。"},
    {"fact_id": "f080", "chapter_id": "c01", "seg": 4, "status": "extracted",
     "text": "李星燃来到这个世界一个月，炼制了一根七星锁魂绳，画了一些符咒，前往驱鬼赚钱。",
     "quote": "李星燃来到这个世界也就一个月时间，只能是炼制了一根七星锁魂绳，画了一些符咒，前往驱鬼，先赚一笔钱。"}
   ],
   "found_by": ["李星燃·块1"],
   "confidence": "high",
   "hard": true
  }
 ],
 "summary": {
  "red": 2, "yellow": 1,
  "by_layer": {"confirmed": 0, "mixed": 1, "candidate": 2},
  "by_kind": {"naming": 1, "timeline": 1, "setting": 0, "event": 1},
  "insufficient": 2, "alias_hints": 0, "duplicate_ids": 0
 }
}
```

别名提示条目（`alias_hints` 一条；机械挖掘，字段值取自《1979西北往事》实测）：

```json
{
 "hint_id": "a001",
 "names": ["周卫军", "周新军"],
 "fact_ids_a": ["f002", "f003", "f004"],
 "fact_ids_b": ["f024", "f032", "f036"],
 "note": "写法只差一字，疑似同一实体；程序不自动合并、不算矛盾，请作者认"
}
```

完整性条目（`integrity.duplicate_ids` 一条；取自《三国》实跑，该账本有 50 个重复号）：

```json
{
 "problem": "duplicate_id",
 "id": "f274",
 "kept": {"chapter_id": "c03", "seg": 2, "text": "桃林庄到了。"},
 "dropped": [{"chapter_id": "c01", "seg": 1, "text": "刘瑁醒来时鼻子里全是药味，药味苦、潮，还带着一点发霉的木头味。"}]
}
```

`integrity` 还带一次性的 `note` 和 `next_step`（修账后重跑体检才算数）。

## 语义规则

1. **材料不足 ≠ 内容矛盾**：判不死的进 `insufficient`，永远不混进 `conflicts`；矛盾账已覆盖的问题不在存疑账里复读。
2. **别名不自动合并**：同名/疑似同人只进 `alias_hints`，由作者认；模型判出的「同一人写法冲突」才进矛盾账。
3. **数据事故不冒充剧情矛盾**：账本自身违约（重复事实号）由完整性预检机械拦下，坏号只认首次出现，副本不喂模型。
4. **只读投影**：本报告不改任何事实状态；`next_step` 都指回审查台或原文，不提供「就地修复」。
5. 证据定位只有 `chapter_id`＋`seg` 段级坐标；`quote` 是抽取时模型转抄、未回填校验（I-013），**不保证能在原文精确 find 到**。
6. v1 报告的任一 `chapter_revision_ref` 落后于 C11 current 时，整份报告的 `source_revision_state` 派生为 STALE；投影可以继续展示历史，但不能为高影响写操作提供依据。
7. 旧 v0 报告没有 revision ref，迁移时统一标 `LEGACY_REVISION_UNKNOWN`，重跑后才能成为 CURRENT。

## Backward compatibility

- v0 顶层组合字符串 `C6_HEALTH_REPORT v0` 不冒充 v1；旧 reader 遇到 v1 必须 fail closed。
- v1 不修改 conflicts／insufficient／alias／integrity 的故事语义，只增加来源版本水位。
- 产品 `check.py` 尚未施工 v1；本票只冻结正式合同。

## 仍未解决

- 无双序（故事顺序 vs 叙述顺序）：倒叙/回忆会触发时间线误报，故 v0 时间线封顶黄灯。
- 无豁免机制：作者「已阅，故意的」无处落笔，重跑会原样再报（零唠叨只管单次报告内去重）。
- 分组扫描有盲区：两条事实若不共享任何挖掘出的实体、又分属不同兜底块，就没机会同屏比对；设定类矛盾没有设定集材料架（M1 v1）对照，只能靠事实句互证。
- 模型自评 hard/confidence 运行间会漂移（同输入两跑，同一对事实在 conflict 和 insufficient 间翻转过一次）。


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/C7_PLOT_LAYER.md git_blob=5064f613608dbcdd80c03ba7c216a8e6df8af675 bytes=6477 -->

# 源文件：`novel-mvp/contracts/C7_PLOT_LAYER.md`

- Git blob：`5064f613608dbcdd80c03ba7c216a8e6df8af675`
- 字节：6477
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# C7 · 剧情层（PLOT_LAYER）

**版本：v1**（M8 单次出题快照；v0 只少本版新增的三个稳定引用）

一句话用途：作者给一句「我要达成的目的」，系统吐出**计划**——卡片选项、卡上目的注解、写作指导三层、跟已确认事实打架的冲突。这是计划，不是事实；不回写 `facts.json`。

| 方向 | 模块 |
|---|---|
| 发 | M8 续写规划；现有 [plan.py](../mvp/plan.py) 仍是未升级的 v0 试跑代码，不属于本轮施工 |
| 收 | M0 展示、选择／停点动作层；未来 M9／M10／网页画布（本切片不接线） |

语义规则（ADD-037／A9、ADD-036／G5）：

- 目的挂到卡上（附着或单独开卡），人加的注解影响选项，**不改底层事实账**。
- 跟已确认事实或本章原意图打架时，冲突必须爆出来，问改哪边。
- 反向模式先生成「前面得先达成什么」的前置卡。
- 写作指导是出题副产品，不另开 API。三层＝卡片要解决什么／对白透露什么／插件写法（没有插件就空串）。
- J1：给要求给信息点，**不给示范成文**。
- C7 是可覆盖、可过期的只读快照。它没有规划账、事实账或 actual 写权，也不是完整章计划。

## 顶层结构

| 字段 | 类型 | 含义 | 必填 |
|---|---|---|---|
| contract | str | 固定 `"C7_PLOT_LAYER v1"` | 是 |
| project / generated_at / model | str | 哪本书、何时出题、用什么模型（`--stub` 时为 `stub`） | 是 |
| purpose | str | 作者要达成的目的 | 是 |
| purpose_note | str | 卡上注解／额外限制（可空） | 是 |
| mode | str | `forward` 正向出题／`reverse` 先拆前置卡 | 是 |
| purpose_placement | str | `standalone` 单独开卡／`attach` 附着在剧情卡上（有注解时） | 是 |
| chapter_intent | str | 本章原意图（可空）；用来对拍冲突 | 是 |
| confirmed_fact_ids | list | 本次吃进的已确认事实号 | 是 |
| cards | list | 出题卡（含前置卡） | 是 |
| conflicts | list | 跟真值或本章原意图打架的条目；可空，但字段必须在 | 是 |

## 卡片（cards 一条）

| 字段 | 类型 | 含义 | 必填 |
|---|---|---|---|
| id | str | 本份产出内唯一，如 `card01` | 是 |
| role | str | `purpose` 目的卡／`prerequisite` 前置卡／`attach` 附着卡 | 是 |
| title | str | 卡标题（人话） | 是 |
| purpose_note | str | 本卡要达成的效果／作者注解 | 是 |
| options | list | 至少 1 条；每条 `{id, label, reveal_intent}` | 是 |
| recommended_option_ref | str | 主推荐的稳定引用 | 是；必须指向本卡一个真实 `options[].id` |
| planning_card_ref | str | 这道题所属的稳定主架卡／规划对象引用 | 是；正式 AC 号或完整沙箱卡引用 |
| planning_card_rev | int | 出题时看到的规划对象修订号 | 是；从 1 起，写前必须仍与当前对象一致 |
| guidance | obj | 写作指导三层，见下 | 是 |

`options[].id`：`A`／`B`／`C`。`label`＝选项方向（不是成文）。`reveal_intent`＝对白该透露的信息点。

`recommended_option_ref` 只保存选项 ID，不复制选项正文。选项重排后，推荐对象身份不能变化；引用不存在时必须拒绝，不能退回 `options[0]`。

`planning_card_ref` 优先引用已有稳定 AC 号；沙箱期使用章工作台规定的完整引用，例如 `SB-0001#d-ac-1`。C7 的局部 `cards[].id` 只用于在本快照内找卡，不得进入长期规划账。`planning_card_ref` 不存在、不可选择，或 `planning_card_rev` 已过期时，选择动作必须在 planstore 写入前停止。

`guidance`：

| 字段 | 含义 |
|---|---|
| card_problem | 这张卡要解决什么 |
| dialogue_reveal | 对白该透露什么 |
| plugin_craft | 插件自带写法；没有插件就 `""` |

## 冲突（conflicts 一条）

| 字段 | 类型 | 含义 | 必填 |
|---|---|---|---|
| kind | str | `fact` 顶撞已确认事实／`intent` 顶撞本章原意图 | 是 |
| fact_id | str | 涉事事实号；`intent` 类可空串 | 是 |
| fact_text | str | 涉事事实句或原意图原文 | 是 |
| why | str | 为什么打架 | 是 |
| ask | str | 固定问法：改目的，还是改已确认事实／本章原意图？ | 是 |

## 真实示例（stub 形状）

```json
{
  "contract": "C7_PLOT_LAYER v1",
  "project": "_m8_v0_selftest",
  "generated_at": "2026-08-13 19:00:00",
  "model": "stub",
  "purpose": "让陈平在这一章活着走出来，并告诉九棺真相",
  "purpose_note": "",
  "mode": "reverse",
  "purpose_placement": "standalone",
  "chapter_intent": "继续瞒住棺中有人",
  "confirmed_fact_ids": ["f001", "f002"],
  "cards": [
    {
      "id": "card01",
      "role": "prerequisite",
      "title": "前置：让关键人物处于能被改变的状态",
      "purpose_note": "后面那张目的卡要成立，这里必须先成立",
      "options": [
        {"id": "A", "label": "先把「已死」从公开认知里拆开一条缝", "reveal_intent": "只透露有人在查，不透露结论"},
        {"id": "B", "label": "先安排一次无法用「已死」解释的现场痕迹", "reveal_intent": "痕迹本身，不解释来源"},
        {"id": "C", "label": "先让知情者自己动摇", "reveal_intent": "动摇，不给新设定"}
      ],
      "recommended_option_ref": "B",
      "planning_card_ref": "SB-0001#d-ac-1",
      "planning_card_rev": 1,
      "guidance": {
        "card_problem": "后面要让人活着出现，先处理「已经死了」这笔账",
        "dialogue_reveal": "只能透露「这件事没结」",
        "plugin_craft": ""
      }
    }
  ],
  "conflicts": [
    {
      "kind": "fact",
      "fact_id": "f001",
      "fact_text": "陈平已经死了，埋在后山。",
      "why": "已确认事实写「死」，目的要「活着走出来」",
      "ask": "改目的，还是改已确认事实？"
    }
  ]
}
```

## 接缝边界与未施工部分

- C7 自己不改账、不重出变更清单。选定、整组驳回或自动放行必须另走 [C7_SELECTION_ACTION.md](C7_SELECTION_ACTION.md)，再由 planstore 校验和落盘。
- C7 不落规划账 `plan.json`；现有 v0 试跑代码仍只覆盖写 `plan_latest.json`，正式 v1 发送端与 planstore 尚未施工。
- 本版只绑定稳定规划卡，不把 `arc_card`、槽、场、PE、事实或 actual 塞进 C7。
- 插件写法位恒空，不接插件系统。


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/C7_SELECTION_ACTION.md git_blob=d1b2b0a702ce818b748f3a6175b01fa979ec2f4a bytes=5613 -->

# 源文件：`novel-mvp/contracts/C7_SELECTION_ACTION.md`

- Git blob：`d1b2b0a702ce818b748f3a6175b01fa979ec2f4a`
- 字节：5613
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# C7_SELECTION_ACTION · C7 选择动作

**版本：v1**

一句话用途：把一份 C7 只读快照上的一次作者选择或合规自动放行，作为**写入前命令信封**交给 planstore 校验。

这份动作合同是短命传输工件，不是账本、长期真源或第三份规划存储。C7 和动作层都没有 `plan.json` 写权；只有 planstore 可以在全部检查通过后写规划账。

## 1. 合同身份

| 字段 | 固定值／规则 |
|---|---|
| `contract` | 固定 `"C7_SELECTION_ACTION v1"` |
| `identity` | 固定 `"write_before_command"`，表示写入前命令，不表示已落账 |

本合同不用 C8／C9 等全局编号。C8、C9 已有其它正式含义；这里沿用描述性名称，避免撞号。

## 2. 完整字段

除下表外不得自造字段：

| 字段 | 类型 | 含义 | 约束／合法来源 |
|---|---|---|---|
| `contract` | str | 合同名与版本 | 固定 `"C7_SELECTION_ACTION v1"` |
| `identity` | str | 短命动作身份 | 固定 `"write_before_command"` |
| `operation_id` | str | 本次复合写入号 | 由动作层产生；供幂等、流水和提交日志使用 |
| `actor` | enum | 谁作选择 | 只允许 `author`／`auto`；禁止 `model` |
| `ts` | str | 动作时间 | 系统时间 |
| `action_kind` | enum | 做哪种处置 | `digest_selection`／`discard_group` |
| `stop_point` | str | 本动作消费的既有停点 | 只引用现行停点登记，不在本合同新增 P 号或默认值 |
| `source_c7_snapshot_sha256` | str | 所见 C7 快照的完整摘要 | 必须与接收时的 C7 快照一致 |
| `card_local_id` | str | 在该 C7 快照内找哪张卡 | 必须存在；只用于写前定位，不得落长期账 |
| `planning_card_ref` | str | 操作哪张稳定规划卡 | 必须与 C7 卡和选择记录一致；不得按标题猜 |
| `expected_card_rev` | int | 动作所见的规划卡修订号 | 必须与 C7 的 `planning_card_rev` 及当前对象一致 |
| `expected_revs` | obj | 本次规划目标的预期修订号 | key 为稳定规划 ID，value 为当前 rev |
| `plan_mutations` | list[obj] | 请求 planstore 执行的规划变化 | 本版选定动作只允许一个 `{kind:"digest_event", target_ref:"PE-…"}`；整组驳回必须为空 |
| `option_record` | obj | 通过校验后准备写入的选择记录 | 形状与 [PLAN_LEDGER_STORAGE.md](PLAN_LEDGER_STORAGE.md) 的 `option_record` 完全一致 |

`source_c7_snapshot_sha256` 绑定完整快照；`card_local_id` 只在这份快照中定位。长期规划账只保存稳定 `card_ref`，不保存 C7 局部卡号或整份动作信封。

## 3. 两种动作

### `digest_selection`

- `option_record.group_status=active`；
- `chosen_key` 必须指向 `option_record.options[].key` 中的真实选项；
- `recommended_key` 必须与 C7 的 `recommended_option_ref` 相同；
- `digest_applied`、`plan_mutations` 和选中项的 `digest_refs` 必须指向同一个现有 PE；
- `expected_revs` 必须带该 PE 的当前 rev。

### `discard_group`

- 只允许 `actor=author`；
- `option_record.group_status=discarded`；
- `chosen_key=null`、`digest_applied=[]`、`plan_mutations=[]`、`expected_revs={}`；
- 不得偷偷采用推荐项，也不得产生规划消化。

“尚未处理／被停点挡住”不生成动作和 `option_record`。它与作者明确整组驳回不是同一种状态。

## 4. 选择来源与停点权力

| `actor` | 可以做什么 | 明确不能做什么 |
|---|---|---|
| `author` | 选择一个真实选项；明确整组驳回 | 不能让选择直接获得事实、Canon 或 actual 权力 |
| `auto` | 仅在 P1 当前设置为 `auto_pass` 时采用稳定主推荐 | 不能选非推荐项、整组驳回、夹带 `author_decision`，也不能越过 P3 |
| `model` | 不合法 | 模型只能提供候选和推荐，不能成为选择主体 |

自动放行由模型之外的停点／策略层决定。`actor=auto` 只能表示合规自动动作，不能冒充作者亲签。遇到 P3 或其它现行规则要求作者确认的边界，planstore 必须在写入前停止。

## 5. planstore 写前硬门

planstore 必须在任何写入前依次确认：

1. 动作字段严格符合本合同，且没有额外字段；
2. C7 快照摘要、局部卡号和动作绑定一致；
3. C7 主推荐指向真实 option，不退回 `options[0]`；
4. `planning_card_ref` 存在、仍可选择，且三处 rev 一致；
5. `actor` 合法，选择记录的 `decided_by` 与它一致；
6. `auto` 符合 P1 `auto_pass`、只选主推荐、没有作者签字；
7. `option_record`、`plan_mutations` 和 `expected_revs` 的稳定引用都存在且未 stale；
8. `discard_group` 不带选定项或规划变化。

任一项失败都在写入前硬停：不能取第一个选项，不能按标题模糊匹配，不能静默新建相似对象，也不能先写账再报警。

## 6. 落账与真值边界

检查通过后，planstore 只保存长期需要的结果：

- `option_record` 中的稳定卡引用、当时推荐号、选择来源和题组状态；
- 合法选定动作要求的规划层消化；
- 既有规划流水与提交日志需要的 `operation_id`、actor 和对象变化。

整份动作信封不得复制进 `plan.json` 成为第三本账。

无论 `author` 还是 `auto`，本动作最多表示“已经安排进规划／规划层已经消化”。它永远不能表示“故事里已经发生”：

```text
F- 新增 = 0
facts.json 写入 = 0
actual 变化 = 0
人物／世界当前状态变化 = 0
```

实际发生只能由写后对账或已有合法作者签字路径推进。

来源：Codex


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/C10_INTAKE_MATERIAL_IDENTITY.md git_blob=2fc40f15b0575df9de0308fbae78e2c74b184a76 bytes=18803 -->

# 源文件：`novel-mvp/contracts/C10_INTAKE_MATERIAL_IDENTITY.md`

- Git blob：`2fc40f15b0575df9de0308fbae78e2c74b184a76`
- 字节：18803
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# C10 · Intake 材料身份（INTAKE_MATERIAL_IDENTITY）

**当前正式版本：v4**

**合同 ID：`C10_INTAKE_MATERIAL_IDENTITY`**

**ADOPTION_STATUS：v4 正式合同已冻结；v1 Intro／Chapter、v2 Setting 与 v3 Title 产品路径已实现；v4 Tags producer／consumer 未实现。Title 的旧 validator 采用标签债继续记为 `NON_BLOCKING_ADOPTION_STATUS_DEBT`。**

一句话用途：在 C1 之前保存“冻结 source 的哪个连续区间是什么材料身份，以及这条身份凭什么成立”。v2 比 v1 增加同轴 `SETTING`，v3 比 v2 增加同轴 `TITLE`，v4 比 v3 增加同轴 `TAGS`。

`SETTING_CONTENT_STRUCTURE = OUT_OF_SCOPE`

`TITLE_CONTENT_SEMANTICS = OUT_OF_SCOPE`

`TAGS_CONTENT_SEMANTICS = OUT_OF_SCOPE`

`TAGS_UNIT_GRANULARITY = ONE_CONTIGUOUS_DECLARED_BLOCK_PER_MATERIAL_UNIT`

`OUTLINE_MIGRATION_STATUS = NOT_EXECUTED`

## 1. Owner、方向与边界

`MATERIAL_IDENTITY_OWNER = INTAKE_MATERIAL_UNIT`

`MATERIAL_UNIT_GRANULARITY = SOURCE_SPAN`

| 方向 | 主体 |
|---|---|
| 写 | Intake material identity writer；当前产品写 v1 Intro／Chapter／Unknown、v2 Setting 与 v3 Title；v4 Tags writer 待施工 |
| 存 | Intake material store |
| 读 | C1 上游投影门、材料展示／确认层；当前产品已接 Intro／Setting／Title／Chapter，Tags 待施工 |
| 不直接读 | C1、C2、M3；它们只接投影门之后的合法章节对象 |

C10 是 C1 上游合同，不是 C1 扩字段。Intro、Setting、Title 与 Tags 可以合法存在于材料存储中，而不需要伪造章节 id 或写入 `chapters.json`。

Setting role 只表示：该 source span 属于作者提供的设定参考材料。它不能推出内容为真、已经发生、属于硬规则、当前生效、可写事实账、可作为 Chapter evidence 或可进入 M3 章节事实抽取。

Title role 只表示：该 source span 属于作品级书名／作品标题材料。它不是 Confirmed Chapter 内部的 chapter heading，也不能把标题里的营销、类型或剧情暗示推成事实、Chapter evidence 或 M3 输入。

Tags role 只表示：该连续 source span 属于作者或受控入口明确给出的作品类型标签材料块。它不拆单个标签值，也不能把“重生、权谋、女强”等标签文字推成故事事实、Chapter evidence 或 M3 输入。

## 2. 正式序列化形状

v1、v2、v3 与 v4 使用相同顶层形状。JSON 对象只允许下列字段，额外字段不合法：

| 字段 | 类型 | 必填 | 可空 | 默认 | 含义 |
|---|---|---:|---:|---|---|
| `contract` | str | 是 | 否 | 无 | 固定 `C10_INTAKE_MATERIAL_IDENTITY` |
| `version` | enum | 是 | 否 | 无 | `v1`／`v2`／`v3`／`v4`；consumer 必须按版本分发 |
| `material_unit_id` | str | 是 | 否 | 无 | Intake 命名空间内稳定且唯一的材料单元号 |
| `source_ref` | obj | 是 | 否 | 无 | 指回冻结 source 与原始连续区间 |
| `identity_revisions` | list[obj] | 是 | 否 | 无 | 从 1 起连续、只追加的身份 revision 链 |

没有任何字段拥有隐式默认值。缺字段、未知版本或未知 role 不得降级成 Chapter。

### 2.1 `source_ref`

| 字段 | 类型 | 必填 | 可空 | 约束 |
|---|---|---:|---:|---|
| `source_id` | str | 是 | 否 | 指向同一 Intake 命名空间内的冻结 parent source |
| `source_sha256` | str | 是 | 否 | 64 位小写 hex；对应 parent source 原始字节 |
| `coordinate_basis` | enum | 是 | 否 | 固定 `DECODED_UNICODE_CODEPOINT_V1` |
| `start` | int | 是 | 否 | 0 起算、左闭；必须 `0 <= start < end` |
| `end` | int | 是 | 否 | 右开；不得超过冻结解码文本长度 |
| `slice_sha256` | str | 是 | 否 | 原样切片按 UTF-8 编码后的 SHA-256 |

### 2.2 `identity_revisions[]`

| 字段 | 类型 | 必填 | 可空 | 约束 |
|---|---|---:|---:|---|
| `revision_no` | int | 是 | 否 | 从 1 连续递增 |
| `role` | enum/null | 是 | 仅 Unknown 可空 | v1：`INTRO`／`CHAPTER`／`null`；v2：再增加 `SETTING`；v3：再增加 `TITLE`；v4：再增加 `TAGS` |
| `state` | enum | 是 | 否 | `CONFIRMED`／`CANDIDATE`／`UNKNOWN` |
| `basis` | obj | 是 | 否 | 身份依据，见第 4 节 |
| `actor` | obj | 是 | 否 | 写入或确认该 revision 的主体 |
| `recorded_at` | str | 是 | 否 | RFC 3339 时间，必须带时区 |
| `reason` | str/null | 是 | 是 | 一句修订原因；Unknown 初建可空 |

`basis` 固定字段为 `type`、`reference`；`actor` 固定字段也为 `type`、`reference`。Confirmed 与 Candidate 的两个 reference 均需非空，Unknown 的 basis reference 必须为 null。

### 2.3 v4 Tags 示例

```json
{
  "contract": "C10_INTAKE_MATERIAL_IDENTITY",
  "version": "v4",
  "material_unit_id": "MU-TAGS-EXAMPLE-001",
  "source_ref": {
    "source_id": "SRC-TAGS-EXAMPLE-001",
    "source_sha256": "ab5524dc9535634943b192c3b5ba867dfdd6326d4b6af13f3f39b1041616d557",
    "coordinate_basis": "DECODED_UNICODE_CODEPOINT_V1",
    "start": 0,
    "end": 12,
    "slice_sha256": "ab5524dc9535634943b192c3b5ba867dfdd6326d4b6af13f3f39b1041616d557"
  },
  "identity_revisions": [
    {
      "revision_no": 1,
      "role": "TAGS",
      "state": "CONFIRMED",
      "basis": {
        "type": "USER_DECLARATION",
        "reference": "UI-TAGS-DECLARATION-001"
      },
      "actor": {
        "type": "USER",
        "reference": "USER-EXAMPLE"
      },
      "recorded_at": "2026-08-18T09:00:00+08:00",
      "reason": "用户明确选择该连续区间为作品类型标签材料"
    }
  ]
}
```

## 3. Source span 正式规则

1. `source_sha256` 总是对冻结的原始 source bytes 计算；不得对清洗稿、转码稿或摘录计算。
2. parent source 必须保存原始字节、解码方式和精确解码文本；这些属于 source owner，不在每个 C10 record 中重复。
3. `start`／`end` 对精确解码文本按 Unicode code point 计数，0 起算、左闭右开 `[start,end)`。
4. source 解码完成后不得做 Unicode normalization、换行归一、trim 或其他文本改写。
5. `slice_sha256 = SHA256(decoded_source[start:end].encode("utf-8"))`。
6. 原始 source SHA、解码元数据、span 或 slice SHA 任一不匹配，投影必须 fail closed。
7. 同一 source 下可有多个 material units；区间不得重叠。未覆盖区间必须在上游覆盖账中显式可见，不能静默丢失。

C2 也使用 0 起算、左闭右开和 Python／Unicode code point 计数，但它指向规范化拼接章节文本；C10 指向未规范化的冻结 source 解码文本。两者不能混用。

## 4. 身份、状态与 authority

### 4.1 v1 原样兼容

| `state` | `role` | `basis.type` | `actor.type` | 权力 |
|---|---|---|---|---|
| `CONFIRMED` | `INTRO`／`CHAPTER` | `USER_DECLARATION` | `USER` | 用户明确声明 |
| `CONFIRMED` | `INTRO`／`CHAPTER` | `STRUCTURED_ENTRY` | `SYSTEM` | 有合同约束的结构化入口 |
| `CANDIDATE` | `INTRO` | `CONTENT_CLASSIFICATION_CANDIDATE` | `PARSER`／`MODEL` | 只形成候选 |
| `UNKNOWN` | `null` | `NO_ASSERTION` | `SYSTEM` | 没有足够身份依据 |

v1 的 role、state、authority、revision 和消费语义不得因 v2／v3／v4 改变。

### 4.2 v2 Setting 扩展

v2 保留全部 v1 合法组合，并增加：

| `state` | `role` | `basis.type` | `actor.type` | 权力 |
|---|---|---|---|---|
| `CONFIRMED` | `SETTING` | `USER_DECLARATION` | `USER` | 用户明确声明该 span 是设定参考材料 |
| `CONFIRMED` | `SETTING` | `STRUCTURED_ENTRY` | `SYSTEM` | 合同约束的 Setting 输入槽或受控结构化入口 |
| `CANDIDATE` | `SETTING` | `CONTENT_CLASSIFICATION_CANDIDATE` | `PARSER`／`MODEL` | 只形成候选，不拥有确认权 |

普通文件名、自由 metadata、关键词、regex 或模型语义猜测不能写 Confirmed Setting。受控 manifest／metadata 只有在已被合同约束为结构化 Setting 入口时，才复用 `STRUCTURED_ENTRY + SYSTEM`。

除此之外的组合全部非法。v2 仍不定义 Candidate Chapter；Unknown 仍只能使用 role null。

### 4.3 v3 Title 扩展

v3 保留全部 v1／v2 合法组合，并增加：

| `state` | `role` | `basis.type` | `actor.type` | 权力 |
|---|---|---|---|---|
| `CONFIRMED` | `TITLE` | `USER_DECLARATION` | `USER` | 用户明确声明该 span 是作品书名材料 |
| `CONFIRMED` | `TITLE` | `STRUCTURED_ENTRY` | `SYSTEM` | 合同约束的 Title 输入槽或受控书名字段 |
| `CANDIDATE` | `TITLE` | `CONTENT_CLASSIFICATION_CANDIDATE` | `PARSER`／`MODEL` | 只形成候选，不拥有确认权 |

第一行、文件名、字数、短文本、书名号、关键词、regex 或模型语义猜测都不能写 Confirmed Title。受控 manifest／metadata 只有在字段已被正式合同约束为作品书名时，才复用 `STRUCTURED_ENTRY + SYSTEM`。

除此之外的组合全部非法。v3 仍不定义 Candidate Chapter；Unknown 仍只能使用 role null。

### 4.4 v4 Tags 扩展

v4 保留全部 v1／v2／v3 合法组合，并增加：

| `state` | `role` | `basis.type` | `actor.type` | 权力 |
|---|---|---|---|---|
| `CONFIRMED` | `TAGS` | `USER_DECLARATION` | `USER` | 用户明确声明该连续 span 是作品类型标签材料 |
| `CONFIRMED` | `TAGS` | `STRUCTURED_ENTRY` | `SYSTEM` | 合同约束的 Tags 输入槽或受控标签集合字段 |
| `CANDIDATE` | `TAGS` | `CONTENT_CLASSIFICATION_CANDIDATE` | `PARSER`／`MODEL` | 只形成候选，不拥有确认权 |

文件名、自由 metadata、井号、顿号、短词列表、关键词、regex 或模型语义猜测不能写 Confirmed Tags。受控 manifest／metadata 只有在字段已被正式合同约束为作品类型标签材料时，才复用 `STRUCTURED_ENTRY + SYSTEM`。

除此之外的组合全部非法。v4 仍不定义 Candidate Chapter；Unknown 仍只能使用 role null。

### 4.5 Setting 内容硬隔离

`SETTING_CONTENT_STRUCTURE = OUT_OF_SCOPE`

C10 v2／v3／v4 不包含 `rule_id`、`ability_id`、`exception_id`、`applicability`、`usage_limit`、`effective_rule`、`setting_fact` 或同义字段。ADD-043 继续开放。

### 4.6 Title 内容硬隔离

`TITLE_MATERIAL != STORY_FACT_EVIDENCE`

Confirmed Title 只能证明当前作品标题文本如此。例如《重生后我成为九州第一剑仙》不能自动证明主角重生、九州存在、主角成为剑仙或天下第一。

C10 v3／v4 不包含 `is_title`、`book_title_identity`、`may_emit_c1`、`may_enter_m3`、`title_is_fact`、`title_truth_bearing`、marketing、genre、story hint、SEO 或平台标题结构。

Work／Book Title 是 C10 Intake Material Role；chapter heading 是 Confirmed Chapter material 内部的章节结构。两者 owner、生命周期、consumer 和裁决权不同，不得因代码都使用 `title` 一词而共用身份字段。

### 4.7 Tags 内容硬隔离

`TAGS_MATERIAL != STORY_FACT_EVIDENCE`

Confirmed Tags 只能证明当前连续 source span 是作品类型标签材料。例如“重生、权谋、女强”不能自动证明主角已经重生、故事一定存在权谋或主角具备任何性别／能力事实。

C10 v4 不包含 `tag_values`、`tag_count`、`normalized_tags`、单标签 id、genre、theme、audience、推荐、搜索权重、SEO、`is_tags`、`may_emit_c1`、`may_enter_m3` 或同义字段。

一个连续且由同一 authority 明确声明的多标签块是一个 Tags material unit；块内标签值、分隔符、顺序、去重和归一化不在 C10 中解析。被其他材料隔开的 Tags 块必须分别建立连续 material units。

## 5. Revision 规则

- revision 1 表示 material unit 的初始身份快照；后续改判只追加，不原地覆盖或删除；
- `revision_no` 必须严格为 `1..N`，数组升序；当前有效身份恒为最后一条；
- material unit 的 source span 是稳定边界；span 改变要新建 material unit；
- v4 revision 可以在 Intro、Chapter、Setting、Title、Tags、Candidate 与 Unknown 的合法组合间追加改判，消费资格随最后一条 revision 重新计算；
- Setting → Chapter 只有在新的 revision 获得合法 Confirmed Chapter authority 后，才重新获得 C1 投影资格；
- Chapter → Setting 会立即关闭新的 C1／M3 下发，并把旧派生物交给失效／重算清单；C10 不静默删除既有 C1；
- Title → Chapter 只有在新 revision 获得合法 Confirmed Chapter authority 后，才重新获得 C1 投影资格；
- Chapter → Title 会立即关闭新的 C1／M3 下发，并把旧派生物交给失效／重算清单；C10 不静默删除既有 C1；
- Tags → Chapter 只有在新 revision 获得合法 Confirmed Chapter authority 后，才重新获得 C1 投影资格；
- Chapter → Tags 会立即关闭新的 C1／M3 下发，并把旧派生物交给失效／重算清单；C10 不静默删除既有 C1；
- 现有 v1／v2／v3 records 不自动升 v4。若未来需要把旧 unit 改判为 Tags，必须另行授权显式、无损的 record-version upgrade，保留 unit id、source ref 与旧 revisions；本票不迁移数据。

## 6. 身份与消费权限分离

C10 不保存 `is_setting`、`is_intro`、`is_title`、`is_tags`、`may_emit_c1`、`may_enter_m3` 或同义布尔字段。消费资格由当前 revision 与 consumer policy 确定性派生：

| 当前身份 | 保存／展示 | Chapter C1 writer | M3 chapter-fact extraction |
|---|---:|---:|---:|
| Confirmed Chapter | 是 | 是，仍需现有切章与无损门 | 只能经合法 C1→C2→admission 间接进入 |
| Confirmed Intro | 是 | 否 | 否 |
| Candidate Intro | 是 | 否 | 否 |
| Confirmed Setting | 是 | 否 | 否 |
| Candidate Setting | 是 | 否 | 否 |
| Confirmed Title | 是 | 否 | 否 |
| Candidate Title | 是 | 否 | 否 |
| Confirmed Tags | 是 | 否 | 否 |
| Candidate Tags | 是 | 否 | 否 |
| Unknown | 是 | 否 | 否 |

Setting、Title 与 Tags 不是“永远不可消费”。未来 planning、context packer、consistency checker、world reference UI、书架展示、标签展示或搜索等消费者如需读取，必须另定 policy；本合同不授予它们真值、推荐、训练、导出或删除权。

## 7. Mixed source

v4 正式支持同一 source SHA、不同不重叠 span 的材料单位共存：

```text
[0,7)    Confirmed Title
[7,22)   Confirmed Intro
[22,34)  Confirmed Setting
[34,46)  Confirmed Tags
[46,59)  Confirmed Chapter
```

五个 units 必须共用相同 `source_id`、`source_sha256` 和 `coordinate_basis`，各自保存精确 `slice_sha256`。Title、Intro、Setting 与 Tags 不产生 C1；只有 Chapter 获得进入现有 chapterization／C1 门的资格。

合同不规定机器怎样自动发现边界。Explicit Setting／Title／Tags 的边界来自用户声明或合同约束的结构化入口；无法确认的区间写 Candidate／Unknown，不能默认 Tags 或 Chapter。一个连续多标签块整体是一个 Tags unit，不在身份层拆单标签。

## 8. 版本与向后兼容

### v4 reader 读取 v1／v2／v3

必须继续接受全部合法 v1 Intro／Chapter／Candidate Intro／Unknown、v2 Setting 与 v3 Title records，消费结果不变。正式 fixtures 保留六类 v1、六类 v2 和八类 v3 样本的原字节与顺序作为机械兼容证据。

### v1 reader 读取 Setting／v2

`OLD_READER_SETTING_BEHAVIOR = REJECT_FAIL_CLOSED`

旧 reader 遇到 `version=v2` 必须拒绝未知版本；遇到错误标成 `version=v1` 的 Setting 必须拒绝未知 role。不得 fallback Chapter、Intro、draft，不得静默 coercion，也不得忽略 role 后继续 emission。

### v1／v2 reader 读取 Title／v3

`OLD_READER_TITLE_BEHAVIOR = REJECT_FAIL_CLOSED`

v1／v2 reader 遇到 `version=v3` 必须拒绝未知版本；遇到错误标成 `version=v1`／`version=v2` 的 Title 必须拒绝未知 role。不得 fallback Chapter、Intro、Setting、draft，不得静默 coercion，也不得忽略 role 后继续 emission。

### v1／v2／v3 reader 读取 Tags／v4

`OLD_READER_TAGS_BEHAVIOR = REJECT_FAIL_CLOSED`

v1／v2／v3 reader 遇到 `version=v4` 必须拒绝未知版本；遇到错误标成 `version=v1`／`version=v2`／`version=v3` 的 Tags 必须拒绝未知 role。不得 fallback Chapter、Intro、Setting、Title、draft，不得静默 coercion，也不得忽略 role 后继续 emission。

### 旧数据不迁移

- 既有 v1 Intro／Chapter records 原样保留；
- 既有 v2 Setting records 原样保留；
- 既有 v3 Title records 原样保留；
- 历史 legacy draft Setting 不自动重分类、不伪造 C10 provenance；
- 历史 legacy draft Title、文件首行、metadata 中的可疑书名和旧项目标题不自动重分类、不伪造 C10 provenance；
- 历史 legacy draft Tags、自由 metadata、短词列表和旧平台标签不自动重分类、不伪造 C10 provenance；
- 历史 `C1.kind=outline` 继续兼容，不增加 C10 Outline role；
- C1／C2 字段和版本不变。

### Unknown contract/version

consumer 只读取明确支持的 C10 version。未知 contract／version／field／role 均 fail closed 并保留 source，不得走 `else → Chapter`。

## 9. 产品采用接缝

`CONTRACT_CAPABILITY != PRODUCT_CAPABILITY`

- C10 v4 已正式冻结；
- 当前产品通过 v1 路径写 Intro／Chapter／Unknown，通过 v2 路径写 Explicit Setting，通过 v3 路径写 Explicit Title；现有产品行为保持；
- `TITLE_ADOPTION_STATUS_DEBT = NON_BLOCKING_ADOPTION_STATUS_DEBT`；旧 validator 的 `NOT_IMPLEMENTED` 标签不在本票修订；
- v4 Tags producer／consumer 未实现；
- 正式合同存在不表示产品入口已经支持 Tags；
- 只有未来产品施工票可以让 writer 显式产出 v4 Tags，并接入现有 C1 投影门；
- PROD-01～07 现行行为不变。

## 10. Future extension seam

`OUTLINE_MIGRATION_STATUS = NOT_EXECUTED`

`R13_C10_V4_ALIGNMENT = OPEN`

Tags 单标签值、归一化、去重、推荐与题材推断保持未来独立内容接缝；它们不在 C10 v4。Outline 保持未来迁移接缝，ADD-043 的规则／能力／例外结构继续开放。

## 11. 机器件与验收

- Schema：[C10_INTAKE_MATERIAL_IDENTITY.schema.json](C10_INTAKE_MATERIAL_IDENTITY.schema.json)
- v1 兼容＋v2 Setting＋v3 Title＋v4 Tags fixtures：[C10_INTAKE_MATERIAL_IDENTITY.fixtures.jsonl](C10_INTAKE_MATERIAL_IDENTITY.fixtures.jsonl)
- 单一版本分发 validator：[validate_c10_intake_material_identity.py](validate_c10_intake_material_identity.py)

正式 validator 必须验证严格字段、版本化 role／authority 组合、revision 链、source raw SHA、精确 span／slice SHA、mixed-source 无重叠、Setting／Title／Tags 零 Chapter emission、v1／v2／v3 全兼容及旧 reader fail-closed；同时检查 C1／C2 bytes 不变。

来源：CZ 2026-08-18 `T03-CONTRACT-04__C10_TAGS_ROLE_FORMALIZATION`


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md git_blob=6c02565783c2159969b0622714216bc42c05265b bytes=6518 -->

# 源文件：`novel-mvp/contracts/C11_CHAPTER_REVISION_LEDGER.md`

- Git blob：`6c02565783c2159969b0622714216bc42c05265b`
- 字节：6518
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# C11 · 章节版本真源（CHAPTER_REVISION_LEDGER）

**正式版本：v1**

一句话用途：在稳定 `chapter_id` 下保存不可变、连续递增的章节正文版本链，并唯一指出当前版本。

## 1. Owner 与边界

| 项 | 正式规则 |
|---|---|
| owner | `CHAPTER_REVISION_LEDGER` |
| 持久单位 | 一条 stable `chapter_id` 的 revision chain |
| 唯一真值 | 章节内容历史与 current revision |
| C1 | current revision 的物化视图，不保存第二份历史 |
| C10 | 输入材料与 source span 真值，不负责判断替换哪一章 |
| C4 | 事实真值；只保存 revision ref、anchor 和 needs-recheck 状态 |
| planstore | stable slot mapping 仍只绑 chapter_id；正文依赖 RE 在修订后 stale |

`C10.identity_revisions[]`、写作区 `work_rev`、规划对象 `rev` 都不是 chapter revision，禁止改名复用。

## 2. Ledger 字段

| 字段 | 类型 | 规则 |
|---|---|---|
| `contract` | str | 固定 `CHAPTER_REVISION_LEDGER` |
| `version` | str | 固定 `v1` |
| `chapter_id` | str | 稳定章节身份；首次合法接收后不因标题、正文、文件名或章号变化 |
| `current_revision_no` | int | 必须等于 `revisions[]` 最后一项，禁止回拨 |
| `revisions` | list | 从 1 连续递增、只追加，至少一项 |
| `last_operation_id` | str | 最近一次真正改变 ledger 的成功 action |

### `revisions[]`

| 字段 | 类型 | 规则 |
|---|---|---|
| `revision_no` | int | 首版 1，以后严格 +1 |
| `title` | str | 本版章节标题 |
| `text_sha256` | str | 本版逐字正文 UTF-8 SHA-256 |
| `chars` | int | Unicode codepoint 数 |
| `content_ref` | obj | `C10_SOURCE_SPAN` 或 `LEGACY_C1_SNAPSHOT` |
| `origin_material_ref` | obj/null | 新输入引用 C10 material unit；legacy blob 为 null |
| `change_kind` | enum | `INITIAL`／`REPLACE`／`RESTORE` |
| `restores_revision_no` | int/null | 只有 RESTORE 非空，且必须指向更早的真实 revision |
| `committed_at` | str | 提交时间 |
| `commit_operation_id` | str | 产生本版的动作号，链内唯一 |
| `actor` | enum | 固定 `AUTHOR` |

Ledger row 不内嵌正文。`content_ref` 必须能逐字回放正文，回放内容的 SHA 和字符数必须等于本 revision。

## 3. Content ref

### C10 source span

```json
{
  "kind": "C10_SOURCE_SPAN",
  "source_id": "SRC-0001",
  "source_sha256": "…",
  "coordinate_basis": "DECODED_UNICODE_CODEPOINT_V1",
  "start": 0,
  "end": 1200,
  "slice_sha256": "…"
}
```

`origin_material_ref` 同时保存 `{material_unit_id, identity_revision_no}`。C10 identity revision 只证明材料身份，不得充当 chapter revision。

### Legacy snapshot

```json
{
  "kind": "LEGACY_C1_SNAPSHOT",
  "blob_sha256": "…"
}
```

只在旧 C1 无法唯一回放到 C10 source span 时使用。blob 以内容寻址保存，不能被覆盖。

## 4. Current、替换与恢复

- 首次合法章节生成 r1，`change_kind=INITIAL`。
- 修改同章只在原 `chapter_id` 下追加 r2、r3……，不得新发 chapter_id。
- 恢复旧内容不回拨 current 指针：例如 current=r2、恢复 r1，必须追加 r3，写 `RESTORE + restores_revision_no=1`。
- 已提交 revision 永不删除、改号或逐字段改写。
- COMMITTED 后不能物理 rollback；撤回只能 RESTORE-as-new-revision。

## 5. Revision ref 与 anchor

所有 revision-aware 消费者使用：

```json
{
  "chapter_id": "c01",
  "revision_no": 2,
  "revision_text_sha256": "…"
}
```

正式证据坐标固定为：

`CHAPTER_REVISION_TEXT_UNICODE_CODEPOINT_0_BASED_HALF_OPEN`

```json
{
  "chapter_id": "c01",
  "revision_no": 2,
  "revision_text_sha256": "…",
  "coordinate_basis": "CHAPTER_REVISION_TEXT_UNICODE_CODEPOINT_0_BASED_HALF_OPEN",
  "start": 10,
  "end": 18,
  "slice_sha256": "…"
}
```

坐标相对该 revision 的逐字 C1 text。C2 normalized offset 和 C10 source span 都不能冒充 revision anchor。anchor slice 必须回验 SHA。

## 6. Fact 迁移与 current truth

章节修订预检只允许确定性结果：

| 结果 | C4 v1 处置 |
|---|---|
| verified old slice 在新版唯一命中 | 保持原 status，revision ref／anchor 前进 |
| 新版 0 次命中 | `needs_recheck / evidence_gone` |
| 新版多次命中 | `needs_recheck / anchor_ambiguous` |
| legacy quote 在旧、新两版各唯一 | 补 VERIFIED anchor，保持原 status |
| legacy quote 无法双边唯一验证 | `needs_recheck / legacy_anchor_unverified` |

`needs_recheck` 不属于 current truth：M6、M8、M11 不消费，M7 不把它当 confirmed 或普通候选扫描。程序不能凭相似度、文件名或模型意见自动恢复 confirmed。

## 7. 原子提交

一次 revision commit 的正式原子组：

1. ledger append 与 current pointer；
2. C1 current projection；
3. C4 revision refs、anchors、needs-recheck effects；
4. C10→chapter revision projection receipt；
5. 受影响 planstore RE stale、history、blob；
6. operation／transaction receipt。

协调器复用现有 `.planstore.lock`、`.planstore_txn/`、operation ID 与 story commit sequence；不得新建第二把 project truth lock、第二套 fact writer 或第二套 plan writer。全部 effects 必须在 prepare 前算完，恢复只能得到完整 before 或完整 after；未知 SHA 进入 `NEEDS_MANUAL_RECOVERY`。

## 8. Legacy migration

- 每条旧 draft C1 保留原 `chapter_id`，建立 revision 1，正文 bytes 不变。
- 可唯一回放 C10 exact span 时引用 C10；否则使用 `LEGACY_C1_SNAPSHOT`。
- legacy fact quote 唯一命中 r1 时生成 VERIFIED anchor，否则保留 `LEGACY_UNVERIFIED`；章节第一次修订时必须双边验证或转 needs_recheck。
- 旧 C6 没有 revision ref 时统一是 `LEGACY_REVISION_UNKNOWN`。
- duplicate chapter id、悬空 fact chapter_id、source replay 多义或 SHA 不闭合时整项目强停。
- Outline 不迁。

## 9. 机器件

- Schema：[C11_CHAPTER_REVISION_LEDGER.schema.json](C11_CHAPTER_REVISION_LEDGER.schema.json)
- 正式验收夹具：[C11_CHAPTER_REVISION_LEDGER.fixtures.jsonl](C11_CHAPTER_REVISION_LEDGER.fixtures.jsonl)
- Validator：[validate_c11_chapter_revision_ledger.py](validate_c11_chapter_revision_ledger.py)
- 作者提交命令：[CHAPTER_REVISION_COMMIT_ACTION.md](CHAPTER_REVISION_COMMIT_ACTION.md)
- 事务回执：[CHAPTER_REVISION_COMMIT_RECEIPT.md](CHAPTER_REVISION_COMMIT_RECEIPT.md)

来源：CZ 2026-08-18 `M1-M4-CONTRACT-01__CHAPTER_REVISION_LEDGER_AND_REVISION_AWARE_CONSUMER_FORMALIZATION`


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/CHAPTER_SLOT_SNAPSHOT.md git_blob=576feb283872065294bab9dc0a430ee16b2571b0 bytes=3524 -->

# 源文件：`novel-mvp/contracts/CHAPTER_SLOT_SNAPSHOT.md`

- Git blob：`576feb283872065294bab9dc0a430ee16b2571b0`
- 字节：3524
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# CHAPTER_SLOT_SNAPSHOT · 章槽只读快照

**版本：v1**

一句话用途：从一份身份明确的 `plan-v2` 当前快照中，按稳定章槽号投影出该槽及其场、计划事件、故事线的只读切片，供独立工具或后续适配器读取。

它与 `C7_PLOT_LAYER v1` 完全不同：C7 仍是一次出题的候选快照；本合同只回答“当前规划账里这个章槽写了什么”。它不取代 C7，也不给任何消费者规划账、事实账或 actual 写权。

## 1. 身份与来源绑定

| 字段 | 类型 | 规则 |
|---|---|---|
| `contract` | str | 固定 `CHAPTER_SLOT_SNAPSHOT` |
| `version` | str | 固定 `v1` |
| `status` | str | 固定 `plan`；所有内容均为规划，不表示已发生 |
| `source_plan_version` | int | AuthorWorkspace 逻辑键 `plan` 的当前正整数版本 |
| `source_plan_sha256` | str | `plan-v2` 对象按 UTF-8、键排序、紧凑 JSON 并追加换行后的 SHA-256 |
| `generation_watermark` | obj | 重复保存计划版本、SHA、槽修订和章纲提交水位；相同输入必须相同 |
| `basis_refs` | obj | 本快照实际读取的槽、场、计划事件和故事线稳定引用 |

快照没有现场时间字段。它的生成水位完全来自输入计划身份，因此同一输入可逐字重复。来源计划版本、SHA 或槽修订变化后，旧快照即可能过期，消费者必须重新投影。

## 2. 章槽字段

以下字段均逐字复制自唯一命中的 `plan-v2.slots[]`：

- `slot_ref`、`slot_rev`；
- `goal`、`summary`；
- `entry_state`、`exit_condition`、`exit_hook`；
- `storyline_refs`、`scene_refs`；
- `must_not`、`risks`；
- `outline_checkpoint`。

`outline_checkpoint` 没有时明确为 `null`。有值时只允许 `{outline_rev, source_slot_ref, source_commit_seq}`，且 `source_slot_ref` 必须等于本章槽。

## 3. 引用闭合切片

`scenes` 按章槽的 `scene_refs` 顺序投影；每场的 `pe_refs` 再决定 `events` 顺序。`storylines` 按章槽的 `storyline_refs` 顺序投影。

- 场至少保留 `id/rev/slot_ref/goal/summary/pe_refs`；地点、人物、情绪、画面、对白信息点等现行字段存在时原样复制。
- 计划事件至少保留 `id/rev/scene_ref/text`；用途、所属故事线、计划时间、来源与偏差说明等现行字段存在时原样复制。
- 故事线保留 `id/rev/name/alias/priority/members/line_status`。`last_scene_ref` 可能指向别章，因此不进入本章闭合切片。
- 任一稳定 ID 重复、引用重复、引用悬空、场跨槽、计划事件跨场或事件故事线不属于本槽，整份快照拒绝。

## 4. 真值与写权边界

快照明确不包含：

- `facts`、`actual`、`actuality`、`confirmed`；
- `handover_parts`、`slot_status`、`truth_bearing`；
- `digest_status`、`digest_ref`、`prose_status`；
- `reconciliation_edges` 或选择动作。

源计划里的 `digested` 只表示规划层已安排，handover 只表示作者交棒，对账边只表示检查关系；本快照不会把它们改写成“已发生”。快照也没有任何 planstore 写入口。

## 5. 与 C7、M10 的兼容边界

- `C7_PLOT_LAYER v1` 继续保存一次出题所需的目的、选项、推荐、写作指导和冲突；本快照没有这些字段。
- 当前 M10 `m10-scene-slice-r1` 还要求人物／地点锚、镜头视觉信息等。本快照只从 plan-v2 投影，不能直接冒充该输入；后续若接 M10，仍需单独的归一化适配器和锚来源。

来源：Codex


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/FACT_REVIEW_ACTION.md git_blob=cfae2c518e0741735c9fffa3c6d6e0370668cec9 bytes=3771 -->

# 源文件：`novel-mvp/contracts/FACT_REVIEW_ACTION.md`

- Git blob：`cfae2c518e0741735c9fffa3c6d6e0370668cec9`
- 字节：3771
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# FACT_REVIEW_ACTION · M5 事实确认／改判动作

**版本：v1**

一句话用途：作者对一条 current C4 候选做确认、驳回、改判或改写；动作本身是短命命令，只有事务协调器成功提交后，`facts.json` 才发生变化。

它不是事实账、检测结果、作者签字账本或第二份真源。旧 CLI 可以继续叫 `confirm`，旧调用面可以继续调用 `store.set_status`／`store.edit_fact_text`，但都只能转成本动作，再由 [factstore.py](../mvp/factstore.py) 进入现有跨文件事务协调器。

## 权力边界

| 项 | 规则 |
|---|---|
| actor | 只允许 `author` |
| 模型／自动档 | 可以生产 extracted 候选，不能提交本动作 |
| facts | 只改动作点名的既有 `f…`；不得自造新事实号 |
| planstore | 只把引用该事实的 active RE 转为 stale；不得改原计划文字 |
| actual | 不写裸 actual；旧支持关系在事实状态或文本变化时失效 |

## 字段

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `contract` | str | 合同身份 | 固定 `FACT_REVIEW_ACTION` |
| `version` | str | 版本 | 固定 `v1` |
| `operation_id` | str | 幂等动作号 | 同号同载荷回放；同号不同载荷拒绝 |
| `actor` | enum | 动作主体 | 只允许 `author` |
| `fact_ref` | str | 目标事实 | 必须唯一指向 current `f…` |
| `expected_status` | enum | 作者看到的状态 | `extracted`／`confirmed`／`rejected` |
| `expected_fact_sha256` | str | 作者看到的整条记录摘要 | canonical JSON SHA-256；代替新增 C4 revision 字段 |
| `decision` | enum | 作者动作 | 见下表 |
| `replacement_text` | str\|null | 作者改写后的事实句 | 只有改写类动作可非空 |
| `note` | str | 作者备注 | 可空串 |

### 动作表

| `decision` | 结果 |
|---|---|
| `confirm` | 当前记录变为 `confirmed` |
| `reject` | 当前记录变为 `rejected` |
| `edit` | 保留当前状态，只替换作者点名的事实句；兼容旧 `edit_fact_text` |
| `edit_and_confirm` | 在一个事务里改写并确认；禁止旧 CLI 先改单文件再确认 |

`confirm` 与 `reject` 都可用于改判。动作不新增事实状态，也不自动生成新的 C3／C4 条目。

## 写前硬门

提交前必须同时满足：

1. action 字段完整且 actor 为作者；
2. `fact_ref` 在 current C4 中唯一存在；
3. current 状态和整条记录摘要与 `expected_*` 完全相同；
4. 改写类动作有非空 `replacement_text`，非改写类动作不夹带它；
5. `facts.json`、受影响的 `plan.json`、流水、blob 与 commit log 可以进入同一个恢复事务。

任一失败都在写前拒绝。不得先改事实再把 RE 标 stale，也不得先改 RE 再补事实。

## RE 与 actual support

若被修改的事实正被 active RE 引用，确认、驳回、改判或文本变化都必须在同一事务把旧 RE 转为 `stale`，rev +1，并留 `fact_basis_stale` 流水。旧 RE 保留原引用和原摘要供追溯，但不再支持 actual。

把该事实以后重新改回 `confirmed`，不会静默复活旧 RE。要恢复 actual 支持，必须重新走 current C1、current planning baseline 和新的对账边。

## 恢复与幂等

本动作复用 `.planstore.lock`、`.planstore_txn/`、`commit_log.jsonl`、`plan_history.jsonl` 和 `blobs/`。prepare 行保存不含故事正文的结果回执，供进程重启后同 operation ID 回放；跨文件只写一部分时按恢复底稿整体回滚，全部目标已写完时补 commit。

候选新增与历史重复号修复不是 M5 作者处置，但它们修改同一 `facts.json`，也必须经 [factstore.py](../mvp/factstore.py) 复用同一文件锁和事务提交，不能与 M5 并存第二个裸写入口。


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/RECONCILIATION_CANDIDATE.md git_blob=8f05011a2c8ca30aec502a096ae55940348fc987 bytes=3913 -->

# 源文件：`novel-mvp/contracts/RECONCILIATION_CANDIDATE.md`

- Git blob：`8f05011a2c8ca30aec502a096ae55940348fc987`
- 字节：3913
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# RECONCILIATION_CANDIDATE · 计划—书稿六态观察候选

**版本：v1**

一句话用途：把 current C1 书稿、当前规划对象和已经存在的 C3 事实候选做一次六态语义比对，交出可机械验收的短命候选。它不是对账边、事实账、作者决定或 actual。

## 身份与方向

| 方向 | 模块 |
|---|---|
| 发 | 对账语义模型只返回 item 语义；程序补齐 run、C1／planning 绑定和冻结的 C3 候选 |
| 收 | planstore 对账观察 writer；作者 facts 准入动作 |
| 落盘 | 不单独建库；正式结果只落既有 `plan.json.reconciliation_edges[]`，事实只落既有 M4 `facts.json` |

模型没有写权。模型不得生成 `RE-`、`f`／`F-`、作者决定、actual、planstore 字段或事实状态。

## 顶层字段

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `contract` | str | 合同身份 | 固定 `RECONCILIATION_CANDIDATE` |
| `version` | str | 版本 | 固定 `v1` |
| `reconcile_run_id` | str | 本次观察动作号 | 使用既有 operation ID 词法；不是长期对象 ID |
| `chapter_ref` | str | 被对照 C1 | 必须是合法 `kind=draft` 章节 |
| `chapter_text_sha256` | str | 本次看到的 C1 原文字节摘要 | 与 current C1 `text` 精确一致 |
| `slot_ref` | str | 对应规划槽 | 必须由 current active slot mapping 连接到该 C1 |
| `planning_basis_commit_seq` | int | 本次看到的 planning 水位 | 必须是真实已提交水位 |
| `fact_candidates` | list[obj] | 冻结 C3 候选输入 | 程序包装，不允许模型改写 |
| `items` | list[obj] | 六态观察项 | 见下表 |

### `fact_candidates[]`

这是 C3 的本轮局部包装，不是第二本 facts：

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `candidate_ref` | str | 本轮局部引用 | run 内唯一，不进入全局发号器 |
| `text` | str | C3 事实候选句 | 非空 |
| `quote` | str | C1 逐字证据 | 非空且必须逐字存在于 current C1 |
| `seg` | int\|null | C2 段号 | 有则为正整数 |
| `source` | str | C3 生产来源 | 非空模型／文件身份 |

### `items[]`

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `item_key` | str | run 内观察项引用 | run 内唯一 |
| `planned_ref` | str\|null | PE／H／MC | `unplanned` 必须为 null，其余必须是真实 current 对象 |
| `planned_rev` | int\|null | 计划对象修订 | 与 current 对象一致；`unplanned` 为 null |
| `outcome` | enum | 六态观察 | `exact`／`variant`／`unrealized`／`contradicted`／`unplanned`／`ambiguous` |
| `coverage` | enum | 本项覆盖 | `full`／`partial` |
| `variant_note` | str\|null | 变体说明 | `variant` 必须非空；其他为 null |
| `evidence_quote` | str\|null | 本项书稿证据 | exact／variant／contradicted／unplanned 必须逐字存在；unrealized 必须 null |
| `fact_candidate_refs` | list[str] | 支持本项的本轮 C3 引用 | exact／variant／contradicted／unplanned 非空；unrealized／ambiguous 为空 |
| `rationale` | str | 观察理由 | 说明腔，不得夹带作者决定 |

## 机械覆盖与写权

1. 当前 handover part 覆盖的每个 PE 必须恰好出现一次；不能漏、不能重复。
2. 重要 unplanned 可以额外出现；不得创建 PE 或拿首个 PE 代替。
3. 模型漏掉已交棒 PE 时整份候选 STRICT FAIL；程序不得伪造 ambiguous 补绿。
4. ambiguous 是合法安全弃权，可以继续保持。
5. 候选通过后，观察 writer 可以创建稳定 RE，但新边的 `actual_fact_refs=[]`、`actual_fact_basis_sha256=null`；此时没有 actual 支持权。
6. 只有后续作者 facts 准入动作才能让 confirmed C4 引用进入边。

## stale

下列任一发生，候选失效：

- C1 文本 SHA 改变；
- 目标 planning 对象 rev 改变／消失；
- slot mapping 不再把该 C1 连到该槽；
- 相同 run 已被不同载荷占用。



<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/RECONCILIATION_FACT_ADMISSION_ACTION.md git_blob=9a70d47a44cfb5a8e9effa90e7f48e7ee96d96c2 bytes=4756 -->

# 源文件：`novel-mvp/contracts/RECONCILIATION_FACT_ADMISSION_ACTION.md`

- Git blob：`9a70d47a44cfb5a8e9effa90e7f48e7ee96d96c2`
- 字节：4756
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# RECONCILIATION_FACT_ADMISSION_ACTION · 对账后 facts 准入动作

**版本：v2**（增加 current chapter revision 绑定与 VERIFIED anchor 输出；v1 保留为迁移前动作）

一句话用途：作者针对已经落成稳定 RE 的 exact／variant／contradicted／unplanned 观察，逐项确认哪些 C3 事实候选可以进入 M4 confirmed facts，并在同一事务把 confirmed 引用接回对账边。

它是一次短命 command，不是事实账、对账账本、作者签字 ledger 或第三份真源。

## 权力边界

| 项 | 规则 |
|---|---|
| actor | 只允许 `author` |
| 模型 | 只能提供上游观察和 C3 候选，不能构造或提交本动作 |
| facts | 只由 M4 规则接纳；动作不能指定 f／F- 编号 |
| planstore | 只更新动作点名的 current RE；不得改原计划文字 |
| actual | 不写裸 actual 字段；只可能形成可回验的 exact／variant 派生支持 |

## 顶层字段

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `contract` | str | 合同身份 | 固定 `RECONCILIATION_FACT_ADMISSION_ACTION` |
| `version` | str | 版本 | 固定 `v2` |
| `operation_id` | str | 幂等动作号 | 同号同载荷回放；同号不同载荷拒绝 |
| `actor` | enum | 动作主体 | 只允许 `author` |
| `reconcile_run_id` | str | 上游观察 run | 必须与候选一致 |
| `candidate_sha256` | str | 整份候选摘要 | canonical JSON SHA-256 exact match |
| `chapter_ref` | str | 当前 C1 | 与候选、RE、slot mapping 一致 |
| `chapter_revision_ref` | obj | 当前 C11 revision | `{chapter_id, revision_no, revision_text_sha256}`；必须与 C1、candidate、RE 完全一致 |
| `chapter_text_sha256` | str | 当前书稿摘要 | 与 current C1、候选、RE 一致 |
| `decisions` | list[obj] | 作者逐边确认 | 非空；edge 不能重复 |

### `decisions[]`

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `edge_ref` | str | 稳定 RE | 必须 active、current 且属于本轮候选 |
| `edge_rev` | int | 作者看到的边修订 | 必须等于 current rev |
| `fact_candidate_refs` | list[str] | 作者确认的本轮 C3 候选 | 非空、run 内真实、逐条有 C1 证据 |
| `reconciliation_action` | enum\|null | 对差异的作者处置 | 见下表 |
| `note` | str | 作者说明 | 可空串 |

## 六态准入表

| outcome | facts 准入 | `reconciliation_action` |
|---|---|---|
| `exact` | 作者逐条确认后允许 | 必须 null；事实确认本身已经是作者签字 |
| `variant` | 允许 | 当前书稿赢时固定 `accept_as_is`；要改稿则不走本动作 |
| `contradicted` | 允许把当前书稿事实入账 | 必须 `accept_as_is`；`rewrite_draft` 只回写作区，当前动作不得入账 |
| `unplanned` | 允许重要新增入账 | 必须 `accept_as_is`；不得顺手创建 PE |
| `unrealized` | 不存在书稿事实 | 禁止进入本动作；规划处置走既有 planstore 路径 |
| `ambiguous` | 当前不能安全确认事实 | 禁止进入本动作；可以继续保持 ambiguous |

## 写前硬门

执行前必须同时满足：

1. action、candidate、current C1、active mapping、current RE 属于同一章槽，并引用同一个 C11 current revision；
2. candidate SHA、C1 SHA、chapter revision ref、planned rev、edge rev 全部 current；
3. 每个确认的 quote 逐字存在于 C1；
4. facts 载荷只能来自候选冻结的 C3 条目，作者不能借 action 自造隐藏字段；
5. RE 尚未接入其他 confirmed facts；
6. facts.json、plan.json、history、blob、commit log 可以经 [factstore.py](../mvp/factstore.py) 进入同一恢复事务；`reconcile.py` 不得另留 facts 裸写入口。

任一失败都在写前拒绝，facts 与 planstore 都保持 0 变化。不得先写 facts 再补 RE，也不得因 PE 已安排而自动生成事实。

## 成功结果

成功事务只做：

- M4 分配内部 `f…`，写 C4 v1 `status=confirmed`、current `chapter_revision_ref`、C1 quote、source 和作者确认时间；
- 对逐字 quote 计算 Unicode codepoint 半开坐标与 slice SHA，写 `anchor_state=VERIFIED` 和正式 `anchor_ref`；
- RE 写 `actual_fact_refs` 与事实基线摘要，rev +1；
- variant／contradicted／unplanned 写既有 `author_decision=accept_as_is`；
- history／blob／commit log 留痕。

原 C1、原计划文字、PE `digest_status` 和其他真值对象不得被改写。

## v1 backward compatibility

- v1 action 没有 chapter revision ref，只能在项目仍处于 legacy C1／C4／plan r06 时使用。
- 项目迁移到 C11／C1 v1 后，v1 action 必须 fail closed；不能通过“当前只有一版”猜 ref。
- 现役 `reconcile.py` 仍实现 v1，本票只冻结 v2 正式合同；产品升级另开施工票。


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/WRITING_DESK_WORK_DRAFT.md git_blob=3f2559e3995d4a348231d218dcfe50771aa58c3a bytes=4304 -->

# 源文件：`novel-mvp/contracts/WRITING_DESK_WORK_DRAFT.md`

- Git blob：`3f2559e3995d4a348231d218dcfe50771aa58c3a`
- 字节：4304
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# WRITING_DESK_WORK_DRAFT · 写作区工作稿

**版本：v1**

一句话用途：保存同一章槽下作者正在编辑的当前工作稿，并用单调修订号区分 current 与 stale；它不是章节书稿、冻结证据或真值。

## 1. 合同身份与 owner

| 项 | 正式规则 |
|---|---|
| `contract` | 固定 `"WRITING_DESK_WORK_DRAFT"` |
| `version` | 固定 `"v1"` |
| owner | 写作区工作稿 owner；不属于 planstore、C1、事实账或章节版本库 |
| 身份来源 | 由稳定章槽 `slot_ref` 派生，不发全局工作稿 ID |
| 当前内容 | 只保存作者当前工作态资产；不得由 AI 改写、补写、续写或润色 |

物理存储是写作区实现细节，可复用现有本地工作区保存机制；本合同不新建 manuscript 数据库、第二章节库或工作稿账本。当前工作稿必须能在中断后恢复，但不能因此获得 C1、冻结书稿、事实证据或 actual 身份。

## 2. 派生身份

稳定 lineage：

```text
S-0001@work
```

可读修订身份：

```text
S-0001@work-r2
```

`work_ref` 固定由 `slot_ref + "@work"` 派生；可读修订身份由 `work_ref` 与 `work_rev` 组合。两者都不是新持久 ID，不进入任何 `id_counters`。

## 3. 完整字段

除下表外不得自造字段：

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `contract` | str | 合同名 | 固定 `"WRITING_DESK_WORK_DRAFT"` |
| `version` | str | 合同版本 | 固定 `"v1"` |
| `work_ref` | str | 工作稿 lineage | 必须由 `slot_ref` 派生 |
| `slot_ref` | str | 所属稳定章槽 | 必须指向当前项目中存在的 `chapter_slot.id` |
| `source_outline_ref` | str | 打开写作区时消费的章纲版本 | 必须是该章当时可消费的 current outline 身份 |
| `work_rev` | int | 当前工作稿修订号 | 首次保存为 1；作者内容改变时严格 +1 |
| `state` | str | 工作态 | 固定 `"working"` |
| `entry_mode` | enum | 作者文字从哪里进入 | `typed`／`pasted`／`edited`；只记入口，不改变权力 |
| `text` | str | 作者当前原文 | 逐字保存，不规范化、不改标点 |
| `text_sha256` | str | 当前原文摘要 | 对 UTF-8 原文计算 SHA-256；只做完整性校验，不是第二身份 |
| `last_operation_id` | str | 最近成功保存动作 | 复用全局 `operation_id` 幂等原语 |

合法示例：

```json
{
  "contract": "WRITING_DESK_WORK_DRAFT",
  "version": "v1",
  "work_ref": "S-0001@work",
  "slot_ref": "S-0001",
  "source_outline_ref": "S-0001@outline-r2",
  "work_rev": 2,
  "state": "working",
  "entry_mode": "edited",
  "text": "作者逐字输入的当前工作稿",
  "text_sha256": "...",
  "last_operation_id": "op-work-edit-r2"
}
```

## 4. 保存动作与 revision

保存动作沿用候选已经验证的输入：

```json
{
  "operation_id": "op-work-edit-r2",
  "slot_ref": "S-0001",
  "source_outline_ref": "S-0001@outline-r2",
  "expected_rev": 1,
  "entry_mode": "edited",
  "author_text": "作者原文"
}
```

规则：

- 首次创建要求 `expected_rev=0`，成功得到 `work_rev=1`；
- 后续保存要求 `expected_rev` 等于 current `work_rev`，成功后严格 +1；
- stale `expected_rev` 写前拒绝，返回 `STALE_WORK_REVISION`；
- 相同 `operation_id` 与相同载荷重放返回原结果，不增加 revision；
- 相同 `operation_id` 携带不同载荷拒绝；
- 不新增工作稿专用 dedupe key 或第二套幂等系统；
- 本版不冻结完整旧稿历史树。当前工作稿是可恢复的作者资产；旧 revision 只按现有操作回执／摘要能力追踪，不复制长期全文。

作者是否能显式选择历史工作稿版本交棒继续开放；普通消费者只能使用 current revision。

## 5. 权力边界

```text
work draft
≠ C1 ChapterDoc
≠ frozen manuscript
≠ fact evidence
≠ actual
```

保存、自动保存或人工修改工作稿都不得自动：

- 创建 C1；
- 创建 F- 或写 facts；
- 修改 actual；
- 冻结书稿；
- 触发交棒；
- 收工或关章；
- 自动打开下一章。

工作稿的直接消费者只有写作区当前编辑、检测侧读取，以及正式收工／交棒动作层。检测结果、收工动作和交棒动作各有自己的身份，不能用“文件存在”代替作者动作。

来源：Codex


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/WORK_DRAFT_HANDOVER_ACTION.md git_blob=69467c245875eb181412a3117d17a4a9d1e00fac bytes=4214 -->

# 源文件：`novel-mvp/contracts/WORK_DRAFT_HANDOVER_ACTION.md`

- Git blob：`69467c245875eb181412a3117d17a4a9d1e00fac`
- 字节：4214
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# WORK_DRAFT_HANDOVER_ACTION · 工作稿显式交棒动作

**版本：v2**

一句话用途：作者明确选择“以这篇为准”时，把一个 current work revision 送到 C1 接收边界。它是短命命令，不是 C1、账本、事实承认、actual、对账或关章。

本合同不用 C8／C9 等全局编号；这些编号已有正式含义。

## 1. 完整字段

除下表外不得自造字段：

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `contract` | str | 合同名 | 固定 `"WORK_DRAFT_HANDOVER_ACTION"` |
| `version` | str | 合同版本 | 固定 `"v2"` |
| `operation_id` | str | 本次动作号 | 复用现有幂等原语 |
| `actor` | enum | 谁明确交棒 | 固定 `author` |
| `intent` | enum | 作者意图 | 固定 `adopt_as_manuscript` |
| `work_ref` | str | 工作稿 lineage | 必须指向 current work draft |
| `work_rev` | int | 工作稿修订号 | 必须等于 current revision |
| `slot_ref` | str | 对应稳定章槽 | 必须与工作稿一致 |
| `source_outline_ref` | str | 工作稿所见章纲版本 | 必须与工作稿一致 |
| `chapter_title` | str | 作者这次明确确认的 INITIAL 章标题 | 单行、非空、已去掉首尾空白；不允许系统猜测或默认“未命名章节” |
| `target_contract` | str | 目标接收边界 | 固定 `C1_CHAPTER_DOC` |
| `target_planstore_result` | str | C1 成功后的规划账目标 | 固定 `handover_parts` |

合法示例：

```json
{
  "contract": "WORK_DRAFT_HANDOVER_ACTION",
  "version": "v2",
  "operation_id": "op-handover-work-r2",
  "actor": "author",
  "intent": "adopt_as_manuscript",
  "work_ref": "S-0001@work",
  "work_rev": 2,
  "slot_ref": "S-0001",
  "source_outline_ref": "S-0001@outline-r2",
  "chapter_title": "雨夜来信",
  "target_contract": "C1_CHAPTER_DOC",
  "target_planstore_result": "handover_parts"
}
```

## 2. current／stale 硬门

提交前必须确认 `work_ref`、`work_rev`、`slot_ref` 与 `source_outline_ref` 全部对应同一 current work draft。

若 `work-r1` 已被作者修改为 `work-r2`，普通交棒动作再次引用 r1 必须在任何 C1 或 planstore 写入前返回 `STALE_WORK_REVISION`。不得默默改用 r2、提交 r1，或因内容相似放行。

作者将来是否可以显式选择历史工作稿 revision 交棒继续开放；本版不新增这项能力。

## 3. 正式路由

```text
current work-rN
    ↓ 作者明确“以这篇为准”
WORK_DRAFT_HANDOVER_ACTION v2
    ↓
AWAITING_C1_ACCEPTANCE
    ↓ C1 接收并验证
合法 C1 chapter identity
    ↓
planstore 才可追加 handover_parts
```

动作携带工作稿引用和作者确认的 `chapter_title`，不复制工作稿全文。C1 接收端通过 `work_ref + work_rev` 从写作区工作稿 owner 取得作者原文。INITIAL 成功后，标题的长期 owner 立即变为 `C11.revisions[].title`，C1 只物化 current C11 标题；不另建第二本标题账。动作本身不能创建或伪造 C1/C11。

`slot.title_hint`、C10 `TITLE` 材料和文件名都不能替代 `chapter_title`。空标题、自动生成标题或占位标题都必须在 C10/C11/C1 写入前回作者。

只有 C1 成功返回合法 `chapter_id` 后，planstore 才能走已有 `handover_parts` 路径。C1 拒绝、尚未完成或 chapter identity 缺失时，规划账写入必须为 0。

## 4. 权力边界

保存工作稿、检测、full-check、skip-check、no-prose 或文件存在都不能产生本动作。只有 `actor=author` 且 `intent=adopt_as_manuscript` 才能进入交棒路由。

本动作不得携带或直接修改：

- C1 字段或冻结状态；
- `handover_parts`、`slot_status`、`truth_bearing`；
- facts／F-／actual；
- 对账结果；
- chapter close 或自动开下一章。

planstore 落账后原计划仍作为“当初的打算”保留；交棒不自动改写原计划文字，也不自动生成对账边。

## 5. v1 兼容边界

v1 没有 `chapter_title`，只能保留给旧 planstore 回归和历史读取。它不再是正式 INITIAL 路由，不得由文件名、`slot.title_hint`、旧 CLI `--title` 或其他调用者参数补齐后冒充 v2。现行 AuthorWorkspace 交棒 preflight 只接受 v2。

来源：Codex


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/WRITING_DESK_CHECK_RESULT.md git_blob=e6234a935e5986508a05c24c4b7242da783e07f4 bytes=8958 -->

# 源文件：`novel-mvp/contracts/WRITING_DESK_CHECK_RESULT.md`

- Git blob：`e6234a935e5986508a05c24c4b7242da783e07f4`
- 字节：8958
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# WRITING_DESK_CHECK_RESULT · 写作区当场检测结果

**版本：v1**

一句话用途：保存 T14 对一份确定工作稿、确定章纲和确定检查范围完成的诊断结果，供 `full_check` 收工动作引用。它不是全绿证明，不修改工作稿、规划或真值。

本合同使用描述名，不占 C8／C9，也不增加全局检测结果发号器。

## 1. 身份与 owner

| 项 | 正式规则 |
|---|---|
| `contract` | 固定 `"WRITING_DESK_CHECK_RESULT"` |
| `version` | 固定 `"v1"` |
| owner | 写作区 T14 检测侧；不是 planstore、C1、事实账或章节状态 owner |
| 结果身份 | 由 current `work_ref`、`work_rev` 与现有 `operation_id` 派生 |
| 直接消费者 | [WRITING_DESK_CLOSEOUT_ACTION.md](WRITING_DESK_CLOSEOUT_ACTION.md) 的 `full_check` 路线 |
| 真值效力 | 无；诊断结果不能创建 F-、actual、PE、作者签字或关章状态 |

正式结果引用形如：

```text
S-0001@work-r2#check-op-t14-01
```

程序按下面的关系派生：

```text
<work_ref>-r<work_rev>#check-<operation_id>
```

它不进入任何 `id_counters`。相同 `operation_id` 继续复用现有幂等语义；模型不能生成或修改结果身份。

## 2. 完整字段

除下表外不得自造字段：

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `contract` | str | 合同名 | 固定 `"WRITING_DESK_CHECK_RESULT"` |
| `version` | str | 合同版本 | 固定 `"v1"` |
| `check_result_ref` | str | 本次检测结果身份 | 必须按 §1 派生 |
| `operation_id` | str | 本次检测动作号 | 复用现有幂等原语 |
| `slot_ref` | str | 所属稳定章槽 | 必须存在，且与工作稿、章纲同章 |
| `work_ref` | str | 被检查的工作稿 lineage | 必须指向该章 current 工作稿 |
| `work_rev` | int | 被检查的工作稿修订号 | 必须等于 current revision |
| `work_text_sha256` | str | 被检查正文摘要 | 对作者原文 UTF-8 字节计算 SHA-256 |
| `source_outline_ref` | str | 对照的章纲版本 | 必须是该章当时可消费的 current outline |
| `source_commit_seq` | int | 该章规划输入水位 | 必须等于 outline checkpoint 绑定的本章水位 |
| `input_package_sha256` | str | 本次冻结检测输入摘要 | 对程序冻结的实际输入包计算 SHA-256，不复制输入全文 |
| `scope` | object | 机械检查范围 | 形状见 §3，由程序提供 |
| `status` | str | 本次执行状态 | 合法正式结果固定 `"completed"` |
| `judgments` | list[object] | 五类语义诊断 | 形状见 §4 |

合法示例：

```json
{
  "contract": "WRITING_DESK_CHECK_RESULT",
  "version": "v1",
  "check_result_ref": "S-0001@work-r2#check-op-t14-01",
  "operation_id": "op-t14-01",
  "slot_ref": "S-0001",
  "work_ref": "S-0001@work",
  "work_rev": 2,
  "work_text_sha256": "...",
  "source_outline_ref": "S-0001@outline-r2",
  "source_commit_seq": 1401,
  "input_package_sha256": "...",
  "scope": {
    "mode": "chapter",
    "target_ref": "S-0001",
    "requirement_refs": ["PE-1401"]
  },
  "status": "completed",
  "judgments": [
    {
      "category": "covered",
      "requirement_ref": "PE-1401",
      "evidence_quote": "林乔从维修柜底层找到了那张发黄的旧工单。",
      "explanation": "工作稿明确写出林乔取得旧工单。"
    }
  ]
}
```

## 3. coverage

`scope` 只允许三个字段：

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `mode` | enum | 检查粒度 | `scene`／`chapter` |
| `target_ref` | str | 实际检查对象 | `chapter` 时必须等于 `slot_ref`；`scene` 时必须引用该章已有稳定场／段对象 |
| `requirement_refs` | list[str] | 本次实际检查的 PE／约束引用 | 由程序从 current outline 与合法约束来源冻结，不允许模型删改 |

每个 `requirement_ref` 必须恰好出现一次 planned judgment，类别只能是 `covered`／`mismatch`／`missing`／`unknown`。`unplanned` 是额外 finding，不占用也不能替代既定 requirement 的判断。

局部 `scene` 结果可以合法完成，但不能满足全章 `full_check`。全章收工只接受：`mode=chapter`、`target_ref=slot_ref`、要求集合完整且逐条判定的 current 结果。模型声称“检查完成”不构成 coverage 证据。

## 4. judgments 与五类正式诊断

每条 judgment 只允许：

| 字段 | 类型 | 约束 |
|---|---|---|
| `category` | enum | `covered`／`mismatch`／`missing`／`unplanned`／`unknown` |
| `requirement_ref` | str\|null | `covered`／`mismatch`／`missing`／`unknown` 必须引用输入中的真实 requirement；`unplanned` 必须为 null |
| `evidence_quote` | str\|null | `covered`／`mismatch`／`unplanned` 必须逐字存在于工作稿；`missing` 必须为 null；`unknown` 有可定位原文时必须逐字引用 |
| `explanation` | str | 只解释诊断理由，不得携带修稿文本或处置决定 |

五类语义固定如下：

| 类别 | 正式语义 | 权力边界 |
|---|---|---|
| `covered` | 当前 requirement 在已检查工作稿中得到足够承接 | 不等于整章全绿；必须有合法工作稿证据 |
| `mismatch` | 工作稿已经写出内容，但与当前 requirement／约束不一致 | 只诊断，不自动改稿或改计划 |
| `missing` | 当前明确 requirement 应在该范围内覆盖，但没有找到 | 不自动补写正文 |
| `unplanned` | 工作稿出现当前有效章纲／计划没有安排的新增内容 | 只进入后续作者对账候选，不创建 F-、actual 或 PE |
| `unknown` | 当前材料不足或表达模糊，不能安全归入其他四类 | 不得 fallback 为 covered、mismatch 或 missing |

同一段工作稿可以让既定 PE 得到 `covered`，同时再产生一条 `unplanned`。两者不是互斥枚举，不能用计划外 finding 吞掉既定 PE 的覆盖判断。

## 5. requirement 与 must-not 引用

结果只引用约束来源，不复制第二份约束真源：

- 来源已有稳定 ID 时，直接复用该 ID；
- 当前章纲的 `must_not` 仍只有字符串时，程序按下面格式派生引用：

```text
<source_outline_ref>#must_not:<SHA-256("must_not\0" + 约束原文) 的前 12 位>
```

派生引用不进入 `id_counters`，也不给检测侧新增规则裁决权。接收端必须能从 `source_outline_ref` 对应的真实来源解析它；解析不到、来源跨章或来源已经 stale 时写前拒绝。模型自造约束 ID、只凭显示文本匹配或在结果里复制可独立修改的 must-not，都不是合法引用。

界面可以从真实来源编译人话显示，但显示文本只是 projection，不是 T14 保存的新约束。

## 6. 双版本 current／stale

结果只有同时满足下面两组条件才是 current：

### 工作稿

- `work_ref` 等于当前章的工作稿 lineage；
- `work_rev` 等于 current revision；
- `work_text_sha256` 等于 current 作者原文摘要。

作者从 work-r2 改到 work-r3 后，r2 结果保留可追，但立即失去 current `full_check` 消费资格。不得按章号模糊接受旧结果，也不得静默抬高旧 revision。

### 章纲

- `source_outline_ref` 等于当前可消费章纲身份；
- `source_commit_seq` 等于该章 outline checkpoint 绑定的 planning baseline。

同章 planning 更新使 outline stale 时，引用旧 outline 的检测结果同步 stale。跨章 planning 更新不得误伤本章结果。旧结果不复制 planning snapshot，也不能静默改绑新水位。

## 7. “检测完成”不等于“全绿”

```text
VALID_CHECK_RESULT != ALL_CLEAR
```

`status=completed` 只表示：Schema 合法、版本绑定有效、coverage 完整、所有既定 requirement 已判定。即使 judgments 中含有 `mismatch`、`missing`、`unplanned` 或 `unknown`，结果仍可以是一次合法完成的检测，并供 `full_check` 引用。

本合同没有 `pass`、`clean`、`checked` 或 `all_clear` 字段。未来关章 QC 如需全绿标准，必须另走自己的合同；不得倒灌到 T14 检测完成语义。

## 8. 模型与程序分权

模型只负责：

- finding 分类；
- 从工作稿选择证据；
- 给出诊断理由。

程序负责：

- `check_result_ref` 与 `operation_id`；
- work／outline／planning baseline 绑定；
- requirement 与 constraint 引用合法性；
- coverage；
- Schema 与 stale 判定。

模型不能发正式 result ID、修改 work／outline revision、新建 must-not、扩大 scope 或给自己签 current。

## 9. 禁止字段与写入边界

正式结果不包含并必须拒绝：

- `replacement_text`／`rewritten_prose`／`generated_dialogue`；
- `automatic_fix`／`applied_patch`／工作稿 mutation；
- plan mutation／自动新增 PE；
- facts／F-／actual；
- author decision／handover／chapter close。

T14 结果只诊断。作者改工作稿、忽略 finding 或反向改计划，属于下一阶段的作者处置动作，本合同不表达也不自动选择。

来源：Codex


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/WRITING_DESK_CHECK_DISPOSITION_ACTION.md git_blob=20fc2c628f90fdbfe413c6afd44adae5009c5d37 bytes=7222 -->

# 源文件：`novel-mvp/contracts/WRITING_DESK_CHECK_DISPOSITION_ACTION.md`

- Git blob：`20fc2c628f90fdbfe413c6afd44adae5009c5d37`
- 字节：7222
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# WRITING_DESK_CHECK_DISPOSITION_ACTION · T14 mismatch 作者处置动作

**版本：v1**

一句话用途：作者针对一个 current `mismatch` finding，明确选择回去改工作稿、当前保持规划不改，或进入既有规划编辑入口。它是一次短命 command，不是检测结果、账本、真值或“问题已解决”状态。

本合同使用描述名，不占 C8／C9，也不增加 disposition ledger 或全局 finding 发号器。

## 1. 身份与 owner

| 项 | 正式规则 |
|---|---|
| `contract` | 固定 `"WRITING_DESK_CHECK_DISPOSITION_ACTION"` |
| `version` | 固定 `"v1"` |
| owner | 写作区作者动作层 |
| actor | 只允许 `author`；禁止 `model`／`auto` |
| 直接输入 | current [WRITING_DESK_CHECK_RESULT v1](WRITING_DESK_CHECK_RESULT.md) 中的一条 `mismatch` finding |
| 生命周期 | 短命 command；消费后丢弃，只保留必要运行／幂等回执 |
| 真值效力 | 无；不能创建 F-、actual、handover 或 chapter close |

系统可以自动检测 mismatch，但不能替作者决定改工作稿还是改规划。小白自动档也不能获得本动作的 actor 权力。

## 2. finding 派生引用

正式 check result 的 judgment 不增加全局 finding ID。本动作按不可变结果内容派生引用：

```text
<check_result_ref>#finding:<SHA-256(category + "\0" + requirement_ref + "\0" + evidence_quote + "\0" + explanation) 前 12 位>
```

它不进入 `id_counters`。接收端必须从 `check_result_ref` 解析原结果并重新计算；不得按标题、显示文本或“最相似 finding”静默匹配。

## 3. 完整字段

除下表外不得自造字段：

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `contract` | str | 合同名 | 固定 `"WRITING_DESK_CHECK_DISPOSITION_ACTION"` |
| `version` | str | 合同版本 | 固定 `"v1"` |
| `operation_id` | str | 本次作者动作号 | 复用现有幂等原语 |
| `actor` | enum | 谁决定处置方向 | 固定 `author` |
| `check_result_ref` | str | 来源检测结果 | 必须解析到 current 正式结果 |
| `finding_ref` | str | 具体 finding 派生引用 | 必须属于该 check result，且类别为 `mismatch` |
| `work_ref` | str | 当前工作稿 lineage | 必须与 check result 和 current work 一致 |
| `work_rev` | int | 当前工作稿修订号 | 必须与 check result 和 current work 一致 |
| `source_outline_ref` | str | 当前章纲身份 | 必须与 check result 和 current outline 一致 |
| `source_commit_seq` | int | 当前本章 planning baseline | 必须与 check result 和 current outline checkpoint 一致 |
| `route` | enum | 作者选择下一步去哪里 | `edit_work`／`keep_plan`／`edit_plan` |

合法示例：

```json
{
  "contract": "WRITING_DESK_CHECK_DISPOSITION_ACTION",
  "version": "v1",
  "operation_id": "op-disposition-01",
  "actor": "author",
  "check_result_ref": "S-1402@work-r2#check-op-live-02",
  "finding_ref": "S-1402@work-r2#check-op-live-02#finding:...",
  "work_ref": "S-1402@work",
  "work_rev": 2,
  "source_outline_ref": "S-1402@outline-r2",
  "source_commit_seq": 1402,
  "route": "edit_work"
}
```

动作只携带引用，不复制完整 finding、工作稿、章纲、plan snapshot 或替换正文。

## 4. 三条正式 route

### `edit_work`

语义：作者选择保持规划不变，回到工作稿编辑。

动作只返回现有 `WRITING_DESK_WORK_DRAFT v1` 作者保存入口，等价运行边界为 `AWAITING_WORK_EDIT`。它不得携带 replacement prose、修改工作稿、生成新 revision 或调用写作模型。

作者真正修改并保存后：

```text
work-r2
→ author save
→ work-r3
→ old check result stale
→ recheck required
```

旧 disposition 不能把旧结果恢复 current，也不能宣称 mismatch 已解决。

### `keep_plan`

语义：作者看见 mismatch，当前既不改工作稿，也不改规划；规划继续维持现有权力。

正式硬边界是 **0 mutation**：

- work draft diff = 0；
- outline diff = 0；
- planstore diff = 0；
- facts／F-／actual = 0。

原 finding 继续是 `mismatch`，不得改成 covered、resolved、all-clear 或 dismissed-as-correct。原 check result 仍可以作为一次 current、完整检测被 full-check 引用，因为 `VALID_CHECK_RESULT != ALL_CLEAR`。

本动作不写 `deviation_note`，也不新增 `ignored_finding` 数组或 disposition ledger。若未来确有长期消费者需要记住“作者已看过”，必须另行证明谁读取、保存多久、是否改变业务判断，以及 work／outline 变化后怎样失效。

### `edit_plan`

语义：作者认为当前工作稿方向才是自己现在想要的，进入已有合法规划编辑入口。

动作只返回 `AWAITING_PLAN_EDIT`。它不得携带 plan patch、直接写 planstore、创建或删除 PE，或修改 outline checkpoint。

真正规划变化继续走现有作者确认写回边界：

```text
mismatch finding
→ author chooses edit_plan
→ disposition action
→ existing author plan-edit boundary
→ actor=author / action=update + commit
→ planning baseline advances
→ old outline stale
→ old check result stale
```

不为这条路新增通用 planning action 合同。

## 5. 写前硬门

提交前必须同时确认：

1. `check_result_ref` 解析到 current 正式结果；
2. work ref、revision 与正文摘要仍满足该结果的 current 条件；
3. outline ref 与本章 baseline 仍满足该结果的 current 条件；
4. `finding_ref` 属于指定 check result；
5. finding 类别严格等于 `mismatch`；
6. `actor=author`；
7. route 属于本合同三个枚举。

任一项失败都在路由或写入前拒绝。不得 fallback 到最新 finding、相似文本、当前最新 work 或最新 outline。

## 6. 其他四类 finding

本合同只消费 `mismatch`：

- `covered` 不生成 disposition 待办；
- `missing` 保持 missing，不自动补写，也不套本合同三选；
- `unplanned` 保持规划外新增诊断，不创建 PE、F- 或 actual；
- `unknown` 保持 unknown，不强迫作者选择确定答案。

missing、unplanned、unknown 将来需要什么作者动作，必须按各自语义另案验证，不能借本合同提前冻结。

## 7. “选择路线”不等于“解决问题”

动作没有并必须拒绝：

- `resolved`／`all_clear`／`finding_status=covered`；
- replacement prose／自动改稿；
- plan patch／直接 planstore 写入；
- facts／F-／actual；
- handover／chapter close。

`edit_work` 和 `edit_plan` 只有在各自上游真正产生新 revision／commit 后，才会通过 stale 传播淘汰旧结果；随后仍需重新检测。`keep_plan` 没有上游变化，因此 mismatch 原样保留。

## 8. 幂等与留痕

相同 `operation_id` 与相同载荷重放返回原运行回执，不重复打开工作稿编辑、规划编辑或产生第二次作者决定。相同 operation 携带不同载荷必须拒绝。

动作不新增 disposition 专用 dedupe key，也不进入 planstore history：Route B 没有账本变化，Route A 的真正修改由工作稿保存动作留自己的 operation，Route C 的真正修改由 planstore update／commit 留自己的 operation。

来源：Codex


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/WRITING_DESK_CHECK_UNKNOWN_ADJUDICATION_ACTION.md git_blob=49fc9f947b5f6ce03b0c65d7cc972f52acfa36bd bytes=6940 -->

# 源文件：`novel-mvp/contracts/WRITING_DESK_CHECK_UNKNOWN_ADJUDICATION_ACTION.md`

- Git blob：`49fc9f947b5f6ce03b0c65d7cc972f52acfa36bd`
- 字节：6940
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# WRITING_DESK_CHECK_UNKNOWN_ADJUDICATION_ACTION · T14 unknown 作者人工裁决

**版本：v1**

一句话用途：作者针对一个 current `unknown` finding，独立记录自己认为它是 covered、missing 或 mismatch。原模型 finding 永远保持 unknown，作者裁决只作为 `self_reported` 展示覆盖层。

本合同同时冻结短命 action 与其运行 receipt；不占 C8／C9，不增加全局裁决 ID，也不创建 adjudication ledger。

## 1. actor 与允许结果

actor 只允许：

```text
author
```

禁止 `model`／`auto`。允许的 `decision` 只有：

```text
covered
missing
mismatch
```

不允许 `unplanned`：它是额外计划外 finding，不是既定 requirement 的人工改类。继续保持 unknown 不需要创建本动作，也不能用 `decision=unknown` 伪造一次裁决。

## 2. finding 与裁决身份

`finding_ref` 沿用 T14 finding 派生方式：

```text
<check_result_ref>#finding:<SHA-256(category + "\0" + requirement_ref + "\0" + evidence_quote + "\0" + explanation) 前 12 位>
```

裁决 receipt 身份由 finding 与现有 `operation_id` 派生：

```text
<finding_ref>#adjudication-<operation_id>
```

两者都不进入 `id_counters`。接收端必须从指定 check result 重新解析 finding，不得按文本相似度、最新一条或界面标题匹配。

## 3. action 完整字段

除下表外不得自造字段：

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `contract` | str | action 合同名 | 固定 `"WRITING_DESK_CHECK_UNKNOWN_ADJUDICATION_ACTION"` |
| `version` | str | 合同版本 | 固定 `"v1"` |
| `operation_id` | str | 本次作者动作号 | 复用现有幂等原语 |
| `actor` | enum | 谁人工裁决 | 固定 `author` |
| `check_result_ref` | str | 来源检测结果 | 必须解析到当前可消费结果 |
| `finding_ref` | str | 具体 unknown finding | 必须属于该结果且类别严格为 unknown |
| `work_ref` | str | 被检查工作稿 lineage | 必须与结果及 current work 一致 |
| `work_rev` | int | 被检查工作稿 revision | 必须与结果及 current work 一致 |
| `source_outline_ref` | str | 被检查章纲身份 | 必须与结果及 current outline 一致 |
| `source_commit_seq` | int | 被检查本章 planning baseline | 必须与结果及 current outline checkpoint 一致 |
| `decision` | enum | 作者人工裁决 | `covered`／`missing`／`mismatch` |

合法示例：

```json
{
  "contract": "WRITING_DESK_CHECK_UNKNOWN_ADJUDICATION_ACTION",
  "version": "v1",
  "operation_id": "op-unknown-adjudication-01",
  "actor": "author",
  "check_result_ref": "S-1405@work-r2#check-op-live-05",
  "finding_ref": "S-1405@work-r2#check-op-live-05#finding:...",
  "work_ref": "S-1405@work",
  "work_rev": 2,
  "source_outline_ref": "S-1405@outline-r2",
  "source_commit_seq": 1405,
  "decision": "covered"
}
```

action 只携带引用和作者选择，不复制工作稿、章纲、finding 文本、证据引文或 plan snapshot。

## 4. receipt 完整字段

合法 action 产生下面的运行 receipt。除下表外不得自造字段：

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `contract` | str | receipt 名 | 固定 `"WRITING_DESK_CHECK_UNKNOWN_ADJUDICATION_RECEIPT"` |
| `version` | str | receipt 版本 | 固定 `"v1"` |
| `adjudication_ref` | str | 裁决派生身份 | 按 §2 派生 |
| `operation_id` | str | 来源动作号 | 与 action 相同 |
| `actor` | enum | 谁裁决 | 固定 `author` |
| `check_result_ref` | str | parent 结果 | 与 action 相同 |
| `finding_ref` | str | parent unknown finding | 与 action 相同 |
| `decision` | enum | 作者裁决 | 与 action 相同 |
| `basis` | enum | 裁决依据等级 | 固定 `self_reported` |
| `status` | enum | receipt 是否形成 | 固定 `recorded` |

receipt 是独立作者覆盖层，不是新的 check result。原正式 judgment 保持：

```text
category = unknown
```

## 5. 展示与消费者

当前写作区 finding 展示／人工清点层是唯一直接消费者。它必须并列显示：

```text
模型诊断：unknown
作者裁决：covered／missing／mismatch（self-reported）
```

不得压成“模型已确认 covered”，也不得隐藏原 unknown。

明确不消费本 receipt：

- full-check：仍只读取 current、coverage 完整的正式 check result；人工裁决前后资格不变；
- 后续检测模型：只读取 current work／outline，不把旧 receipt 当书稿证据；
- handover；
- planstore／facts／actual／关章；
- C9／M11。

若 `decision=mismatch`，写作区可以继续给作者展示改工作稿／改规划入口，但不能把原 unknown finding 偷换成正式 mismatch finding，也不能绕过各入口自己的 current 校验。

## 6. current／stale

receipt 只有同时满足下面条件，才能作为当前写作区 overlay：

1. parent check result 的 work ref、revision、文本摘要仍满足 current；
2. parent result 的 outline ref 与 planning baseline 仍满足 current；
3. finding 仍属于 parent result 且类别为 unknown；
4. 写作区当前展示／消费的 check result 仍是 receipt 的 parent。

以下任一变化都会使旧 receipt 对当前界面 stale：

- work ref／revision／文本变化；
- outline ref／planning baseline 变化；
- 重新检测产生新 `check_result_ref`，写作区切到新结果。

旧 receipt 可以作为检测侧审计工件保留，但不得迁移到新 finding、自动重放，或把新 unknown 直接判成旧 decision。它随 parent result 保存必要运行回执，不新建独立 adjudication ledger。

## 7. self_reported 边界

`basis=self_reported` 只表示作者做了人工判断。它不表示：

- 工作稿存在可逐字回引的模型证据；
- `prose_basis=verified`；
- 模型改变了 unknown 诊断；
- PE 已兑现；
- 读者已经知道；
- facts／actual 可以推进。

本合同不写 planstore 的 `prose_basis`。若未来确需把 author-covered 映射为 PE `prose_basis=self_reported`，必须另行证明 planstore 是消费者，并补独立写入、stale 与撤回规则。missing／mismatch 人工裁决不能机械写成“已成文”。

## 8. 写前硬门与幂等

提交前必须校验：

- result、work、outline、baseline 全部 current；
- finding 属于该 result 且类别为 unknown；
- actor 为 author；
- decision 属于三个正式值；
- action 不含任何额外字段。

相同 `operation_id`＋相同载荷返回同一 receipt，不重复生成裁决。相同 operation 携带不同 decision 必须拒绝；不新增专用 dedupe key。

## 9. 禁止字段与权限

action／receipt 都不包含并必须拒绝：

- evidence quote／作者说明冒充书稿证据；
- replacement prose／自动改稿；
- 原 check result mutation；
- plan patch／`prose_basis` 写入；
- PE／F-／actual／暗稿；
- full-check PASS／handover／chapter close。

来源：Codex


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/WRITING_DESK_CLOSEOUT_ACTION.md git_blob=f67a0a4929b94027871e573bee316146dd314e56 bytes=4366 -->

# 源文件：`novel-mvp/contracts/WRITING_DESK_CLOSEOUT_ACTION.md`

- Git blob：`f67a0a4929b94027871e573bee316146dd314e56`
- 字节：4366
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# WRITING_DESK_CLOSEOUT_ACTION · 写作区收工动作

**版本：v1**

一句话用途：表达作者结束本轮写作区工作的三种路线。它是一次短命命令，不是账本、章节状态、关章、冻结书稿、事实或 actual。

本合同不用 C8／C9 等全局编号；这些编号已有正式含义。

## 1. 完整字段

除下表外不得自造字段：

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `contract` | str | 合同名 | 固定 `"WRITING_DESK_CLOSEOUT_ACTION"` |
| `version` | str | 合同版本 | 固定 `"v1"` |
| `operation_id` | str | 本次动作号 | 复用现有幂等原语 |
| `actor` | enum | 谁发起收工 | 当前只允许 `author` |
| `slot_ref` | str | 操作哪个稳定章槽 | 必须存在 |
| `route` | enum | 走哪条收工路线 | `full_check`／`skip_check`／`no_prose` |
| `work_ref` | str\|null | 工作稿 lineage | 有工作稿路线必须指向 current；无书稿路线必须为 null |
| `work_rev` | int\|null | 工作稿修订号 | 有工作稿路线必须等于 current；无书稿路线必须为 null |
| `check_result_ref` | str\|null | [T14 正式检测结果](WRITING_DESK_CHECK_RESULT.md)身份 | 只允许 `full_check` 携带 |

合法 full-check 示例：

```json
{
  "contract": "WRITING_DESK_CLOSEOUT_ACTION",
  "version": "v1",
  "operation_id": "op-closeout-01",
  "actor": "author",
  "slot_ref": "S-0001",
  "route": "full_check",
  "work_ref": "S-0001@work",
  "work_rev": 2,
  "check_result_ref": "S-0001@work-r2#check-op-t14-01"
}
```

## 2. 三条路线

| `route` | 人话 | 工作稿要求 | 检测结果要求 | 明确不能表示 |
|---|---|---|---|---|
| `full_check` | 有工作稿，引用一次已完成检测后收工 | 必须 current | 必须解析到合法、current、全章 coverage 完整的 [WRITING_DESK_CHECK_RESULT v1](WRITING_DESK_CHECK_RESULT.md) | 不能自己保存 `PASS=true` |
| `skip_check` | 有工作稿，作者明确跳过检测 | 必须 current | 必须为 null | 不等于 PASS、clean、no issue 或 checked |
| `no_prose` | 当前没有工作稿，结束本轮规划／写作工作 | `work_ref`、`work_rev` 都为 null | 必须为 null | 不等于写成、关章或 actual |

`skip_check` 携带任何 `check_result_ref` 必须以 `SKIP_CHECK_MUST_NOT_REFERENCE_RESULT` 写前拒绝。`full_check` 引用不存在、未完成、work／outline 已 stale、跨章或 coverage 不是当前全章的结果，也必须写前拒绝。结果含 mismatch、missing、unplanned 或 unknown 不等于“没有检测”，不能仅凭 finding 非空拒绝这次收工引用。

## 3. 检测结果依赖口

本版消费正式 [WRITING_DESK_CHECK_RESULT.md](WRITING_DESK_CHECK_RESULT.md)：

```text
check_result_ref
→ must resolve to a valid current WRITING_DESK_CHECK_RESULT v1 owned by the detection side
```

接收端至少机械核对：

- `slot_ref`、`work_ref`、`work_rev` 与 current 工作稿完全一致；
- `work_text_sha256` 仍对应 current 作者原文；
- `source_outline_ref` 与 `source_commit_seq` 仍对应本章 current outline checkpoint；
- `scope.mode=chapter`、`scope.target_ref=slot_ref`，且 requirement coverage 完整；
- `status=completed`，Schema 与引用校验通过。

full-check 要的是“当前全章检测完整发生”，不是 `ALL_CLEAR`。接收端不能把裸 `PASS`、界面文案、局部场检测或 skip 行为伪装成正式检测结果。

## 4. 动作结果与权力边界

动作接收端可以返回与 `operation_id` 对应的幂等回执，说明：

- full-check：`completed_result_referenced`；
- skip-check：`skipped_by_author`；
- no-prose：`not_applicable_no_manuscript`；
- `handover_effect=none`；
- `chapter_close_effect=none`；
- `truth_effect=none`。

整份动作是短命传输工件，不得塞进 `plan.json` 成为 `closeout` 对象，也不得携带或触发：

- `passed`／`chapter_closed`；
- C1 创建或冻结书稿；
- facts／F-／actual；
- `handover_parts`；
- 已写章数、连续更新或字数增长；
- 自动打开下一章。

`no_prose` 动作已经可以正式表达，但“规划进度 +1”由哪个长期 owner 保存仍是 GAP。本版不得把它塞进 planstore、章节状态、actual 或新 progress ledger。TEMP 实验需要计数时只能生成标明 `NOT_FORMAL_PLANSTORE_WRITE` 的回执。

来源：Codex


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/CHAPTER_REVISION_COMMIT_ACTION.md git_blob=b7746c0ddb062b9c18ef063f44d03b12c96fa719 bytes=4913 -->

# 源文件：`novel-mvp/contracts/CHAPTER_REVISION_COMMIT_ACTION.md`

- Git blob：`b7746c0ddb062b9c18ef063f44d03b12c96fa719`
- 字节：4913
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# CHAPTER_REVISION_COMMIT_ACTION · 章节版本采用动作

**正式版本：v1**

一句话用途：作者明确要求把一个或多个已完整给出的章节内容采用为 stable chapter 的新 current revision。

它是短命 command，不保存正文历史，不自动猜目标章节。

## 顶层字段

| 字段 | 类型 | 规则 |
|---|---|---|
| `contract` | str | 固定 `CHAPTER_REVISION_COMMIT_ACTION` |
| `version` | str | 固定 `v1` |
| `operation_id` | str | 幂等动作号；同号同载荷回放，同号不同载荷拒绝 |
| `actor` | enum | 固定 `AUTHOR` |
| `intent` | enum | 固定 `ADOPT_AS_CURRENT_CHAPTER_REVISION` |
| `items` | list | 非空；整个 batch 全成或全不成 |

## `items[]`

| 字段 | 类型 | 规则 |
|---|---|---|
| `target_chapter_id` | str | 必须明确绑定现有 stable chapter |
| `expected_current_revision_no` | int | 必须等于 current，防 stale 写入 |
| `candidate_title` | str | 作者采用的本版标题 |
| `candidate_content_ref` | obj | REPLACE 必须是 C11 定义的 C10 source span；RESTORE 必须逐字段复制历史 target revision |
| `candidate_origin_material_ref` | obj/null | REPLACE 必须是精确 `{material_unit_id, identity_revision_no}`；RESTORE 必须 null |
| `candidate_text_sha256` | str | 必须等于 content ref 逐字正文 SHA |
| `change_kind` | enum | `REPLACE`／`RESTORE` |
| `restores_revision_no` | int/null | RESTORE 必填，REPLACE 必须 null |
| `target_basis` | enum | `EXPLICIT_CHAPTER_ID`／`EXPLICIT_SLOT_MAPPING`／`AUTHOR_CONFIRMED_CANDIDATE` |
| `reason` | str | 可空但不能省略 |

## Target 门

- 章卡、已绑定 planstore slot 或作者确认候选可以提供明确 target。
- 文件名、标题、章号、内容相似度只能产生候选，不能直接构造本动作。
- 无明确 target、多个候选或标题冲突时返回 `NEEDS_TARGET_CONFIRMATION`，正式写入为 0。
- 任何 item target／revision／content／anchor effects 预检失败，整个 batch 写入为 0。

## C10 current eligibility 门

- INITIAL 建立 ledger r1、REPLACE 采用新内容前，都必须引用唯一存在的 C10 material unit 与它当前最后一条 identity revision。
- 现役 C10 validator 必须判定该 current identity 为 `CONFIRMED + CHAPTER`；Setting／Intro／Title／Tags／Unknown／Candidate 全部拒绝。
- action content ref 的 source id、parent source SHA、坐标系、start、end、slice SHA 必须和同一 C10 material object 的 `source_ref` 逐字段相同。
- 作者 action 不能携带或改写 `role`、`state`、`basis`、identity actor 或同义字段；作者采用版本不等于作者改判材料身份。

### INITIAL 唯一机器入口

- INITIAL 不扩成 `items[].change_kind` 新枚举；它只通过正式组合入口 `validate_initial_commit(ledger, material_records)` 预检。
- 该入口必须一次执行 ledger Schema、r1/r2 kind 位置、origin material ref 和 current C10 eligibility；四门不能拆开后由调用方任选。
- 缺少 C10 material records／resolver、material unit 不存在或引用无法回验时必须拒绝，不能降级成只调用 ledger 结构 helper。
- ledger 内部结构 helper 不是写入授权，不得被 INITIAL writer 当成正式入口。

## RESTORE 两道顺序预检门

RESTORE 是同一次提交内顺序执行的两道预检，不是两个持久命令，也不产生 pending 状态：

1. `RESTORE_LINEAGE`：`restores_revision_no` 必须指向同一 stable chapter 的真实历史 revision；action 的 title、text SHA、content ref 必须逐字段复制该历史 target，`candidate_origin_material_ref` 必须为 null。
2. `REACTIVATE_CURRENT`：只从历史 target 的 `origin_material_ref.material_unit_id` 加载当前 C10 record；当前 identity 仍须是 `CONFIRMED + CHAPTER`，且当前 C10 source ref 必须与历史 target content ref 逐字段相同。

两门都通过才原子追加 `change_kind=RESTORE` 的新 revision。lineage 通过但 reactivation 失败仍返回 REJECTED、整个 batch 0 写入；历史 revision 不删不改。`LEGACY_C1_SNAPSHOT` 没有可复核的当前 C10 material ref，必须 fail closed。

## NO_CHANGE 与幂等

- candidate SHA 等于 current revision 时返回 `NO_CHANGE`，不新增 revision，不写 C1／facts／projection／planstore。
- 同 operation ID＋同载荷返回原回执并标 `replayed=true`。
- 同 operation ID＋不同载荷拒绝 `OPERATION_ID_PAYLOAD_CONFLICT`。

## 权力边界

- `actor=MODEL` 或缺少作者采用 intent 一律拒绝。
- 动作不能发新 chapter_id、修改已提交 revision、直接改 C4 status、修改规划文字或写裸 actual。
- C10 material 可以先独立保存；未通过 current eligibility 门的材料不获得 current chapter 权力。

来源：CZ 2026-08-18 `M1-M4-CONTRACT-01__CHAPTER_REVISION_LEDGER_AND_REVISION_AWARE_CONSUMER_FORMALIZATION`


<!-- SURVEY_PACK_SOURCE pack=PACK_02 path=novel-mvp/contracts/CHAPTER_REVISION_COMMIT_RECEIPT.md git_blob=553278b4166c098f0fab95228960f62fa16e8ad4 bytes=2070 -->

# 源文件：`novel-mvp/contracts/CHAPTER_REVISION_COMMIT_RECEIPT.md`

- Git blob：`553278b4166c098f0fab95228960f62fa16e8ad4`
- 字节：2070
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# CHAPTER_REVISION_COMMIT_RECEIPT · 章节版本提交回执

**正式版本：v1**

一句话用途：记录一次 revision action 的机械结果、幂等状态和跨 owner 写入计数；它不拥有正文或事实真值。

## 字段

| 字段 | 类型 | 规则 |
|---|---|---|
| `contract` | str | 固定 `CHAPTER_REVISION_COMMIT_RECEIPT` |
| `version` | str | 固定 `v1` |
| `operation_id` | str | 对应 action |
| `transaction_id` | str/null | COMMITTED 时非空；写前拒绝可为 null |
| `status` | enum | `COMMITTED`／`NO_CHANGE`／`REJECTED`／`NEEDS_TARGET_CONFIRMATION`／`NEEDS_MANUAL_RECOVERY` |
| `replayed` | bool | 是否返回已存在的同载荷结果 |
| `reason_code` | str/null | 拒绝或恢复原因；成功／NO_CHANGE 为 null |
| `items` | list | 每个 action item 的结果 |
| `writes` | obj | 各 owner 实际写入数量 |

### `items[]`

| 字段 | 类型 | 规则 |
|---|---|---|
| `chapter_id` | str | stable target |
| `before_revision_no` | int | action 看到的 current |
| `after_revision_no` | int | COMMITTED 时 +1；NO_CHANGE 时不变 |
| `result` | enum | `REVISION_APPENDED`／`UNCHANGED`／`REJECTED` |
| `text_sha256` | str | 候选／current SHA |
| `facts_migrated` | int | 保持 current status 并前进 anchor 的事实数 |
| `facts_needs_recheck` | int | 退出现行真值消费的事实数 |

### `writes`

固定字段：

```text
ledger_records
c1_current_views
facts
projection_receipts
planstore_reconciliation_edges
planstore_history_rows
```

全部为非负整数。

## 状态规则

- `COMMITTED`：所有 owner 都是完整 after，不能物理 rollback。
- `NO_CHANGE`：所有 writes 必须为 0，revision 不增加。
- `REJECTED`／`NEEDS_TARGET_CONFIRMATION`：所有 writes 必须为 0。
- `NEEDS_MANUAL_RECOVERY`：发现文件 SHA 不属于冻结 before／after；不得猜测、补写或宣布成功。
- 一次 batch 不能同时出现 COMMITTED 与 REJECTED item。

来源：CZ 2026-08-18 `M1-M4-CONTRACT-01__CHAPTER_REVISION_LEDGER_AND_REVISION_AWARE_CONSUMER_FORMALIZATION`
