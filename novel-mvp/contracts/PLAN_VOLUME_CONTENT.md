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
