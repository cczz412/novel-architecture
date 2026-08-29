# CCZ-57 M3 B-01 r03.5：候选事实版本与证据定位

## 这块主要解决什么

你可以直接理解成：M3 保存的不是一截正文，而是一条条“事实候选／账本条目”。每条候选都要带上自己的事实、状态和逐字证据，小说辅助产品以后才能沿着候选找到它对应的原文依据。

B-01 只搭这层机械底座，不判断事实对不对，也不把候选冒充成正式事实。本施工只使用合成章节，不读取真实小说，不调用模型，不访问网络。

## 准入依据

- A 阶段 PR #186 的受审 head 是 `9eafdac71f412be3f7b8ad5fd81ffc84c3de3a26`，merge commit 是 `019df751641533c7de4d56aa38f50747fb564036`。
- 旧 B-01 merge commit 是 `905346f56cd51259c15a9517ead1517227c1719a`；旧 `r03.3-candidate` 对象只读保留。
- B-01 r03.5 合同文件 SHA-256 是 `34c695b81d1e06730eba71d75fa8176c98ca086c3aea6c29c289c4bde07b4772`。
- CZ 语义决定回执 SHA-256 是 `54dcd1e6bb6ddd7b3d166c568995f6d78bb544f213044e316f6ef1d24c660058`。
- 正式施工票是 GitHub Issue #195；开工时 current main 是 `189fb4a28a036aa5126baf32950f0fef2b359fa5`。

## 输入是什么

B-01 的候选适配层读取三类合成输入：

- 已接纳的章节版本，里面有精确章节编号、修订号和全文 SHA；
- 同一个作者工作区来源代次；
- 同代写作资料，第一版至少包含题材和核心人物，可选平台、简介和规划。

现行上游还没有可直接复用的 M3 `RecordRef`。因此这里固定的是只读候选接口和合成夹具，不宣称模块一的真实产品接线已经完成，也不增加新的上游 writer。

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

- 调用方只提交 `fact`、`status`、`evidence`，以及按需提供的 `speaker`；不能提交字符范围或匹配位置。
- B-01 自己在精确章节 UTF-8 bytes 中查找 evidence，并把所有匹配位置写进绑定对象；同一句重复出现不会偷偷挑一个位置。
- evidence 必须完整落在当前责任段内，必须能逐字回读。
- 句数只按 `。？！` 判断，连续句末符号算一次，句末后的引号或括号不另算一句；非空 evidence 只能有 1～2 句。
- 事实是候选内容，evidence 是它对应的逐字原文依据；两者不能混成一个字段。

## 最重要的边界

- 新 writer 只写对象合同 `r03.5-candidate`、候选 schema `novel-fact-extraction-v2.1`。
- 旧 `r03.3-candidate` 对象不补字段、不重算哈希，只能通过兼容读取器返回“历史只读”摘要。
- B-01 只创建 root baseline。真实 child 创建、pointer 推进和回退仍归 B-06。
- pointer 只能使用 `FIXTURE_ONLY`，并把 schema、来源代次和输入绑定纳入身份；不能写产品 current pointer。
- `VersionDiff`、两个 Locator 都是随时重算的结果，不能保存成第二份真源。
- 失败必须发生在发布前。测试会比较对象数、pointer 数、目录内容和状态文件哈希，不能靠写后删除冒充 0 写入。
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

来源：Codex
