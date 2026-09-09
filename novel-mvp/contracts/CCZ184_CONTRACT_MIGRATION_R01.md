# 八份工程合同迁入索引 R01

本批把八份 Linear 合同原文带入 GitHub 独立分支供审阅。只新增文档和入口，不修改产品语义、代码或 Schema；不删除旧文，也不提前切换主存。批准范围见 [工程工单 #351](https://github.com/cczz412/novel-architecture/issues/351)，准备依据见 [CCZ-184 R01](https://linear.app/ccz/issue/CCZ-184)。

内容分工沿用 [协作.三方主存分工@v2](https://app.notion.com/p/3d45cadc4d0f8115b10cc1fb4ba7786f)。GitHub 对照基线为 `8ddd4a333874363c898a122c7be3a28b809d54de`。分支文档不是当前主存切换回执，合同冻结也不代表运行能力开放。

## 从这里读

| 合同 | 本批文件 | 原主存 | 原版本／批准依据 |
|---|---|---|---|
| 正式事实晋级 | [合同原文](FACT_PROMOTION_CONTRACT.md) | [Linear 原文](https://linear.app/ccz/document/0f53514ba07d) | FACT_PROMOTION_CONTRACT v1；请求 FACT_PROMOTION_REQUEST v1；回执 FACT_PROMOTION_DECISION_RECEIPT v1；[CCZ-86](https://linear.app/ccz/issue/CCZ-86) 的合同冻结／完成记录 |
| 统一调用 | [合同原文](UNIFIED_ACTION_CALL_CONTRACT.md) | [Linear 原文](https://linear.app/ccz/document/de71f0c079d8) | UNIFIED_ACTION_CALL_CONTRACT v1；UNIFIED_ACTION_CALL／UNIFIED_ACTION_RECEIPT v1；[CCZ-152](https://linear.app/ccz/issue/CCZ-152) 的合同冻结／完成记录 |
| 作品档案 | [合同原文](AUTHOR_WORKSPACE_PROJECT_PROFILE.md) | [Linear 原文](https://linear.app/ccz/document/95c53ae186c4) | author-workspace-project-profile-v1；2026-08-25 整理稿；[CCZ-97](https://linear.app/ccz/issue/CCZ-97) 的合同冻结／完成记录 |
| M1 统一父合同 | [合同原文](M1_ADMISSION_RECOVERY_CONTRACT.md) | [Linear 原文](https://linear.app/ccz/document/1d7326ec4a61) | 无独立总版本号；2026-08-25 整理稿及作品档案扩展。内部引用 generation-v2 等子合同版本；[CCZ-85](https://linear.app/ccz/issue/CCZ-85) 后续批准回执，详见下节 |
| 诚实读回 | [合同原文](M1_READBACK_CONTRACT.md) | [Linear 原文](https://linear.app/ccz/document/589505871791) | 无独立总版本号；2026-08-25 整理稿＋同日作品档案扩展；[CCZ-90](https://linear.app/ccz/issue/CCZ-90) 的合同冻结／完成记录 |
| generation 接纳 | [合同原文](AUTHOR_WORKSPACE_GENERATION_ADMISSION.md) | [Linear 原文](https://linear.app/ccz/document/0283c30f7f9d) | author-workspace-generation-v2；2026-08-24 冻结稿＋08-25 作品档案扩展；[CCZ-88](https://linear.app/ccz/issue/CCZ-88) 的合同冻结／完成记录 |
| 待接纳授权验证 | [合同原文](M1_PENDING_CONTENT_VERIFICATION.md) | [Linear 原文](https://linear.app/ccz/document/90abc86c731d) | 未标独立总版本号；2026-08-24 冻结稿＋08-25 扩展；验证策略 full-content-verification-v1；[CCZ-94](https://linear.app/ccz/issue/CCZ-94) 的合同冻结／完成记录 |
| 动作身份与幂等 | [合同原文](M1_ACTION_INTENT.md) | [Linear 原文](https://linear.app/ccz/document/4e7563eb6d19) | m1-action-request-v1；author-workspace-canonical-json-v1；2026-08-24 冻结稿＋08-25 扩展；[CCZ-89](https://linear.app/ccz/issue/CCZ-89) 的合同冻结／完成记录 |

## 批准与历史状态

七份子合同在本次读取时均有冻结／完成记录，对应票为 Done；只证明各自合同交付。M1 父合同有单独的后续批准记录：

[CCZ-85](https://linear.app/ccz/issue/CCZ-85) 评论 `5e626151-9b7b-46fc-aa31-f8ac4df47493` 记录 CZ 于 **2026-08-29 07:36:43 +08:00** 回复“都同意同意”，正式批准统一合同，解除已满足的合同阻塞；父票保持 In Progress，继续承载模块工作。评论同时说明旧“批准后父票 Done”不再执行。原合同顶部的“等待最终批准”是未同步的历史文字，本批原样保留并在此解释，不重新索要同一批准。

批准评论没有绑定当时全文字节哈希。本次指纹证明迁入文本与本次读取一致；批准状态依据后续评论、子合同完成记录及 CZ 本批对 R01 的明确批准，不把这个指纹冒充历史签名。

原文中的旧 main 与 #123 状态是当时快照。[#123](https://github.com/cczz412/novel-architecture/issues/123) 本次读取为 CLOSED，旧正文和标签不构成可施工入口。旧代码缺口的当日核对见 CCZ-184 R01；其中当前仓库已有通用 current 快照，但 M1 尚未按这批合同完成整条接纳与读回语义，不能概括成“完全没有快照”。

[公共读取合同](LEDGER_READ_TOOL_CONTRACT.md) 已有 v2 文本并保留 v1 兼容；统一调用原文中的 v1 引用保持不变，不静默改成 v2。M1 canonical-json-v1 的尾换行规则也原样保留，不与共同调用摘要算法强行合并。

## 原文怎样核验

每份文件用 `CCZ184_SOURCE_BEGIN` 和 `CCZ184_SOURCE_END` 注释划定原文区。核验时取两标记之间内容，去掉标记边界各一个换行，对该字符串按 UTF-8 原样计算 SHA-256，不额外追加换行。原文区必须与 Linear 工具返回的 content 完全一致。

这是 Markdown 读取指纹，不是 Linear 内部存储字节，也不是批准时的字节签名。表中时间照录工具 updatedAt；M1 文本含 08-25 扩展而时间仍在 08-24 UTC，不用时间字段替代版本判断。

| 合同 | source ID | updatedAt（UTC） | 字符数 | 原文 SHA-256 |
|---|---|---|---|---|
| 正式事实晋级 | `20944fa7-87c9-4d77-a544-d318238f3737` | 2026-08-31T22:37:40.610Z | 8952 | `56e8a61f09e402512a3da59a7e5f0fe570d065600ff6fdbb5a8f160c6de343fd` |
| 统一调用 | `60f90f86-f0f5-47d8-b931-688c87a26d86` | 2026-08-31T22:37:42.202Z | 12904 | `a356c6fbac03ede7c2dd7d5f59b4b836fa8020f67aa4f7f382a0768b837fb2b3` |
| 作品档案 | `3d63099b-5d4c-4fc5-a37f-fe5c75d3588b` | 2026-08-24T17:58:39.680Z | 10382 | `ce49f6b1f9dc36658b52e96e118e4037d6771c52445c57005cd63d9537ca1cb3` |
| M1 统一父合同 | `415629c7-eba2-4950-af6b-f71f9bcb6313` | 2026-08-24T17:59:17.914Z | 11431 | `2084c6da0e27836f8b2a3d6e4f8a11658b2521b7268c293c54acc7a13b513930` |
| 诚实读回 | `49227a4b-574e-462e-9170-7066a9881254` | 2026-08-24T17:59:14.356Z | 11009 | `0ff7bca6f8b8c5650f6a88e8f6e6435e2fb881b0bf7d7924ce259ed95074ffa0` |
| generation 接纳 | `5a15678b-a396-4032-9ac8-999776ff0434` | 2026-08-24T17:59:10.762Z | 14152 | `40eee8d992a55b3ad9176745b40feea1b2e11db87adebb9ccd7196635f3b8507` |
| 待接纳授权验证 | `eaef32be-5ead-4508-85a3-41f962e67c4b` | 2026-08-24T17:59:07.116Z | 10790 | `b3dd6d7efd19a490b0c413c5053c29d3968132414e5983f14b7dfe62b87eba76` |
| 动作身份与幂等 | `d9380e9e-f16e-44dc-b525-0da52dc6b787` | 2026-08-24T17:59:03.532Z | 13993 | `6d75dd4246b7db7274ea33ab5f4103cc343afa4509b428166bdfc416bc447dd4` |

## 互链与交接边界

原文中的 Linear 合同链接原样保留。本批文件的对应关系由上表提供：M1 动作身份 → 待接纳验证 → generation 接纳 → 诚实读回，作品档案扩展和统一父合同覆盖这一组。事实晋级与统一调用只按既有 action ID、动作合同版本、原始业务回执引用／摘要交接，不共享内部状态定义。

本批不生成新 Schema、校验器或能力 ID 登记，不以合同迁入冒充实现。版本、算法、机器字段、正文链接与测试向量均未重写。未来若要修订语义，回各自 owner 和新的批准写集处理。

只有 PR 后续获准合并并完成固定提交回读后，才按另行批准的切换步骤更新 Notion 工程索引与旧 Linear 来源路标。旧主存仍按现有登记读取，历史不删除；本批不执行这些外部切换。

来源：Codex
