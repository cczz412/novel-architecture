# M3 B-06｜事实候选最小提交核心

这个目录只解决一件事：B-05 已经明确说“这组 Patch 可以交给 B-06”以后，把修改保存成新的事实候选版本，并安全地把 current pointer 从旧版本推到新版本。

你可以直接理解成：B-04 写修改单，B-05 审修改单，B-06 才是真正把获准修改存成下一版。它仍然没有把事实写进十本账，也没有把候选升级成正式事实。

## 一次提交只落三样东西

- 一个新的 child CandidateVersion；
- current pointer 从 exact base 通过 compare-and-swap 推进到 child；
- 一份 `M3_CANDIDATE_MERGE_RECEIPT`，说明用了哪份 B-05 路线、哪组 Patch、旧版本和新版本分别是谁。

三样共用同一个 SQLite 事务。任何一步失败，child、pointer 更新和 MergeReceipt 都不会出现半套。

这里没有 `M3_COMMIT_INTENT` 表，也没有每次提交的 before/after pointer snapshot 表。MergeReceipt 只保存前后指针的哈希、代次和候选引用，不再复制两份完整指针对象。

## B-01～B-06 怎么接

```text
CCZ-142 质量筛选后的干净初抽
  → B-01 保存 root CandidateVersion

发现问题时才走：
B-02 记录问题与覆盖缺口
  → B-03 按需受控读取证据
  → B-04 生成 Patch 与保护范围
  → B-05 验证并路由
  → B-06 原子保存 child 并推进 pointer
```

B-02～B-05 不是每一条干净候选都要强制跑一遍。它们只处理有问题、要复查或要修改的部分；B-03 也只在确实需要回读证据时出现。因此这条线是按问题触发的漏斗，不是一条越堆越长的固定流水线。

## 共享修改内核

B-05 原来已经会在内存里试应用 Patch。B-06 没有再写第二套 apply、item hash、lineage index、排序和 version payload hash 逻辑，而是直接共用：

`work/ccz57_m3_b05_patch_route_r03_5/candidate_mutation_kernel.py`

B-05 用它算 trial child，B-06 用同一份代码生成正式 child。B-06 还会把结果和 B-05 原件里的 `canonical_apply_result_hash` 对回去；逐字不一致就拒绝提交。

## 失败边界

这些情况全部失败关闭，正式三件套保持不变：

- B-05 route 不是当前 active，或该 route unit 不是 `ALLOW_FOR_B06`；
- B-05 绑定的 base、Patch、ProtectionSet 和当前输入不一致；
- B-02 scope、政策选择或非内容门在两次权威读取之间漂移；
- B-05 的试应用结果和 B-06 child payload 对不上；
- current pointer 已经被别的提交推进；
- 同一个 operation id 换了输入；
- child、pointer 或 receipt 任一步出现注入故障；
- 两个并发请求同时抢同一个 exact base。

同一个 operation id、同一份输入重放时，只回读原来的 MergeReceipt，不再写第二个 child。

## 给 B-07 留的只读安全插口

B-07 接入后，B-06 可以在同一个 SQLite 提交事务里，先通过受信任的 reader 只读核对当前 run。你可以直接理解成：真正落 child 之前，再确认“这次运行还活着，而且仍在等这次 B-06 发布”。

这个插口只接受 project、run、epoch 和状态版本四项定位断言。当前状态、`B06_OUTCOME_PENDING` 和 pending operation 是否匹配，必须由安装在 service 上的 reader 从本地数据库回读，调用方不能自己报一个“可以继续”。

- 已经存在的同 operation MergeReceipt 会先回读，后来即使 run 已经 STOPPED，也能完成 ack-lost 对账；
- 尚未发布的新 operation 才检查 run fence；
- fence 不匹配时，child、pointer、MergeReceipt 保持 0 新写入；
- reader 只拿到同一 connection 的 SELECT-only 视图，不能借这个插口写 RunState；
- run fence 身份进入 request hash，同 operation 不能偷偷换 run、epoch 或状态版本。

B-06 仍不创建也不修改 `CurrentRunState` 或 `StopReceipt`。这两样由后续 B-07 的唯一 writer 负责。

## 当前证明到哪

当前是 synthetic fixture 施工件：

- 不读取小说正文；
- 不调用模型、网络或真实 API；
- 不写十本账、正式事实或作者确认；
- 只证明 B-01～B-05 夹具可以接到 B-06，并证明原子性、幂等、并发、reopen 和失败回滚。

⚠️ 它还不是产品已投入使用。CCZ-142 的真实保存结果、生产 current-pointer store、B-02／政策／门的正式 authority reader 还没有接进这个目录。那些适配继续由 CCZ-142 影子接线验证，不能拿这里的 fixture PASS 冒充真实产品已经跑通。

## 运行

在仓库根目录执行：

```bash
uv run --locked pytest -q work/ccz57_m3_b06_commit_core_r01/test_b06_commit_core.py
uv run --locked python work/ccz57_m3_b06_commit_core_r01/self_check.py
uv run --locked ruff check work/ccz57_m3_b06_commit_core_r01
```

来源：Codex
