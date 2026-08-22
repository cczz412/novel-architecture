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
