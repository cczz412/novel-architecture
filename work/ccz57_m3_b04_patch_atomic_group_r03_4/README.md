# CCZ-57｜M3 B-04 Patch atomic group 候选施工

这个目录只解决一件事：把局部修订整理成可独立检查的候选组，同时保护没有被这次修订选中的原内容。

它会保存三种不可变原件：

- `M3_CANDIDATE_PROTECTION_SET`：列出这次不能碰的现有字段；
- `M3_PATCH_PROPOSAL`：记录准备修改什么，但不真正修改 CandidateVersion；
- `M3_CAUSAL_HINT_PROPOSAL`：保存“可能有关”的不可提交提示。

`PatchPreview` 只在内存里临时重算，方便以后展示。它不是第四种原件，不生成记录编号和记录哈希，也不写文件。

## 当前准入

- current `main`：`2307831d7b62eb57992d3be368a3a635ebb8b7b7`；
- A merge：`019df751641533c7de4d56aa38f50747fb564036`；
- B-01 merge：`905346f56cd51259c15a9517ead1517227c1719a`；
- B-02 reviewed head：`5e43484859aba53c594023e93ee5fa43291b057a`；
- B-02 merge：`2307831d7b62eb57992d3be368a3a635ebb8b7b7`；
- B-02 merge/readback receipt 已固化为本目录 fixture；
- B-04 GitHub 施工票：[#193](https://github.com/cczz412/novel-architecture/issues/193)；
- B-04 Linear 票：`CCZ-136`。

## 两条合法路线

1. 不使用 SourceSlice：`authorized_source_slice_refs=[]`；
2. 使用 B-03 R02 的 exact SourceSlice RecordRef：只复制引用，不读取内容，不调用 B-03 writer。

两条路线分别有固定的 Causal、Patch 和 Preview hash，不能共用 stable ID。

## 离线验收

```bash
uv run --offline --locked python work/ccz57_m3_b04_patch_atomic_group_r03_4/self_check.py
uv run --offline --locked pytest -q work/ccz57_m3_b04_patch_atomic_group_r03_4/test_b04_patch_atomic_group.py
cd work/ccz57_m3_b04_patch_atomic_group_r03_4 && sha256sum -c MANIFEST.sha256
```

## 明确不做

- 不调用模型 API、网络、socket、DNS 或子进程；
- 不读取真实小说正文或 `local/`；
- 不生成 Patch 验证、准入、作者决定或生命周期回执；
- 不提交 child CandidateVersion；
- 不调用 B-03、B-05、B-06、B-09 writer；
- 不持久化 `PatchPreview`；
- 不证明提案语义正确，也不代表作者已经接受。

来源：Codex
