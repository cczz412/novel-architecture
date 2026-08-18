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
