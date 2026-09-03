# CHAPTER_THIN_CARD_ACCEPTANCE v1

这是一套给本章薄卡合同使用的离线验收。它用 12 个固定场景检查范围、来源状态、版本、水位、权限、体量和执行准入有没有串线。

它不是薄卡 runtime，也不是新的取件核心。通过这套验收，只表示合成输入在当前合同下能得到可判断、可复查的结构结果；不证明真实小说取件准确率，不证明数据库、页面或主 AI 已经可用。

## 验收对象

### `CHAPTER_THIN_CARD_ACCEPTANCE_CASE v1`

一张固定场景卡。它只保存：

- 场景编号和合成输入配方；
- 应出现的薄卡、准入回执或失败回执；
- 应保留的来源状态；
- 两种体量边界；
- 字段级断言；
- 对应的一个防空跑反例。

场景卡不是事实、账本、章节规划或权限真值，也不能被产品模块当成薄卡读取。

### `CHAPTER_THIN_CARD_ACCEPTANCE_SUITE_RECEIPT v1`

整套验收回执。只有 A01～A12 全部通过、12 个防空跑反例全部被准确拒绝、外部调用计数全部为 0，状态才可以写成 `PASS`。

回执保存当次依赖文件 SHA。它只说明这一轮读了哪个合同水位，不能代替 Git commit、PR 或运行时 current owner。

## 12 个固定场景

| 编号 | 检查什么 | 通过时必须看到 |
| --- | --- | --- |
| A01 | 正常起章 | 范围逐字段投影；HARD 材料全在常驻层；人物当前定义、故事时间切片、当前规划、上一章已提交状态和未提交增量没有合并身份；九项准入检查通过 |
| A02 | 新书首章 | 首章身份成立；上一章快照是合法 `null`；没有伪造上一章 need、摘要或任务信 |
| A03 | 上一章存在但交接结果合法为空 | 上一章已提交快照仍保留；`EMPTY / VALID_EMPTY_OBJECT` 不得改写成无匹配、未追踪或来源损坏；不补猜材料 |
| A04 | 当前任务精确无匹配 | 选中事实 0、事实类 C9 need 0、任务级来源证明 1、`NO_MATCH / NO_MATCHING_ENTRIES` 1、伪造事实 owner 0 |
| A05 | 可选来源尚未追踪 | 来源结果保留 `UNTRACKED`；不补假版本、SHA 或正文；HARD 材料仍齐；准入为 `ADMITTED_WITH_GAPS` |
| A06 | 无权限盒子 | 两份隐藏内容不同的合成输入得到完全相同的可见失败；不出现隐藏 ID、标题、数量、水位、哈希或回取入口 |
| A07 | 完全授权 | 托管确认可以减少人工停点，但故事范围、人物范围、source need 和常驻材料数量不能扩大 |
| A08 | 两种体量上限 | reader 的 100 条业务项上限和薄卡的 262144 UTF-8 bytes 上限分别验；MAY 先于 SHOULD 降级；HARD 不得降级，必读最小集超限必须失败 |
| A09 | 编译期间来源前进 | 不同 storage generation 不能拼成成功薄卡；必须在成功卡产生前拒绝 |
| A10 | 旧卡过期 | 旧卡字节和 SHA 不变；新的准入回执写 `STOPPED / SOURCE_ADVANCED`，并要求重新编译 |
| A11 | 损坏、不支持或规则缺失 | 只产生失败回执，或在成功卡产生前稳定拒绝；失败对象不能带薄卡 ID、常驻层或按需层 |
| A12 | JSON 与测试行集合等价 | 展开再还原后值、类型、空值、数组顺序、权限状态和来源状态完全相同；storage generation 检查仍然有效 |

## 空、无匹配和未追踪不能混

- `EMPTY`：对象存在，当前内容合法为空。
- `NO_MATCH`：系统按已确认范围查过，但没有找到符合条件的内容。
- `UNTRACKED`：当前没有登记这个可选来源，系统不能假装已经查过。
- `UNAUTHORIZED`：当前没有权限。回执不能泄露对象是否存在。

这四种结果不能互相替换。A03、A04、A05、A06 分别钉住对应语义。

## 两种体量限制

### reader 单次最多 100 条

这项按业务项数量计算。第 101 条不能静默丢弃，也不能保留前 100 条后声称读取完整。超出时应该分页、缩窄范围或停止，不由薄卡删材料来掩盖。

### 薄卡最多 262144 UTF-8 bytes

这项按规范 JSON 序列化后的 UTF-8 字节数计算，不按字符数、token 数或磁盘文件大小计算。

需要降级时：

- 只移动完整、可回取而且有 handle 的条目；
- 同一义务等级内按 C9 原顺序逆序移动；
- MAY 先移动，仍超限才移动 SHOULD；
- HARD 和控制最小集始终常驻；
- 必读最小集仍超限时，返回 `REQUIRED_RESIDENT_CONTENT_TOO_LARGE`。

100 条和 262144 字节是两道不同的门，不能合成一个值。

## 权限遮蔽

A06 使用两份隐藏标记不同的合成输入。隐藏标记不会进入 C9 请求，也不会进入可见回执。验收只比较两份可见失败字节是否完全相同。

允许显示的是当前任务失败和通用 `UNAUTHORIZED` 原因。不允许显示隐藏盒子的 ID、标题、数量、内容、哈希、水位、存在性差异或回取入口。

## 测试专用逻辑行集合

`CANDIDATE_LOGICAL_ROWSET__TEST_ONLY` 只用于 A12。它把规范 JSON 的每个节点展开成：

- JSON Pointer 路径；
- 值类型；
- 是否存在；
- 数组序号；
- 原值。

验收器随后机械还原 JSON，并逐值比较。这个行集合不是数据库 Schema，不定义表名、列名、索引、外键、事务、SQL、ORM 或数据库品牌。

业务内容即使能够等价还原，也不能绕过存储代际检查。storage generation 变化后，旧卡仍要重新准入或重新编译。

## 防空跑反例

每个主场景只有一个反例，共 12 个：

| 编号 | 故意做错什么 | 必须被抓住的错误 |
| --- | --- | --- |
| A01-NEG | HARD 材料移出常驻层 | `A01_HARD_NOT_RESIDENT` |
| A02-NEG | 给首章塞上一章快照 | `A02_FIRST_CHAPTER_CONFLICT` |
| A03-NEG | 把合法空改成无匹配 | `A03_EMPTY_RECAST` |
| A04-NEG | 把无匹配改成合法空 | `A04_NO_MATCH_RECAST` |
| A05-NEG | 给未追踪来源补假版本 | `A05_FAKE_VERSION` |
| A06-NEG | 在无权限失败中泄露隐藏 ID | `A06_PERMISSION_LEAK` |
| A07-NEG | 托管确认后扩大 source need | `A07_SCOPE_EXPANDED` |
| A08-NEG | 把 HARD 材料移到按需层 | `A08_HARD_DEMOTION` |
| A09-NEG | 把混合代际结果标成成功 | `A09_MIXED_GENERATION_ACCEPTED` |
| A10-NEG | 原地修改旧卡 | `A10_OLD_CARD_MUTATED` |
| A11-NEG | 给失败对象塞薄卡字段 | `A11_FAILURE_SUCCESS_MIXED` |
| A12-NEG | 丢失数组序号或值类型 | `A12_ROWSET_NOT_EQUIVALENT` |

反例只证明验收器能抓错，不增加产品场景，也不进入 12 个通过数量。

## 运行边界

验收器只读取同目录合同、Schema 和合成夹具，并在内存里调用现有 validator。它：

- 不接真实 reader；
- 不接真实 C9；
- 不读取小说正文、事实句子、十本账或作者材料；
- 不访问数据库、网络、模型、权限服务、UI 或主 AI；
- 不写业务对象；
- 不选择物理存储路线。

套件回执中的真实 reader、真实 C9、业务文件、数据库、网络、模型和 UI 调用必须全部为 0。

## 运行命令

```bash
uv run --locked python novel-mvp/contracts/validate_chapter_thin_card_acceptance.py
uv run --locked pytest -q tests/test_novel_mvp_chapter_thin_card_acceptance.py
```

来源：Codex
