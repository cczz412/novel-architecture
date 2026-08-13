# 首次应用记录｜BG 家族开跑前

状态：`PRE_RUN_GUARDRAILS_ACTIVE_NO_MODEL_AUTHORITY`

## 外调触发

当前处理的是“确认背景是否帮助消歧、还是污染事实”的问题。本地历史调查库已经有“背景卡与证据防火墙”“上下文范围”两组回包，P3 也留下了确认背景不可测的本地缺口，因此本轮记为 `REUSE_EXISTING`，暂不生成新外调简报。复用入口：

- `references/survey-inbox/items/SI-002_T5_R04_fact_extraction_research.md`
- `references/survey-inbox/packages/T5_R04_FACT_EXTRACTION_RESEARCH_RETURNS_20260811_R01/BATCH_INDEX.md` 中“背景卡与证据防火墙”“上下文范围与长度”两组
- `references/survey-inbox/packages/T5_R04_FACT_EXTRACTION_RESEARCH_RETURNS_20260811_R01/02_RETURNS_DIGEST.md`
- `finetuning/experiments/T5_R04_INPUT_CONTEXT_CONTRACT_P3_20260808_R01/sealed_inputs_r01/track_b/BACKGROUND_MIN_CONFIRMED_NOT_TESTABLE_GAP.md`
- `finetuning/experiments/T5_R04_INPUT_CONTEXT_CONTRACT_P3_20260808_R01/P3_RESULT_TICKET.md`

后续若现有材料不能回答新的方向性问题，而且答案会改变下一个尚未冻结的比较单元，再按本合同停手出简报。

## 格内预注册

R02 已登记 BG 输入臂：无背景基线、确认相关背景、等长度中性背景和冲突压力背景；条件式背景训练 2×2 只预注册，不提前执行。

本轮先做 24 题来源与截止点盘点，不生成背景正文、不渲染请求、不运行模型。材料通过后，当前主比较单元固定为：BG-0 复用冻结基线，BG-1 确认背景与 BG-2 等长度中性背景一起冻结、同批执行、统一盲审和统一出分。BG-1 或 BG-2 任一材料不足时，主比较单元停在准备态；不能先看一臂再补另一臂。

BG-3 冲突背景现在预注册为 `BLOCKED_DIAGNOSTIC`，不阻断主比较。它只在 BG-1 通过预注册晋级门并被选为主比较赢家后释放，用来检查收益是不是建立在“模型盲信背景”上；否则零调用。它永不训练，也不能在看分后临时改材料或门值。BG-4～BG-7 只登记为 `BLOCKED_CONDITIONAL`；只有背景输入臂通过主比较及预注册的必要压力门后，才可另审训练 2×2，之前不生成请求、不加载模型、不训练。

## 尺子门

当前 Gold 校准门状态：`NOT_YET_SATISFIED`。当前评分器校准门状态：`NOT_YET_SATISFIED`。DEV24 现有结果票和 R11 运行后的语义裁决都不能倒充运行前的 `GOLD_CALIBRATION_RECEIPT`。

在任何 BG 模型调用前，必须补齐状态为 `PASS_FINAL_CALIBRATED` 的 DEV24 Gold 校准回执；另建评分器校准回执，填入 BG-0 基线臂与结果票 SHA、比较方向、Precision／Recall／F1、Recall 不退的具体门值、背景倒灌假事实的统计分母与允许上限、背景证据禁用门和统一选胜规则。任一缺件就停在准备态。来源盘点、SHA 核对和材料充足性判断不调用模型，可以继续。

## 接力页

EX 已在 R11 正式收口并保留无示例基线；本次已把微调接力页更新到 R11，并登记 BG 来源预检为下一动作。BG 主比较单元形成正式结论时更新一次；若后来释放 BG-3 或训练 2×2，每个比较单元各自在收口当天再更新一次，并指向对应结果票。

## 冻结引用

- R02 家族登记册 SHA：`1032f11162508f5b1747c606d932671d157eaadfdd02bf7f154e65ba78799134`
- R11 README SHA：`274efcf9f1e5207ea49a4232e3d03645d1fcb66522dcb6da5feca8e13f99581e`
- R11 登记册 SHA：`147d6eea3d13d675b529293fafc2e845262eb947159867122c999651aff2b49f`
- R11 EX 结果票 SHA：`721814540968c8154d21cba4dbf8149ea86f887233d37afcbedcb14a63df9938`

本记录没有模型加载、推理、训练、API、Notion、Git 或生产动作。

来源：Codex
