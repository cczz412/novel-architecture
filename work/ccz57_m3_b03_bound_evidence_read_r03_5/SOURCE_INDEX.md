# B-03 r03.5 只读接口来源

| 来源 | 这里使用什么 |
| --- | --- |
| CZ 语义版本决定回执（2026-08-29） | 产品入口固定为“事实条目 → 已绑定 evidence”，任意范围输入拒绝。 |
| B-03 r03.5 完整替代施工合同草稿 R01 | CandidateVersion、定位器、B-02 context、正式账本 adapter 缺失时失败关闭，以及 B-04 分界。 |
| B-01 r03.5 | CandidateVersion、LineageLocator、EvidenceLocator、item hash、章节修订和来源代次。 |
| B-02 r03.5 | 上下文准入和 source evidence binding 的 evidence hash、句数、全部匹配位置。 |
| B-03 R02（只继承指定机械规则） | 7 类记录、8 个 writer/projector、lifecycle、可信时间、tombstone 和事务；旧 range/max chars 正例不继承。 |
| 三路 Sol XHigh 独立审查（2026-08-29～30） | 收紧进程中断恢复、唯一 writer、Request／政策／用途绑定、权威时间、撤回／到期即时清除、tombstone 哈希和符号链接逃逸。 |

不读取 `local/`、真实小说正文、网络或模型 API。

来源：Codex
