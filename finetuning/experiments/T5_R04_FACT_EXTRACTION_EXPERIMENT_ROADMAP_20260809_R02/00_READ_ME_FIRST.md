# 事实抽取实验总路牌 R02｜先看这里

✅ 当前是 **18 个旧登记家族 + 1 个新指代后处理家族 = 19 个家族**。真正排队的只有 **READ 正文范围**，不是看见清单就把全部实验跑一遍。

旧 R01 的 66 项是“登记格”，不是 66 个模型，也不是 66 个必须运行的实验。现场真正已经训练过的独立 LoRA 只有 7 个：旧输出格式 4 个，旧短范围匹配 3 个。R02 只负责把命名、归属和顺序说清楚，不新增运行权。

父登记册是 `finetuning/experiments/T5_R04_FACT_EXTRACTION_EXPERIMENT_ROADMAP_20260808_R01/ARM_REGISTRY.json`，SHA-256 为 `f9e1d3b864e383fe0d7c23462a5445e224352b6003047038483444429795b7d8`。R01 全目录保持不动。

🔥 当前顺序只有两轮：

- Round 1：输出固定为 `OUT-2-IDLIST`。READ-1/2/4 从同一个注册 base／parent 独立训练，只改 READ renderer，得到三个不同 adapter，再选出 `READ-WINNER`。
- Round 1 同时让同一个未微调 base 分别回答 READ-1/2/4 三套题面，用来区分“base 本来就会”和“训练带来的增益”。三个 LoRA 只答各自匹配题面，不互相串跑。
- Round 2：阅读范围固定为 `READ-WINNER`。OUT-3/4 从同一个 base 独立训练；`OUT-2-IDLIST` 使用 Round 1 已有的 READ-WINNER adapter。共同格身份完全相同才复用。
- 因此不是 3×3 九格，正常最多 5 个**训练配方／LoRA 组合**。base 的推理调用单独计，不包含在“5”里。当前组合只写成 `READ-WINNER + OUT-WINNER`。

这条 Demo 路线承认不能穷尽 READ×OUT 的所有交互。只有赢家差距很小、换数据后名次反转或出现明确交互信号，才补 1—2 个定向交叉格；不会自动补齐九格。

训练教材只用项目原创 TRAIN36。现有真实 24 题沿用旧目录名 `CONFIRM24`，但当前角色改为 `LOCAL_REAL_SCREEN24`，也就是“本机真实筛选考试”。它只用于 READ、OUT 的 Demo 筛选与淘汰，永不进入训练、选样、调参或 gold 修改。Round 1 已经看过结果后，它也不能再称为最终盲考、生产泛化证明或一次性未见确认；真要做最终结论，需要另建未见题，但这不阻断当前 Demo。

后续顺序是 RULE → EX → BG。PURPOSE 已打平暂停，STATE 已出现负面和泄漏，继续暂停。其余家族只是后续或条件式候选。

Wave3 继续暂停。本目录没有训练、推理、API、Notion、Git、生产默认或现役指针变更。

来源：Codex
