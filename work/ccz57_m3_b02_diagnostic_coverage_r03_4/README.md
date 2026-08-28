# CCZ-57 M3 B-02 Diagnostic 与 Coverage 离线外壳

这块主要解决一个问题：同一份 CandidateVersion 上发现的问题不能靠覆盖旧内容来改状态，Coverage 也不能顺手改候选事实。B-02 把“当时发现了什么问题”和“后来这个问题怎样结束”拆成不可变原件与追加式生命周期回执，再从这些原件重算当前开放问题。

## 当前施工门

- GitHub 施工 Issue：[#191](https://github.com/cczz412/novel-architecture/issues/191)，开工时为 Open 且带 `status:ready`。
- Linear：`CCZ-130`，开工时为 `In Progress`，没有活动硬阻塞。
- A 阶段 merge：`019df751641533c7de4d56aa38f50747fb564036`。
- B-01 merge 与开工时 GitHub current main：`905346f56cd51259c15a9517ead1517227c1719a`。
- B-01 合并回读凭证文件 SHA-256：`98ab63f1b8ff34844ba346839cb7471aeb784d400282f12c3d4fb686a5183138`。
- 本轮只获准本地代码施工和离线测试；不包含 commit、push、创建 PR、转 Ready 或合并。

## 读取什么

- GLOBAL-A 的成功准入原件原始 bytes 和它引用的精确复审／接口 manifest；
- B-01 merge/readback 原始 bytes；两份回执都先核文件 SHA，再解析 JSON 和内部 hash；
- B-01 合并后的 SegmentIndex 与 CandidateVersion 固定夹具；
- CandidateVersion 内嵌的 LineageLocator；
- CandidateVersion 已携带的 `origin_attempt_refs`；B-02 只做九字段成员校验，不重新打开 A 存储；
- 调用方提交的合成 Diagnostic 与 Coverage 观察，不读取真实正文。

## 输出什么

- `M3_DIAGNOSTIC_RECORDER_IDENTITY`：记录哪一版 Diagnostic recorder 写了原件；
- `M3_DIAGNOSTIC`：记录“当时为什么认为这里有问题”；
- `M3_DIAGNOSTIC_LIFECYCLE_RECEIPT`：只追加 `SUPERSEDED_BY_PATCH_REVIEW` 或 `CLOSED`；
- `M3_COVERAGE_OBSERVATION`：只记录 `MATCHED`、`MISSING`、`PARTIAL`；
- 开放问题派生视图：每次从原件重算，不落盘，不形成第五个真源。

唯一写集：

```text
work/ccz57_m3_b02_diagnostic_coverage_r03_4/**
```

## 运行方法

这是普通离线 Python，使用仓库锁定环境：

```bash
uv run --locked ruff check work/ccz57_m3_b02_diagnostic_coverage_r03_4
PYTHONDONTWRITEBYTECODE=1 uv run --locked pytest -q -p no:cacheprovider work/ccz57_m3_b02_diagnostic_coverage_r03_4/test_b02_diagnostic_coverage.py
PYTHONDONTWRITEBYTECODE=1 uv run --locked python work/ccz57_m3_b02_diagnostic_coverage_r03_4/self_check.py
```

正式 self-check 会先在内存里生成报告候选，核对目录成员、缓存目录、MANIFEST 和候选报告 bytes 全部一致后，才原子替换正式 `OFFLINE_REPLAY_REPORT.json`。失败时保留旧报告，不会先落一份假 PASS。

## 边界

- 不读取真实小说或 `local/`；
- 不调用真实模型 API、网络、socket、DNS、子进程或动态执行；
- 不生成 Patch、Eligibility、Decision、child CandidateVersion、因果 sidecar、作者状态或支持包；
- 不修改 B-01 CandidateVersion、item、lineage 或 pointer；
- 不生成 Gold，不评分，不证明抽取准确率、作者验证或产品验收；
- 不写 C3、M4、`f...`、`CE-...` 或 `FACT_CAUSAL_EDGE`；
- 不启动 B-03～B-12。
- GLOBAL-A 与 B-01 回执通过后，service 的私有准入方法才创建提交闭包；模块不再暴露可直接取出底层提交闭包的 runtime 工厂，store 也没有解锁令牌或 `stage`；
- 通过准入的上游 context 会封成私有 canonical bytes；对外读取只返回副本，后续改副本不能扩大 evidence 或漂移 CandidateVersion／LineageLocator；
- 四种输出只允许固定 record type、版本、来源、访问级别、留存级别和固定目录映射；提交闭包会用 sealed context 和当前 records 复核完整对象关系，pending 文件也要完成同一套语义、JSON、外壳和 bytes 回读后才做唯一一次原子发布。

当前 M3 能读取固定 CandidateVersion、LineageLocator 和已封装的上游引用，并在离线夹具中输出不可变 Diagnostic／Coverage 原件。小说辅助产品还缺少从作者真实小说运行中生成这些原件、长期保存完整历史、判断当前版本并把真实进度安全传给作者状态模块的能力。这个缺失会卡住作者在产品界面里查看“哪一段仍被卡住、是否部分完成、下一步要做什么”。

来源：Codex
