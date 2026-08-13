# 调研结论

✅ 最合理的研究先验不是“越详细越好”，而是 **R10 附近的短合同**：约 8～10 条原子化决策规则，加上贴近字段的简短业务语义。R0 很可能欠定义；R15 应保留为压力测试，不应预设为赢家。

公开证据没有证明跨任务、跨模型都存在固定的倒 U 曲线，但已经出现很贴近 IE 的“中等详细度较好”迹象：

- ACE05 的 Argument Classification F1 从无规则 29.73，升到约 164-token 指南的 35.20；约 285-token 版本为 32.81，约 440-token 综合指南反降到 28.34。RichERE 对应为 25.32、26.35、27.18、20.81。但各版本内容也不同，而且规则同时用于训练和推理，不能把差异只归因于长度。[ACL Findings 2025](https://aclanthology.org/2025.findings-acl.677.pdf)
- GoLLIE 的跨任务零样本 IE 从 42.3±0.1 升到 55.3±0.2；在已见、监督 schema 上则是 73.3 对 73.0，几乎无益。规则更可能帮助未见标签和边界，而不是重复模型已经学会的固定任务。[ICLR 2024](https://proceedings.iclr.cc/paper_files/paper/2024/file/cda04d7ea67ea1376bf8c6962d8541e0-Paper-Conference.pdf)
- ManyIFEval 保持任务不变、从 1 条加到 10 条互不冲突约束时，所有十个模型都退化；总体平均全满足率在 5 条时为 0.574，10 条时仅 0.213。它测的多为格式规则，不是语义 IE，但 instruction competition 确实存在。[EMNLP Findings 2025](https://aclanthology.org/2025.findings-emnlp.896.pdf)

因此，本项目的待验证曲线应写成：

[
R0 < R5 ;\lessgtr; R10 ;\gtrless; R15
]

而不是预注册成“R10 一定最好”。

## A、最相关的 15 项研究与工业实践

| 工作                                                         | 量化观察                                                     | 对本项目的含义与边界                                         |
| ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| [GoLLIE，ICLR 2024](https://proceedings.iclr.cc/paper_files/paper/2024/file/cda04d7ea67ea1376bf8c6962d8541e0-Paper-Conference.pdf)；[代码](https://github.com/hitz-zentroa/gollie) | 零样本 IE 42.3→55.3；去掉代表性候选后为 49.9；已见任务约 73.3→73.0 | 标签、角色、字段语义很重要；但增益来自整套 guideline-following 训练，不能当作零训练 Prompt 的保证 |
| [Event Extraction with Annotation Guidelines，ACL 2025](https://aclanthology.org/2025.findings-acl.677.pdf) | ACE AC 29.73→35.20；约 440-token 综合版降至 28.34；RichERE 25.32→最高 27.18→20.81 | 最接近“中等详细度较好”的证据；内容与长度仍混杂               |
| [SLIMER](https://arxiv.org/abs/2407.01272)                   | BUSTER 未见标签 40.41→45.27；Amenity 33.38→28.18，Trailer 23.44→58.62 | 指南是否切中歧义，比字数更关键；坏规则会真实伤害             |
| [Did You Read the Instructions?，ACL 2023](https://aclanthology.org/2023.acl-long.172/) | 自动删掉约 60% 任务定义 token，性能持平或提高；结构化定义最高约 +4.2 Rouge-L | 优先保留输出标签及字段语义，压掉背景散文                     |
| [JsonTuning](https://arxiv.org/abs/2310.02953)               | 结构化 task card 总平均 23.90→27.69；NER 35.82→42.15         | 把输入、动作、字段语义分槽，通常好过无层次说明；这是训练表示消融 |
| [ManyIFEval，EMNLP 2025](https://aclanthology.org/2025.findings-emnlp.896/) | 5 条规则全满足率 0.574，10 条为 0.213；GPT-4o 评审却报 0.815/0.657 | 多规则会竞争；还表明 LLM judge 会掩盖失守，规则应尽量机械评分 |
| [FollowBench，ACL 2024](https://aclanthology.org/2024.acl-long.257/) | ChatGLM3-6B 从 L1 60.9 降至 L5 21.4；Baichuan2-7B 58.3→25.5  | 小模型常对复合约束敏感；旧模型、混合任务，不可直接给 Qwen 定上限 |
| [PLOVER Codebook，ACL 2024](https://aclanthology.org/2024.acl-long.35/) | 222 条扁平描述 75.6；分层查询 89.1                           | 组织方式可能比堆规则更重要；模型是 NLI 分类器，不证明生成模型必然偏爱决策树 |
| [KnowCoder，ACL 2024](https://aclanthology.org/2024.acl-long.475/)；[代码](https://github.com/ICT-GoKnow/KnowCoder) | code prompt 对普通 IE prompt 仅 +0.8 F1；去掉负类和全空样本分别 -7.4、-2.1 F1 | 不应迷信代码/有限状态写法；空窗和难负例必须进入训练          |
| [LMDX，ACL Findings 2024](https://aclanthology.org/2024.findings-acl.899/) | text-not-found/hallucination 低于约 0.6%，并由解码器全部过滤 | “逐字证据、合法 ID、允许区域”既要写成硬规则，也要程序验      |
| [Instruction Position Matters，ACL Findings 2024](https://aclanthology.org/2024.findings-acl.693/) | 把训练指令移到正文后，在翻译上最高 +9.7 BLEU                 | 支持文后 checklist 对照；并非推理时位置的直接证明            |
| [Lost in the Middle，TACL 2024](https://aclanthology.org/2024.tacl-1.9/)；[Irrelevant Context，ICML 2023](https://proceedings.mlr.press/v202/shi23a.html) | 关键信息位于上下文中部时利用率较差；无关句显著干扰推理       | 不要把最关键的取证权限埋在长合同中部；只读区必须明示         |
| [Prompt-format Sensitivity，ICLR 2024](https://proceedings.iclr.cc/paper_files/paper/2024/hash/6c0e99d736da621403018ca7b32b1a4d-Abstract-Conference.html) | 仅改等义格式，LLaMA2-13B 最大相差 76 个准确率点；模型间格式排名相关性弱 | Qwen 的最佳排版不能迁给 Ling 或 Doubao                       |
| [PromptIntern，EMNLP 2024](https://aclanthology.org/2024.findings-emnlp.602/)；[PAFT，EMNLP 2025](https://aclanthology.org/2025.emnlp-main.37/) | 专门内化后输入 token 可降逾 90%、推理快 4.2 倍；动态提示训练 87.57，固定方案次优 83.32 | SFT 后直接删 Rulebook 与专门训练模型内化规则不是一回事；固定字面模板有依赖风险 |
| [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)、[Google Structured Output](https://ai.google.dev/gemini-api/docs/structured-output)、[HF SFTTrainer](https://huggingface.co/docs/trl/sft_trainer) | Schema 可管 key/type/enum，但语义仍可能错误；官方建议字段 description 和应用端验证；SFT 可只算 assistant/completion loss | JSON Schema 不能代替业务合同；空值路径、字段语义和机械验证缺一不可 |

成熟证据集中在 annotation guideline、task definition、codebook、schema description、负例及验证器。Model card 主要用于披露模型，不是每个样本的任务指令；目前没有可信消融证明“把 model card 塞进 Prompt”会提高 IE。评分 rubric 也更适合留给 evaluator——ManyIFEval 已显示 LLM 评分会大幅高估多规则遵守率。

## B、哪些证据分别指向两边

支持“讲清楚”的部分：

- 未见 schema、细粒度标签、稀有事件类型受益最大。
- `status`、`speaker`、`evidence_ids` 的业务语义必须定义，不能只列名称和类型。
- 正负对照、空答案、unknown、近邻类别区别，比泛泛解释更有效。
- “逐字证据”“只读区不得取证”“无事实可空”应写成硬规则，并由程序再次验证。

警告“规则太多”的部分：

- 多条独立约束的联合遵守率会乘法式下降。
- 长综合指南可能比中等长度指南差，还可能增加解析错误。
- 冗余定义、无关背景和重复说明会占前向计算、注意力及有效上下文。
- 自然语言、表格、代码、决策树没有跨模型统一排名。

结论不是“规则少”，而是 **少量、高信息密度、可判定的规则**。

## C、本地零训练单变量对照

长度实验全部沿用现役位置。模型 checkpoint、量化、Qwen 原生 chat template、正文、Schema、解码参数、最大输出、后处理和样本顺序全部锁定。[Qwen 官方说明](https://qwen.readthedocs.io/en/latest/getting_started/concepts.html)也明确要求使用指定 chat template。

| 臂   | 合同内容                                                     | 建议规模        | 研究假设         |
| ---- | ------------------------------------------------------------ | --------------- | ---------------- |
| R0   | 当前任务、负责区、输出格式                                   | 原样            | 欠定义基线       |
| R5   | ①取证范围；②计划/承诺/推测；③误信/否认；④一事实一断言；⑤空答案、unknown、证据 | 120～180 中文字 | 最大性价比       |
| R10  | R5 拆成 10 条独立 if/then；另加只读泄漏、speaker、非事实排除等 | 250～350 中文字 | 当前最可能的胜者 |
| R15  | R10＋`fact/status/speaker/evidence_ids` 四项语义＋优先级/冲突处理 | 400～600 中文字 | 完整合同压力测试 |

执行方式：

- 用 TRAIN24 写定四份 Prompt；看 DEV24 前冻结文本、记录哈希。
- DEV24 只做选择，不再改 Prompt；胜者和次胜者进权利明确的冻结考卷复核。
- 4×24＝96 次长度请求；胜者再做 3×24＝72 次位置请求，共 168 次/固定解码轮。
- 有采样或云端轻微非确定性时跑三轮，共 504 次；固定 seed 并保留原始输出。
- DEV24 只有 24 个窗口，只能筛查。报告窗口级 paired bootstrap 95% CI，不把小差异写成生产定律。
- A v2.7 等权利未定数据只能评测，不得进入训练。

⚠️ R15 同时增加规则和字段语义。若 R15 胜出，应补一个 `R10F＝R10＋仅字段语义` 的诊断臂，否则无法判断收益来自字段说明还是额外五条规则。

## D、位置的最小对照

先选定同一份 R* 内容，再移动位置。

| 条件                   | 放置方式                                           | 含义                 |
| ---------------------- | -------------------------------------------------- | -------------------- |
| system-only            | 完整 R* 放 system；user 只放区域标签、正文、Schema | 测稳定高权限前缀     |
| user-before-text       | system 只有任务身份；完整 R* 紧贴正文之前          | 测局部邻近和现役形态 |
| system＋文后 checklist | 完整 R* 放 system；正文后重复 3 项复核             | 测 recency/提醒效应  |

文后 checklist 固定为：

> 复核：①只从负责区抽取；②证据逐字且 ID 合法；③无合格事实则输出空数组。

第三臂同时改变了位置、重复次数和 token 数，不是纯位置因果实验。若它胜出，再补一个同 token 长度、不重复业务规则的对照，或把同一完整 R* 整体移到正文后确认。

## E、预注册指标与胜出规则

| 指标                 | 预注册口径                                                   |
| -------------------- | ------------------------------------------------------------ |
| Semantic fact P/R/F1 | micro 为主；窗口 macro 为辅；另报严格端到端 F1               |
| 过抽                 | FP/千正文字符；分计划兑现化、误信真相化、否认真相化、总结、情绪、常识、只读泄漏 |
| 漏抽                 | FN/金标 fact；另报有事实窗口覆盖率                           |
| Status               | 已匹配 fact 上的 macro-F1、混淆表；另报 fact＋status 联合 F1 |
| Speaker              | exact/macro-F1；`unknown` 单列 P/R                           |
| Evidence             | evidence ID 合法率、最小充分证据率、逐字匹配率               |
| Read-only leakage    | 事实仅由只读区支持的比例；引用只读 evidence 的比例，两项分开 |
| Schema               | 原始 JSON 合法率、字段完整率、enum 合法率；无效输出的严格 F1 记 0 |
| 保守度诊断           | facts/千字、空答案率、明确正例 recall、每窗预测数量          |
| 成本                 | 实际 tokenizer 输入/输出 token、冷/热 TTFT、端到端 p50/p95 延迟 |

建议提前锁定的筛查门槛：

- 主指标：semantic fact micro-F1。
- Recall 不低于 R0 超过 2 个百分点。
- 明确正例 recall 不低于 R0 超过 3 个百分点。
- Read-only leakage 不得上升。
- Schema 合法率下降不得超过 1 个百分点。
- 若差异均落在置信区间内，选择更短的合同。

这些百分点是实验决策门槛，不是文献定律。

## F、怎样排除“只是更保守”

建立成对最小对照，每对只改一个词或一个区域标签：

| 对照                    | 真正理解应出现的变化            | 纯保守的表现                 |
| ----------------------- | ------------------------------- | ---------------------------- |
| “已经离开”↔“打算离开”   | 保留正确断言并切换现实性/status | 两句都少抽或计划句直接消失   |
| “答应归还”↔“已经归还”   | 承诺与兑现分开                  | 全部不抽                     |
| “他以为门锁了”↔“门锁了” | 前者绑定认知者/不升格世界事实   | 前者直接丢弃                 |
| “他否认杀人”↔“他杀了人” | 抽否认行为，不抽被否认内容      | 否认窗口空答，连否认行为也漏 |
| 同一句在负责区↔只读区   | 只读版本不得贡献 fact/evidence  | 两个版本都少抽               |

真实边界增益应同时满足：

- 边界型 FP 下降；
- 明确已发生事实的 TP 基本不变；
- 错误 status 变成正确 status，而不是变成 omission；
- 每窗事实数量没有跨所有类别统一收缩；
- 空窗精度提高，但有事实窗口覆盖率不下降。

## G、推荐长度、规则数量和写法

当前研究默认值：

- 语义规则：8～10 条，250～400 中文字。
- 字段 description：每项约 10～30 字，紧贴字段。
- 包含字段说明后的可复用合同：建议不超过 600 中文字；实际 token 必须用各模型 tokenizer 单独记录。
- 超过该长度的内容只有在 semantic F1 提升、Recall 门槛通过后才保留。

写法建议：

1. 一个编号只表达一个可判定动作。
2. 用“若 X，则标 Y；不得标 Z”的正反配对。
3. 权限和证据规则放开头；正文后只重复三项关键检查。
4. 互斥现实状态用紧凑 if/then；不要写成长篇解释。
5. JSON Schema 管形状，`description` 管字段业务语义。
6. 完整决策树留在标注手册和 evaluator；运行 Prompt 只保留最容易混淆的叶规则。
7. 长度实验阶段不放 few-shot，避免把规则数和示例效应混在一起。

## H、哪些信息分别放哪里

| 长期放生产 Prompt                      | 放训练样本                     | 留给 evaluator/程序          |
| -------------------------------------- | ------------------------------ | ---------------------------- |
| 负责区和允许取证区                     | 计划/兑现、承诺/兑现的最小对照 | JSON、enum、字段完整性       |
| 背景、只读区不得独立造事实或证据       | 误信、否认、推测、条件句       | evidence ID 存在性和区域权限 |
| 每条 fact 一个断言                     | 真空窗、unknown、难负例        | 逐字 span/offset 对齐        |
| `status/speaker/evidence_ids` 核心语义 | 同义 Rulebook 和不同表述模板   | 去重、评分阈值、语义匹配     |
| 无事实可空、不得猜测                   | 稀有长尾及文学复杂案例         | P/R/F1、升级阈值、成本与审计 |
| 排除总结、纯情绪和常识                 | 背景诱饵、未来信息诱饵         | 数据权利、来源和运行日志     |

评分权重、升级策略、数据权利和内部审计流程不应告诉模型。

### SFT 与重复 boilerplate

“每个训练样本重复 Rulebook 就等于浪费 loss”不成立：

- 使用 `assistant_only_loss` 或 `completion_only_loss` 时，Rulebook 不承担直接 token loss，但仍占前向计算、注意力和上下文。[HF TRL](https://huggingface.co/docs/trl/sft_trainer)
- 一项覆盖 525 个 SFT 配置的研究发现，给 Prompt token 较低至中等权重，平均相对提升约 6.55%；不同模型的最优权重不同。[TACL 2025](https://aclanthology.org/2025.tacl-1.62/)
- 固定一个字面版本反复训练会增加模板依赖风险。训练时可轮换少量语义等价版本；推理时再用未见改写做压力测试。

训练和推理不必逐字一致。必须严格一致的是模型原生 role/control token、EOS、generation prompt 和 chat serialization；业务语义应稳定。

生产 Prompt 只改措辞、顺序或压缩重复句时，不自动重训，先跑冻结回归集。若改变 `status` 定义、证据资格、负责区权限、unknown 规则或字段结构，就等于任务合同改变：应同步更新金标、训练样本和 evaluator，再由实测决定是否重新 SFT。

## I、三层复验方案

### 1. Dense Qwen 本地代理

- 跑完整 R0/R5/R10/R15。
- 用胜者跑三个位置条件。
- 对前两名加一份未训练同义改写，检查模板依赖。
- 若进入 SFT，再做最小 2×2：训练短/完整 × 推理短/完整。
- 固定本地 checkpoint、量化、Qwen 原生模板和推理后端。Qwen3-4B 的官方通用 IFEval 分数不能替代本项目 IE 实测。[Qwen3-4B 模型卡](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)

### 2. Sparse Ling Tiny

权重、许可和可复现实训方案可用后，只复验三个结论：

- R0 对 Qwen 前两名；
- Qwen 最佳位置对次佳位置；
- canonical Rulebook 对等义改写。

不重跑全部组合。Dense 与 Ling 的差异同时包含 tokenizer、预训练、后训练、总参数、激活参数及路由差异，不能把结果直接归因于“稀疏架构”。

### 3. Doubao Mini/Lite

- Mini 只迁移本地前两名合同，使用权利明确的冻结考卷。
- Lite 只跑预注册复杂子集及升级案例；Mini、Lite 分开报数，不共享胜者结论。
- 云 SFT 只给最终合同和一份短合同做训练/推理交叉，不进行多臂探索。
- 每次记录精确 endpoint/snapshot。官方将 Mini 定位为吞吐和高并发，Lite 定位为质量与速度平衡，但没有中文小说事实抽取消融可供外推。[Seed2.0 官方资料](https://seed.bytedance.com/en/seed2)

## J、候选精简 Rulebook

下面约 314 字，只是 **研究候选 R10-C**，用于 R10/R15 试验和措辞讨论；不得直接替换现役合同。

只抽取当前“负责区”中由原文直接支持、会影响人物、物品、关系、事件或状态的事实。每条 fact 只写一个核心断言。计划、承诺、条件、推测、误信、否认分别按原意标注，不得改写成已经发生或世界真相；否认行为可记录，被否认内容不可当真。背景区和只读上下文只用于消歧，不能单独产生 fact，也不能作为 evidence。evidence 必须逐字取自允许取证区；使用 evidence_ids 时，只选覆盖该证据的编号。status 表示断言的现实性或模态，不等同于事件类型。speaker 仅在原文明示归属时填写，否则用 unknown。不要抽剧情总结、纯情绪或氛围描写、一般常识。没有合格事实时输出空 facts，不得凑数或猜测。

一句执行结论：**先锁死四份合同，完成 96 次长度筛查；再用胜者完成 72 次位置筛查。生产迁移只带走前两名和它们明确赢下的边界类型。**

来源：ChatGPT