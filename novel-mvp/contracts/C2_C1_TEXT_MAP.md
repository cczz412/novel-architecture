# C2 → C1 受控文本映射合同

版本：`C2_C1_TEXT_MAP v1`。用途：证明一段规范化引文确实对应同一章、同一 revision 的原章连续片段。#322 第一刀冻结合同与离线校验；第二刀提供下述显式运行入口。

默认 C2/C3/C4 v1 入口保留原规则。显式启用 `text_mapping=True` 或 M2 `options.text_mapping=true` 后，M2 输出 `text_map`，M3 传递 `text_map_evidence`，M4 在当前原章与责任范围下复验并事务保存。工作区入口为 `persist_current_mapped_segments`。章仍是文本身份单位，责任段只是一次抽取范围；不增加跨章匹配，也不改变全章整合。

## 输入与可信边界

机器形状见 [Schema](C2_C1_TEXT_MAP.schema.json)，纯校验入口为 [validate_mapping](validate_c2_c1_text_map.py)。调用者分别传入待验证 `evidence` 和可信 `snapshot`，不能用证据包自带的快照替代当前状态。

`snapshot` 含 `text`、`chapter_revision_ref`、`responsibility`。第二刀中，C1/C11 的读取方提供当前不可变原章正文和 revision；M2 调度方提供本次任务的责任段分配。M3／模型不得修改这些可信输入。纯校验器不读取本机书库、不写文件，也不把校验结果自动确认成事实。运行调用方负责取得可信快照。

revision 是 `{chapter_id, revision_no, revision_text_sha256}`；SHA-256 对原章逐字文本的 UTF-8 字节计算。相同文本的旧 revision_no 仍拒绝。字符偏移都是 Unicode code point、0 起点、左闭右开；不按 UTF-8 字节、UTF-16 单元或可视字形计数，组合字符不合并。

## 可重放的规范化规则

`normalization_version` 固定 `LF_SPLIT_EDGE_WS_V1`：按 LF 拆自然段，每段只去首尾空白，删除空段，再用一个 LF 连接。空白集合固定为 U+0009–000D、U+001C–0020、U+0085、U+00A0、U+1680、U+2000–200A、U+2028–2029、U+202F、U+205F、U+3000。单独 CR 不作为分段符；CRLF 中 CR 属于段尾空白。段中空白保留，不做 NFC、大小写、标点替换或全文去空白。

`normalized_text` 保存全章规范化结果；`char_map[i]` 是第 i 个规范化字符在原章的 code point 坐标。正文字符逐字映射，连接用的 LF 映射到前一非空段末与后一非空段首之间的第一个真实 LF。`removed_whitespace` 按原章顺序完整保存其余被去掉的连续区间 `{start,end,text}`。这些区间与 char_map 覆盖原章且不重叠；校验器从原章重新生成三项并逐项比较，缺映射、改坐标、漏空白均拒绝。空章无法生成合法引文。

责任范围 `responsibility={seg,start,end}` 使用规范化全章坐标，必须是一个或多个完整自然段，与调用方的任务分配完全相同。`seg` 从 1 起。左右 halo 只作背景，不能扩大责任范围。原章范围由责任范围的首尾映射限定；连接段落间真实存在的空白可被包含，别段正文不能混入。

## 引文的三种身份

| 字段 | 用途 |
|---|---|
| `quote_original` | M3 原封不动保留的候选引文；不能为了过校验覆盖成另一串 |
| `match_start/end`、`normalized_match` | 同一责任范围内的规范化匹配坐标及逐字内容 |
| `original_start/end`、`original_slice`、`original_slice_sha256` | M4 拟保存、可从同一原章精确回取的连续片段及 UTF-8 SHA-256 |

候选引文只能逐字等于原章实际片段或规范化匹配片段。任意增删空白、改标点或改写都拒绝；若候选用了其他转抄形式，应重新取得可支持的候选，不能就地洗白。

规范化匹配的首尾不能是连接 LF，也不能只含空白。匹配必须全章唯一（包含重叠命中）；重复引文即使提交了一组坐标也拒绝。本版本不提供“指定第一次命中”的消歧开关，后续如需人工消歧须另定合同。原章区间必须严格等于 `char_map[match_start]` 到 `char_map[match_end-1]+1`，实际片段与哈希必须精确相等。

## 归属、返回与失败

M2 负责产生映射；M3 保留候选原文、revision 和责任范围；M4 在当前 revision 与责任范围下复验，成功后才可把原章片段交给已有事务 writer。C4 用可选 `text_map_evidence` 保存候选原文与完整来源映射，用 `quote` 保存原章片段，anchor 沿用 C11 原形状。后续 revision 可更新 current anchor，来源映射保持首次入账身份，不能当成新版映射。

本校验器只返回 `{chapter_revision_ref,start,end,text,sha256}` 的拟保存片段，不返回 `confirmed`，不分配事实号或 E-ID，不写正式账本。失败抛出 `ValueError`，不得产生任何写入；调用者也不能在验证前预写。运行层沿现有事务协调器复核 C11 revision 与上游来源版本，并保证失败零写入。

错误码区分 Schema／可信快照无效、快照 SHA 不符、revision 不符、映射重放不符、责任范围不符或无效、超出责任范围、匹配无效或不符、重复引文、原章区间／片段／SHA 不符、候选引文不符。对应正常和拒绝输入见 [合成用例](C2_C1_TEXT_MAP.fixtures.jsonl)；测试同时核对输入不被修改和运行代码未被导入。

来源：Codex
