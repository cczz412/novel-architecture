# CCZ-57 M3 B-01 r03.5：候选事实版本与证据定位

## 这块主要解决什么

你可以直接理解成：M3 保存的不是一截正文，而是一条条“事实候选／账本条目”。每条候选都要带上自己的事实、状态和逐字证据，小说辅助产品以后才能沿着候选找到它对应的原文依据。

B-01 只搭这层机械底座，不判断事实对不对，也不把候选冒充成正式事实。本施工只使用合成章节，不读取真实小说，不调用模型，不访问网络。

这次窄修又补了一道来源门：公开写入入口不再直接接收 `raw_items`。候选必须先经过 CCZ-142 正文抽取交接适配层，换成只对当前 B-01 服务实例有效的临时凭证，再进入 root baseline 初始化。签发能力和普通 B-01 调用面分开分发：CCZ-142 适配端拿签发能力，B-01 调用端只拿入库服务，服务自身既没有公开签发方法，也不能自行完成运行时组装。画布计划事实、章节内核、旧 C3 预览和普通 JSON 都不能从普通 B-01 调用面自报来源后落库。

本次正式采用的输入减法把“题材”和“核心人物”从必填改成可选。B-01 真正离不开的是当前章节修订和来源代次；写作资料没有时可以创建 root，有资料时仍要逐项核对类型、来源代次、排序和重复项。这样 CCZ-142 已筛好的正文抽取结果不会因为上游没另造一份题材卡或人物卡而被挡住。

同时新增 `product_source_adapter.py`，把现有 AuthorWorkspace 的章节索引、章节修订账、C10 材料身份和初始接纳操作映射成 B-01 已有的来源代次记录。它对这四个逻辑键做两次一致读回，不读取章节正文、冻结源或工作稿，不写产品状态，也不调用模型。

## 准入依据

- A 阶段 PR #186 的受审 head 是 `9eafdac71f412be3f7b8ad5fd81ffc84c3de3a26`，merge commit 是 `019df751641533c7de4d56aa38f50747fb564036`。
- 旧 B-01 merge commit 是 `905346f56cd51259c15a9517ead1517227c1719a`；旧 `r03.3-candidate` 对象只读保留。
- B-01 r03.5 合同文件 SHA-256 是 `34c695b81d1e06730eba71d75fa8176c98ca086c3aea6c29c289c4bde07b4772`。
- CZ 语义决定回执 SHA-256 是 `54dcd1e6bb6ddd7b3d166c568995f6d78bb544f213044e316f6ef1d24c660058`。
- 正式施工票是 GitHub Issue #195；开工时 current main 是 `189fb4a28a036aa5126baf32950f0fef2b359fa5`。
- 本次来源准入窄修是 GitHub Issue #203、Linear CCZ-148；分支从 current main `9e115ccc5070760f485594235d67daa30175ba37` 建立。
- 本次真实输入减法是 GitHub Issue #212、Linear CCZ-151；分支从 current main `56a623b2e42e649c975177374ea27a2e3df15431` 建立。

## 输入是什么

B-01 的候选适配层读取两类必需输入和一类可选输入：

- 已接纳的章节版本，里面有精确章节编号、修订号和全文 SHA；
- 同一个作者工作区来源代次；
- 同代写作资料，可选题材、核心人物、平台、简介和规划；整组可以为空。

现行 AuthorWorkspace 没有直接输出 M3 `RecordRef`，所以适配层只在内存里生成现有 B-01 可验证的只读引用，不增加新的上游 writer。产品映射已经用合成 AuthorWorkspace 通过定向测试，但 CCZ-142 运行时还没有调用这个适配层，不能把“适配器存在”写成“真实抽取管线已经装好”。

合成 CCZ-142 交接物还必须逐项绑定作者工作区、章节修订、来源代次、写作资料、责任段、尝试引用和完整候选条目。临时凭证只在签发它的同一个服务实例里可用；普通字典、手工新建的同类型对象、复制品和另一服务签发的凭证都会失败关闭。签发后再改适配端原字典，也不会改变已经封存的候选。

## 输出是什么

持久保存的只有三种不可变记录：

- `M3_SEGMENT_INDEX_SNAPSHOT`：一章按 UTF-8 bytes 切成哪些责任段，并证明从 0 连续覆盖整章；
- `M3_CANDIDATE_VERSION`：某一责任段的 root 候选版本、输入绑定、事实条目和证据绑定；
- `M3_CANDIDATE_POINTER_SNAPSHOT`：合成夹具里的 current pointer 第一次指向哪个候选版本。

另有三个不持久保存的结果：

- `M3_LINEAGE_LOCATOR`：按稳定编号找到候选条目；
- `M3_EVIDENCE_LOCATOR`：从候选条目找到它已经绑定的证据字段；
- `VersionDiff`：临时比较父子候选版本的字段差异。

对象样例和唯一 writer 目录见 `OBJECT_SHAPES.json`。

## 证据怎么绑定

- CCZ-142 交接适配端只提交 `fact`、`status`、`evidence`，以及按需提供的 `speaker`；不能提交字符范围或匹配位置。
- 这四个字段只允许来自 CCZ-142 正文抽取候选交接物；工作卡规划内容即使长得一样，也不能从公开 B-01 写入入口直接落库。
- B-01 自己在精确章节 UTF-8 bytes 中查找 evidence，并把所有匹配位置写进绑定对象；同一句重复出现不会偷偷挑一个位置。
- CandidateVersion 持久 writer 会重新核对段索引、精确章节 bytes 和完整位置集合；调用方即使把错误位置连同哈希一起重算，也不能写入。
- evidence 按来源原始 Unicode code point 保存和哈希，不做 NFC 改写；组合字符的 UTF-8 bytes 必须逐字往返一致。
- evidence 必须完整落在当前责任段内，必须能逐字回读。
- 句数只按 `。？！` 判断，连续句末符号算一次，句末后的引号或括号不另算一句；非空 evidence 只能有 1～2 句。
- 事实是候选内容，evidence 是它对应的逐字原文依据；两者不能混成一个字段。

## 最重要的边界

- 新 writer 只写对象合同 `r03.5-candidate`、候选 schema `novel-fact-extraction-v2.1`。
- 旧 `r03.3-candidate` 对象不补字段、不重算哈希，只能通过兼容读取器返回“历史只读”摘要。
- B-01 只创建 root baseline。真实 child 创建、pointer 推进和回退仍归 B-06。
- pointer 只能使用 `FIXTURE_ONLY`，并把 schema、来源代次和输入绑定纳入身份；不能写产品 current pointer。
- `VersionDiff`、两个 Locator 都是随时重算的结果，不能保存成第二份真源。
- 失败必须发生在发布前。每个失败夹具除了比较对象数、pointer 数、目录内容和状态文件哈希，还会逐项记录 commit、建目录、临时文件写入、原子替换和清理尝试；任一写入尝试都会让 self-check 失败，不能靠写后删除冒充 0 写入。
- 来源准入凭证不持久化，也不进入 CandidateVersion、SegmentIndex、pointer 或操作回执。旧 r03.5 对象字段、固定向量和记录哈希不因本次窄修改变。
- AuthorWorkspace 适配只读取 `chapter_index`、`chapter_revisions`、`chapter_materials` 和 `chapter_admission_operations`；`chapters`、`chapter_sources` 和 `draft` 明确禁止。来源在两次读取之间漂移会直接失败，不会拼出一个混代 root。
- 题材、核心人物、平台、简介和规划都是可选上下文。缺失不再挡住 root；一旦提供，未知类型、重复类型、错误来源代次或非规范排序仍会在发布前失败。
- N08 用两个独立本地 Python 进程证明“提交后中断”和“新进程重开＋同操作重放”；这两个进程属于离线测试工具，不是产品调用。

## 怎么复验

这些命令只使用锁定的本地依赖：

```bash
uv run --offline --locked ruff check work/ccz57_m3_b01_candidate_version_r03_5
uv run --offline --locked ruff format --check work/ccz57_m3_b01_candidate_version_r03_5
uv run --offline --locked pytest -q work/ccz57_m3_b01_candidate_version_r03_5/test_b01_contract.py
uv run --offline --locked python work/ccz57_m3_b01_candidate_version_r03_5/self_check.py
```

`OFFLINE_REPLAY_REPORT.json` 只证明机械检查通过。里面的语义验收仍为空，不能拿它宣布抽取准确、作者认可或产品验收完成。

这道进程内凭证证明的是“普通 B-01 调用面没有签发权，输入经过了组装层单独分发的 CCZ-142 交接能力”，不是远端平台签名，也不防同一 Python 进程里能直接调用私有组装函数的恶意代码。新增产品适配层只关闭 AuthorWorkspace 元数据到 B-01 来源代次的映射缺口；真实 CCZ-142 保存结果还要在它自己的施工线调用这个入口并做影子回放，之后才能说管线已经接上。

来源：Codex
