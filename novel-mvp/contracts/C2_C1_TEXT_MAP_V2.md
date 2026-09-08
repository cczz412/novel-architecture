# C2/C1 显式恢复证据 v2

v2只在调用方明确启用时恢复原章已有的段间LF，并记录点名字段别名适配。原模型引文不改，C4仍保存可从同revision原章逐字回取的连续片段。v1合同、Schema、旧默认路径不变。

## 启用与来源

- `extract.extract_segment(..., text_map_version="v2")`，或M3工具请求额外指定 `text_map_version: "v2"`。缺失时仍为v1；未知版本拒绝。
- 工作区使用独立入口 `persist_current_recovered_fact_candidates`；原 `persist_current_fact_candidates` 的签名与默认行为保持。
- 必须已取得可信、当前revision的映射C2。不得由模型提供原章、责任段或恢复证据；工作区依旧核来源身份与完整批次。
- 模型原始响应完整保留在既有调用方原件中；工作区 `responses_identity` 仍核原始响应，v2的运行回执provider_ref另带 `:TEXT_MAP_V2` 区分操作模式。

## 有版本的证据

沿用 `text_map_evidence`，`contract`仍为 `C2_C1_TEXT_MAP`，扩展 `version`为`v2`。C2/C3/C4顶层仍为各自v1，C11形状不改。

Schema见 [C2_C1_TEXT_MAP_V2.schema.json](C2_C1_TEXT_MAP_V2.schema.json)。v1字段全部保留，增加以下必填字段：

| 字段 | 用途 |
|---|---|
| recovery | 未恢复时null；否则记录规则 `SOURCE_LF_ONLY_V1`、`quote_recovered` 和逐处changes。 |
| provider_item | 每条记录独立保留适配前的原响应条目，正常text条目也必须保存。 |
| provider_adaptation | 无字段适配时null；否则记录 `TEXT_FULLWIDTH_COLON_KEY_V1`、原条目、from_key与to_key。 |

`quote_original`始终为模型原引文，等于C3 quote。发生恢复时，`quote_recovered`等于实际原章连续片段；C4 quote等于该片段。changes记录原章Unicode坐标、回文Unicode坐标，以及 `RESTORE_SOURCE_LF` 或 `SPACE_TO_SOURCE_LF` 原因。

## 恢复与拒绝

先尝试原v1精确匹配。已满足原章原样或既有规范化形式时，不产生恢复记录。原v1失败后，才查受控恢复：

1. 原章非LF字符全部逐字匹配，不改标点、字母大小写、Unicode形式或段内空格。
2. 仅原章确有LF的位置，允许模型遗漏LF或用一个普通空格替代；恢复的LF取自原章，不凭空编造。
3. 在全章枚举允许匹配，必须恰好一个区间，再确认区间整体位于当前责任段。多处匹配、越界、只在halo中出现均拒绝。
4. 恢复出的原章片段仍通过v1映射和全章歧义校验；坐标、SHA、责任范围及全部证据字段必须重放一致。
5. 其他变换不属于本版：任意去空白、TAB/全角空格/两个空格替LF、CRLF删除、文字改写、标点补正等均不兜底。空引文与首尾空白不进入恢复。

## 字段适配

只识别精确键集 `{text：, quote}`，转换成内存候选 `{text, quote}` 后仍走现有严格解析器。原条目由M3直接从本次响应深拷贝到provider_item，不从适配凭据反推，不修改调用方响应。重放时从provider_item推导应有的provider_adaptation；剥除或伪添适配、两份原条目不一致均拒绝。C3构造和入账时同时核对事实文本、原quote；C4后续读取只核来源与引文，不要求作者编辑后的事实文字等于模型原文字。

同时有text与text：、未知附加字段、text:等相似别名、非法类型、空事实句或首尾空白均拒绝。无别名的正常条目不生成适配记录。模型不能自行提交“已适配”证据绕过解析。

## 保存与下游

M3验证原quote与v2证据，M4结合工作区当前C1/C2再核对并保存原章片段和完整首次来源证据。C4重开重放同一v2规则；已有事实来源证据不可替换、剥除或降为v1，同operation幂等与批次原子提交沿用现有工作区。

原响应条目与适配一同随已准入C3进入C4，作为首次来源不可变内容。独立C4校验只证明证据内部一致；外部重新构造整份一致证据不获得来源权威，已有来源整体替换由M4拒绝。

M7/M9通过共同C4校验器读取v2。没有作者确认的extracted事实仍不能触发M9概览；支持证据读取不等于作者确认或产品可用。段级通过、整章批次提交与整书验收分别报告，不从失败批次捞出好条目冒充完成。

来源：Codex
