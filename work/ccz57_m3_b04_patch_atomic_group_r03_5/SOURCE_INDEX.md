# 来源索引

## 工程真值

- GitHub Issue #201：B-04 r03.5 施工票。
- Linear CCZ-147：产品语义兼容修复子票。
- Linear CCZ-142：正文到事实候选父票；2026-08-30 当前票面已明确 B-05 是机器验证与路线判断，不是默认作者接受流程。
- Linear 文档《CZ 原话｜工作卡、承接区、事实句子与账本层级｜2026-08-30》：工作卡、隐藏栏、事实句子和账本层级的当前产品语义入口。
- 开工基线：`main@410596b559ac308f136f82ea2985e34202b2964b`。
- B-01 r03.5 merge：`bab092f4914c41e410599a588f55788ae5ff7b7c`。
- B-02 r03.5 merge：`6c126a85b97444092955e90be88952617805cf17`。

## 合同依据

- B-04 r03.5 施工合同候选 SHA-256：`f6fc914f2047d7ada4570fcfa4896d80706bb07ca2999997cb5a182b76aa27fb`。
- 产品语义窄修原件 SHA-256：`c18d18bd32f848d5835194a4e8b377f703ca7e7ced39fb10832081da65499e22`。
- 语义版本决定 SHA-256：`54dcd1e6bb6ddd7b3d166c568995f6d78bb544f213044e316f6ef1d24c660058`。

上面的固定 SHA 继续证明当时的施工输入。若其中“作者默认接受／二次确认”或“事实候选等同账本条目”的旧表述与 2026-08-30 当前 Linear 裁决冲突，以当前裁决为准；本次只校准说明，不改变 B-04 对象合同。

## 代码依赖

- `work/ccz57_m3_b01_candidate_version_r03_5/**`：完整事实候选 item、LineageLocator、EvidenceLocator。
- `work/ccz57_m3_b02_diagnostic_coverage_r03_5/**`：Diagnostic、Coverage 和 exact source evidence binding。
- `work/ccz57_m3_b04_patch_atomic_group_r03_4/**`：旧版只读回归；本票没有改动。

没有读取小说正文，没有调用真实模型 API，也没有把 TEMP 候选当成工程真值提交。
