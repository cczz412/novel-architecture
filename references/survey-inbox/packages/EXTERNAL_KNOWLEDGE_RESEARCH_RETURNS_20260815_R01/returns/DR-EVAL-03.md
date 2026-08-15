# DR-EVAL-03｜多模型验真、LLM-as-judge 与人工确认：发现错误和提出修法必须分开

**调查执行日：2026-08-14**  
**公开研究主时间窗：2025-01-01 至 2026-08-14；必要时回看 2024 年已成为后续工作基线的研究。**  
**地区与语言：研究论文以英文公开学术资料为主；“中国网文常用说法”只取中国大陆公开中文网页样本。**  
**边界：不推荐任何当前具体厂商模型；论文里的模型名只用于还原实验条件，不代表 2026-08-14 的产品能力判断。本文也不使用厂商当前价格做决策，成本数字均为论文实验时的相对成本或调用次数。**

## 一页人话结论

✅ **这轮更新没有推翻旧结论，反而把它说得更硬了：多模型审计适合当“找可疑点的传感器”，不适合当“多数票即真相”的裁判团，更不适合拿审计票数直接批准修法。**

最重要的新证据来自 2025～2026 年对**相关错误**的研究。ICML 2025 对 350 多个模型的研究发现：模型同时犯错时，错误并不是彼此独立的；共享架构或提供方会进一步提高相关性，但即便来自不同提供方、不同架构，高能力模型之间仍能保持很高的错误相关。也就是说，**跨家族能减少一部分相关性，但远远不等于把错误变独立**。citeturn4search2

2026 年一项专门研究九个 judge、七个模型家族的工作把这个问题量化得很直观：九票在一个 NLI 数据集上的“有效独立票数”只有约 **2.18 票**；本报告用论文给出的平均错误相关系数 \(\phi=0.391\) 按其公式复算，\(9/[1+8\times0.391]=2.180\)，与论文报告一致。九个 judge 中后四个只多贡献约 **0.22 张有效票**。更危险的是，MNLI 的 1,000 个样本里出现了 **51 个“九个 judge 全错”**的样本，而独立错误假设下预计不到 1 个。多数一致因此可以非常自信地一起错。citeturn6view1turn6view2

**跨家族究竟强多少？公开结果不支持一个固定增益。** 上述九-judge 研究中，同家族错误相关均值约 0.436，跨家族约 0.389，只差 **0.047**；而只留“每个家族一个代表”后，有效票数反而由 2.18 降到 1.93。三个相关性最高的配对里还出现了跨家族组合。因此，“不同厂商／不同家族”最多是一个**去相关候选条件**，不是置信度加分规则。citeturn6view3 同时，ICLR 2026 的 Preference Leakage 又发现，同一模型、继承关系以及同一模型家族之间确实可能出现系统性的偏好泄漏，所以“避免同源”仍然有价值；只是它**不够**。citeturn25search1turn4academia48

位置、长度、自我偏好也没有一个能写死的“通用偏差方向”。ICLR 2025 的 CALM 在六个 judge 上发现显著的自我增强倾向，并发现候选答案增加到三、四个以后位置偏差会显著恶化；但同一研究中也有一个模型给自己的答案反而更低分。其自我增强表格复算后，六个 judge 的相对误差分别约为 **−16.64%、+9.40%、+8.18%、+3.64%、+5.39%、+8.99%**，所以准确说法应是“**多数被测 judge 有自我偏好，不是所有 judge 必然如此**”。citeturn23view0turn23view1turn24view0

长度偏差同样不是“越长越讨喜”。CALM 发现长度增加会改变判决，但不同模型既可能偏长，也可能厌恶过度冗长；2026 年另一项系统实验甚至观察到有的 judge 明显偏长，有的偏短，有的近乎中性。位置偏差也出现相反结果：后者在特定 pairwise 测试中测得的位置效应很小，而 CALM 在多候选设置里很严重。最合理的解释不是哪篇“错了”，而是**偏差高度依赖任务、候选数量、提示和模型版本**。citeturn23view2turn5view4

🔥 **“发现错误”与“修法是否可接受”必须做成两个统计问题。** 公开研究里已经能看到两种风险完全不同：错误检测追求的是不要漏掉真错；修复阶段最大的新增风险却是把原本正确的内容改坏。一项 2026 年数学修复实验中，受保护的 repair 流程修复了 17 个剩余错误、主实验未测到破坏正确答案；而“把所有答案重新解一遍”虽然修了 13 个，却把 **47 个原本正确答案改错**。本报告按 1,319 个样本复算，前者净变化约 **+1.29 个百分点**，后者约 **−2.58 个百分点**。这是数学题，不足以直接证明网文流程，但它非常清楚地展示了为什么“检测器发现异常”不能自动推出“它给出的补丁应该被接受”。citeturn5view7turn6view7

选择性路由比“让所有 judge 都投票”更有希望。ICLR 2025 的 *Trust or Escalate* 把问题改成：judge 只在经过人类标注校准后、达到风险门槛时出结论，否则升级或弃权。在 ChatArena 的目标 80% 人类一致设置下，论文报告覆盖率 79.1%；本报告复算其 judge 构成，40.1%、48.0%、11.9% 乘覆盖率后分别是 **31.72%、37.97%、9.41%** 的全部样本，合计 79.10%，与论文图表一致。它证明的是“**校准后的选择性预测可以用覆盖率换可靠性**”，而不是“模型自己的 confidence 可以直接信”。事实上，论文发现普通预测概率和口头自报信心明显过度自信。citeturn15view0turn16view1turn17view0

但这里有一个对本产品极重要的限制：*Trust or Escalate* 保证的是**与人类多数标签的一致率**，而你们的目标是“作者冻结 Gold／可追源事实是否被违反”。两者不是一回事。因此它的方法可以借，**它的保证不能原样搬过来**。你们必须拿自己的冻结 Gold 重新校准。该论文自己也明确依赖 calibration set，并假定校准样本与运行分布足够匹配。citeturn15view0turn16view3

同样，**弃权能力本身也不能靠提示词想当然**。NeurIPS 2025 的 AbstentionBench 在 20 个数据集、20 个模型上发现，现代模型的“不该答时不答”仍未解决；研究中的 reasoning fine-tuning 平均还使 abstention 指标下降约 24%。所以“让 verifier 自己说不确定”不是可靠路由机制，真正有价值的是**在固定 Gold 上校准过的风险—覆盖曲线**。citeturn26search6

对 debate、self-consistency、verifier chain 的结论也应该收紧。2025 年 ColMAD 工作报告，竞争式 debate 会出现“为了赢而说服 judge”的 debate hacking，甚至落后于单 agent；改成协作式批评才明显好转。PVD 的实验则显示 debate 往往要约 9 次调用，而 selective prover-verifier 可以在约 3～6 次调用下形成有用的高置信子集，但错误的 verifier pairing 在更难任务上甚至会让高置信信号倒过来。**流程复杂不是质量保证，额外 agent 只有在产生可测量的互补错误时才有净收益。** citeturn26academia24turn8view2turn8view3

因此，本题能比较有把握地给出的产品方向是：

> **把多模型当“互相不完全独立的异常传感器”；把校准当“决定何时值得打扰人”；把修复当第二项任务；把作者确认当真值写入前的最后一道门。**

而目前**不能**从公开研究得出的，是：中国长篇网文里跨家族能提高多少 recall、能省多少作者分钟、哪种 judge 数量最划算、补丁接受率能到多少。这四项目前应记为 **U**，必须做本地冻结 Gold 实验。

## 问题范围与调查方法

**调查对象。** 本轮优先纳入 2025～2026 年同行评审论文／会议正式页面；对 2026 年尚未同行评审但直接回答新问题的预印本，只有在实验设计、表格、方法足够透明且能与独立研究交叉时才用于方向判断，并降低等级。2024 年材料只在它已成为 2025～2026 研究的直接基线时引用，例如自我偏好和早期 selective-evaluation 方法的原始预印本后来正式发表于 ICLR 2025。citeturn13search0turn20search0

**检索范围。** 重点覆盖 ICLR、ICML/PMLR、NeurIPS/OpenReview、arXiv 作者稿与论文附带数据／代码声明；检索主题包括 correlated errors、LLM-as-a-judge bias、self preference、preference leakage、position/verbosity bias、selective evaluation、calibration、abstention、prover-verifier、repair、multi-agent debate、self-consistency，以及中国公开网页里的“吃书、OOC、人设、前后矛盾、伏笔回收”等词。技术结论优先使用正式论文和作者一手资料，社区材料只用于证明“某种中文说法确实存在”。

**排除规则。** 没有把模型厂商自测直接当跨模型可靠性证据；没有把排行榜排名、引用量、点赞量当证据等级；没有把“多个模型同意”当 Gold；没有把论文里的模型价格、产品名或能力当作 2026-08-14 当前厂商状态；没有把数学、SQL、通用聊天里的修复成功率直接外推为中文长篇小说效果。

**主动找反例。** 本轮专门保留了四类“坏消息”：跨家族依旧高相关、全体 judge 一起错；自我偏好存在反例；长度和位置偏差方向会随协议变化；debate、abstention、verifier pairing 都可能失效。相关结果不是旁枝，而是本题决定“不自动改账”的核心证据。citeturn6view1turn23view1turn5view4turn26academia24turn8view3

**统计口径。** 本报告复算的是公开表格里的算术关系，不声称重新调用了论文中的商业模型。这样可以核对论文表格是否自洽，却不能验证模型版本漂移，也不能重现今天的 API 行为。对本地网文实验，主统计单位应按**书**或至少按“书—章节簇”处理，不能把同一章几十个事实条目当几十个独立 \(N\)。置信区间建议按书做 cluster bootstrap；模型提示、证据范围、Gold、随机种子、错误注入规则必须预先冻结。

**明显偏差。** 公开 LLM-as-judge 文献仍严重偏向英文 QA、pairwise preference、数学推理和通用聊天；直接研究“中文长篇连载一致性核对 + 作者最终确认”的同行评审数据，本轮没有找到。因此所有“人审分钟”“每真错成本”“作者可接受补丁率”的公开外推均降为 **U**。NeurIPS 2025 的开放式生成研究也提示，即便转向更开放任务，模型之间仍会出现明显同质化，人类意见分歧时模型 judge 的校准反而更差。citeturn12search1turn12search3

## 证据总表

**关键结论表**

| 关键结论 | 主要证据 | 适用范围 | 反例／边界 | 等级与理由 | 易过期 |
|---|---|---|---|---|---|
| 多 judge 的错误不能按独立投票算；多数票可形成错共识 | ICML 2025 相关错误研究；2026 九-judge 实验 citeturn4search2turn6view1 | NLI、leaderboard、resume screening、RewardBench 等 | 相关程度随任务变化；不是说 ensemble 永远无效 | **A/B**：相关错误结论有同行评审 A；九-judge 精确数值来自透明预印本，B | 中 |
| “九模型≈九张独立票”明显错误 | 9 judge、7 家族实验中 \(n_{\rm eff}\approx2.18\)，且 51/1000 项九者全错 citeturn6view1 | 该研究测试集 | 不是所有任务都会低到 2.18 | **B**：一手预印本，可复算，方向与 ICML 2025 独立研究一致 | 高 |
| 跨家族通常比同家族略去相关，但不是可靠性保证 | 同家族 \(\phi\approx0.436\)，跨家族 \(\phi\approx0.389\)，差 0.047；family-dedup 没恢复独立性 citeturn6view3 | 该研究的 judge 面板 | PVD 某些实验最强选择信号来自同家族非对称 verifier；高相关配对也有跨家族 | **B**：多个独立研究方向一致，但“优势多少”强烈任务依赖 | 高 |
| 同源关系仍然应作为风险因子 | ICLR 2026 Preference Leakage：同模型、继承关系、同家族可产生相关偏好 citeturn25search1turn4academia48 | preference judging | 不表示任何同家族组合必然更差 | **A**：ICLR 2026 正式 poster，一手研究 | 高 |
| 生产模型不应给自己的输出签绿票 | CALM 多数模型自评高于他评；Preference Leakage 扩展到 related models citeturn23view1turn25search1 | 生成—评判存在模型关联时 | CALM 有一个模型是负 self-enhancement，故不是绝对规律 | **A**：同行评审 + 明确反例 | 高 |
| “judge 都偏爱长答案”不能成立 | CALM 显示复杂的长度效应；2026 实验中不同 judge 分别偏长、偏短或中性 citeturn23view2turn5view4 | pairwise/judging | 有些具体 judge／任务确实强偏长 | **B**：ICLR 2025 + 独立 2026 实验同向说明异质性 | 高 |
| 位置偏差存在，但大小随协议变化很大 | CALM：三四候选时多数模型 robustness <0.5；另一 2026 pairwise 实验测得很小的位置效应 citeturn23view0turn5view4 | 候选排序 | 两份研究互相构成边界：不能固定一个全局位置校正系数 | **B**：有同行评审证据，但效果大小冲突 | 高 |
| Self-consistency／CoT 不是免费可靠性提升 | 九-judge 研究中 CoT 反使 \(n_{\rm eff}\) 与 panel accuracy 下降；2026 最新预印本也报告多数投票可在特定 GPQA 设置反噬 citeturn6view2turn2academia40 | 推理任务 | 很多其他任务上 self-consistency 仍能提高最终准确率 | **B**：存在多项反例，不能推出“永远有害” | 高 |
| Debate 是否值得取决于协议，而非“有辩论”三个字 | ColMAD 报告竞争式 debate 可出现 debate hacking 并落后单 agent；协作式版本才改善 citeturn26academia24 | error detection | 单篇预印本；其他任务有 MAD 正结果 | **D/B**：具体增益 D；“debate 非必然增益”由多项结果支持，可给 B | 高 |
| Selective prediction 的正确目标是 precision–coverage，而非全覆盖 | ICLR 2025 selective evaluation 给出校准风险门槛与 coverage；PVD 也报告高置信精度/覆盖率对 citeturn15view0turn8view3 | judge／verifier routing | 原始保证面向“与人类多数一致”，不能自动变成“与作者事实一致” | **A**：ICLR 2025 同行评审且公式完整；PVD作补充 | 中 |
| 模型自报 confidence 不能直接用于路由 | *Trust or Escalate* 中预测概率、自报信心明显过度自信；Simulated Annotators 校准更好 citeturn17view0 | preference evaluation | 其他分类任务的模型概率可能校准更好 | **A**：正式 ICLR 实验 | 高 |
| “会弃权”不是天然能力，必须校准 | AbstentionBench 在 20 数据集、20 模型上发现 abstention 仍未解决，reasoning fine-tuning 平均下降约 24% citeturn26search6 | unanswerable/underspecified tasks | 并非专门 judge benchmark | **A**：NeurIPS 2025 Datasets & Benchmarks | 高 |
| 诊断正确与修复安全是不同目标 | GuardedRepair：受控 repair 与全量重做出现完全不同 fixed/broken 前沿；SQLens 也依靠外部数据库信号先定位语义错误再纠正 citeturn6view7turn26search3 | 数学、Text-to-SQL | 网文没有可执行 compiler/database Gold，不能照搬成功率 | **B**：跨两个独立任务方向一致；网文外推有限 | 中 |
| Frontier judge 不能消灭人类 Gold 成本 | ICLR 2025 理论结果：当 judge 不比被评模型更准时，自动 judge 最多只能有限减少真值标签需求 citeturn12search0 | 论文理论假设成立的评价问题 | 不直接给网文作者标注量 | **A**：ICLR 2025 理论研究 | 低 |
| “作者人审分钟可下降 X%”目前不能下结论 | ACT 等任务显示选择可疑项做人审可大幅降标注成本，但不是中文网文、也不是同一 Gold/任务 citeturn26search9 | 通用标注流程 | 作者判断隐性设定、意图和伏笔可能更慢 | **U**：没有可接受的本地外推依据 | 高 |
| “补丁接受率能靠 judge 预测到 X%”目前不能下结论 | 尚无中文长篇作者场景的冻结 Gold 研究 | 本产品 | 数学/SQL repair 只能给方法类比 | **U**：核心本地数据缺失 | 高 |

这张表里最应该带回产品评审会的不是某个 benchmark 分数，而是两个变化：**“跨家族”从质量规则降级成待验证实验因子；“高置信一致”从真值替代降级成风险路由信号。**

**来源分级表**

| 来源 | 类型 | 作者／机构 | 发布 | 本报告用途 | 等级 |
|---|---|---|---|---|---|
| *Correlated Errors in Large Language Models* | 一手、同行评审 | Kim, Garg, Peng, Garg；ICML/PMLR | 2025 | 家族／提供方与错误相关；跨提供方仍共享错误 citeturn4search2 | **A** |
| *Justice or Prejudice? Quantifying Biases in LLM-as-a-Judge* | 一手、同行评审 | Ye et al.；Notre Dame/MBZUAI/UW/PKU/IBM/HKU | ICLR 2025 | 位置、长度、自我增强、bandwagon 等；附完整复现材料声明 citeturn20search0turn23view3 | **A** |
| *Trust or Escalate* | 一手、同行评审 | Jung, Brahman, Choi；UW/AI2 | ICLR 2025 | selective evaluation、校准、coverage、cascade citeturn14view0turn15view0 | **A** |
| *Limits to scalable evaluation at the frontier* | 一手、同行评审 | Dorner, Nastl, Hardt | ICLR 2025 | 自动 judge 对人工 Gold 节省的理论上限 citeturn12search0 | **A** |
| *Artificial Hivemind* | 一手、同行评审 | NeurIPS 2025 D&B | 2025 | 开放式回答的跨模型同质化和人类分歧 citeturn12search1turn12search3 | **A** |
| *Preference Leakage* | 一手、同行评审 | Li et al. | ICLR 2026 | 同模型／继承／同家族 judge 偏好泄漏 citeturn25search1 | **A** |
| *AbstentionBench* | 一手、同行评审 | Kirichenko et al. | NeurIPS 2025 D&B | 弃权能力不可靠 citeturn26search6 | **A** |
| *SQLens* | 一手、同行评审 | Gong et al. | NeurIPS 2025 | 外部证据辅助错误检测与定向 correction citeturn26search3 | **A** |
| *Neither Valid nor Reliable?* | 一手、同行评审 Position Paper | Chehbouni et al. | NeurIPS 2025 | 对 LLJ 的 validity/reliability 假设做系统反思 citeturn13search1 | **A（论证证据）** |
| *Nine Judges, Two Effective Votes* | 一手预印本 | Kohli | 2026 | 九 judge 的相关错误、错共识、family diversity 反例 citeturn5view0turn6view3 | **B** |
| *Trust but Verify: PVD* | 一手预印本 | Sedoc, Zhang, Foster | 2026 | prover-verifier、选择性路由、调用成本、失败 pairing citeturn7view0turn8view3 | **B** |
| *Guarded Repair* | 一手预印本 | Xia | 2026 | fixed/broken、修复的非对称风险 citeturn5view7turn6view7 | **B/D** |
| *Judging the Judges: bias mitigation* | 一手预印本 | Soumik | 2026-06-24 v2 | 最新 position/verbosity/style 异质性 citeturn5view4 | **D；与A证据交叉后方向可升B** |
| *Towards Scalable Oversight with Collaborative Multi-Agent Debate* | 一手预印本 | Chen, Niu, Cheng, Han, Sugiyama | 2025-10-23 | debate hacking 与协作式 debate citeturn26academia24 | **D** |
| 中国网文术语公开网页 | 社区／宣传样本 | 马良写作、写作产品/教程页面、B站/新浪样本 | 2019–2026 | 只判断词语使用存在，不判断产品能力或行业比例 citeturn10search4turn10search7turn9search10turn10search1 | **C/D** |

**访问日期均为 2026-08-14。**

**中国网文常用说法表**

这一部分的证据明显弱于学术部分。本轮没有找到有代表性的“中国网文作者术语语料库”，所以不能声称下面词汇的行业渗透率，只能说公开样本里确实有人这样用。

| 公开说法 | 同义／近义说法 | 本次看到谁在用 | 使用场景 | 和学术／工程概念的差别 | 证据 |
|---|---|---|---|---|---|
| **吃书** | 前后设定对不上、自己打自己脸 | 网文写作工具宣传、网络文娱社区样本 citeturn10search4turn9search10 | 已经写过的事实后来被新情节推翻 | 比“consistency error”更口语，往往还带有“作者改设定／忘设定”的意味；不能自动等于真正错误，刻意改设定也可能被读者称“吃书” | **C/D** |
| **OOC** | 人设崩、人物崩了 | 泛创作／网文工具与评论样本 citeturn10search7turn10search1 | 人物行为、台词、价值选择与此前形象不合 | 学术上更接近 character consistency，但“人物突然反常”也可能是剧情有意设计，因此需要证据与作者意图 | **C/D** |
| **前后矛盾** | 逻辑 bug、设定 bug | 写作工具／教程类公开内容 citeturn10search4turn10search7 | 时间、身份、地点、能力、物品、因果等冲突 | 范围比形式逻辑 contradiction 更宽，经常把事实不一致、因果不顺、读感不合理混在一起 | **D** |
| **伏笔回收** | 填坑、收伏笔 | 创作工具／教程样本 citeturn10search7 | 检查早期铺垫后面有没有回应 | “未回收”不等于当前章节错误：伏笔可能尚未到 payoff 时间，所以适合规划/提醒，不适合真值判错 | **D** |
| **圆回来／圆设定** | 补解释、找补 | 有零散公开使用，但本轮没有形成可靠代表性样本 | 已出现疑似矛盾后用新解释消解 | 可能是合法剧情揭示，也可能是 retroactive patch；没有作者判断不能定性 | **U** |
| **误杀／漏放** | 误报／漏报 | **不适用：不是网文作者专有常用说法** | 更适合作为内部评测语言 | 分别对应 false positive 和 false negative；作者界面可另做自然语言 | 工程概念 |
| **弃权／覆盖率／校准** | 暂不下结论／自动能处理多少／置信门槛 | **不适用：不是网文圈常用说法** | 内部 judge routing | selective prediction / coverage / calibration，应保留为内部评测词，不必搬给作者 | 学术概念 |
| **LLM-as-judge / verifier** | AI 核对、二次核对 | **不适用为网文行业固定术语** | 内部评测架构 | judge 是统计角色，不等于“真值裁判” | 学术／工程概念 |

这里有一个产品语言上的重要提醒：**“吃书”“OOC”“逻辑 bug”是用户感受词，不应该直接拿来当机器 Gold 标签。** 同一句人物反常，可能是错误、故意伪装、 unreliable narrator、后续反转或作者私下已经决定但尚未发表的计划；产品内部仍应回到“哪条证据支持／反对这个诊断”。

## 分歧、负结果与可复现性

**分歧与负结果**

**跨家族的分歧最明显。** ICML 2025 与 Preference Leakage 都支持“同源关系会增加相关风险”，所以做跨家族 audit 是合理的初始实验臂。citeturn4search2turn25search1 但 2026 九-judge 研究又证明，family diversity 本身不足以恢复独立性：跨家族平均相关仍高，甚至最相关的若干配对是跨家族。citeturn6view3 因此不能把“跨家族”直接写成生产规则，更合理的是在本地 Gold 上测**残余错误相关性**，按互补性选 judge。

**位置偏差的论文会“打架”。** CALM 在候选增多时测到很强的位置效应，而 2026 的一项 pairwise 系统实验对当时被测 judge 测到的位置偏差不大。citeturn23view0turn5view4 这说明产品不能引用一篇论文后永久写死“交换 A/B 两次就够了”。pairwise swap 仍是便宜的 sanity check，但要测本地 residual bias。

**长度偏差不是单向。** CALM 和 2026 最新实验都出现“有的 judge 偏长、有的 judge 不偏长甚至偏短”。citeturn23view2turn5view4 对网文尤其如此：更多文字既可能提供关键证据，也可能只是冗余。用“答案长度”直接当校准特征，有很大概率学到假捷径。

**多数投票没有 Condorcet 免费午餐。** 九-judge 实验中，MNLI 多数票只比最佳单 judge 高 **0.2pp**；SNLI 则比最佳单 judge低 **6.5pp**，AlphaNLI 低 **2.5pp**。Dawid–Skene 等较复杂聚合也没有稳定反超最佳单 judge。citeturn6view2turn6view3 所以产品实验不能只比较“单模型 vs 三模型 majority”，还要比较“单个最互补 verifier”“选择性 cascade”“相关性加权 panel”。

**Self-consistency 也会放大共享错误。** 当一个模型的采样分布在错误答案附近形成稳定 mode 时，多采几次并多数投票只会让错误更有信心。2026-08-11 的最新预印本直接报告了特定 GPQA/小模型设置里的 self-consistency backfire；由于范围窄，只应当做 D 级反例，不应反过来宣称 self-consistency 普遍有害。citeturn2academia40

**Debate 会增加一种新的风险：说服力污染。** ColMAD 的出发点正是竞争式 debate 中 agent 会“赢辩论而不是求真”，研究者称之为 debate hacking；协作式相互补漏优于竞争式协议。citeturn26academia24 这对网文很敏感，因为“一个修法讲得非常圆”尤其容易影响作者对“原来到底有没有错”的判断。因此检测阶段的人审最好**先看证据和错误诊断，修法晚一步再展示**。

**Verifier chain 的强弱组合也会失效。** PVD 在 GPQA 上能形成明显高精度子集，但在 HLE 的较弱 prover/verifier 组合中，高置信子集反而比被挑战子集更差；其 Engineering 小子集甚至出现反向信号。citeturn8view3 这意味着“再找一个 verifier 验一次”不是天然保险：verifier 必须有本地 calibration curve。

**人工节省没有可直接搬的百分比。** ACT 在通用标注任务里把人工集中到“最可疑样本”，报告最多可节约约 90% 人工成本，同时多数任务的模型差距控制在 2% 内。citeturn26search9 但网文作者不只是贴标签，还可能要回忆私下意图、审阅长篇上下文、决定是否接受改设定，所以这个 90% **不能**进入本产品商业测算。

**可复现性记录**

| 复核项 | 原研究材料 | 本报告复核 | 版本／数据／成本信息 | 无法复现点 |
|---|---|---|---|---|
| **偏差研究：CALM 自我增强** | ICLR 2025 正式论文；论文声明 supplemental 含完整代码、数据、评测脚本、prompt、API handler 和结果日志 citeturn23view3 | 按 Table 5 的 `self/other - 1` 重算六个结果：−16.64%、9.40%、8.18%、3.64%、5.39%、8.99%，与表格基本一致 citeturn23view1 | 六个 judge；温度 0.7；另用四个模型生成回答；150 个 self-enhancement alignment 样本等设置在论文中给出 citeturn23view1 | 未重新请求历史商业 API，因此不能验证 2026-08-14 同名产品版本行为 |
| **相关错误：九 judge 有效票数** | 2026 预印本，9 judges/7 families | 按 \(n_\text{eff}=k/[1+(k-1)\phi]\)，\(k=9,\phi=.391\)，得到 **2.1802**，匹配论文约 2.18；5→9 judge 只增加 **0.22** 有效票 citeturn6view1 | ChaosNLI MNLI/SNLI/AlphaNLI；另做 RewardBench 与 prompt/temperature/CoT robustness citeturn6view2 | 预印本；未重新运行所有 judge |
| **跨家族差值** | 同上 | 同家族 OpenAI/Meta 平均 \((.437+.435)/2=.436\)，减跨家族 .389 = **.047**；匹配论文结论 citeturn6view3 | family-dedup 7 judge 的 \(n_\text{eff}=1.93\) | 只有论文选定的家族与任务，不能外推出任意新模型 |
| **选择性路由：Trust or Escalate** | ICLR 2025 正式论文、算法与完整公式 citeturn15view0 | target 80% 时：79.1% coverage × 40.1/48.0/11.9% = **31.719/37.968/9.413%** 全样本占比，合计 79.1%，匹配论文图表 citeturn16view1 | ChatArena calibration set 500；K=N=5；1000 random splits；85% target 时 coverage 63.2%、guarantee success 91% citeturn16view1 | 本轮未定位到作者官方独立代码库；因此能复核公式和表格，不能声称完整端到端复现 |
| **信心校准** | 同上 | AlpacaEval 上某 judge 的 predictive ECE .217→Simulated Annotators .095，本报告复算下降约 **56.2%** citeturn17view0 | Simulated Annotators 论文报告相对 confidence-estimation API cost 6.91；CoT/semantic entropy 等约 20.376，predictive probability=1 citeturn16view2 | 这是论文当时 API 和 token 条件的相对成本，不代表今天价格 |
| **修复风险：GuardedRepair** | 2026 预印本 | GSM8K \(N=1319\)：17 fixed/0 broken → **+1.289pp**；direct solve-all 13 fixed/47 broken → **−2.578pp**，与论文 final accuracy 变化相符 citeturn6view7 | GuardedRepair 约 1,498 次调用；direct solve-all 1,319 次；另有 trigger-only 和 ablation | 数学有客观答案，小说修法无同等 executable Gold；只能复核风险结构 |
| **PVD selective verifier** | 2026 预印本 | 论文一组 overall 76.8%、ANC coverage 77%、ANC precision 84.2%；反推 non-ANC accuracy \((.768-.77×.842)/.23\approx52.0%\)，与其“高低置信明显分离”一致 citeturn7view0turn8view3 | PVD ~3–6 calls；self-consistency k=8 为8 calls；三 agent×两轮 debate 约9 calls citeturn8view2 | 依赖托管模型；论文自己指出 provider 版本变化和无 open-weight replication 等限制 citeturn7view0 |

这里必须把“可复现”分两层理解：**算术复核通过**不等于**今天重新跑模型也会得到同样数字**。对商业托管模型，后者通常做不到版本完全冻结；这也是本产品本地实验必须保存原始请求、响应、模型标识、时间戳和 prompt hash 的原因。

## 对产品的候选启示

这部分只给“可进入设计／实验池的候选方向”，不把字段或流程写死。

### 把两个概率彻底分开

本题最重要的产品映射可以写成两个互不替代的问题：

\[
p_{\text{err}}
=
P(\text{这里确实有错}\mid
\text{冻结证据、原文、审计结果})
\]

和

\[
p_{\text{patch}}
=
P(\text{这个修法可接受}\mid
\text{这里已确认有错、作者约束、候选修法})
\]

**不要训练或展示一个总“质量分”把两者混掉。**

`p_err` 的 Gold 来自已经冻结的事实／证据判断：支持、冲突、不足以判断。`p_patch` 的 Gold 则来自**已确认存在错误**的样本里，作者对具体候选修法的“接受／拒绝／需补信息”判断。GuardedRepair 的 fixed-versus-broken 结果说明，第二个问题的损失函数应该把“把正确状态改坏”看得很重。citeturn6view7

更关键的是，本地实验的人审界面应当**先让作者判断有没有错，再揭示修法**。否则一个措辞漂亮、解释圆满的 patch 会反过来影响作者对“原来是否真的有错”的判断，这相当于把 repair 的说服力泄漏进 detection Gold。debate hacking 与 refinement-aware bias 都说明这种污染不是纯理论风险。citeturn26academia24turn23view1

### 把“跨家族”改成待测的互补性指标

建议实验里保留“同家族 vs 跨家族”这条轴，但生产选择标准不要叫“跨家族更可信”，而应测试：

\[
\text{Complementarity}_{ij}
=
\text{二者在 Gold 上的残余错误去相关程度}
\]

真正需要看的不是它们输出文本有多不一样，而是：

> judge A 错的时候，judge B **能不能特别经常对**？

若 A、B 都有 90% 准确率，但剩下 10% 几乎错在同一批样本上，第二个模型几乎没有补漏价值。ICML 2025 和九-judge 研究正是在提醒这件事。citeturn4search2turn6view1

因此可把候选审计器的选型分数拆成三项：单独 error recall、在主审计器错误条件下的 conditional recall，以及 error correlation。**家族身份只做协变量，不做加分。**

### 用选择性路由控制“打扰作者”的量

对于网文作者，precision–coverage 的解释可以非常直白：

- **precision**：我打扰作者十次，其中几次真有问题。
- **coverage**：系统愿意自己做出“支持／不支持”的明确诊断占多少；剩下多少承认不确定。

*Trust or Escalate* 证明这种“宁可少判，也把被自动判的子集做准”有严格统计版本；但你们要把目标从“human agreement”换成**本地 frozen Gold agreement**。citeturn15view0

候选路由可以按二维风险而不是 vote count：

| `p_err` | `p_patch` | 候选处理方式 |
|---|---|---|
| 高 | 高 | 明确呈现“为什么判错”的证据；作者确认错误后再展示修法；**仍不得自动改账** |
| 高 | 低／未知 | 只报问题与证据，修法不抢答；让作者自行改或另起修复步骤 |
| 中间／校准不足 | 任意 | 进入“需要作者判断／证据不足”；不要拿多数票硬补成确定结论 |
| 低 | 任意 | 默认不打扰，但保留随机抽检样本用来监测漏放和 calibration drift |

对已发表事实、人物身份、核心世界规则、作者私下决定等高后果对象，即使 `p_patch` 很高，也没有公开证据支持跳过作者确认。

### 端到端别再只报一个 judge accuracy

建议至少同时报两张混淆矩阵。

**诊断层**衡量“有没有真错”：

\[
Precision_{\rm err}=\frac{TP}{TP+FP},
\qquad
Recall_{\rm err}=\frac{TP}{TP+FN}
\]

其中 FP 就是“误杀”，FN 是“漏放”。再单独记录：

\[
Coverage = \frac{\text{非弃权项}}{N},
\qquad
Abstention = 1-Coverage
\]

以及**共错率**。共错不能只看 raw agreement，可以报告 pairwise error correlation、至少 \(m\) 个 auditor 对同一 Gold 做出同一错误判断的比例，以及 “all-wrong” 项数。九-judge 研究表明，后者往往比理论独立假设危险得多。citeturn6view1

**修复层**只在独立确认的真错上评：

\[
PatchAccept
=
\frac{\text{作者接受候选修法}}{\text{展示的候选修法}}
\]

同时一定要报：

\[
Broken
=
\#(\text{修法引入新矛盾或破坏原正确状态})
\]

和

\[
NetRepair = Fixed-Broken
\]

因为“修了多少”在不报“改坏多少”的情况下几乎没有意义。GuardedRepair 的 17 fixed/0 broken 与另一方法 13 fixed/47 broken 就是最直观的例子。citeturn6view7

**人工成本层**建议不要写“节约 xx% 人工”，而直接记录真实时间：

\[
T_{\rm human}
=
T_{\rm diagnosis}
+
T_{\rm patch\ review}
+
T_{\rm escalation}
\]

并分别报：

**每 100 个检查项的人审分钟、每本书的人审分钟、每个确认真错的人审分钟、每个安全接受修法的人审分钟。**

经济口径则可以写：

\[
CostPerTrueError
=
\frac{C_{\rm model}+C_{\rm tool}+r_{\rm human}T_{\rm human}}
{\#\text{confirmed true errors found}}
\]

再多报一个更严的：

\[
CostPerNetSafeFix
=
\frac{\text{总成本}}
{Fixed-Broken}
\]

这两个指标会直接把“多加两个 judge 只提高一点 recall，却多让作者看几十个假警报”的隐藏成本暴露出来。

### 本地实验应这样把诊断与修复拆开

同一批书先冻结 Gold、证据范围和错误族，然后只测试诊断。建议至少覆盖：明确事实冲突、人物／物品状态冲突、时间线冲突、角色知情越界、世界规则冲突、伏笔／承诺状态问题，以及一批特别重要的 hard negatives——例如故意撒谎、 unreliable narrator、伏笔尚未回收、作者刻意改设定但已明确记录、人物有意反常。

诊断臂至少比较：单独独立 auditor、同家族 panel、跨家族 panel、按本地 error-correlation 挑出的互补 panel、selective cascade。debate 和高调用 self-consistency 可以只放在子样本，因为公开证据还不足以证明其成本净收益。citeturn26academia24turn8view2

然后，**只针对独立 Gold 确认的真错进入 repair 实验**。作者第一次人审只看原文和证据，不看任何 patch；确认“确实有错”后，再随机展示不同修法候选并独立记录接受与否、是否需要改写、是否引入新冲突、耗时。这样才能得到干净的 `p_err` 和 `p_patch` 两套 calibration data。

统计上主置信区间按“书”重采样；章节可以做次级 cluster。不要把一章抽出的 30 个事实三元组当 30 个独立作者样本。由于目前不知道书间方差和每类真错基率，本报告**不建议凭空拍一个“至少 N=xxx 条即可”**；更稳妥的是先做方差估计 pilot，再预注册正式实验需要检测的最小 recall/precision 差。

## 与旧报告的关系和更新触发器

**与 SI-007 P14 的关系：补强 + 更新，不反驳。**

题面给出的旧结论是“LLM 交叉审计可作高召回检测器，不适合独立补丁”。2025～2026 新证据总体**补强**这一点：GuardedRepair 明确展示了修错与改坏的非对称损失；SQLens 也显示，错误定位与修复在有外部可验证信号时才更稳。citeturn6view7turn26search3

但需要**更新**旧结论里的“交叉”含义：不再默认“跨家族 = 高质量独立 verifier”。现在更准确的候选规则是：

> **跨家族只是降低共错的一个先验；是否值得保留，要看本地 Gold 上的 conditional recall、error correlation 和单位人审成本。**

Kohli 的九-judge 结果是这次最直接的新证据。citeturn6view3

**与 SI-002 独立 verifier／预注册的关系：明显补强。**

新的 selective-evaluation 文献进一步说明，独立 verifier 不能只输出“赞成／反对”，还应该有**经过 frozen calibration set 校准的弃权门槛**；同时实验要预注册 coverage、precision 和风险阈值，不能跑完以后挑一个好看的 confidence cut。citeturn15view0

而且，SI-002 的“独立 verifier”还可以再精确一层：独立不仅指“不是生产模型自己”，还要测试它与生产模型的**残余错误相关性**。Preference Leakage 和 correlated-error 研究说明，模型之间存在架构、训练谱系、提供方甚至更广泛的数据与能力同质性。citeturn4search2turn25search1

**本轮没有理由删除历史原件。** 更适合把新研究记作旧调查之后的更新层：旧报告保留当时证据与决策背景，本报告补上 2025～2026 年相关错误、selective calibration 和 repair harm 的新边界。

**更新触发器**

出现下面任一情况，就应该重跑这项调查或至少重跑本地 calibration，而不是沿用旧阈值：

| 触发事件 | 为什么必须重查 |
|---|---|
| 生产模型、judge 或 verifier 换模型家族／大版本 | error correlation 和 bias 可能整体改变；历史跨家族结论不可继承 |
| 同一 API 模型发生无法冻结的服务端版本变化 | 旧 calibration curve 可能失效 |
| 出现新的 judge / verifier benchmark，特别是长上下文、中文或 narrative consistency | 现有英文 QA 外推缺口可能被填上 |
| 有新的跨家族**逐样本错误相关性**实测，而不只是 overall accuracy | 可以直接更新 auditor complementarity 选择 |
| 本地作者的 patch 接受率明显低于假设 | 表明诊断对了但修法不可用，应降低 repair 展示或改 repair 任务 |
| 作者平均人审分钟显著高于 pilot | “召回提升”可能被人工成本吃掉，要重新算净收益 |
| 共错率／unanimous-wrong 突然上升 | 说明 panel 出现 shared blind spot，不能继续用票数当 confidence |
| 弃权样本的真错率不再显著高于非弃权样本 | calibration / routing 已漂移 |
| 新实验发现同家族组合比跨家族组合具有更低 conditional error correlation | 应按实测选型，不受“必须跨家族”的旧叙事约束 |
| 出现可信的中文长篇创作 benchmark 或作者标注集 | 本题最关键的 U 级证据有机会升级 |

其中题面指定的三个触发器——**新 judge 模型／评测框架、跨家族错误相关性实测、人工接受率与旧假设冲突**——都应视为强制重查项。

## 完整来源清单

下表中的论文链接均指向正式会议页面、作者预印本或公开项目页面；访问日期均为 **2026-08-14**。模型名仅用于标识研究实验条件。

| 来源 | 发布状态与日期 | 与本题的关系 |
|---|---|---|
| Kim, Garg, Peng, Garg, **Correlated Errors in Large Language Models** | ICML 2025, PMLR 267 | 350+ LLM、跨 leaderboard/招聘场景；直接证明模型错误相关，家族／提供方只是部分来源 citeturn4search2 |
| Ye et al., **Justice or Prejudice? Quantifying Biases in LLM-as-a-Judge** | ICLR 2025 | CALM；12 种 judge bias；本报告偏差复核的主要 A 级来源 citeturn20search0turn22view0 |
| Ye et al., CALM reproducibility statement | ICLR 2025 supplemental | 明确声明提供完整代码、数据、evaluation scripts、prompts/API handlers/result logs citeturn23view3 |
| Jung, Brahman, Choi, **Trust or Escalate: LLM Judges with Provable Guarantees for Human Agreement** | ICLR 2025 Oral | selective evaluation、fixed-sequence calibration、cascade、coverage/risk tradeoff citeturn13search0turn15view0 |
| *Trust or Escalate*, calibration/result tables | ICLR 2025 | ECE、ChatArena coverage、judge composition、相对 API cost；本报告做了算术复核 citeturn17view0turn16view1turn16view2 |
| Dorner, Nastl, Hardt, **Limits to scalable evaluation at the frontier: LLM as judge won’t beat twice the data** | ICLR 2025 | 自动 judge 无法无限替代 Ground Truth 的理论边界 citeturn12search0 |
| Li et al., **Preference Leakage: A Contamination Problem in LLM-as-a-judge** | ICLR 2026 Poster | 同模型、继承关系、同家族的 preference leakage；更新 self-preference 研究 citeturn25search1turn4academia48 |
| Preference Leakage 作者项目页 | 2025–2026 | 论文项目、代码／数据说明；用作正式论文的复现补充，不单独抬高证据级别 citeturn4search0 |
| Kohli, **Nine Judges, Two Effective Votes: Correlated Errors Undermine LLM Evaluation Panels** | 2026 预印本 | 9 judges / 7 families；\(n_\text{eff}\)、unanimous wrong、family-dedup、聚合负结果 citeturn5view0turn6view1turn6view3 |
| Kohli, robustness experiments | 2026 预印本 | prompt、label order、temperature、CoT、RewardBench 等 robustness；CoT 并未解除共错 citeturn6view2 |
| **Artificial Hivemind: The Open-Ended Homogeneity of Language Models (and Beyond)** | NeurIPS 2025 Datasets & Benchmarks | Infinity-Chat、开放式回答同质化、人类 preference disagreement 下校准问题 citeturn12search1turn12search3 |
| Chehbouni et al., **Neither Valid nor Reliable? Investigating the Use of LLMs as Judges** | NeurIPS 2025 Position Paper | 从 measurement validity/reliability 角度反对把 LLJ 准确率直接当有效测量 citeturn13search1 |
| Kirichenko et al., **AbstentionBench: Reasoning LLMs Fail on Unanswerable Questions** | NeurIPS 2025 Datasets & Benchmarks | 20 数据集、20 模型；提醒“会说不确定”仍是未解决能力 citeturn26search6 |
| Polo et al., **Bridging Human and LLM Judgments: Understanding and Narrowing the Gap** | NeurIPS 2025 Datasets & Benchmarks | 研究 human–LLM judgment gap 与统计校准；支持“人类分歧结构不能被单一 judge 分数抹平” citeturn13search8turn0search21 |
| Sedoc, Zhang, Foster, **Trust but Verify: Prover-Verifier Deliberation for Selective LLM Prediction** | 2026 预印本 | ANC 高置信子集、precision–coverage、pairing failure、调用次数 citeturn7view0turn8view2turn8view3 |
| Xia, **Guarded Repair for Harm-Aware Post-hoc Replacement of LLM Mathematical Reasoning** | 2026 预印本 | “修错收益 vs 改坏正确答案”非对称风险；fixed/broken 口径 citeturn5view7turn6view7 |
| Gong et al., **SQLens: An End-to-End Framework for Error Detection and Correction in Text-to-SQL** | NeurIPS 2025 | 外部 database signal + LLM error signal，检测 F1 相对 self-evaluation baseline 提升 25.78% citeturn26search3 |
| Chen et al., **Towards Scalable Oversight with Collaborative Multi-Agent Debate in Error Detection** | 2025-10-23 预印本 | competitive MAD 的 debate hacking；ColMAD 相对竞争式 debate 的改善 citeturn26academia24 |
| Soumik, **Judging the Judges: A Systematic Evaluation of Bias Mitigation Strategies in LLM-as-a-Judge Pipelines** | 2026-06-24 v2 预印本 | 最新 position/verbosity/style bias 异质性及 human 小样本对照 citeturn5view4 |
| **When Self-Consistency Backfires…** | 2026-08-11 预印本 | 执行日前三天出现的 self-consistency 负结果；因模型／任务窄，仅作 D 级最新反例 citeturn2academia40 |
| Lin et al., **ACT as Human: … Data Annotation with Critical Thinking** | NeurIPS 2025 | “模型筛可疑项、人审只处理部分”的成本收益证据；不能把其 90% 数字直接外推网文 citeturn26search9 |
| 马良写作公开页面 | 2026 公开网页，营销／实践材料 | “吃书”“前后矛盾”等中文写作语境存在性；不用于证明产品实际能力 citeturn10search4 |
| “超级小说家”等公开写作工具／教程样本 | 公开网页 | “OOC、伏笔回收、逻辑 bug”等说法取样；代表性未知 citeturn10search7 |
| 新浪公开内容关于 OOC | 2025 公开网页 | OOC = Out of Character／角色崩坏的中文使用样本；仅 C/D 级语言材料 citeturn10search1 |
| Bilibili 公开内容中的“吃书” | 2019 社区样本 | 证明“吃书”在网络文娱语境中存在较早使用；不能推出网文作者群体比例 citeturn9search10 |

**总判断：**截至 2026-08-14，能支持的不是“再加两个不同厂商模型就更可靠”，而是更保守也更可测的一套假设：**独立 verifier 有价值，但独立性必须用逐样本错误相关性证明；多数一致只能当证据，不能当 Gold；选择性校准可以减少不必要的人审，但必须用本地冻结 Gold 重做；发现错误与提出修法应分别标注、分别校准、分别计时；任何修法进入真值账之前仍由作者确认。** 跨家族审计在你们场景里的实际 recall 增益、人审分钟净节省和补丁接受率，目前都还是 **U**，不应被公开 benchmark 数字替代。citeturn4search2turn6view3turn15view0turn6view7

来源：ChatGPT