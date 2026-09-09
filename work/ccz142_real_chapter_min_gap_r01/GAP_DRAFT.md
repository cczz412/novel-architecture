# GitHub #271｜真章最小挡点说明

状态：`CONSTRUCTION_DRAFT__NOT_MERGED`  
核对日期：2026-09-05  
施工入口：GitHub #271；Linear 宿主：`CCZ-142`  
指定版本：`main@9c2fb95881caf795aae46f1838a93eb674a63a5e`  
施工口径：Q7＝施工 C；完成标准仍是人话结果卡。

## 结论：必须停，不交代码补丁

**本轮只点名一个挡点：指定 main 上的候选读写链仍是“仅供测试”的身份，缺少已合入的产品候选身份通路。这正是未合 PR #235 所属的产品 namespace／access 范围。** [E1][E4][E5][E6]

这里的“身份通路”，指候选版本、指向当前版本的指针，以及读取它们的程序，都按同一套获准使用的产品身份工作。现有测试身份叫 `FIXTURE_ONLY`，不能换个页面标题就当成产品候选权威。

因此，票面要求的二选一结论是：**必须停（#235 范围）**，不是“本票能补”。本次只交这份缺口说明。既不补 #235，也不在新目录里复制一套替代实现。[E1][E2]

这不等于“任何文本都不能做离线夹具实验”；本轮判断的是：在不冒充产品权威的前提下，能否把现有链路交成“这本书第几章丢进去，得到所要求的人话结果卡”。本轮没有读取或试跑真实章节。

## 为什么点名这一块

### 已合入的库，解决的是单库写入，不是产品身份

候选库说明把边界写得很清楚：B01 与 B06 的候选合同仍把指针身份固定为 `FIXTURE_ONLY`；产品采用前，还要另行批准候选版本、指针和读者的产品 namespace／access 迁移。[E4]

只读核对候选库代码开头时，也能看到它仍从 B01 导入 `FIXTURE_POINTER_NAMESPACE`，库结构身份仍为 `r02-candidate`。这与说明一致；本轮没有重审该库的写入、锁或迁移正确性。[E8]

### 现有 A 轨能读夹具，但不会把它读成产品身份

负责“从当前指针读候选，再排成人话卡”的函数叫 `prove_current_read`。指定版本的实际代码保留了下面几条规则：[E5]

| 实际条件或字段 | 代码行为 | 本轮怎样解读 |
|---|---|---|
| 没有传入库路径 | 返回 `GAP_NO_LIVE_STORE` | 只能说明这次调用没给路径，不能据此宣布用户机器上没有库 |
| 成功读到夹具，且有可展示条目 | 可以返回 `READ_OK`，同时在 `limitations` 中保留 `GAP_NOT_PRODUCT_IDENTITY` | 读成功不等于已有产品身份 |
| 读到有条目的候选，但指针身份不是 `FIXTURE_ONLY` | 末尾检查返回 `GAP_NOT_PRODUCT_IDENTITY` | 把标签换成产品身份，也不能直接通过现有读路 |
| 表示产品是否已采用的字段 `product_adopted` | 保持 `False` | 不能把一次读取或展示成功写成产品采用 |

这里特别区分“读失败的缺口”和“读成功但仍有的限制”：夹具正常读出时，`GAP_NOT_PRODUCT_IDENTITY` 可以出现在 `limitations`，并不要求 `status` 一定是 `GAP`。本说明沿用这个已有名称指认身份限制，没有新增或改写运行时缺口码。

上表是代码核对，不是本轮运行回执，也不是对某本书的抽取结果。

### #235 当前确实还没合入

在线 PR 元数据返回：`state=open`、`draft=true`、`merged_at=null`。本轮只查看它的标题、说明和状态，没有打开它的差异补丁，也没有审查、执行或带回分支实现。[E6]

在线 `main` 指针与指定完整 SHA 一致；该提交是 PR #269 的合入提交。本轮没有把 #235 的分支或其说明中的旧 base 当成 main。[E3]

这些证据指向的是同一个身份挡点，不是三个待施工任务。

## 为什么不改成“本票能补一个入口”

已有预览包提供了无活库页和夹具 HTML 样张，并写明身份仍是 `FIXTURE_ONLY`。因此，“能打开一张卡”这件事已经有可看的样张；它不能替代“真章产品候选已经可用”的证明。[E7]

新增入口、说明或缺口展示，可以让人更容易看见当前状态，却不能补上产品身份。给调用补一个库路径，也只能消除“这次没给路径”的条件，不能消除读出后仍有的身份限制。[E5]

在线 #271 明确要求：缺口若属于未合的产品 namespace，停。收紧评论又点名，候选库、A 轨三包、B01–B09 和 `product_candidate_authority_r01` 都只读。把同样的逻辑复制进本票新目录，不会因此变成获准的“极薄接线”。[E1][E2]

**本轮到这里停止施工。** 不新增启动器、读者、转换器、产品身份伪装或兜底写入。真实小说 API 也没有被另列成第二个挡点；本轮既未调用，也不判断它是否已经可用。

同样，#235 后续即使测试全绿或发生合入，也不能直接推出 `CCZ-142` 完成。#271 明写的完成标准仍是人话结果卡，机械 PASS 不代表抽取准确率。[E1]

## 在线真源与 ZIP 对照

本轮把在线 #271 正文及收紧评论作为施工授权，使用指定 SHA 的 GitHub 文件判断代码现状。ZIP 里的提示词、判断卡和口述只作为待核对材料，没有拿它们扩大授权。

| 对照项 | 核对结果 | 采用口径 |
|---|---|---|
| ZIP 写的 `main@9c2fb958` 与在线 main | 一致，完整 SHA 见本文开头 | 不换基线 |
| ZIP 写的 #235 仍为 Draft、不是 main | 与在线 PR 元数据一致 | 不拿分支代码当已合入能力 |
| ZIP 的 #271 摘录与在线正文 | 停手条件一致；ZIP 摘录不是完整票面 | 在线正文优先 |
| 2026-09-05 收紧评论 | ZIP 中的票面摘录和打包提示未完整带入该条评论；当前用户消息与在线评论均已补充 | 按在线评论的更窄写集执行 |
| 候选库、只读证明包、HTML 预览包的三份 README | ZIP 文件的 Git blob 哈希与指定 SHA 下在线返回的哈希全部一致 | 三份文件没有内容漂移 |

三份已逐字核对文件的仓库路径与 Git blob 哈希如下。ZIP 内对应路径均在 `02_current_route/` 下。

| 仓库路径 | Git blob SHA |
|---|---|
| `work/ccz142_candidate_authority_r01/README.md` | `1de3dda7cad240e88524d78af4c8f8489496a003` |
| `work/ccz142_current_candidate_read_proof_r01/README.md` | `09caaeadaf0b73d0cfa21ff8154fb3ee4ab20d40` |
| `work/ccz142_current_candidate_read_preview_r01/README.md` | `540ee1af5e0e26cc0132f4073f95a03949d2d187` |

**已核对范围内没有相反的业务结论。** 发现的是 ZIP 授权摘录不完整，不是允许越出写集的另一份授权。未对其他仓库文件作“全部一致”或“全仓不存在替代路径”的断言。

本轮只调用 GitHub 只读工具核对授权、状态和代码。没有调用 Linear、Notion、Slack，也没有把这些地方视为已经核对过的真源。

## 本次交件与检查结果

回包只有同一份说明的两个相同副本：

```text
GAP_DRAFT.md
work/ccz142_real_chapter_min_gap_r01/GAP_DRAFT.md
```

根目录副本供直接阅读，是 ZIP 包装文件，**不要把它写到仓库根目录**。相对仓库路径下的副本，是本票唯一待新增文件，满足在线票面“写集里一张缺口说明”的要求。若本地目标路径已经存在，不要覆盖，应先核对“只允许新建”的边界。

代码补丁为零，没有附 #235 实现，没有生成产品候选或修改任何上游目录。未提交、推送、创建 PR、合并、转 Ready 或关票，也未改任何在线状态。

| 检查 | 本轮结果 | 不能据此推出什么 |
|---|---|---|
| 输入 ZIP 自带 SHA256SUMS | 17 个列出成员全部匹配；ZIP 共 18 个成员 | 不代表产品能力或语义准确率 |
| 三份关键 README 与在线 Git blob 对照 | 3 份全部匹配 | 不代表整仓逐文件对照 |
| 回包内容与写集检查 | 仅两个相同 Markdown 副本；唯一仓库新文件在允许目录内 | 不代表已经写入仓库或获准合入 |
| 定向 pytest、self_check、Ruff | 未执行；本轮没有代码补丁，不套用“能补”分支的测试回执 | 不报告代码 PASS、准确率或真章可用 |
| 真实章节与模型 API | 未读取、未调用 | 不报告某本书第几章已经出卡 |

输入包：`issue271_min_gap_pro_build_20260905.zip`。其 SHA-256 为：

```text
da65614f0dc139e575b8cdb045606903ab74ef6b49d0e1c94e7a7a4cc9b1d8e0
```

本地验收只需确认：结论明确选“必须停”，只点名产品候选身份这一个挡点，回包没有代码或越界文件。在线票面允许以缺口说明完成本票的交件要求；本回包本身不等于票已关闭或模块已完成。[E1]

## 仍无法确认／证据缺口

本轮没有真实章节、实际库现场和对应运行结果，不能确认某本书第几章的候选是否存在、能否完整出卡，或抽取准确率是多少。后续应由获准操作真实数据的本地执行者，在单独授权的范围内核对。这影响未来的真章完成验收，不影响本轮按指定 main 停在身份边界的判断。

本轮未审 #235 的实现或测试，不能确认该 PR 是否足够、安全，或是否应合入。应由该 PR 的独立审查和拍板流程确认。这个未知也不允许本票代写、代审或代合。

## 证据索引

以下 GitHub 文件均按本文开头的完整 SHA 读取；引用代码时以函数名定位，没有把 ZIP 的目录薄切片冒充完整代码。

- **[E1]** [GitHub #271 在线正文](https://github.com/cczz412/novel-architecture/issues/271)：唯一挡点、停手条件、写集、只交说明的验收规则、Q7 与完成标准。
- **[E2]** [#271 收紧评论](https://github.com/cczz412/novel-architecture/issues/271#issuecomment-5550476228)：所有极薄接线只能在本票新目录；缺口若是 #235，只交说明。
- **[E3]** [在线 main 引用](https://api.github.com/repos/cczz412/novel-architecture/git/ref/heads/main)与[指定提交](https://github.com/cczz412/novel-architecture/commit/9c2fb95881caf795aae46f1838a93eb674a63a5e)：核对时 main 指针与指定 SHA 一致，提交为 PR #269 的合入。
- **[E4]** [候选库 README，第 46–50 行](https://github.com/cczz412/novel-architecture/blob/9c2fb95881caf795aae46f1838a93eb674a63a5e/work/ccz142_candidate_authority_r01/README.md#L46-L50)：夹具身份与另行批准产品身份迁移的边界。
- **[E5]** [现有只读证明代码](https://github.com/cczz412/novel-architecture/blob/9c2fb95881caf795aae46f1838a93eb674a63a5e/work/ccz142_current_candidate_read_proof_r01/current_read_proof.py)：`_base_proof`、`prove_current_read`、`project_human_card`；另见[该包 README](https://github.com/cczz412/novel-architecture/blob/9c2fb95881caf795aae46f1838a93eb674a63a5e/work/ccz142_current_candidate_read_proof_r01/README.md)。
- **[E6]** [PR #235](https://github.com/cczz412/novel-architecture/pull/235)及[本轮读取的 PR 元数据接口](https://api.github.com/repos/cczz412/novel-architecture/pulls/235)：只用于标题、说明及 `open`／`draft=true`／`merged_at=null` 状态核对，不是代码审查结论。
- **[E7]** [HTML 预览包 README](https://github.com/cczz412/novel-architecture/blob/9c2fb95881caf795aae46f1838a93eb674a63a5e/work/ccz142_current_candidate_read_preview_r01/README.md)：现有 HTML 样张、夹具横幅与未接真实小说 API 的边界。
- **[E8]** [候选库代码，第 1–165 行](https://github.com/cczz412/novel-architecture/blob/9c2fb95881caf795aae46f1838a93eb674a63a5e/work/ccz142_candidate_authority_r01/candidate_authority.py#L1-L165)：本轮只读范围；导入 B01 的夹具身份常量，库结构身份为 `r02-candidate`。

来源：ChatGPT
