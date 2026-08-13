# ChatGPT Pro 工单｜T5 R04 单一 A 教材删减与病因体检 R07

请先完整读取 `00_READ_ME_FOR_REVIEWER.md`，再按下面顺序读材料：

1. `current_truth/`：当前 A 身份、CZ 已拍的 5 本固定排除项、外审边界。
2. `current_route/`：不含正文和答案的 585 行元数据、79 本书分布和返回合同。
3. `upstream_evidence/`：产品目标和已知故障家族。

## 你的任务

我们以后只维护 A 语义源。B/C 和考卷这轮完全冻结，不需要讨论。现在只把 A 训练教材变得更贴近“现代中文网文的大纲供料”，减少来源不合适、单书过量、题材过量和可能教坏模型的训练段，并为下一波新网文补位列清单。

🔥 这轮的主目标是“先把差的筛出去”，不是“尽量保住现有训练规模”。后续还会继续加入不同作者、不同题材的新网文，所以不要担心删得多了暂时不能训练，也不要为了守住 585 行、某个题材比例或某种稀有状态，把明显不合适、重复或容易教坏模型的教材勉强留下。稀有能力若确有价值，可以在后续新网文里重新补。

你拿不到小说正文、fact 文本、evidence 文本和 assistant 标准答案，这是故意的。你可以做来源研究、分布审查和候选删减；不能伪装成已经完成逐条语义定罪。

下面的“一、二、三、四”只是任务分段，不是 A/B/C 教材名称。B/C 教材和考卷仍然冻结。

### 一、核实 79 本书的来源身份和题材

对 `A_BOOK_DISTRIBUTION_NO_TEXT.jsonl` 中每本书逐一给出：

- 它是平台连载网文、传统名著、出版文学、影视剧本/小说化文本，还是无法确认；
- 大类型、小类型、频道倾向；
- 至少一条可核查来源链接，优先作品官方页、首发平台、出版社或权威资料；
- 若无法联网或无法确认，必须写 `UNKNOWN`，不得凭书名猜。

本轮 CZ 已拍 5 本固定排除：水浒传、红楼梦、三国演义、白鹿原、大明王朝1566（全集）。这 5 本共 80 行，必须写 `REMOVE_FIXED_CZ`，不得重新投票。

### 二、设计删减规则并逐行给候选决策

对全部 585 行各写一条 `ROW_DECISIONS.jsonl`，定位键必须是 `line_number + segment_id + source_record_sha256`。可用决策只有：

- `KEEP`
- `REMOVE_FIXED_CZ`
- `REMOVE_CANDIDATE`
- `SEMANTIC_REVIEW_REQUIRED`
- `BLOCKED_NO_EVIDENCE`

判断时同时看：

- 书是不是现代平台网文；
- 同书/同章行数是否过量；
- 题材是否扎堆；
- 稀有状态和困难边界是否会被误删；
- 高事实密度、长输出、证据复用、复合事实、冷动作等机器风险旗标；
- 产品只强抽热事实，不追求细枝末节和固定条数。

删减时请把下面三种东西优先挑出来：

1. 来源就不适合现代中文网文训练的整书或训练段；
2. 同一本书、同一类场景或相似题材反复出现，继续保留只会加重过拟合的段；
3. 可能强化琐碎动作、复合事实、长证据、机械复读等已知坏习惯的段。

⚠️ 机器旗标只是“去本地读原文”的理由，不是自动删除规则。尤其不能看到长输出就删掉误信、承诺、条件、转述或长链等稀有教材。

### 三、给三档方案，但推荐一档

给出保守、平衡、激进三档删减后的：

- 剩余书数、行数、事实对象计数；
- 单书最大行数与前十本分布；
- 大类型/小类型分布；
- 八种状态分布；
- 机器风险旗标分布；
- 可能损失的稀有教学能力。

推荐一档时不要为了追求固定删减比例硬删，也不要为了保住当前规模少删。优先选择“质量最好、后续最容易用新网文补齐”的方案。CZ 已固定排除的 80 行必须进入三档共同底座。

`TARGET_DISTRIBUTION.json` 还必须给出下一波新网文补位计划：

- 删后还缺哪些大题材、小题材、频道和叙述形态；
- 误信、承诺、条件、转述、章节出口等稀有能力各缺多少；
- 每本新小说最多建议贡献多少训练段；
- 建议优先找多少本新小说、多少段，不要求一步凑满；
- 哪些缺口必须等首训真实错例出现后再补，不能靠想象造数据。

### 四、分开写病因，不许把相关性写成因果

对既有坏表现——少抽、乱抽琐碎动作、复合事实、长证据、复读、截断、格式失败——逐项写：

- A 教材能直接支持的证据；
- 反证或别的可能解释；
- B 桥接转换、训练强度、基座、解码等其他变量；
- 要怎样做消融试验才能确认；
- 当前置信度。

特别提醒：B v2.1 曾全局改写桥接条件，不能把那轮退化全部怪到 A；但这轮不设计或修改 B/C。

## 回包要求

ZIP 根目录必须严格只有 9 个文件，文件名和计数按 `RETURN_CONTRACT.json`。不要再包第二层目录，不要放输入材料副本，不要放正文、事实、证据或 assistant 答案。

`BOOK_CLASSIFICATION_RESEARCH.jsonl` 每本书一行，共 79 行，至少包含：

```json
{"sample_id":"...","book_title":"...","author":"...","medium_class":"WEB_SERIAL|CLASSIC|PRINT_LITERARY|SCREENPLAY_OR_TV_SOURCE|UNKNOWN","platform_or_publisher":"...","genre_main":"...","genre_subtypes":["..."],"source_urls":["..."],"confidence":"high|medium|low"}
```

`BOOK_DECISIONS.jsonl` 每本书一行，共 79 行，至少包含：

```json
{"sample_id":"...","decision":"KEEP_ALL|CAP_ROWS|REMOVE_FIXED_CZ|REMOVE_BOOK_CANDIDATE|HUMAN_REVIEW","recommended_row_cap":null,"reason_codes":["..."],"rare_coverage_protection":["..."],"evidence_refs":["..."]}
```

`ROW_DECISIONS.jsonl` 每个训练行一行，共 585 行，至少包含：

```json
{"line_number":1,"segment_id":"...","source_record_sha256":"...","decision":"KEEP|REMOVE_FIXED_CZ|REMOVE_CANDIDATE|SEMANTIC_REVIEW_REQUIRED|BLOCKED_NO_EVIDENCE","reason_codes":["..."],"book_rank_after_pruning":null,"semantic_review_reason":null}
```

`SEMANTIC_REVIEW_QUEUE.jsonl` 只收需要本地读原文/答案的行，每条必须指向 `ROW_DECISIONS`，并说明要查什么，不能编造答案内容。

格式至少是：

```json
{"line_number":1,"segment_id":"...","source_record_sha256":"...","check_items":["核这段是否只教琐碎动作"],"why_metadata_insufficient":"元数据没有事实文本，不能直接定罪"}
```

`TARGET_DISTRIBUTION.json` 必须有：

- `recommended_scenario`：`conservative|balanced|aggressive`；
- `scenarios`：恰好三档，每档都给剩余书数、行数、事实数、单书上限、前十本、题材/八态/风险分布、稀有能力风险和推荐理由；
- `replacement_plan`：新网文优先缺口、建议新增书数与段数、每本上限、稀有状态目标、哪些等首训错例后再补；
- `status`：`CANDIDATE_PENDING_LOCAL_VERIFICATION`。

每档方案的字段格式固定如下。尤其是 `top_books`，只写 `sample_id` 和暂计保留行数，不能另换字段名：

```json
{
  "name": "balanced",
  "remaining_book_count": 60,
  "remaining_row_count": 400,
  "remaining_fact_count": 3500,
  "max_rows_per_book": 12,
  "top_books": [
    {"sample_id": "T5W01-001", "row_count": 12}
  ],
  "genre_distribution": {"某个大类型或现有元数据值": 20},
  "status_distribution": {"已发生": 2000, "误信": 20},
  "risk_flag_distribution": {"high_fact_density_ge18": 30},
  "rare_coverage_risks": ["可能损失的稀有教学能力"],
  "recommendation_reason": "为什么保留这一档"
}
```

推荐档的 `genre_distribution` 必须按元数据字段 `p3_story_type_value` 逐行计数，空值统一记作 `UNVERIFIED`；`status_distribution` 是暂计保留行的 `status_counts` 逐项求和；`risk_flag_distribution` 是暂计保留行的 `risk_flags` 出现次数。前十本按暂计保留行数降序、`sample_id` 升序取前 10。本地验收器会重新计算这些值，不接受估算数。

🔥 `ROW_DECISIONS.jsonl` 代表推荐档的逐行方案。推荐档的剩余行数、书数、事实数、单书最大行数、前十本、题材分布、八态分布和风险旗标分布，必须由这 585 条决定机械复算得到：`KEEP`、`SEMANTIC_REVIEW_REQUIRED`、`BLOCKED_NO_EVIDENCE` 暂计保留；`REMOVE_FIXED_CZ`、`REMOVE_CANDIDATE` 计删除。不得手填另一套数字。

书级和行级也必须一致：

- `KEEP_ALL`：该书不能出现 `REMOVE_CANDIDATE`；
- `CAP_ROWS`：暂计保留行数必须等于 `recommended_row_cap`；
- `REMOVE_BOOK_CANDIDATE`：该书所有行必须是 `REMOVE_CANDIDATE`；
- `HUMAN_REVIEW`：该书至少一行必须进入语义复核或证据不足；
- `REMOVE_FIXED_CZ`：固定 5 本全部 80 行必须同样标固定删除。

`FAILURE_CAUSALITY_HYPOTHESES.json` 必须恰好覆盖 7 个不重复故障家族：`UNDER_EXTRACTION`、`TRIVIAL_ACTION_OVER_EXTRACTION`、`COMPOUND_FACTS`、`LONG_EVIDENCE`、`MECHANICAL_REPETITION`、`TRUNCATION`、`FORMAT_FAILURE`。每条必须含：故障家族、A 教材支持证据、反证、其他变量、消融试验、置信度；支持证据和反证都不能为空。

`RETURN_MANIFEST.json` 写 `root_file_count: 9`，但 `files` 只登记其余 8 个文件的字节数和 SHA-256，不登记自己，避免自哈希循环。`SELF_CHECK.md` 必须原样写出下面这些机器行：

```text
BOOK_KEYS=79/79
ROW_KEYS=585/585
FIXED_REMOVE_ROWS=80/80
UNKNOWN_KEYS=0
DUPLICATE_KEYS=0
MISSING_KEYS=0
STATUS=CANDIDATE_PENDING_LOCAL_VERIFICATION
NO_MATERIALIZED_A=true
```

第 9 行接着原样写：

```text
没有输出已删除后的 A
```

`SELF_CHECK.md` 必须严格只有上面这 9 行，不能加标题、代码框、空行、解释或其他字符；本地验收器会对整份文件逐行精确比较。

当前回包状态只能是：`CANDIDATE_PENDING_LOCAL_VERIFICATION`。

来源：Codex
