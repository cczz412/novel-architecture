# T5 R04 新小说训练集长期施工合同

- **适用对象**：Codex 与后续接力 agent
- **文件性质**：长期施工候选合同；需挂接到现有 `active/requirements/` 后才成为正式规则
- **项目状态**：`CANDIDATE_PENDING_CZ_PROMOTION`
- **目标规模**：候选池约 500 本；正式训练窗口约 1,100～1,300；分批建设
- **默认格式路线**：A 唯一人工真源，C-2 机械训练视图

> 这条线会持续很久。任何一轮聊天都可能中断，所以工程状态必须完全落盘。下一位执行者只读仓库文件，也应能知道：现在做到哪里、哪些已冻结、哪些待返修、下一步只能做什么。

---

## 一、核心定义

### 1. 书、作者与窗口

- **书**：一部独立小说，使用稳定 `book_id`。
- **作者**：按作者归一后的稳定 `author_id`；同一作者的不同作品必须在同一数据分区。
- **训练窗口**：一次模型输入对应的一段正文和一组事实答案，不等于一条 fact。
- **事实对象**：窗口输出数组中的一个原子事实。
- **窗口位置**：`HEAD / MIDDLE / TAIL / WHOLE`。

### 2. A 与 C-2

- **A Gold**：人工维护的唯一语义真源，保存事实、状态、speaker 和字符级逐字证据。
- **C-2 View**：程序从 A 和 unit map 机械派生的短输出训练视图。
- **B 单元**：负责区之前紧邻的机械桥接单元，可作为证据开头，不能作为证据终点。
- **T 单元**：本段负责区，所有被抽取事实必须在 T 中落地。
- **只读上下文**：无编号，只帮助消歧，不能作为证据。

### 3. 全局与局部 ID

- 数据库保留全局唯一 `source_unit_id`；
- 模型只看每个窗口内部的 `B01/T01`；
- 唯一定位键为 `sample_id + local_id`；
- 不允许模型输出全局书号、章节号、长前缀或字符坐标。

---

## 二、文档身份与承接方式

### 绑定原则

- `active/requirements/` 才能成为施工真源；
- `reports/`、顾问报告、example、bridge、实验记录只能作证据或说明；
- 若仓库已有 T5 R04 主办页，必须挂接现有主办页，不另建平行真源；
- 若没有正式主办页，只能提交“建议承接结构”，不得擅自宣布已 active。

### 建议的 active 文件

```text
active/requirements/t5_r04_cplus/
  00_SCOPE_AND_AUTHORITY.md
  01_SOURCE_AND_SPLIT_CONTRACT.md
  02_WINDOW_SELECTION_CONTRACT.md
  03_ATOMIZER_CONTRACT.md
  04_A_GOLD_CONTRACT.md
  05_C2_RENDER_CONTRACT.md
  06_REVIEW_AND_QC_CONTRACT.md
  07_EVALUATION_CONTRACT.md
  08_TRAINING_COMPARISON_CONTRACT.md
  09_RIGHTS_AND_PROVENANCE_CONTRACT.md
```

若当前仓库命名不同，沿用现有结构，不要为了匹配本文件重排全库。

---

## 三、必须长期保存的状态文件

建议维护：

```text
state/
  RUN_STATE.json
  DECISION_LOG.jsonl
  OPEN_ISSUES.jsonl
  WORK_QUEUE.jsonl
  CHANGELOG.md

locks/
  AUTHOR_SPLIT_LOCK.json
  SOURCE_POOL_LOCK.json
  FORMAT_LOCK.json
  ATOMIZER_LOCK.json
  EVALUATOR_LOCK.json
  TRAINING_RECIPE_LOCK.json

registry/
  AUTHORS.jsonl
  BOOKS.jsonl
  CHAPTERS.jsonl
  SAMPLES.jsonl
  SOURCE_UNITS.jsonl

batches/
  BATCH_001/
  BATCH_002/
  ...
```

### `RUN_STATE.json` 最少字段

```json
{
  "project":"T5_R04_CPLUS",
  "status":"PREFLIGHT|COLLECTING|REVIEWING|FROZEN|TRAINING|EVALUATING|BLOCKED",
  "active_batch":"BATCH_001",
  "active_contract_version":"cplus-contract-r01",
  "last_completed_sample_id":"...",
  "completed_books":0,
  "completed_windows":0,
  "accepted_windows":0,
  "quarantined_windows":0,
  "next_action":"...",
  "blockers":[],
  "updated_at":"..."
}
```

### `DECISION_LOG.jsonl`

每一行只写一个决定：

```json
{"decision_id":"D0001","date":"2026-08-07","status":"PROPOSED|APPROVED|REJECTED|SUPERSEDED","decision":"C-2 采用 C2_UNIT","reason":"...","approved_by":"CZ|PENDING","supersedes":null}
```

没有 `APPROVED` 的决定不能静默进入 active。

### `OPEN_ISSUES.jsonl`

```json
{"issue_id":"I0001","severity":"P0|P1|P2","question":"纯编号证据是否接受单元级额外文字","owner":"CZ|Codex","status":"OPEN|RESOLVED|DEFERRED","blocking_stage":"FORMAT_FREEZE"}
```

---

## 四、每次接力的开工和收工纪律

### 开工前固定读法

接力者必须按顺序读取：

1. 当前项目 `00_ROUTE_MAP`；
2. 当前 live `active/requirements/`；
3. `RUN_STATE.json`；
4. `DECISION_LOG.jsonl` 最近有效决定；
5. `OPEN_ISSUES.jsonl` 中 P0/P1 未决项；
6. 当前 batch manifest；
7. 当前 work queue；
8. 上一次 `HANDOFF.md`。

然后输出“首层已扫证明”：

- 看到了哪些顶层目录；
- 读了哪些关键文件；
- 当前 active batch；
- 当前下一动作；
- 当前阻塞项；
- 是否发现身份冲突。

### 收工前固定落盘

每次会话结束前，哪怕只完成少量工作，也要更新：

- `RUN_STATE.json`；
- 完成和未完成的 sample IDs；
- 新增、淘汰、隔离数量；
- 本轮修改文件及 SHA；
- 新发现问题；
- 当前批次分布统计；
- 下一步唯一动作；
- `HANDOFF.md`。

禁止只在聊天里说“做到第几本”。

### 中断恢复粒度

- 每 25 本或 50 个窗口，哪个先到就写 checkpoint；
- 每个 checkpoint 必须可独立校验和重跑；
- 单个样本处理必须幂等：重复执行不会生成第二个不同版本；
- 已冻结文件只读，修复使用新 revision。

---

## 五、来源登记与作者级分割

### 1. 分割必须先于选段

目标比例接近：

```text
train 80%
dev   10%
test  10%
```

候选 500 本可近似为：

```text
train 约 400 本
dev   约 50 本
test  约 50 本
```

但实际按作者组分割，不能为了命中 400/50/50 拆作者。

### 2. 作者隔离

- 同一作者全部作品只属于一个 split；
- 已知笔名、曾用名和同一写作者的作品应归到同一 `author_id`；
- 无法确认的作者关系写 `unknown`，不能凭感觉合并；
- 当前 41 题与旧 48 题涉及的作者和作品不得进入训练；
- 任何 split 变化都生成新锁文件和泄漏审计。

### 3. 来源登记 schema

`BOOKS.jsonl` 建议字段：

```json
{
  "book_id":"BK0001",
  "author_id":"AU0001",
  "title":"...",
  "author_display":"...",
  "source_path":"...",
  "source_sha256":"...",
  "publication_bucket":"RECENT|LEGACY|UNKNOWN",
  "genre_primary":"...",
  "genre_secondary":[],
  "rights_status":"TRAINING_CLEARED|RIGHTS_PENDING|REFERENCE_ONLY|REJECTED",
  "split":"train|dev|test",
  "split_lock_version":"split-r01",
  "status":"CANDIDATE|ACCEPTED|REJECTED|QUARANTINED"
}
```

### 4. 权利闸门

- `TRAINING_CLEARED`：允许进入真实训练；
- `RIGHTS_PENDING`：可做候选分析和内部审查，不得进入训练 run；
- `REFERENCE_ONLY`：只读参考；
- `REJECTED`：不再使用。

训练 manifest 必须拒绝非 `TRAINING_CLEARED` 行，而不是靠人工记忆。

---

## 六、每本小说取多少窗口

### 默认量

| 情况 | 数量 |
|---|---:|
| 每本基础 | 2 个窗口 |
| 补缺口 | 第 3 个 |
| 独特教学价值 | 极少数第 4 个 |
| 同一章 | 通常 1 个，特殊最多 2 个 |
| 同一作者全部作品 | 默认最多 4 个训练窗口 |

一本书的 8～12 个机械分段不等于 8～12 份独立信息。共享人物、事件、作者句式和情节上下文的窗口，不应按行数当成独立覆盖。

### 分轮策略

```text
第 1 轮：每本取 1 个，优先扩大作者和文风覆盖
第 2 轮：训练书再取第 2 个，避开同章和相同结构
第 3 轮：只按 dev 缺口补第 3 个
第 4 轮：极少数明确理由补第 4 个
```

### 同一作者上限例外

只有同时满足下面条件才可超过 4 个：

- 提供当前数据集中稀缺结构；
- 不能由其他作者替代；
- 不进入 dev/test；
- 有例外票；
- 作者总占比仍低；
- CZ 或 active 合同明确放行。

---

## 七、多人协作不能只按“第几段”分工

每个待选窗口必须先分配采样槽位。推荐记录：

```json
{
  "selection_slot":{
    "book_progress":"EARLY|MID|LATE",
    "chapter_position":"HEAD|MIDDLE|TAIL|WHOLE",
    "text_form":"NARRATION|DIALOGUE|CHAT|FORUM|SYSTEM_PANEL|LETTER|LIST|OTHER",
    "fact_density":"ZERO|LOW|MEDIUM|HIGH",
    "status_focus":["计划"],
    "speaker_level":"NONE|EXPLICIT|DISTANT_ATTRIBUTION|MULTI_SPEAKER",
    "reference_level":"NAME|PRONOUN|ALIAS|ROLE_TITLE|MULTI_ENTITY",
    "evidence_span":"ONE_UNIT|TWO_UNITS|THREE_PLUS",
    "noise_tags":["ONOMATOPOEIA"],
    "reason":"补足章尾计划类显式 speaker"
  }
}
```

### 基础两槽

- **S1**：前中段进度，章节中部，普通叙述或行动；
- **S2**：中后段进度，章首或章尾，优先与 S1 不同的文本形态和难度。

### 补充槽

- **S3**：由 dev 错误和覆盖缺口决定；
- **S4**：只接受明确“其他书难替代”的稀有结构。

工人 A、B、C 可以处理不同槽位，但不能各自自由挑“看起来不错”的段落。中央 work queue 必须先分配 book、slot 和 worker，避免撞车和同质化。

---

## 八、覆盖广度怎么管

不要建立一个要求每个题材、每种 status、每个位置全部交叉覆盖的巨大矩阵。采用“主轴配额 + 次轴监控”。

### 主轴

- 小说年代或目标业务相似度；
- 题材；
- 全书进度；
- 章节位置；
- 文本形态；
- 事实密度。

### 次轴

- 8 种 status；
- speaker 类型；
- 指代难度；
- 单元跨度；
- 多人物同场；
- 否定、条件、误信、承诺；
- 拟声词、聊天、系统面板、列表和断句异常。

### 分布纪律

- 近年目标业务相似文本建议占 75%～85%；
- 旧教材只保留 15%～25% 的高价值独特样本；
- 单一题材到 35% 预警，接近 40% 必须说明；
- status 不做机械平均，约 70% 跟随自然分布，约 30% 用于补稀有能力；
- 稀有 status 必须来自足够多不同作者和书，不能集中在少数来源；
- 每一批约 200 个窗口都输出分布报告，与累计分布并列。

“近年”的年份边界、题材上限和稀有 status 最低数量必须在 pilot 后写入 active，不得边挑边变。

---

## 九、窗口选择与事实密度

### 推荐密度

- 普通窗口：2～6 个事实；
- 复杂窗口：6～8 个事实；
- 通常不超过 8 个；
- 超过 8 个时优先缩小负责区或另选窗口；
- 0～1 条事实的低密度样本单列，仅在产品需要学会空答和克制过抽时纳入。

### 不应选入主训练的窗口

- 靠大量背景常识才能判断；
- 人工也难稳定决定事实边界；
- 证据跨很长范围才能成立；
- 同一证据支持大量高度近似事实，容易形成模板复读；
- 全是拟声词、标点或无信息碎片；
- 章节缺损、乱码、顺序不明；
- 与已入选窗口大段近重复；
- 只因“很难”而难，没有真实产品价值。

难样本不是越多越好。训练主干要先让模型稳定学会正确 schema、停止和基本抽取，再用少量高价值复杂样本补边界。

---

## 十、切段器合同

### 1. 切段器必须在标注前运行

顺序固定：

```text
原始章节冻结
→ 机械切段
→ 形成 B/T/只读区域
→ 人工标 A
→ 程序派生 C-2
```

禁止：

```text
先看金标
→ 再把边界切得刚好包住答案
```

### 2. 切段基本规则

- 自然段、句号、问号、感叹号为强边界；
- 超长句再按分号、冒号、完整分句或可解释逗号边界拆；
- 连续拟声词合并为一个单元；
- 极短碎片与相邻内容合并；
- 不跨人物发言轮次合并；
- 系统面板、聊天消息、论坛帖、列表项分别成单元；
- 不改写、纠错、补标点或删除原文；
- 每个单元保存原始起止字符位置；
- display text 与 raw span 分开，任何展示清洗都不能破坏回溯。

### 3. 长短阈值

“60～80 字”只能作为原型区间，不应在未测前写成永久规则。先在 30～50 个窗口上报告：

- 单元字符长度分布；
- 每窗单元数；
- A 证据跨几个单元；
- C 覆盖 A 时多带多少文字；
- 拟声词和对话轮次的异常数。

再冻结 `max_unit_chars`、短碎片阈值和合并优先级。

### 4. 窗口尺寸

- 模型可见的编号单元目标约 15～35 个；
- 超过 50 个需复核窗口是否过大；
- 整章可以有 200 个全局单元，但一次模型窗口不应展示 200 个候选编号；
- 局部窗口再映射成 `B01/T01...`。

### 5. B 区生成

- B 区只取负责区前紧邻的 0～3 个完整单元；
- 数量由固定规则决定；
- 不按某条 fact 的证据需要挑 B；
- HEAD 时 B 为空；
- B 只能作为 evidence 起点或中间，不能成为最后一个 ID。

### 6. 必做机械验证

- 同一输入、同一版本连跑两遍 SHA 一致；
- unit spans 顺序正确，不重叠；
- 目标原文范围无丢字；
- 每个 local ID 唯一；
- local→global→raw text 可反向逐字还原；
- HEAD/MIDDLE/TAIL/WHOLE 与上下文实际一致；
- B/T 权限可程序判断；
- 切段器不读取 gold 文件。

---

## 十一、A Gold 合同

### 推荐结构

```json
{
  "sample_id":"T5R04-N-B001-S001",
  "facts":[
    {
      "fact_id":"F001",
      "fact":"陈川决定明早出发",
      "status":"计划",
      "speaker":"陈川",
      "evidence_spans":[
        {
          "source_unit_id":"BK0001-CH003-U0042",
          "local_id":"T02",
          "char_start":0,
          "char_end":8,
          "text":"“明早出发。”他说"
        }
      ]
    }
  ]
}
```

### 语义规则

- 一条事实只表达一个核心断言；
- 只认当前窗口正文；
- evidence 必须是原文连续逐字短句；
- evidence 最小但足够，不加入无关解释；
- status 只使用现行八态：`已发生 / 正在发生 / 计划 / 承诺 / 条件 / 推测 / 误信 / 否定`；
- speaker 按当前正式合同执行，缺省统一为 `null`；
- 身份称谓、代词和别名不能随意互换；
- 不能从书名、简介、分类、常识或后文补答案；
- 找不到明确支持就不抽，不猜；
- 事实必须在 T 中落地，证据可以从 B 开始但不能在 B 结束；
- 事实列表按最早 evidence 起点排序；
- 同一窗口不得出现完全重复 fact；
- 若多个事实共享同一证据，必须确认它们确实是不同原子断言，而不是拆碎同一句话凑数量。

### 证据多段问题

默认 evidence 是一段连续原文。若业务确实允许离散证据：

- active 合同必须明确；
- A 使用 `evidence_groups` 表示多个连续组；
- C-2 也应使用分组后的 ID 列表；
- 不允许用一个跳号数组偷偷表达离散证据。

---

## 十二、C-2 机械派生合同

### 输出结构

```json
{"facts":[{"fact":"陈川决定明早出发","status":"计划","evidence_ids":["B01","T01","T02"],"speaker":"陈川"}]}
```

### 固定序列化

- 顶层只有 `facts`；
- 对象字段顺序：`fact / status / evidence_ids / speaker`；
- `speaker` 无值为 JSON `null`；
- UTF-8，`ensure_ascii=false`；
- 正式训练采用同一紧凑 JSON 风格；
- 不加 Markdown 代码围栏；
- 结尾一个换行和一个 EOS；
- 同一批所有正向、特殊、低密度样本都用同一容器。

### ID 规则

- ID 必须在当前题面可见；
- 按原文顺序；
- 不重复；
- 最后一个必须是 T；
- 默认要求覆盖 A evidence 的最小连续单元集合；
- 若 A evidence 只落在 T02 中间，C-2 仍返回整个 `T02`；
- 不能为了减少额外文字而重新看 gold 切单元。

### C-2 信息损失报告

每次渲染必须计算：

- `gold_char_coverage`：C 单元覆盖了多少 A evidence 字符；
- `extra_char_count`：C 单元额外带入多少非 gold 字符；
- `extra_char_ratio`；
- `unit_count`；
- `exact_unit_boundary_match`；
- 需要 1、2、3、4+ 个 ID 的事实数量。

在没有这个报告前，不得称 C-2 为“无损 A”。

### 锚字

- 模型输出合同中不含锚字；
- 人工查看界面可由程序展示 `T02｜“明早……`；
- 展示锚字和省略号不进入训练答案、评分或金标；
- 不得人工回填锚字到 C 数据。

---

## 十三、独立语义复审

每个 A 窗口至少做两遍：

### 第一遍：独立抽取

审查者先只看原文，不看候选答案，独立列出应抽事实。

### 第二遍：逐条比较

再看候选，检查：

- 漏项；
- 额外断言；
- 错主体；
- 错因果；
- 原子性；
- status；
- speaker；
- evidence 是否逐字；
- evidence 是否最小充分；
- B/T 终点是否合法。

禁止只检查 JSON 合法、证据可搜到就全 PASS。禁止几秒钟批量全通过或全拒绝。

### 审查状态

```text
CANDIDATE
REVIEWED_PASS
REVIEWED_FIX
ADJUDICATED_PASS
REJECTED
QUARANTINED
FROZEN
```

每次修订保留旧值、修改理由、审查人和时间，不覆盖历史。

---

## 十四、机械 QC 清单

每个冻结批必须通过：

### 来源和分割

- source SHA 可验证；
- author split 无交叉；
- 当前 41、旧 48 和来源书籍无泄漏；
- 训练权利状态合格；
- 同书、同章、同作者上限合格；
- 近重复窗口已检查。

### A Gold

- JSON schema 合法；
- fact 非空且无完全重复；
- status 枚举合法；
- speaker 类型一致；
- evidence text 与 source span 逐字一致；
- evidence 终点落 T；
- 事实数在允许范围；
- 高风险样本有复审记录。

### C-2

- 完全由 A 机械派生；
- `fact/status/speaker` 与 A 一致；
- local IDs 全部可见；
- 顺序和去重合法；
- 最后一个 ID 为 T；
- local→global 映射存在；
- 字符覆盖和额外带入统计已生成；
- 无字符坐标、锚字或全局长编号残留。

### 训练格式

- system/user/assistant 模板版本一致；
- JSON 字段顺序统一；
- EOS 存在；
- assistant 尾部未被截断；
- loss mask 合法；
- 训练行与冻结 manifest 一一对应；
- 没有把 dev/test 行写入 train。

---

## 十五、错误码建议

统一错误码，避免不同人写不同描述：

```text
SRC_MISSING
SRC_SHA_MISMATCH
RIGHTS_NOT_CLEARED
AUTHOR_SPLIT_LEAK
BOOK_LIMIT_EXCEEDED
CHAPTER_DUPLICATE
WINDOW_NEAR_DUPLICATE
ATOMIZER_NONDETERMINISTIC
UNIT_MAP_BROKEN
WINDOW_POSITION_WRONG
BRIDGE_GOLD_LEAK
A_SCHEMA_INVALID
A_FACT_UNSUPPORTED
A_FACT_NON_ATOMIC
A_STATUS_WRONG
A_SPEAKER_WRONG
A_EVIDENCE_NOT_VERBATIM
A_EVIDENCE_ENDS_IN_B
A_TOO_DENSE
C_DERIVATION_MISMATCH
C_ID_NOT_VISIBLE
C_ID_ORDER_INVALID
C_ID_DUPLICATE
C_EVIDENCE_ENDS_IN_B
C_MAPPING_MISSING
C_OVERCAPTURE_HIGH
SERIALIZATION_DRIFT
EOS_MISSING
TRAIN_DEV_TEST_LEAK
EVALUATOR_VERSION_DRIFT
```

错误码定义写在 active 合同，不能边做边给同一问题换名字。

---

## 十六、评分器合同

### 1. 保留原始输出

每题必须保存：

- prompt；
- raw output；
- token 数；
- finish reason；
- 是否触顶；
- 解析结果；
- 恢复结果；
- 重复诊断；
- 逐层分数。

### 2. 分层评分

#### 传输与格式

- 正常结束率；
- 触顶率；
- 原始 JSON 有效率；
- schema 合法率；
- 完整对象复读率；
- 平均与 P95 输出长度。

#### 事实语义

- exact fact match；
- deterministic normalized match；
- fact recall；
- over-extraction；
- 漏项数量；
- 案例级完整率。

归一化规则必须固定、可复现，不能使用外部 API 临时裁判。

#### status 与 speaker

先配对 fact，再判断 status 和 speaker，不能把 speaker 单个差异把整个事实语义直接归零而不单列原因。

#### A evidence

- 逐字存在；
- 最小证据匹配；
- 支持事实；
- 证据召回和过长。

#### C-2 evidence

- ID 可见率；
- ID 结构合法率；
- 终点 T 合法率；
- gold unit precision/recall；
- 映射后字符 coverage；
- extra char ratio；
- 人工证据支持复核。

### 3. 严格分与诊断分并列

- 严格分用于合同验收；
- 诊断分用于找病因；
- JSON 恢复后的对象只进入诊断分；
- 不得把一个总 F1 作为唯一结论。

### 4. 人工复核

每轮至少覆盖：

- 格式有效；
- 格式失败；
- 复读；
- 截断；
- 语义近似但严格 0；
- status 错；
- speaker 错；
- 证据 ID 错；
- 证据覆盖正确但多带文字。

抽样清单必须在看结论前冻结，不能只挑成功案例。

---

## 十七、A / C-2 对照训练合同

### 唯一允许变化

```text
A：evidence 为逐字原文
C-2：evidence_ids 为局部编号
```

### 其他全部一致

- 基座；
- LoRA 层、rank、alpha、dropout；
- 学习率、batch、梯度累积；
- epoch 或实际步数；
- 样本 split；
- 样本顺序；
- chat template；
- seed；
- max seq length；
- 阶段策略；
- 解码；
- evaluator。

### 训练前检查

- 两臂行数一致；
- 两臂 sample IDs 一致；
- `fact/status/speaker` 逐条一致；
- 旧冻结卷和当前卷无交集；
- 实际消费输入 SHA 与 sealed 数据一致；
- assistant 尾部和 EOS 未被截断；
- 输入、目标 token 差异已统计。

### 阶段策略

优先：正向与特殊样本混合打散。

若保留“正向 → 特殊”：

- 两阶段 schema 完全相同；
- 第二阶段混入正向回放；
- 保留 stage1 checkpoint；
- stage1 与 final 同卷比较；
- 回放比例、顺序和 seed 写入 lock；
- 不把阶段差与数据量差混成一个实验。

---

## 十八、每批交付物

每个 `BATCH_xxx` 至少包含：

```text
BATCH_SCOPE.md
BATCH_MANIFEST.json
SOURCE_SELECTION.jsonl
RAW_SOURCE_INDEX.jsonl
ATOMIZER_CONFIG.json
SOURCE_UNITS.jsonl
A_GOLD.jsonl
A_REVIEW.jsonl
C2_DERIVED.jsonl
MECHANICAL_AUDIT.json
SEMANTIC_AUDIT.md
COVERAGE_REPORT.md
REJECTED_AND_QUARANTINED.jsonl
SHA256SUMS.txt
HANDOFF.md
```

冻结后不得修改。返修建立：

```text
BATCH_001_R02/
```

并写明从 R01 继承了什么、修了什么、哪些 sample ID 变了。

---

## 十九、分批扩数与反馈回路

### 推荐节奏

```text
候选池和 split 锁定
→ 100 本 / 约 200 窗口
→ A 复审 + C-2 派生
→ A/C-2 成对训练和 dev 评测
→ 生成错误缺口单
→ 下一批 100 本
```

### 缺口单只允许来自 dev

缺口可写：

- 计划 status 不足；
- 多 speaker 归属错误；
- 章尾截断理解差；
- 聊天记录过抽；
- 两单元证据漏第二单元；
- 代词错主体；
- 空答窗口过抽。

不能写：

- “sealed test 第 12 题没答对，所以去找一条相似训练样本”；
- “模型不行，多加一些难题”；
- “这本书好看，多取几条”。

### 扩数停止条件

- 连续两批主要指标无改善；
- 新增样本的近重复率上升；
- 数据分布偏向单一题材或模板；
- 复读、漏字段主要由训练或解码造成；
- C-2 额外带入量超过产品可接受范围；
- 语义复审返修率持续过高；
- 权利状态无法按时清理。

---

## 二十、版本和变更管理

### 合同版本写入每一行

训练样本至少携带：

```json
{
  "contract_version":"t5-r04-cplus-r01",
  "atomizer_version":"atomizer-r03",
  "a_gold_version":"a-gold-r02",
  "c_render_version":"c2-render-r01",
  "split_lock_version":"split-r01"
}
```

### 合同变化只能发生在批次边界

- 同一冻结批内部不能混两个 atomizer 版本；
- 改字段顺序必须整批重渲染；
- 改切段器必须重新生成 unit map 和 C-2；
- 改 status 或 speaker 合同必须重新审 A；
- 评分器修复需要新 evaluator version，并对旧 raw outputs 回放；
- P0 bug 不能只修部分行后继续追加。

---

## 二十一、最容易出现的返工点

⚠️ **纯编号并不等于字符级无损。** 先定 `C2_UNIT` 合同和额外带入容忍度。

⚠️ **B 区若按 gold 选择，会成为答案提示。** B 必须机械取紧邻单元。

⚠️ **把句子切得越碎，编号越多，任务未必越简单。** 过碎会制造大量 `咚/咚/咚` 和编号长链。

⚠️ **为了让证据刚好一单元而看 gold 切段，会造成训练/上线分布不一致。**

⚠️ **同一本书只取两条也不自动等于独立。** 两条要避开同章、同事件和同结构。

⚠️ **新小说不自动代表更符合产品。** 仍要看文本形态、事实密度和目标用户分布。

⚠️ **第三条样本只能由 dev 缺口驱动。** 否则很快又会堆回少数题材和作者。

⚠️ **C 输出短不等于语义好。** 少答、早停和复读后闭合也会显得短。

⚠️ **JSON 成功率不是最终正确率。** 格式、语义、状态、speaker、证据必须分开。

⚠️ **扩大 2048 不会自动修复复读。** 可能只让循环更长。

⚠️ **特殊样本放在训练末尾会改变最近格式先验。** schema、字段顺序和回放必须统一。

⚠️ **所有运行都要保留 raw output。** 没有 raw output，就无法区分评分错杀和模型真失败。

---

## 二十二、单批验收清单

### 数据身份

- [ ] 书、作者、split、rights 均已登记
- [ ] 未包含当前 41、旧 48 及其来源
- [ ] source SHA 可验证
- [ ] 无作者级泄漏

### 选样

- [ ] 每本基础量和作者上限合规
- [ ] 采样槽位明确
- [ ] 同章和近重复合规
- [ ] 分布报告已生成

### 切段

- [ ] gold-blind
- [ ] 两次运行 SHA 一致
- [ ] unit map 可逐字回溯
- [ ] B/T/只读区权限正确
- [ ] 单元长度与数量分布合格

### A Gold

- [ ] 两遍语义复审完成
- [ ] 事实原子、status、speaker 正确
- [ ] evidence 逐字、最小充分
- [ ] facts 数量合规

### C-2

- [ ] 全量机械派生
- [ ] A/C 语义字段逐条一致
- [ ] ID 可见、顺序、终点合法
- [ ] coverage 与 extra chars 已统计
- [ ] 无锚字、坐标和长编号残留

### 训练与评测

- [ ] 实际消费输入 SHA 对上
- [ ] chat template、EOS、loss mask 已核验
- [ ] 单变量对照成立
- [ ] raw outputs 完整
- [ ] 分层评分完成
- [ ] 人工复核覆盖失败类型

### 续作

- [ ] RUN_STATE 已更新
- [ ] DECISION_LOG 已更新
- [ ] OPEN_ISSUES 已更新
- [ ] HANDOFF 已写
- [ ] 下一步唯一动作明确

---

## 二十三、Codex 每轮完成后的回传模板

```markdown
# T5 R04 C+ BATCH RETURN

## STATUS
- 当前状态：
- active batch：
- contract version：

## COMPLETED
- 完成书数：
- 完成窗口：
- A 事实数：
- C-2 派生数：
- 淘汰/隔离数：

## DISTRIBUTION
- 作者数：
- 题材：
- 年代桶：
- 章节位置：
- 文本形态：
- status：
- speaker：
- 证据跨度：

## QC
- 机械校验：
- 语义复审：
- mapping：
- leakage：
- rights：

## CHANGES
- 本轮修改：
- 变更原因：
- 影响 sample IDs：

## OPEN ISSUES
- P0：
- P1：
- P2：

## NEXT_ACTION
- 下一步只写一个动作：

## FILES_AND_SHA
- 文件：SHA-256
```

---

## 二十四、最终原则

这条线追求的不是“尽快堆到 1,200 行”，而是建立一个能长期扩展、随时中断、随时复算、不会偷偷漂移的训练资产。

判断每一步是否值得继续，只看四件事：

1. 新数据是否真的增加了独立结构和文风覆盖；
2. A 的语义真值是否稳定；
3. C-2 是否能机械重建并保持可解释的证据粒度；
4. 同卷、同配方、分层评测是否证明模型能力在改善。

任何阶段只要这四件事没有同时成立，就先停在当前批次修合同，不继续用更多小说掩盖问题。

