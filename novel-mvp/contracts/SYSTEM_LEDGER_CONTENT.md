# SYSTEM_LEDGER_CONTENT · 体系账内容合同

**正式版本：`system-ledger-content-v1`**

一句话用途：保存体系定义卡、同类排序和有方向的体系关系；题材包预填必须保留来源，作者改写后 pack_ref 原样留痕，仍能回溯原包。

## 1. 发／收模块与边界

| 角色 | 模块／对象 | 权限与边界 |
|---|---|---|
| 作者定义 | 作者直接编辑体系卡 | 直接编辑按共同信封的 `AUTHOR_ATTESTATION` 处理 |
| 预填提出 | 题材包／插件 | 只能写 `pack_prefilled + candidate + pack_ref` |
| 唯一落盘 | 后续设定账统一 writer | 复用 planstore 原子提交与统一发号；L4 不实现 runtime |
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
8. 禁止本票实现统一 writer、取件码或 handle 迁移。
9. 禁止本票定义知情边、ADD-043 拆条、READER 结构或新账申请流程。

## 7. 开放问题

知情边字段枚举、ADD-043 规则拆条、READER 侧数据结构、新账申请流程只留位。取件码扩十本和现役 handle 迁移留 L5，不在 L4 定义。

## 8. 机器件与状态

- `SYSTEM_LEDGER_CONTENT.schema.json`
- `validate_system_ledger_content.py`
- `SYSTEM_LEDGER_CONTENT.fixtures.jsonl`
- `tests/test_novel_mvp_system_ledger_content_contract.py`

实现状态：`CONTRACT_ONLY__UNIFIED_WRITER_PENDING`。
