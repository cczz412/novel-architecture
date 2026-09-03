# CCZ-142｜PRODUCT_CANDIDATE_AUTHORITY 产品接线 R03

✅ 这块把 PR #230 的“单一候选 writer”继续接到产品身份：B01 root 和 B06 child 不再沿用 `FIXTURE_ONLY`，而是使用 `PRODUCT_CANDIDATE_AUTHORITY` namespace 与 `PRODUCT_CANDIDATE_AUTHORITY_READ_ONLY` access。

## 你可以怎么理解

- `CandidateAuthorityStore` 仍是 root、child 和 current pointer 的唯一候选持久 writer。
- B01／B06 构造时拿到一份冻结身份配置。请求正文不能自己把 fixture 切成 product，也不能改其中一个字段混用。
- 产品 CandidateVersion 使用 `r04-product-candidate` 合同、`pcv:` 记录编号和新的 RecordRef／record hash。
- 产品 pointer key 包含项目 ID 的完整 SHA-256，再绑定候选 Schema、章节修订、责任段和输入绑定哈希。
- B02～B09 仍写自己的原件或派生视图，只是能够安全读取同一套产品 CandidateVersion 引用。

R02 把产品迁移绑到四个同时成立的条件：项目、随库持久化的 store ID、数据库位置摘要、目标 pointer。只有这四项都和 staged 记录一致，才能切换、激活产品读取或记录前向修复。

R03 再把这组关系写进迁移控制库：一个项目只能绑定一个产品 authority store，同一项目的每个 pointer 也只能绑定该 store。不同章节和责任段可以继续在同一个 store 里各自切换；换迁移编号不能把同一项目或同一 pointer 接到第二个库。项目绑定、pointer 绑定和 `CUTOVER_COMMITTED` 状态在同一 SQLite 事务中提交，并发争抢只能有一个胜者。

影子一致性不再只比较两个字符串。来源与目标语义哈希都必须是 64 位小写十六进制 SHA-256，同时保存目标 store ID、数据库位置摘要、pointer key 和 pointer 代次。切换前会重新核对整组绑定；前向修复推进 pointer 时，也会在同一个迁移控制事务里推进保存的 pointer 代次。

普通 B01 `FixtureStore` 和普通 `B06CommitStore` 均会在创建第二份产品存储前拒绝产品 profile。这两道门由真实构造探针验收，不再在回执里直接写死 writer 数量。

上游 PR #230 R03 head `dd3219b9d4b9e6112431014394a152ef2680e013` 已通过 merge commit `68e13f64e475eece2d7d7cf2e26597335a734129` 进入 main，PR #235 的 base 已重定向到该 main。产品 profile、稳定 store ID 与 `r02-candidate` schema 身份同时生效；上游 root authority 序列锁、旧数据迁移原子门和逐表完整 schema 结构校验没有被产品接线绕过。

本轮的 B02～B05 对象来自现有合成 publisher，用来验证它们能不能完整绑定产品 CandidateVersion；它们自己的 `POLICY_FIXTURE_READ_ONLY` 输出身份没有在本票里晋升。产品化的是 CandidateVersion、pointer 和唯一 authority store，不把测试侧车原件偷换成产品原件。

## 旧历史怎么处理

旧 `FIXTURE_ONLY + POLICY_FIXTURE_READ_ONLY` 原件不改字节、不改哈希、不改引用，也不推进 pointer。

`LegacyCandidateMigration` 遇到 synthetic fixture 时固定返回 `MIGRATION_SYNTHETIC_FIXTURE_INELIGIBLE`。即使旧对象的上游已经是产品只读身份，也必须重新走产品 B01 构造和迁移控制门，不能直接复制旧 CandidateVersion 冒充产品对象。

迁移控制器只保存迁移状态和事件，不保存 CandidateVersion 或 current pointer：

```text
DISCOVERED
  → SOURCE_VERIFIED
  → TARGET_STAGED（产品读取仍关闭）
  → SHADOW_VERIFIED
  → CUTOVER_COMMITTED（旧 run 仍不能续跑）
  → POST_CUTOVER_ACTIVE
```

切换前可以中止，staged 产品对象保持不可见。pointer 检查到切换状态提交全程持有候选库锁；激活产品读取前还会再核对一次。如果 B06 在切换后、激活前推进了 pointer，必须先记录同一目标 pointer 的前向修复，不会直接放行过期影子结果。

## 本地回放覆盖

- 产品 root 创建、重放、跨项目 pointer 隔离；
- B01→B02→B03→B04→B05→B06 child→B07→B08→B09 完整影子链；
- fixture／product 混合 namespace 失败关闭；
- 普通 B01／B06 的第二产品 writer 入口在创建存储前拒绝；
- 跨项目、同项目不同 store、同 store 错 pointer 和前向修复串线均失败关闭；
- 不同迁移编号不能把同一项目接到第二个 store，并发 cutover 只能有一个胜者；
- 同一项目的多个 pointer 可以在同一个 store 中正常绑定；
- 非 SHA-256 影子值、错 store、错 pointer、错代次均在 cutover 前失败；
- cutover 与 B06 并发时，修改不能插入 pointer 检查和切换状态提交之间；
- synthetic fixture 拒绝产品迁移；
- 切换前不可见、中止、CAS 漂移；
- 切换后真实 B06 child 形成新的产品 pointer 代次；
- 控制库只新增项目到 store、项目和 pointer 到 store 的绑定表，没有 CandidateVersion、current pointer、FormalFact 或十本账表；
- 模型 API、网络 API、正式事实和十本账写入均为 0。

## 当前身份

这是 Issue #231 的 Draft R03 工程候选，当前 base 是 `main@68e13f64e475eece2d7d7cf2e26597335a734129`。当前分支和精确 main 临时叠加树均按独立组件入口通过 601 项。测试通过也不等于 PR #235 已经转 Ready、合并或接入正式事实。

来源：Codex
