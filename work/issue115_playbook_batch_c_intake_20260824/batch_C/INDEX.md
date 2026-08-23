# 情景问答｜批次 C：SI-007 其余审查

本批只收 SI-007 P01、P03～P15 中尚未被样张、批次 A 和批次 B 覆盖的施工防歪点。没有重写 `gold_examples/` 的 9 张样张，也没有重写 `batch_A/`、`batch_B/`。P02 只保留既有 No-Go 卡的指针，不把候选设计审查写成现行产品否决。

目录应与 `sources/`、`gold_examples/`、`batch_A/`、`batch_B/` 同级放置，相对链接按此结构编写。

| 遇到什么 | 身份 | 卡片 |
|---|---|---|
| 五份日常循环稿状态互相打架，准备各自施工 | 已拍加固 | [先统一一条日常状态流，再把稿发给开发](cards/one-daily-flow-before-build.md) |
| P01 建议全部未决，或高影响暗稿准备批量放行 | 设计审查风险 | [暗稿能默认，小事和大事不能一锅勾](cards/dark-draft-high-impact-needs-single-sign.md) |
| 无书稿点了收工，准备记成写完并关章 | 已拍加固 | [收工不是关章，无书稿不算写完一章](cards/finish-is-not-close.md) |
| 收工检查散成弹窗，容量和欠账准备自动改剧情 | 已拍加固 | [收口只合并异常，不替作者改剧情](cards/close-with-anomalies-not-autopilot.md) |
| 插件更新后准备让旧项目静默读取最新版 | 已拍加固 | [插件升级不能改写旧结果](cards/pin-plugin-version.md) |
| 模型自报用了插件，准备据此认定作者和版权 | 已拍加固 | [运行回执不是作者署名](cards/runtime-receipt-is-not-authorship.md) |
| 路由器无论如何都要选中至少一个插件 | 已拍加固 | [没有合适插件时，可以一个也不用](cards/router-may-choose-none.md) |
| 私人 Skill 上传后准备直接公开或授予系统权力 | 已拍加固 | [私人 Skill 先过治理门，再谈公开](cards/private-skill-needs-governance.md) |
| 一个许可证标签准备包办整库素材，画不出时让 AI 猜 | 已拍加固 | [素材要逐项核权，画不出来就降级](cards/license-assets-or-degrade.md) |
| 画布节点和浏览器缓存准备成为第二套真源 | 已拍加固 | [画布是交互投影，缓存只是加速层](cards/canvas-is-projection-cache-is-accelerator.md) |
| 产品不代写正文，准备显示平台“安全发布” | 已拍加固 | [不代写，不等于平台一定合规](cards/no-prose-is-not-compliance.md) |
| 人格标签准备直接驱动行为或触发硬冲突 | 已拍加固 | [人格标签只能提醒，不能替角色做决定](cards/psych-labels-are-soft.md) |

## 另见已有卡片（本批不重写）

| SI-007 重叠情景 | 已有卡片 |
|---|---|
| P01 把“选进计划”写成“已经发生” | [选中不是已发生](../gold_examples/cards/selected-is-not-happened.md) |
| P01 检测器没有 unknown，或把未查到写成未发生 | [不知道，不等于没有发生](../batch_A/cards/unknown-is-not-false.md)；[检查器要覆盖回执](../gold_examples/cards/checker-needs-coverage.md) |
| P01 沙箱、草稿或方案准备直接回写真源 | [草稿是提案，产出落画布](../gold_examples/cards/draft-is-proposal.md)；[提示词不是权限](../gold_examples/cards/prompt-is-not-permission.md) |
| **P02 的 No-Go** | [P02 的 No-Go 不是现行产品否决](../gold_examples/cards/p02-nogo-is-candidate.md)；本批不制卡、不改写 |
| P04 方法论目录、节奏口诀、拆书配方准备变硬规则 | [拆书配方是参考，不是真值标签](../batch_B/cards/craft-recipe-is-not-truth.md)；[钩子和情绪只能亮黄灯，不能给作者判分](../batch_B/cards/reader-signals-are-yellow.md) |
| P05／P06 先搭完整结构、完整 Wiki 或一次服务全部人群 | [先回答一个真问题，不先造整本百科](../batch_B/cards/answer-one-question-first.md)；[首发主线不是所有故事用户](../batch_B/cards/serve-current-author-first.md) |
| P06／P15 报告给出价格、套餐或市场数字，准备直接计费 | [调查里的价格表不是施工合同](../batch_B/cards/prices-are-not-contract.md)；其余数字保鲜边界见 [BATCH_NOTE.md](BATCH_NOTE.md) |
| P07／P12 视觉、互动或角色视角生成了新细节，准备回写真源 | [分镜和视频是投影，不是故事真源](../batch_B/cards/visuals-are-projections.md)；[简装精装换视图，不换故事底座](../batch_B/cards/same-truth-different-views.md) |
| P09 结构化记忆与长上下文准备二选一，或把宽读写成当前能力 | [账本可以细，执行包必须瘦](../gold_examples/cards/store-fine-feed-thin.md)；[背景能帮理解，不能替目标段作证](../batch_A/cards/background-is-not-evidence.md) |
| P10 抽取评测只看干净输出或一个总分 | [输出很干净，不等于没有漏抽](../batch_A/cards/clean-output-can-still-miss.md)；[评测不能压成一个总分](../batch_A/cards/evaluation-needs-layers.md)；[引文能对上，不等于事实被证明](../batch_A/cards/evidence-is-not-support.md) |
| P14 审计器发现问题后准备自动改账 | [验真先判，修复不能顺手改账](../batch_A/cards/verifier-diagnoses-not-writes.md)；[开发集高分，不是生产证明](../batch_A/cards/dev-score-is-not-production.md) |

P04、P05、P06、P09、P10、P12、P14、P15 并非“没有读到”，而是新增风险已被旧卡覆盖，或报告里的形状仍未拍。具体取舍和故意没升格的字段、数字、工具名见 [BATCH_NOTE.md](BATCH_NOTE.md)。

本批回包不是 CURRENT，不产生字段冻结、技术选型完成、插件市场上线、平台法律结论、计费、Git 或生产晋级权限。

来源：#115；CZ 2026-08-24
