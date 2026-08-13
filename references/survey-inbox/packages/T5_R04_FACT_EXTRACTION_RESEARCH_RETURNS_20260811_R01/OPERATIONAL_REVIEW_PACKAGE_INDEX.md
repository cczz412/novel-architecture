# T5 R04 外部研究与操作评审 ZIP 追源索引

## 这张表管什么

这是一张本机追源索引，用来区分“外部研究原件”“操作评审回包”和“外发证据包”。扫描范围是 `/Users/a1234/Downloads` 中修改时间不早于 `2026-07-27 00:00:00 +0800` 的 ZIP，共 133 个。

检查只做了这些事：

- 用 `zipinfo`／`unzip -l` 查看 ZIP 成员名、成员大小和 CRC32；
- 对 ZIP 文件本身计算 SHA-256；
- 对已经存在于 Downloads 的同名单文件或同名目录做只读大小、CRC32 和 SHA-256 核对；
- 没有解压、复制、移动或改写任何 ZIP，也没有读取小说正文成员。

当前知识包的 `REPORT_MANIFEST.json` 已收录 58 份外部调查报告。本索引只负责 ZIP 追源，不修改这 58 份报告的数量、身份或摘要。

## A 类：研究回包原件或研究成果整包

| ZIP 绝对路径 | 修改时间 | 字节数 | ZIP SHA-256 | 关键成员摘要 | 原件与现有归档判断 |
|---|---:|---:|---|---|---|
| `/Users/a1234/Downloads/T5_R04_CONTEXT_STRATEGY_DEEP_RESEARCH_RETURN.zip` | 2026-08-02 14:00:46 +0800 | 40412 | `d276c4ee2482e88f168da6058c037718a1fb6f76da9be248d2b48f93a0686402` | `REPORT.md`、`DECISION_TABLE.md`、`EVIDENCE_MATRIX.csv`、`EXPERIMENT_PLAN.md`、`FAILURE_CASES.md`、`MANIFEST_SHA256.txt` | **独立研究回包原件 ZIP。** Downloads 同名目录的 6 件内容现已逐字节归档；主报告计入当前报告总数，五件附件另计，ZIP 本体不重复复制。 |
| `/Users/a1234/Downloads/归档 21.zip` | 2026-07-31 12:11:21 +0800 | 99056 | `c76daee1b91fab7ea5507d7f59c019337d5e77f2e872a772de2425ad23a67191` | 5 份 `deep-research-report - 2026-07-31T*.md`，另有 5 个 `__MACOSX` 元数据成员 | **五份原始研究附件整包。** Downloads 的 5 份同名单文件现已逐字节归档并计入当前报告总数；ZIP 本体不重复复制。 |
| `/Users/a1234/Downloads/generation_consumer_five_deep_research_20260801.zip` | 2026-08-02 01:34:05 +0800 | 59532 | `de11710290cf7ab5d379caf47e159e2c272102cc1591bf0af4f888f64a5af8e7` | 总结、长篇一致性、事实到生成接口、冲突检测、情节控制、大纲规模、证据矩阵 | **研究成果整理包，不当作五份原始附件本身。** 它晚于 `归档 21.zip`，且同样围绕五个研究主题，可能是后续整理件；只看成员表不能证明派生关系。未发现同名目录，当前 58 份 manifest 也未把这个整理 ZIP 当独立报告。 |
| `/Users/a1234/Downloads/T5_R04_CONTEXT_CONTRACT_RESEARCH_AND_P3_20260808_R01.zip` | 2026-08-08 15:30:53 +0800 | 47137 | `2eeb6d1f8fce3509cb665be802c9912adfe1db0bf0ec3605a1ab575b5ab85b87` | 6 个 `DR_*` 问题源稿、P3 下一指令、未来路线骨架、`09_ALL_IN_ONE.md`、manifest | **研究派生汇编，不是原始报告原件。** 六份问题源稿现已单独归档为“候选原 Prompt 源稿，发送逐字身份待确认”；P3 指令和合并稿不计研究报告，ZIP 本体不复制。 |

### A 类同件证据

`T5_R04_CONTEXT_STRATEGY_DEEP_RESEARCH_RETURN.zip` 与同名目录的 6 个成员全部通过“文件名＋未压缩字节数＋CRC32”核对。目录里的 `MANIFEST_SHA256.txt` 记录了 5 个正文文件的 SHA-256，目录文件复算一致：

| 文件 | SHA-256 |
|---|---|
| `DECISION_TABLE.md` | `7187139641208eaa7645996c463a4e649f3d966af0ff35893af51678fce14506` |
| `EVIDENCE_MATRIX.csv` | `a5a17f5dec72effb3feb98bde025e9917b7637cc2301a599bf91988e3e1adbe2` |
| `EXPERIMENT_PLAN.md` | `3c3ae8170dd8b8674e8cd344347cc5d7bd756234ec2ea4de51a5b71e000d11ff` |
| `FAILURE_CASES.md` | `cfe9375f38066033e158833afbe8d120cd71beb2ae088b7160ab68b1ef394d71` |
| `REPORT.md` | `94e25d3c1bc1744c38214687203d982d1124be1fdbc88d6168b5dcd15d04010a` |

`归档 21.zip` 与 Downloads 中五份同名单文件的核对结果如下。这里的 SHA-256 是对单文件复算，不是把 ZIP 成员解压后再算；在“不解压”边界下，只能严谨地写成 5/5 文件名、字节数和 CRC32 相同。

| 单文件 | 字节数 | ZIP 成员 CRC32 | 单文件 SHA-256 |
|---|---:|---|---|
| `deep-research-report - 2026-07-31T120119.068.md` | 46409 | `72a21a12` | `044304dca4d316aea4f05fe5fb57b3d7bc25ea6bf28e02144a8ca217ca464d3e` |
| `deep-research-report - 2026-07-31T120121.684.md` | 39107 | `63718931` | `e8314bdeabd2ddfd53454673d86366a2f495f6a5b2d1d48bf216c355a0d19533` |
| `deep-research-report - 2026-07-31T120123.907.md` | 47391 | `9cf17255` | `bbe90a927a00fb8fd6ef76c40d0c756e4b02c1dce872d1a98e85b995c930695e` |
| `deep-research-report - 2026-07-31T120125.952.md` | 53930 | `321dc4e7` | `769e82289b2e811aed2fbc3072eb60905ec898f95f03f9513b51cbd69e8993d5` |
| `deep-research-report - 2026-07-31T120128.040.md` | 56836 | `dc1cac6f` | `bcc11d610e14c94aaf58ed19ba106e356db81cd5d0b7063b16fdac48d4d0f7f5` |

## B 类：直接服务 T5 R04 的操作评审回包

这些 ZIP 里有报告，但主要产物是裁决、审计、重平衡、根因诊断或执行设计。它们只建索引，不计入当前 58 份独立研究报告。

| ZIP 绝对路径 | 修改时间 | 字节数 | ZIP SHA-256 | 关键成员摘要 | 是否报告原件 |
|---|---:|---:|---|---|---|
| `/Users/a1234/Downloads/Z00_Z01_MARKER_BURDEN_EXTERNAL_REVIEW_20260808_R01.zip` | 2026-08-08 00:58:50 +0800 | 55975 | `a74c4ed3dbbdc3acda2f0e6cc669f7b480be79b4be9ad72c8f072635c7af7464` | marker burden 外审、48 个配对 case、因果解释、最小零训练实验 | 否；操作评审回包。 |
| `/Users/a1234/Downloads/T5_R04_AC_ROOT_CAUSE_CANDIDATE_20260807.zip` | 2026-08-07 14:16:40 +0800 | 39497 | `e303db4a2bbe671cb92935cfcecbe066adfa4746ac4a9e037ddb975be694cf90` | `AC_ROOT_CAUSE_REPORT.md`、82 case 诊断、假设排序、评估器审计、最小证伪计划 | 否；根因候选与评审材料。 |
| `/Users/a1234/Downloads/T5_R04_AC_EXAM_REBALANCE_CHATGPT_PRO_RETURN_20260807.zip` | 2026-08-07 04:10:47 +0800 | 134269 | `4df8d51ebc2e99fa26c149f1a5dd6e7c143fcbc47965c8fdd25233205db8cb38` | 考题重平衡报告、旧 48 条裁决、新 15 条题目与 Gold、合并候选 | 否；数据与考试设计回包。 |
| `/Users/a1234/Downloads/T5_R04_A_V25_ONE_WINDOW_FINAL_REVIEW_CHATGPT_PRO_RETURN_20260806.zip` | 2026-08-06 23:24:33 +0800 | 73313 | `be688d676585770e4d35c2e6505b980a57c5c345922837f95b78ef7a91e446c7` | final review、101 条语义复核、53 本裁剪计划、影响分析 | 否；终审与裁剪决策回包。 |
| `/Users/a1234/Downloads/T5_R04_P3_CONTEXT_VERIFICATION_ChatGPT_Pro_review_20260806.zip` | 2026-08-06 22:41:11 +0800 | 19504 | `0ec41705cdcb4c16181282a8a81e6c17460c4663a7364fb962437f9c626a2865` | P3 context verification 的 Markdown、JSON、manifest、自检 | 否；上下文合同验证回包。 |
| `/Users/a1234/Downloads/T5_R04_A_103_TARGETED_REREVIEW_CHATGPT_PRO_RETURN_20260806_R02.zip` | 2026-08-06 20:35:24 +0800 | 130152 | `b30327987ec302895bf8fb28bcd7216daf6114577e7a494fc7824cc16f124995` | 103 条定向复核、修订行、删项候选、变更日志、未决项 | 否；定向复核与数据修订回包。 |
| `/Users/a1234/Downloads/T5_R04_MISSING_TYPES_MUTUAL_CALIBRATION_ChatGPT_Pro_review_20260806.zip` | 2026-08-06 16:37:02 +0800 | 22314 | `171e0d903a55df72b8df1b3f1b15af569999aa9b0b3cc0fac16a2774bda2f3bb` | missing-types 报告、segment calibration、建议裁决、未决项 | 否；互校操作评审。 |
| `/Users/a1234/Downloads/T5_R04_MISSING_TYPES_DEEP_REVIEW_ChatGPT_Pro_review_20260806.zip` | 2026-08-06 13:19:58 +0800 | 21414 | `7e3686f0c950b34bdc782c5a687c4ef3546e7490f12729182f6ed3dc625cd743` | missing-types 深审报告、segment verdicts、事实变更建议 | 否；语义深审回包。 |
| `/Users/a1234/Downloads/T5_R04_A_CURRICULUM_PRUNING_CHATGPT_PRO_RETURN_20260806.zip` | 2026-08-06 08:17:21 +0800 | 58724 | `f10fe1f09a4e96acda62fa5f965e4f265ba47ed7b8c6cd4af371f61cf8a7c6b9` | 书目分类研究、书与行裁决、裁剪政策、目标分布、失败因果假设 | 否；课程裁剪操作回包。 |
| `/Users/a1234/Downloads/T5_R04_SINGLE_A_SOURCE_DERIVATION_DESIGN_CHATGPT_PRO_RETURN_20260806.zip` | 2026-08-06 06:41:07 +0800 | 33607 | `0d2678955806b70a4d1e3a95cf1b28b127b2f80be51974bd6f34112ed4727710` | 架构决定、规范数据模型、派生 DAG、转换合同、迁移计划 | 否；数据架构设计回包。 |
| `/Users/a1234/Downloads/T5_R04_B_V21_REGRESSION_ROOT_CAUSE_CHATGPT_PRO_RETURN_20260806.zip` | 2026-08-06 03:33:06 +0800 | 28008 | `03dc99f6fd2cdb5cf1c082e5e1cb04fb119a37b1b3ad961a0a483f658b05870f` | B V21 回归根因报告、43 case 诊断、假设排序、最小证伪计划 | 否；训练回归诊断回包。 |
| `/Users/a1234/Downloads/T5_R04_A_CURRICULUM_EXHAUSTIVE_AUDIT_CHATGPT_PRO_RETURN_20260806.zip` | 2026-08-06 02:03:55 +0800 | 401089 | `0604a8a8436b1e5a9dce6577c338e38010608d1904ee37e27925fb9ffcea67a0` | exhaustive audit 报告、5264 facts 审计、585 rows 漏事实审计 | 否；大规模数据审计回包。 |

## C 类：历史或邻接的操作评审

这些包与事实抽取架构、评分、消费端或产品管线有关，但离当前 T5 R04 的训练研究更远。它们同样只建索引，不计入 58 份研究报告。

| ZIP 绝对路径 | 修改时间 | 字节数 | ZIP SHA-256 | 关键成员摘要 | 是否报告原件 |
|---|---:|---:|---|---|---|
| `/Users/a1234/Downloads/B_C_T6_contract_review_v0.2_return.zip` | 2026-08-01 18:25:16 +0800 | 29194 | `4e092a3146d7044c0494c8756ec69e8ca529fc21b56e0bb6b1850120800abc59` | 场景情绪合同、T6 结构合同、T02→T6 映射、机械门、三章试点模板 | 否；下游结构合同评审。 |
| `/Users/a1234/Downloads/CMIN_B_ChatGPT_Pro_review_20260730.zip` | 2026-07-30 22:44:54 +0800 | 33888 | `c6c75683f0ff5dd6582b752cca65fd96973619d87c861ebee52c9f954b809b12` | 主报告、预注册、冻结合同、调用账、评分归因、执行器交接 | 否；历史实验评审。 |
| `/Users/a1234/Downloads/小说事实抽取_组件标准化与Agent循环编排_外部架构审查回包_r01_20260730.zip` | 2026-07-30 20:22:16 +0800 | 53740 | `48f5da8766d5beb5eb5b0a618df88f94e60613034254f546166e6d95e7cd1767` | 主决定、组件清单、失败码、Agent 状态机、三种编排、下一冻结实验 | 否；架构操作评审。 |
| `/Users/a1234/Downloads/MiniMaxV23_hidden_error_external_review_20260730.zip` | 2026-07-30 14:55:17 +0800 | 20236 | `8f9f9ac48ef420a99d6b411b7c13dc51027d34891c2623a2548792862c6d10fc` | 主报告、下一实验、Prompt/合同补丁、评分停止规则、两档产品路线 | 否；历史模型评审。 |
| `/Users/a1234/Downloads/小说事实抽取_隐蔽漏错_低成本语义复核外审_ChatGPT_20260730.zip` | 2026-07-30 10:17:57 +0800 | 31084 | `6bcd892e5716cdc3b53d56221cb2cd834b676ea4d7458f78f6ff445aad77df16` | 主报告、冻结实验、产品路线、可复制 Prompt、程序硬检和多模型裁决合同 | 否；历史语义复核方案。 |
| `/Users/a1234/Downloads/小说事实抽取_隐蔽漏错_两档产品路线_外审回包_20260729.zip` | 2026-07-30 00:26:22 +0800 | 40225 | `c9f88745921520a0693c6e9b598df5e860fc846acf90d6184cb5046c5920a476` | 结论、核对、两档产品路线、下一轮表、模型 Prompt、继续/停止路线 | 否；历史产品路线评审。 |
| `/Users/a1234/Downloads/小说事实抽取_下一轮实验与两档方案_ChatGPT_Pro_review_20260729.zip` | 2026-07-29 21:42:42 +0800 | 40924 | `f579c99eb37f028641f86f927e635deca1ee43e1aad353d79259a1ef35c82845` | 主报告、失败归因、下一轮实验表、两档方案、模型分工、Prompt 建议 | 否；历史实验路线评审。 |
| `/Users/a1234/Downloads/小说事实抽取_隐蔽漏错与低调用修补_ChatGPT_Pro_review_20260729.zip` | 2026-07-29 19:39:36 +0800 | 34563 | `7e85ca46231a8b2e0231bccd7b88f25ced6c4fdc9cadbd0f47b4d9764df817db` | 复核表、错误归因、BERT 抽样、Prompt、事件/风险/修补 schema | 否；历史低调用修补评审。 |
| `/Users/a1234/Downloads/小说事实抽取_元数据与多模型更优方案_ChatGPT_Pro_review_20260729.zip` | 2026-07-29 18:25:47 +0800 | 35027 | `ad846a23b92e869de4d70bac51dd6a5b91bdc63a25abc5673caee048b3cdd2f4` | 主报告、下一实验、模型提示补丁、对照核验 | 否；历史元数据与模型路线评审。 |
| `/Users/a1234/Downloads/小说事实抽取_实时可视化管线_两阶段合并评审_20260729.zip` | 2026-07-29 13:36:00 +0800 | 78734 | `fad1605b8686fde22264a06c6468e44dbd638d7a3ac649c2f56ef6834898f991` | 合并评审、完成合同、受控实验、最小原型、SSE/API 合同、前后端样例 | 否；产品管线评审。 |
| `/Users/a1234/Downloads/小说事实抽取_实时可视化管线_ChatGPT_Pro_review_20260729(1).zip` | 2026-07-29 11:45:25 +0800 | 45148 | `b976d1bfebb599221fe8cb89528638c9b7b6fa4ffd963cc69e1f0bfee3e372ca` | 可视化管线评审、OpenAPI、事件 schema、前后端参考实现 | 否；产品管线初审。 |

## D 类：外发或证据附件包，不是回包原件

这类 ZIP 的成员结构是 reviewer 说明、Prompt、运行证据、当前状态快照或嵌套旧评审。它们可以帮助复现上下文，但不能当成外部调查结论。

| ZIP 绝对路径 | 修改时间 | 字节数 | ZIP SHA-256 | 关键成员摘要 | 身份判断 |
|---|---:|---:|---|---|---|
| `/Users/a1234/Downloads/小说事实抽取_隐蔽漏错与两档路线_完整实验包_20260729.zip` | 2026-07-29 23:43:58 +0800 | 1822486 | `eab1857be157fa27fc16c1e20861f6ca0d211a402e15ce261089aabea46b1ed6` | 654 个成员；`current_truth`、`current_route`、`upstream_evidence`、模型调用证据、嵌套 prior review | 外发/复现实验证据整包，不是新回包。 |
| `/Users/a1234/Downloads/小说事实抽取_MiniMaxV2.3三书诊断_下一修订外审_v2_20260730.zip` | 2026-07-30 14:38:24 +0800 | 49758 | `06568278b9d120889302ede9f0086e674bb27ed7312366ae74678e9960a81f92` | `00_READ_ME_FOR_REVIEWER.md`、truth snapshot、prior review、R09/R10/R11 证据、三个 case 的 payload/output | 给 reviewer 的证据包，不是回包。 |
| `/Users/a1234/Downloads/小说事实抽取_隐蔽漏错_BERT_思考预算_分波修补_ChatGPT_Pro_review_20260729.zip` | 2026-07-29 18:47:07 +0800 | 657715 | `382cf1703546b1fc1f4eafb1c29d79f1883a1f7377f31362649a63224fa6b061` | `01_CHATGPT_PRO_REVIEW_PROMPT.md`、本地实验事实、候选计划、调用/修补证据、旧评审背景 | 外发评审附件包，不是本轮回包。 |
| `/Users/a1234/Downloads/T5_R04_CPLUS_CODEX_BRIEF_20260807.zip` | 2026-08-07 14:47:38 +0800 | 22369 | `6534b2733633870d1769a6f64a41257a25e0b5cf6b60805409decb3acddd9db2` | C+ 路线批准与阶段门、新数据集长线工作合同 | 内部指令/brief，不是外部回包。 |

## 重复 ZIP

最近 15 天的 133 个 ZIP 中，只发现两组整包 SHA 完全重复：

- `/Users/a1234/Downloads/T5_R04_A_CURRICULUM_PRUNING_CHATGPT_PRO_RETURN_20260806 (1).zip` 与 B 类同名无 `(1)` 文件同 SHA：`f10fe1f09a4e96acda62fa5f965e4f265ba47ed7b8c6cd4af371f61cf8a7c6b9`；不重复计数。
- `/Users/a1234/Downloads/小说事实抽取_隐蔽漏错_两档产品路线_外审回包_20260729 (1).zip` 与 C 类同名无 `(1)` 文件同 SHA：`c9f88745921520a0693c6e9b598df5e860fc846acf90d6184cb5046c5920a476`；不重复计数。

## 不纳入本索引的包

明显是小说正文分包、inventory、整语料语义修复、五窗重抽、训练就绪数据、合成教材或正文证据库的 ZIP，没有展开正文成员，也没有混入这张研究/评审索引。UUID 命名的 `ExportBlock` 外层 ZIP 只显示一个内嵌 ZIP；在“不解压”边界下无法继续判断，因此不冒充研究回包。

## 权限边界

这张表只解决“东西在哪里、ZIP 是什么身份、是否已有同名单文件或目录”三个追源问题。它不产生训练、模型调用、API、Notion、Git、上传或生产晋升权限；B/C 类不增加研究报告计数，D 类不当成调查结论。大包仍留在 Downloads，本知识包没有复制它们。

来源：Codex
