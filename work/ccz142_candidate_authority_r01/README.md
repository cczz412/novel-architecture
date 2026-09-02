# CCZ-142｜单一 CandidateAuthorityStore 接线 R01

✅ 这份施工候选已经让 B01 root 与 B06 child／current pointer 写进同一个候选权威库，同时保留 B01～B08 原离线夹具不变。

你可以直接理解成：B01 仍然决定 root 长什么样，B06 仍然决定 child 怎样安全提交；真正碰数据库的候选写入只走 `CandidateAuthorityStore`。

Issue #231 没有另造第二个候选 writer，而是让这个 store 在构造时接受一份不可变的身份配置。原 R01 夹具身份仍然可读；产品身份使用独立合同、只读权限、记录编号和 pointer key，重开时也必须与库内身份一致。

R02 在 metadata 里增加了随库持久化的 `authority_store_id`。它与项目身份、数据库位置摘要一起用来绑定产品迁移：同项目另建一个库，或把库拷到另一个位置，都不能冒充当时切换的目标库。

## 当前工程身份

- GitHub 施工入口：[#227](https://github.com/cczz412/novel-architecture/issues/227)
- 开工基线：`main@c89beb4368b6b79598906bdc27819a16f751155b`
- 当前是 Draft PR 候选，不是产品采用，也没有修改正式事实合同。
- 写集只在 `work/ccz142_candidate_authority_r01/**`。

## root 怎样进入同一个库

对外只给 `CandidateRootInitializer.initialize_root(request)`。调用方提交的是一个绑定 project、章节修订、责任段和输入代次的 root 请求，拿不到整库 `read`、通用 `commit` 或 pointer 裸写能力。

内部继续调用 B01 当前组装器：

1. 两次读取上游 authority，确认章节修订、输入代次和责任段没有漂移；
2. 在内存捕获器里生成并读回 B01 的段索引、root CandidateVersion、初始 pointer 和 pointer snapshot；
3. 把已经通过 B01 合同的冻结写集一次性交给 `CandidateAuthorityStore`；
4. 同 operation 同输入只回原结果，换输入或抢同一 pointer 失败关闭。

内存捕获器不写文件。产品接线路线不会生成 B01 `state.json`。

## child 怎样继续

`CandidateAuthorityStore` 继承现有 B06 原子提交能力。B06 直接打开已经包含 root 的同一 SQLite，不调用 `B06CommitStore.initialize(...)` 复制 root 和 pointer。

child CandidateVersion、current pointer CAS 和 MergeReceipt 仍在一个事务内。B07 run fence 与 B08 责任段终态继续使用原实现和各自 writer。

## 多作用域和迁移

- 每个 `project_scope_id` 使用一份独立 authority store；跨项目请求会在写前拒绝。
- 同一项目可以保存多章节、多责任段和不同输入代次的 root；每个逻辑 pointer 独立。
- 两个并发的同 root 请求只有一个物理提交，另一个幂等回读。
- `LegacyCandidateMigration` 可以只读导入旧 B01 `state.json` 与旧 B06 SQLite；目标库写入仍由 `CandidateAuthorityStore` 完成。
- B06 旧 pointer 只有在 MergeReceipt 能从当前 root 逐代证明到 incoming child 时才允许推进。
- 迁移不覆盖源文件，同 migration ID 换源会在导入前拒绝。

## 当前不能叫产品采用

⚠️ B01 r03.5 与 B06 r01 的候选合同仍把 pointer namespace 固定为 `FIXTURE_ONLY`。本票没有权限改这份既有候选合同，所以这里只证明“单库、窄 capability、原子写入和迁移接法成立”。

正式产品采用前还要单独批准一次合同迁移：给 CandidateVersion、pointer 和相关读者增加产品 namespace／access，并同时回归 B01～B09。Draft PR 不会把这个缺口藏起来。

## 没做什么

- 没写 FormalFact、正式 current pointer、C4、C11、作者签字或十本账；
- 没调用模型 API、网络或浏览器；
- 没读取真实小说正文；
- 没改 B01～B08 现有文件；
- 没删除旧夹具；旧 B06 bootstrap 只在新接线路线被禁止。

## 本地验证

```bash
uv run --locked python -m py_compile work/ccz142_candidate_authority_r01/*.py
uv run --locked ruff check work/ccz142_candidate_authority_r01
uv run --locked pytest -q work/ccz142_candidate_authority_r01/test_candidate_authority.py
uv run --locked python work/ccz142_candidate_authority_r01/self_check.py
```

完整回归还包括 B01、B05、B06、B07、B08 原测试。实际命令、数量和 SHA 见本目录离线回放报告与 PR 描述。

本轮实际通过 423 项：新目录 27 项，B01～B08 直接依赖 396 项。完整分项见 `TEST_RECEIPT_R01.json`。

来源：Codex
