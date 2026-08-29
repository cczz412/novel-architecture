# B-02 r03.5 设计取舍与限制

## 为什么 Diagnostic 要同时带两种定位

LineageLocator 回到候选条目，EvidenceLocator 回到该条目已经绑定的逐字 evidence。只存前者，作者仍不知道问题依据是哪一句；只存后者，又会丢失条目身份。新版把两者当成不可拆的定位对，并核对它们的 lineage、CandidateVersion ref 和合同版本完全相同。

旧版 `origin_attempt_refs` 只能证明某次尝试参与了候选生成，不能证明这条 Diagnostic 对应哪条事实和哪段 evidence，所以新版 Diagnostic 不再接收它作为问题依据。

## Coverage 为什么分来源证据和候选匹配

`source_evidence_binding` 说明“章节里实际观察到了什么”，包括逐字 evidence、bytes 哈希、句数和全部匹配位置。`matched_candidate_bindings` 说明“它和现有哪条候选发生了匹配”。两块分开后，`MISSING` 可以保存可回读的来源证据，同时明确表示没有候选可引用。

`MISSING` 带候选 locator 会让“缺失”与“已经找到候选”互相矛盾，因此合同直接拒绝。`PARTIAL`／`MATCHED` 没有成对 locator 也会拒绝，不能只靠枚举值声称匹配成功。

## 为什么 evidence 不能走全量 NFC

NFC 会把部分分解态字符改成另一个 code point 序列。人眼可能看不出差别，但 UTF-8 bytes、哈希和原文位置都会变化。B-02 的 canonical JSON 只对 `evidence` 与校验它所需的合成 `responsibility_text` 保留原始 code point；普通字段继续 NFC。测试用 `e\u0301` 锁住这条边界。

## 生命周期和开放问题视图

Diagnostic 原件一旦写入不再修改。关闭或被修补审查取代时，只追加生命周期回执。开放问题视图从 Diagnostic 与生命周期回执重算，输出引用、条目位置和 evidence 定位摘要，不复制正文，也不写新文件。

## 当前限制

- Coverage 的 `MATCHED`／`PARTIAL` 是调用方给出的观察分类，本目录只校验引用和证据绑定，不做语义分类模型。
- 本目录只处理合成章节夹具，不证明真实小说的抽取准确率。
- 本目录不生成 Patch 或 CandidateVersion，不确认正式事实，也不做章节五类结果判断。
- 旧 r03.3 对象由旧目录及 B-01 兼容读取保留原 bytes；新版没有迁移 writer。

来源：Codex
