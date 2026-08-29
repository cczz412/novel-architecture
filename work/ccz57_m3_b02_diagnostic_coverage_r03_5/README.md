# CCZ-57｜M3 B-02 r03.5 条目级 Diagnostic 与 Coverage 骨架

✅ 这块主要解决一个问题：作者看到“这条候选有问题”或“这里漏了一条候选”时，小说辅助产品必须能从这条结果回到同一版 CandidateVersion 里的具体条目和逐字依据，不能只剩一次模型尝试或一个无法回读的 span hash。

## 当前读什么、能输出什么

当前模块只读取 B-01 r03.5 的合成 CandidateVersion、SegmentIndex、LineageLocator、EvidenceLocator 和合成章节 bytes。它能输出四类不可变对象：

- `M3_DIAGNOSTIC_RECORDER_IDENTITY`：记录 Diagnostic writer 身份；
- `M3_DIAGNOSTIC`：记录某个具体候选条目及其 evidence 的问题原件；
- `M3_DIAGNOSTIC_LIFECYCLE_RECEIPT`：追加问题关闭或被修补审查取代的状态回执；
- `M3_COVERAGE_OBSERVATION`：记录一段逐字来源证据是已匹配、部分匹配还是缺失。

开放问题列表由 `open_issue_projection.py` 随时重算，不持久化，也不复制原文。

小说辅助产品目前仍缺少从作者真实小说运行中生成这些对象、长期保存完整历史、判断哪一版是当前版，以及把真实进度交给作者界面的能力。这个缺失会卡住作者在实际写作中查看问题、回到逐字依据和安全补候选；本目录只证明离线合同与失败关闭，不代表真实产品已经可用。

## r03.5 的关键边界

- 所有 Diagnostic 和 Coverage 都同时绑定 exact `r03.5-candidate` CandidateVersion、`novel-fact-extraction-v2.1`、章节修订和责任段。
- Diagnostic target 必须同时带同一条目的 LineageLocator 与 EvidenceLocator。缺 EvidenceLocator 时 0 写入，不允许退回 Attempt ref。
- Coverage 的 `source_evidence_binding` 保存逐字来源、UTF-8 bytes 哈希、句数和全部内部匹配位置。
- `MATCHED`／`PARTIAL` 至少保存一组成对的 LineageLocator＋EvidenceLocator；两者必须属于同一条目和同一 exact CandidateVersion。
- `MISSING` 只保存 `source_evidence_binding`，`matched_candidate_bindings` 必须是空列表。
- evidence 沿用 B-01 的保真规则：原始 Unicode code point 和 UTF-8 bytes 原样保存、原样哈希，不做 NFC。普通非来源字段仍做 NFC。
- 旧 `r03.3-candidate` 与旧 B-02 目录只读。新版 writer 不升级旧 `text/quote`，不重算旧哈希。

## 写入、事务与停点

唯一写集是：

```text
work/ccz57_m3_b02_diagnostic_coverage_r03_5/**
```

每个对象先写 `.pending`，回读并重验完整对象集合后才用原子替换落盘。相同身份和相同 bytes 重放返回同一引用；相同身份但 bytes 不同会失败。事务中断会清掉 pending 文件和本轮新建的空目录。

本目录没有模型、网络、真实小说、Patch、CandidateVersion 或 pointer 写路径，也不调用 B-03 reader。停点仍在 B-02 Draft 施工件，不代表 B-03/B-04 获得施工授权。

## 定向验证

```bash
uv run --locked ruff check work/ccz57_m3_b02_diagnostic_coverage_r03_5
PYTHONDONTWRITEBYTECODE=1 uv run --locked pytest -q -p no:cacheprovider work/ccz57_m3_b02_diagnostic_coverage_r03_5/test_b02_diagnostic_coverage.py
PYTHONDONTWRITEBYTECODE=1 uv run --locked python work/ccz57_m3_b02_diagnostic_coverage_r03_5/self_check.py
```

来源：Codex
