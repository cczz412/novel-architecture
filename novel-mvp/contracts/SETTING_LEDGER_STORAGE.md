# SETTING_LEDGER_STORAGE · 设定账统一落盘

**版本：`setting-ledger-storage-v2`；兼容落盘：`setting-ledger-storage-v1`**

一句话用途：六本设定账只从一个落盘方写入。它照规划账 `planstore` 的锁、跨文件原子提交、统一发号和失败回滚来干活；不改 L1～L5 字段表，也不回答人物现在穿什么。

v2 只收紧合同边界，不改变当前 `settingstore.py` 的运行行为。旧 v1 记录继续按旧合同读取；使用 v2 记录时，受信 writer 必须在写前校验 `tags/tag_groups`、组目标和确认流程，并带上必填的 `expected_rev`。本票只写合同，运行接线留给第二刀。

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

### 4.1 v2 写入前提

v2 的 `setting_ledger_write` 必须绑定受信操作身份、作者和项目，携带 `expected_rev`，并在 prepare 前完成前后版本比较：永久 ID 不变、修订号连续、确认状态只能按 `confirmation_forward_v1` 前进、标签组目标仍在对应内容合同清单内。任何组拒绝都在写盘前停止；失败回滚仍恢复到写入前的完整文件和计数器状态。

预期修订号（`expected_rev`）不得省略：创建时显式为 `null`，表示预期记录尚不存在；更新时为当前修订号的正整数，必须与持锁后读到的版本相等。`null` 不能用于更新，布尔值不能冒充整数。沿用 v1 的新建不自带 ID 规则；当前可选参数接口要在第二刀收紧，本轮不改运行代码。

受信操作身份必须由已认证上下文取得，不能只检查调用方传来的 `actor` 字符串非空。写前逐组计算账号权限、任务许可、内容合同及组限制的交集，并比较完整业务正文与组规则；内置组不能被删除、改名或搬走目标。退役保留历史签字，正文不变，不新增签字。任一规则未知、保护组缺失或权限无法判定，都在生成写入计划前拒绝。

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
