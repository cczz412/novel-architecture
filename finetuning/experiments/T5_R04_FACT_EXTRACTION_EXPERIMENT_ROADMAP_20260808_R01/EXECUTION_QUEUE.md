# 最小执行顺序

这条队列禁止把不同家族交叉成全因子大组合。每个家族内部可以运行事前登记的小矩阵，例如 WRNW 的 2×3，或推理臂先胜出后才开的条件式 2×2；矩阵的格子、唯一变量和开启条件必须在看结果前写死。DEV24 只负责筛选；每家族只留一个候选进入“组合合同冻结”，不能分别消耗 CONFIRM24。

## 固定起点

- 短片段输入实验主 checkpoint：`C2_FULL update72`，SHA `321d96c10f00389e557efbeb2d8e3dc1344071cc3cd663b51b8a8c2bd38ea5f9`。
- D_RANGE 只保留为工程备选，不重新训练。
- A／C2／D／E 四个 LoRA 全部不重跑。
- P3 C0 只是这一轮的固定实验对照，不写成生产默认。

## 短片段第一轮

按下面顺序逐家族运行；一个家族结束并封票后，才开下一个：

1. 责任范围：`target-only`／小 halo／当前窗口；
2. 规则：C0／增加 1 条原子规则／增加 2 条原子规则；
3. 示例：EX0／一个安全 contrastive minimal pair；按可观察边界检索 0～2 例是独立后续候选，固定 pair 没过门前暂停；
4. 背景：无背景／确认且相关／等 token 中性／冲突背景；
5. 编号诊断：marker density／citation output／cross-unit 分开；
6. placement：同一短合同放 system、user 正文前、正文后 checklist；
7. 纯长度与目标位置：等内容长度控制，以及目标事实位于头／中／尾。

八规则 C1 不重跑；任务目的 C2 当前暂停；确认前态 C4 不晋级；C3 要等新的身份消歧集；C5 只能等真实坐标专项。

## 短片段确认

每个家族只在 DEV24 上保留一个候选。看到 CONFIRM24 结果之前，先按预注册的机械组合规则冻结唯一 `BEST-SHORT-CONTRACT`，然后在新 `CONFIRM24` 上只比较一次：

```text
C0
vs
BEST-SHORT-CONTRACT
```

如果组合以后收益消失或安全指标退化，不得用同一 CONFIRM24 拆件重组再考；回到 DEV 阶段另开新 revision，并为未来复验准备新的未见确认集。

## 新训练线

### Semantic Core

只先跑 0% 对 5%。总训练窗口、更新数和主任务样本数保持一致，5% 用替换而不是追加。5% 稳定赢，才开 10%；没赢就停。

### 本地 MICRO24 facts-first F

本地包里的 F 是：先训练 `fact/status/speaker`，再为已确认事实训练 citation。它是 M2 的独立暂停线，不能和 evidence-first 混称，也不能从 M1 adapter 续训冒充干净父臂。

当前不能直接运行 `FACTS_FIRST_ZERO_TRAINING_GATE_R01`。M1 的 C2 编号正确率是“已语义命中的事实里 42/42 完全正确”，这个条件分母已经满分，原先写的“再提高 5 个百分点”不可执行，现已撤回。

下一步必须先开 `FACTS_FIRST_METRIC_CONTRACT_PREFLIGHT`，只冻结 scorer、分母、错误归因和阈值，不推理。至少分开：

- Gold facts Oracle：只测固定 48 条 gold facts 的 citation-stage 条件能力，不拿它的 fact F1 和 one-stage 直接比；
- one-stage 对 predicted facts：共同使用 DEV24 全部 48 条 gold facts作分母；
- 端到端 TP：同 case 的事实语义正确，而且 `evidence_ids` 精确正确；
- 事实正确但 citation 错：这条预测不算 TP，预测侧记不可用 FP，对应 gold 仍是 FN；
- wrong／missing／duplicate fact、非法 ID、Schema、termination 继续分层报告。

scorer、配对方法和数值阈值封版后，才允许用同一 C2_FULL update72 和同一数据预注册：

```text
one-stage C2 基线
vs
Gold facts → citation Oracle
vs
Predicted facts → citation
```

当前 `pass_thresholds=null`，因此这三格都是 `NEEDS_METRIC_CONTRACT`，不是可运行实验。指标合同未封版或后续任一门没过，两个 `LORA-FS-*` 都继续 blocked，不训练。

### evidence-first 两阶段

训练前先用同一个现有 C2_FULL update72 checkpoint 做零训练输入诊断：

```text
One-stage 完整输入
Gold Evidence Oracle 输入
Predicted Evidence 输入
```

三臂输出仍用同一个 C2 合同；这里没有、也不假装已有 Stage B checkpoint。Gold Oracle 不赢 One-stage，就不训练 evidence-first。Gold Oracle 赢但 Predicted Evidence 留不住主要收益，也不训练。两道门都过了，才允许另立 Stage A evidence 提议器与 Stage B fact 抽取器的训练合同。

### examples／背景／目的 2×2

只有对应的推理输入臂先赢，才允许登记训练 2×2。冲突背景永不训练。P3 任务目的打平、确认前态负面，所以这两条当前都不开训练。

## 完整章支线

新建 `P4-SYNTH-PILOT6`，只运行：

```text
LOCAL_READ / FULL_CHAPTER_READ
×
P4-GRAN-10 / 20 / 30
```

六臂全是零训练配对诊断。只有出现预注册信号，才补 6 章确认。

同一批完整章再做位置 metadata：

```text
M0：无真实位置 metadata
M1：真实章节／块位置 metadata
C-Nonce：等结构、等 token 的无意义标签
```

metadata 三臂开跑前必须冻结一个共同的 WRNW 条件，登记为 `META_WRNW_FIXED_CONDITION_R01`。三臂共同使用同一 read mode、同一 P4-GRAN-10／20／30 中的一个粒度、同一 splitter、同一 checkpoint 和同一输入；只允许 metadata 的值不同。WRNW pilot 没有唯一赢家时，必须在看 metadata 输出之前由 CZ 另拍一个固定条件。

这条支线只能得到“合成完整章上的候选结果”。生产晋级还要独立 holdout，并在豆包 Mini／Lite 上另行授权验证。

## 公共硬停

- 数据、模型、Prompt、renderer、评分器或分母没有封版；
- 某个臂同时改变两个以上未登记变量；
- DEV24 被用来改 gold、选训练样本或反复调到满意；
- S-02 74 组进入训练；
- 本地 Qwen 结果被写成豆包或生产结论；
- 未获新授权就调用模型、API 或启动训练。

来源：Codex
