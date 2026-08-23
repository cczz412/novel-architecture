# 情景问答｜目录

入口说明：[README.md](README.md)

## 工作台／账本／权限（第一批）

| 遇到什么 | 身份 | 卡片 |
|---|---|---|
| 生成前要不要把所有篮子塞进模型 | 已拍 | [账本可以细，执行包必须瘦](cards/store-fine-feed-thin.md) |
| AI 该看见哪些工具、会不会乱翻后台站 | 已拍＋加固 | [按意图分探讨／查询／真改](cards/intent-gates-tools.md) |
| 生成结果是一墙字还是可点对象；草稿放哪 | 已拍 | [草稿是提案，产出落画布](cards/draft-is-proposal.md) |
| 提示词写了「别乱改」够不够 | 外部先验 | [提示词不是权限](cards/prompt-is-not-permission.md) |
| 作者选了一个计划，算不算已经发生 | 已拍＋设计审查 | [选中不是已发生](cards/selected-is-not-happened.md) |
| 读到 P02 写 No-Go，是不是产品已经否了 | 设计审查风险 | [P02 的 No-Go 不是现行产品否决](cards/p02-nogo-is-candidate.md) |
| 检查器回一个 OK 能不能过 | 已拍＋验收目标 | [检查器要覆盖回执](cards/checker-needs-coverage.md) |
| 篮子协作难，要不要再开一本账 | 已拍＋加固 | [先补户口和指针，不砍树也不加层](cards/no-extra-baskets.md) |
| 拿不准要不要重查／通读报告 | 本票纪律 | [先对卡片和 INDEX，不要重查](cards/look-up-dont-rescan.md) |

## 抽取／评测／记忆（批次 A）

CZ 2026-08-24 同意收进。P4 预检没有写成已拍。「六层」是当前拆法，不是新评测合同。格式 V1.1 未迁。

| 遇到什么 | 身份 | 卡片 |
|---|---|---|
| 引文、位置和 SHA 都合法，能否直接判事实成立 | 已拍加固 | [引文能对上，不等于事实被证明](cards/evidence-is-not-support.md) |
| “打算／可能／除非／某人说”能否只抽事件核心 | 已拍加固 | [别把“想做”抽成“已经做了”](cards/preserve-modal-qualifiers.md) |
| 输出很准，能否认为没有漏抽 | 已拍加固 | [输出很干净，不等于没有漏抽](cards/clean-output-can-still-miss.md) |
| 评测能否只留一个准确率或 F1 | 已拍加固 | [评测不能压成一个总分](cards/evaluation-needs-layers.md) |
| 反复使用的 DEV 高分，能否叫 blind 或生产胜出 | 已拍加固 | [开发集高分，不是生产证明](cards/dev-score-is-not-production.md) |
| 同章几百条事实能否当几百个独立样本 | 外部先验 | [一章里的很多事实，不等于很多独立样本](cards/chapter-is-statistical-unit.md) |
| API 重试成功后，失败记录能否覆盖掉 | 外部先验 | [重试失败也算一次真实尝试](cards/retries-are-real-attempts.md) |
| 一轮同时改模型、Prompt、上下文和评分器，能否归因 | 外部先验 | [一次实验别同时改五件事](cards/change-one-variable.md) |
| 验真器给了修正版，能否自动覆盖候选或真值 | 已拍 | [验真先判，修复不能顺手改账](cards/verifier-diagnoses-not-writes.md) |
| 背景卡、旧状态或检索段能否替目标段作证 | 已拍加固 | [背景能帮理解，不能替目标段作证](cards/background-is-not-evidence.md) |
| 章节顺序或最后修改时间能否代表故事当时状态 | 已拍加固 | [故事时间、叙述位置、系统时间别混成一个字段](cards/separate-three-times.md) |
| 没值或没查到，能否统一写成 false／未发生 | 已拍加固 | [不知道，不等于没有发生](cards/unknown-is-not-false.md) |

## 需求／产品形态（批次 B）

CZ 2026-08-24 同意收进。P4 双入口、10 分钟、动画指标、价格数字没有写成已拍。格式 V1.1 未迁。

| 遇到什么 | 身份 | 卡片 |
|---|---|---|
| 看到“续写、生成、提高产量”，准备加一键正文 | 已拍加固 | [别把编辑助手做成 AI 写手](cards/guide-dont-ghostwrite.md) |
| 报告里人群很多，准备同时服务作者、读者和工作室 | 已拍加固 | [首发主线不是所有故事用户](cards/serve-current-author-first.md) |
| 每个垂直场景都要字段，准备各建一套真源 | 已拍加固 | [垂直场景共用真源，不复制七套产品](cards/one-core-many-projections.md) |
| 导入旧稿前，准备先深抽全书并补齐 Wiki | 已拍加固 | [先回答一个真问题，不先造整本百科](cards/answer-one-question-first.md) |
| 输入已经分类，准备按桶直接入账或丢弃未知内容 | 已拍加固 | [分到哪个桶，不会自动变成真相](cards/classification-is-not-authority.md) |
| 简单／专业模式准备各用一套项目格式 | 已拍加固 | [简装精装换视图，不换故事底座](cards/same-truth-different-views.md) |
| 动画播放成功，准备直接记为激活 | 已拍加固 | [激活不是播完一段动画](cards/activation-is-work-not-animation.md) |
| 手机端准备照搬桌面全部能力 | 已拍加固 | [手机不是缩小版写作台](cards/mobile-is-companion.md) |
| 分镜或视频生成了新细节，准备回写真源 | 已拍加固 | [分镜和视频是投影，不是故事真源](cards/visuals-are-projections.md) |
| 拆书标签准备写进事实账或当硬约束 | 已拍加固 | [拆书配方是参考，不是真值标签](cards/craft-recipe-is-not-truth.md) |
| 钩子、情绪或期待感分数准备当章节硬门 | 已拍加固 | [钩子和情绪只能亮黄灯，不能给作者判分](cards/reader-signals-are-yellow.md) |
| 调查报告给了价格和积分建议，准备直接做计费 | 已拍 | [调查里的价格表不是施工合同](cards/prices-are-not-contract.md) |

## SI-007 其余审查（批次 C）

CZ 2026-08-24 同意收进。字段名、组件数、市场数字、晋江阉割档、心理量表细节没有写成已拍。格式 V1.1 未迁。

| 遇到什么 | 身份 | 卡片 |
|---|---|---|
| 五份日常循环稿状态互相打架，准备各自施工 | 已拍加固 | [先统一一条日常状态流，再把稿发给开发](cards/one-daily-flow-before-build.md) |
| P01 建议全部未决，或高影响暗稿准备批量放行 | 已拍加固 | [暗稿能默认，小事和大事不能一锅勾](cards/dark-draft-high-impact-needs-single-sign.md) |
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

## 规划账合同（批次 D）

CZ 2026-08-24 同意收进。SI-016 是当时候选合同审查，不是现行代码故障。`plan-v2-candidate` 字段表、空数组收窄、C5 候选、具体 ID 格式没有写成已拍。格式 V1.1 未迁。

| 遇到什么 | 身份 | 卡片 |
|---|---|---|
| 目录写着“已对齐”，准备跳过现行合同直接施工 | 设计审查风险 | [“已对齐”只是状态说明，不是施工放行票](cards/aligned-label-is-not-release.md) |
| 下游要读完整规划，准备把一次 C7 出题快照当整本规划账 | 设计审查风险 | [一次出题快照不能冒充完整规划账](cards/snapshot-is-not-ledger.md) |
| 导入时准备把大纲条目和章节书稿排进同一个章节数组 | 已拍加固 | [大纲原稿不能占章节序号](cards/outline-is-not-chapter.md) |
| 准备把黄金三章做成三章上限、付费额度或 C1 类型 | 已拍加固 | [黄金三章是独立工作台，不是三章上限](cards/golden-three-is-workspace.md) |
| 准备把 `truth_bearing`、P 号和内部模块名直接放到作者界面 | 已拍加固 | [作者看人话，合同字段留在内部](cards/schema-names-stay-internal.md) |
| 概览、体检或快照只有生成时间，准备据此判断仍然有效 | 已拍加固 | [投影必须知道自己基于哪一版](cards/projection-needs-source-version.md) |
| 跨账引用遇到 `f001`／`F-0001` 两种写法，准备随便选一种落库 | 已拍加固 | [跨账引用认稳定 ID，不认界面编号](cards/store-internal-id-render-display-id.md) |
| 书稿一保存就准备自动改规划；或没交棒就不允许对账 | 已拍加固 | [保存、对照、交棒是三件事](cards/save-compare-handover-are-separate.md) |
| 想用一个 `status`／`closed`／`completed` 包办审核、交棒、收工和关章 | 已拍加固 | [一个状态字段只能管一条轴](cards/status-belongs-to-one-axis.md) |

来源：#115
