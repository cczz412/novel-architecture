# CCZ-57｜M3 B-04 冲突与限制

## Coverage 只能用于准入，不能从 Patch 原件单独恢复

当前 B-04 读取 B-02 的 Diagnostic 和 Coverage，能够输出 ProtectionSet、PatchProposal、不可提交的 CausalHintProposal，以及临时 PatchPreview。`ADD_CANDIDATE_ITEM` 只有在 Coverage 为 `MISSING` 或 `PARTIAL` 时才允许提出。

R03.4 冻结的 Patch payload 没有 `coverage_refs` 字段，所以小说辅助产品目前还不能把这次实际使用的 Coverage 引用长期保存在 Patch 原件里。后续只拿到 Patch 时，无法单独追溯是哪条 Coverage 放行了新增候选项。B-04 不擅自扩字段；施工回执和离线报告只保存这次验收证据。若产品以后要求从 Patch 原件独立恢复 Coverage 来源，必须先升级蓝图合同。

## SourceSlice 是可选证据，不是硬依赖

当前 B-04 可以读取一条已经通过 B-03 R02 校正的 SourceSlice RecordRef，但只复制引用，不读取正文内容。没有 SourceSlice 时，产品仍能用 Diagnostic 生成合法提案和预览。

小说辅助产品还没有在 B-04 内获得 SourceSlice 正文读取能力，这不会卡住候选 Patch 的生成；它只表示 B-04 不能把引用夸大成已经重新阅读和判断了正文。后续真正需要读取内容时，必须重新经过当时有效的授权判断。

## Preview 不是决定

当前模块读取 CandidateVersion、ProtectionSet、PatchProposal 和 CausalHintProposal，能够输出临时 PatchPreview。小说辅助产品在 B-04 还不能生成并保存 Patch 验证、是否可交作者、作者选择或提交结果；这些能力分别留给 B-05 和 B-06。

如果在这里提前写入 route、eligibility、作者决定或 child CandidateVersion，会让作者把“候选提案”误认成“已经通过并生效的修改”，所以全部失败关闭。

## 原子事务的可见边界

三个 writer 先在 staging 中构造原件，完整校验后通过单次目录 rename 发布。失败时只清理未发布 staging；不会先发布正式文件再靠删除恢复。`PatchPreview` 在原件成功发布并回读后现算，不参加持久事务。

来源：Codex
