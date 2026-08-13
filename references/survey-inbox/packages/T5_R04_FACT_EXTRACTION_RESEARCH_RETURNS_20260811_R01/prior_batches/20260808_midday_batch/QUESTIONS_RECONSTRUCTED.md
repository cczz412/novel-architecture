# 2026-08-08 中午批次｜五个调查问题骨架

⚠️ 这批 10 份完整回包仍在，但当前没有找到当时逐字发送的 Prompt。下面五题是依据同一时段两套回包的标题、正文研究范围和结论配对恢复出的题意，只用于追源，不能冒充原 Prompt。

本目录内的 `Q01`～`Q05` 是归档局部编号。每题包含一份时间戳命名的 Deep Research 回包和一份独立命名回包；两份原件均逐字节保存，源文件不移动、不覆盖。

## Q01｜C2 语义较好但 Schema 失败时，怎样只修格式而不伤语义？

恢复出的题意：判断是否应优先使用通用 JSON grammar、最小 JSON Schema 或其他推理期约束，把格式通过率提高到 100%，同时把事实集合、状态和证据绑定不漂移设为安全门，而不是立即重训 C2。

| 回包 | 原始绝对路径 | 归档相对路径 | bytes | SHA-256 |
|---|---|---|---:|---|
| A | `/Users/a1234/Downloads/deep-research-report - 2026-08-08T124038.754.md` | `returns/01a_c2_schema_repair.md` | 45,848 | `4c0d74eb571f04e5a6ba92fe62472d8031088c27ce83b22bc2c7bb3c0da7d214` |
| B | `/Users/a1234/Downloads/结论1.md` | `returns/01b_c2_schema_repair_review.md` | 25,332 | `4b46f4c6c6567a79c4d2aee3e3a7d2cfd4c44222c9425807bc96f84707d119ff` |

## Q02｜为什么 evidence IDs 可能优于逐字 evidence？

恢复出的题意：区分证据选择、逐字复制、序列化负担和显式对齐监督，判断 C2 的收益来自哪里；不能把一次小样本结果外推成“ID 天生更好”，并应设计能拆开这些机制的对照。

| 回包 | 原始绝对路径 | 归档相对路径 | bytes | SHA-256 |
|---|---|---|---:|---|
| A | `/Users/a1234/Downloads/deep-research-report - 2026-08-08T124045.161.md` | `returns/02a_evidence_ids_vs_text.md` | 43,233 | `7b40c95b3757aecf00c38c04f85c84d0078576ec4efa6ae56c47fa0519e553a0` |
| B | `/Users/a1234/Downloads/总判断3.md` | `returns/02b_evidence_ids_vs_text_review.md` | 16,090 | `abd151e2aed4684f4636f845083f7c902f264c4b33a223ee2298df543c39356e` |

## Q03｜C2 ID List 与 D Range，哪种证据表示更适合小模型？

恢复出的题意：比较完整 ID 列表与起止范围的语义表现、Schema、输出长度和非法状态；检查“字符串更短”是否真的降低学习难度，并研究兼容单点、连续段和离散段的规范表示。

| 回包 | 原始绝对路径 | 归档相对路径 | bytes | SHA-256 |
|---|---|---|---:|---|
| A | `/Users/a1234/Downloads/deep-research-report - 2026-08-08T124104.319.md` | `returns/03a_id_list_vs_range.md` | 37,386 | `4c00efa23e4d7b6aadaab5a3c555733cd495a27c829630b7517dc1465e7a7027` |
| B | `/Users/a1234/Downloads/A. 最相关研究和 GitHub.md` | `returns/03b_id_list_vs_range_review.md` | 14,628 | `e04f8fd02150dc831292672e44dcb6c32b2bdc8c420f2e36034704c4584b3ea2` |

## Q04｜Tiny SFT 用 24 条训练样本迁移到未见 24 条，能证明什么？

恢复出的题意：判断小数据 SFT 更像任务接口学习、已有能力激活、窄规则学习还是样本偶然；明确 adapter-off、prompt-only、随机种子、泄漏检查和未见真实小说等必要边界，不能把单个 DEV24 分数写成稳定通用能力。

| 回包 | 原始绝对路径 | 归档相对路径 | bytes | SHA-256 |
|---|---|---|---:|---|
| A | `/Users/a1234/Downloads/deep-research-report - 2026-08-08T124111.465.md` | `returns/04a_tiny_sft_generalization.md` | 41,276 | `ea6e1f77e375001cce4afe9c207f79288e62c7ff42cfe231a82c302d4e703f76` |
| B | `/Users/a1234/Downloads/A. 当前 24 TRAIN + 24 DEV 能证明什么.md` | `returns/04b_tiny_sft_generalization_review.md` | 20,226 | `eaa812ec5e55a889fcdf9b0c8519d2ef8c013a6995698705971cb05a0033d33a` |

## Q05｜什么时候应放弃让 LLM 生成完整事实对象，改成结构化预测流水线？

恢复出的题意：判断 evidence-first、ID 选择、程序取回原文、确定性排序去重和 JSON 组装，能否减轻小模型同时承担语义判断、复制和格式生成的干扰；同时保留单阶段 C2 作为对照，不能未经实验直接淘汰。

| 回包 | 原始绝对路径 | 归档相对路径 | bytes | SHA-256 |
|---|---|---|---:|---|
| A | `/Users/a1234/Downloads/deep-research-report - 2026-08-08T124118.498.md` | `returns/05a_structured_prediction_pipeline.md` | 59,518 | `e10bb9a8a66b66175a9cc14ff6b913f334248eca1bd721921e228e59558c7958` |
| B | `/Users/a1234/Downloads/结论5.md` | `returns/05b_structured_prediction_pipeline_review.md` | 17,822 | `0aff7f213b3a502f8c3eefc1a8062c9a1856d02a3275aa12773d4d2469789b6a` |

来源：Codex
