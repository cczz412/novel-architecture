# 调查批次索引

## 2026-07-31｜五问批次＋一份独立历史报告

五份同一时段报告的问题主题和原件见 [问题主题恢复页](prior_batches/20260731_batch/QUESTIONS_RECONSTRUCTED.md)。另有一份 [同模型多步纠错与上下文工程报告](historical_foundations/20260731_multistep_correction/README.md)。这些题意均由报告恢复，不是逐字 Prompt。

## 2026-08-01／02｜基础批次＋上下文策略整包

- [基础批次三题三报告](prior_batches/20260801_02_foundation_batch/QUESTIONS_RECONSTRUCTED.md)
- [上下文策略回包](historical_foundations/20260802_context_strategy_return/README.md)：一份主报告、五份附件，报告数只计一份。

## 2026-08-07｜六问六回包

问题主题、完整报告和 SHA 见 [问题主题恢复页](prior_batches/20260807_batch/QUESTIONS_RECONSTRUCTED.md)。这批正是旧聊天复合摘录曾列出、但原知识包没有真正收进去的六份原件。

## 2026-08-08 中午｜五问双回包

五个问题各有两份独立回包，共 10 份。题意和配对见 [问题主题恢复页](prior_batches/20260808_midday_batch/QUESTIONS_RECONSTRUCTED.md)。逐字 Prompt 尚未找到。

## 2026-08-08 下午｜六问双回包

当时把同一组 6 个问题分别交给两类外部调查，得到 12 份互不重复的报告。逐字 Prompt 已无法从当前主会话恢复，问题骨架见 [QUESTIONS_RECONSTRUCTED.md](prior_batches/20260808_batch_a/QUESTIONS_RECONSTRUCTED.md)。

现在另找回了 [六份候选 Prompt 源稿](prompt_sources/20260808_six_question_source_candidates/README.md)。它们与六问主题逐题吻合，但缺少“外部窗口确实逐字照发”的证据，因此只作为候选源稿，不替换旧身份说明。

| 问题 | batch A | batch B |
|---|---|---|
| 规则书详细度 | [A01](prior_batches/20260808_batch_a/returns/01_input_context_rulebook_length.md) | [B06](prior_batches/20260808_batch_b/returns/06_rule_count_prompt.md) |
| 固定示例／minimal pair | [A02](prior_batches/20260808_batch_a/returns/02_examples_minimal_pair.md) | [B01](prior_batches/20260808_batch_b/returns/01_fixed_fewshot_examples.md) |
| 章节／块位置 metadata | [A03](prior_batches/20260808_batch_a/returns/03_position_metadata.md) | [B05](prior_batches/20260808_batch_b/returns/05_chapter_block_position_metadata.md) |
| 背景卡与证据防火墙 | [A04](prior_batches/20260808_batch_a/returns/04_background_evidence_firewall.md) | [B04](prior_batches/20260808_batch_b/returns/04_character_identity_context.md) |
| 告知下游用途 | [A05](prior_batches/20260808_batch_a/returns/05_downstream_purpose_prompt.md) | [B02](prior_batches/20260808_batch_b/returns/02_task_purpose_prompt.md) |
| 上下文范围与长度 | [A06](prior_batches/20260808_batch_a/returns/06_context_length_scope.md) | [B03](prior_batches/20260808_batch_b/returns/03_context_scope_research_industry.md) |

## 2026-08-09｜训练稳定性与教材

问题原文见 [QUESTIONS.md](prior_batches/20260809_batch/QUESTIONS.md)。5 个问题得到 6 份回包；Q01 有 3 份独立复核。

| 问题 | 回包 |
|---|---|
| Q01 batch 配对与梯度累积 | [调查主报告](prior_batches/20260809_batch/returns/01_lora_sft_batch_pairing_investigation.md) · [机制复核 A](prior_batches/20260809_batch/returns/02_batch_pairing_mechanism_review_a.md) · [技术审查 B](prior_batches/20260809_batch/returns/03_batch_pairing_mechanism_review_b.md) |
| Q02 空／稀疏／中密教材 | [教材配额报告](prior_batches/20260809_batch/returns/04_new24_curriculum_distribution.md) |
| Q03 4B 数据量与训练剂量 | [TRAIN96 建议](prior_batches/20260809_batch/returns/06_train96_base_restart_recommendation.md) |
| Q04 目标段／局部／整章 | [READ 对照设计](prior_batches/20260809_batch/returns/05_read_context_comparison_design.md) |
| Q05 4B 到 Mini 排名桥 | 本批没有单独文件回包；另一个产品架构调查批次有 [4B→商用迁移报告](../PRODUCT_ARCHITECTURE_RESEARCH_RETURNS_20260809_R01/returns/RESEARCH_06_4B_PROXY_TO_COMMERCIAL_MOE_2026-08-09.md)，只作交叉参考，不倒填成本批回包。 |

## 2026-08-10｜具体失败面的外部校准

问题原文见 [QUESTIONS_20260810.md](QUESTIONS_20260810.md)。

| 问题 | 回包 |
|---|---|
| Q01 规则越加越差 | [完整报告](returns/01_rule_constraint_interference.md) |
| Q02 固定双成员对比例 | [完整报告](returns/02_ex_contrastive_pair.md) |
| Q03 小说责任块切分 | [完整报告](returns/03_novel_responsibility_chunking.md) |
| Q04 DEV24 统计可信度 | [完整报告](returns/04_dev24_statistics.md) |
| Q05 LoRA 教材与训练 | [完整报告](returns/05_lora_sft_training.md) |

## 2026-08-11｜A／B／C 对照前置三问

逐字 Prompt、完整回包、SHA 和外发包追源见 [批次说明](prior_batches/20260811_pre_abc_batch/README.md)。

| 问题 | 回包 |
|---|---|
| 主抽取＋盲补漏＋逐条验真能否稳定修到可用 | [完整报告](prior_batches/20260811_pre_abc_batch/returns/01_multistage_pipeline.md) |
| 何时保留多步 API，何时微调 Mini／Lite | [完整报告](prior_batches/20260811_pre_abc_batch/returns/02_api_vs_finetune_constraint_optimization.md) |
| 怎样证明独立验真器没有与提议模型共同犯错 | [完整报告](prior_batches/20260811_pre_abc_batch/returns/03_independent_verifier_preregistration.md) |

这三份报告返回时，新的 A／B／C Prompt 对照与最终模型筛选尚未完成。报告里的具体模型和岗位只按“历史候选建议”读取；后续模型去留必须由同批对照结果另行决定。

## 2026-08-11｜停点15决策支持两问

逐字 Prompt、完整回包、SHA 和共享证据包追源见 [批次说明](prior_batches/20260811_stop15_decision_support_batch/README.md)。

| 问题 | 回包 |
|---|---|
| 两块精确分加剩余块边界，何时足够形成 3～5 名初步候选 | [完整报告](prior_batches/20260811_stop15_decision_support_batch/returns/01_partial_score_shortlist_stopping.md) |
| 36～60 次 PROMPT-A／B／C 执行合同是否存在归因漏洞 | [完整报告](prior_batches/20260811_stop15_decision_support_batch/returns/02_prompt_abc_contract_audit.md) |

这两份是顾问意见：第一份只影响尚未生成的短名单派生规则；第二份只影响尚未冻结的 A／B／C 派生执行票。回包中的部分进度数字不是当前真源，也不产生模型选择、API、训练或生产权限。

## 2026-08-11｜判别卷、调用账与确认卷三问

Prompt 源逐字副本、三个代码块 Prompt、完整回包、SHA 和时间边界见 [批次说明](prior_batches/20260811_discrim_cost_confirm_batch/README.md)。

| 问题 | 回包 |
|---|---|
| 四章小样本判别卷怎样筛出候选 | [完整报告](prior_batches/20260811_discrim_cost_confirm_batch/returns/01_discrimination_test_design.md) |
| 多平台 API 的费用、Token、时延与重试怎样双账 | [完整报告](prior_batches/20260811_discrim_cost_confirm_batch/returns/02_api_cost_token_latency_ledger.md) |
| `CONFIRM4` 怎样封存、一次性开封和按披露程度降级 | [完整报告](prior_batches/20260811_discrim_cost_confirm_batch/returns/03_confirm4_seal_open_protocol.md) |

这三份报告返回于 `FRESH-DISCRIM4` 权利门审查期间，早于任何 `DISCRIM` 正文开封或新的 API 调用。它们只有顾问身份：不能授权 API、训练、模型选择、Prompt 改写、`CONFIRM` 开封或生产晋级。报告建议的 12 章确认、`ε=0.02`、90% bootstrap、保留约 5～8 个且最多 10 个条件等数字也没有得到 CZ 拍板，不能自动执行。

## 2026-08-12｜DISCRIM17 部分盲审试选方法一问

逐字 Prompt、完整回包、SHA 和外发包追源见 [批次说明](prior_batches/20260812_discrim17_partial_blind_review_method_audit/README.md)。

| 问题 | 回包 |
|---|---|
| 225／916 条已审时，怎样用可达上下界停审并只选择有决策价值的匿名行 | [完整报告](prior_batches/20260812_discrim17_partial_blind_review_method_audit/returns/01_discrim17_partial_blind_review_method_audit.md) |

这份报告只作方法顾问证据。它支持停止默认 Wave06～21，也支持把试选器退修为 R02；不能授权真实解盲派生、候选、排名、API、A／B／C、训练或生产晋级。报告中的“累计 R05 尚不存在”是打包时快照，本地随后已生成 R05，当前状态不从报告倒推。

来源：Codex
