# WO-01 专用评分合同

## 固定分母

- 三臂只能是 `TARGET_ONLY / SMALL_HALO / CURRENT_WINDOW`；
- 每臂 24 题，顺序与 DEV24 canonical 完全相同；
- 每臂共同 48 条 gold；
- 两个自然空答案保留；
- 不删题，不按模型表现换邻域。

## 分层，不揉成一个总分

- `semantic_recoverable`：容器即使坏了，只要能机械恢复 fact object，仍可进入同 case 语义裁决；
- `semantic_structured`：只有完整 Schema 通过的 facts 才计；
- `strict_structured`：Schema 通过后，fact 字符串逐字匹配；
- `end_to_end_usable`：语义命中后，Schema、status、speaker 和 evidence 都正确才计可用；
- JSON／Schema、status、speaker、evidence、只读泄漏、空题误报、复读、触顶和 clean stop 各自单列。

💡 例如 fact 正确但 evidence 写成 `B01`：

- 可恢复语义可以命中；
- 只读泄漏加一；
- evidence binding 失败；
- end-to-end usable 不通过。

非法 JSON 仍是格式失败，不能因恢复出事实就洗成 Schema PASS。

## 语义裁决

字符串规范化后同题唯一匹配可以机械命中。未匹配预测必须生成 same-case 盲审队列；没有完整裁决时，scorer 状态只能是 `HARD_STOP_SEMANTIC_ADJUDICATION_REQUIRED`，不能输出“最终 semantic F1”。

裁决只允许同 case，且按 `case_id + prediction_fact_sha256` 绑定，绝不把 arm 放进人工裁决键。同题同文本在三臂强制复用一个结论。给审查者的盲队列不显示 arm；arm 到候选的关系只进隐藏 sidecar，评分时机械回填。

裁决必须通过 `SEMANTIC_ADJUDICATION_SCHEMA.json`，并绑定产生候选的同一份 raw SHA。只把 `SEMANTIC_EQUIVALENT` 且绑定本题真实 gold ID 的记录算作 TP；部分正确、过宽、过窄、文本支持但额外、错误、幻觉或不清楚都不自动算 TP。重复、冲突、陌生 case、陌生 gold、预测文本 SHA 不符、拿旧 raw 裁决套新 raw 全部硬停。

人工裁决只回答 fact 语义是否等价，不能放行 status、speaker、evidence 或 Schema；这些始终由机械层单独计算。只有盲队列全部裁完、`semantic_pending=0` 后，才生成配对 bootstrap。

本合同继承的只是 M1/P3 已冻结的分层和同题裁决原则，来源 SHA 写在 `SOURCE_BINDING.json`。旧 scorer 的历史臂、路径和输出目录没有被复用。

## 原始答卷身份闸

正式评分必须同时读取 `RAW_OUTPUTS_72.jsonl` 和同一目录的 `RUN_RECEIPT.json`。评分前逐行核对固定顺序，以及 `sequence_index / arm / row_index / case_id / request_sha256 / gold_binding_sha256`。运行票还要绑定 raw、runner、授权票、R01 manifest、request plan 和 run ID。任一字段缺失或漂移都在算分前硬停。

TEST_ONLY 分支夹具只走私有函数，不可冒充正式 score 命令的运行票。

## 两道不可覆盖输出

- `scoring_pre_adjudication/`：生成初分、盲化队列、隐藏 occurrence sidecar 和 receipt。即使队列为 0，也保留零候选票。这里的语义分不是最终成绩，不生成 bootstrap；
- `scoring_final/`：只能在 pre 工件 SHA 未变、裁决集合与盲队列完全一致且 `semantic_pending=0` 时新建。它绑定 pre receipt、queue、adjudication、raw 和 run receipt 的 SHA，才允许产生最终 semantic F1 与 bootstrap。

两个目录只允许在同一个授权 run 目录下新建，已存在即拒绝覆盖；final 不能重写或删除 pre。

来源：Codex
