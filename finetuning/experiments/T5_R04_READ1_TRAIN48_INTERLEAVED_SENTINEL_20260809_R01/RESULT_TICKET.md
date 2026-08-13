# SM-INTERLEAVED iter24｜结果

结论：`FAIL_SM_INTERLEAVED_AT_L6_REAL8_GATE`。

本格唯一变化是把 TRAIN48 后12条从纯短／纯中相邻批改为 `[0,10][0,8][1,7][2,6][2,5][3,4]`；48条 payload 多重集、前36行、762条事实、Prompt、Gold、模型、训练参数和解码均未改变。只训练了 iter24，没有运行 iter48/72/96。

- 排序版训练数据 SHA：`95e78fc3aff86194e2579f5c7d0ec5e5887cfacf0f30788702f02c4e3e88ac73`。
- runner SHA：`e6fabfb6349f0f0c14f2cafe5760571a9cad6f898ece50a665b1642baf0ed507`；scorer SHA：`a19d8bdca348696000c2387edaf1afb39977526ae55915a1df0f604da656f32d`。
- iter24 adapter SHA：`5d216293ca8d10c18c3cb67d25fc9ea32076f13692c0da9f34a04361cb6f14ca`。
- L6：TP=10，FP=47，FN=8，P=0.175439，R=0.555556，F1=0.266667；L01/L02预测数={'LC-L01': 18, 'LC-L02': 8}。
- REAL8：TP=32，FP=37，FN=53，P=0.463768，R=0.376471，F1=0.415584。
- 14题稳定性：复读=0，触顶=0，重复事实=0。
- 第一道门：{'l6_f1_at_least_0_208955': True, 'l6_fp_below_42': False, 'real8_f1_at_least_0_431': False, 'real8_tp_at_least_35': False, 'two_zero_gold_cases_exactly_empty': False, 'zero_repetition': True, 'zero_token_limit': True}。
- 未进入 REAL24。

本轮训练调用1次，本地推理只到事前门允许的范围；API调用0。没有运行其他LoRA、READ2/READ4、OUT、Notion、Git或现役指针操作。

来源：Codex
