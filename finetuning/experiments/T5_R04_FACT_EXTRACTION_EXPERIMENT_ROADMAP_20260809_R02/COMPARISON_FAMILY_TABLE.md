# 对照家族总表

同一 FAMILY 内才直接比较，跨 FAMILY 不直接宣布胜负。旧名字只用于追溯。

| 家族 | 中文名 | 只改什么 | 组内 arms | 状态 | 是否需要独立 LoRA | 材料 | 何时跑 |
|---|---|---|---|---|---|---|---|
| READ | 正文可见范围 | 只改变前部只读正文范围 | `READ-1-TARGET`、`READ-2-HALO`、`READ-3-CURRENT-WINDOW`、`READ-4-FULL-CHAPTER` | 正在准备 | 是；READ-1/2/4 从同一 base 独立训练，产出三个不同 adapter | 训练：仅原创 TRAIN36；考试：仅 LOCAL_REAL_SCREEN24（旧目录名 CONFIRM24），绝不进训练/选样/调参/改 gold | TRAIN36 与筛选题 gold 冻结后 |
| OUT | 答案与证据写法 | 只改变 assistant 的 evidence 表示 | `OUT-1-FULLQUOTE`、`OUT-2-IDLIST`、`OUT-3-IDRANGE`、`OUT-4-IDQUOTE` | 等待 READ-WINNER | 是；OUT-3/4 从同一 base 独立训练，OUT-2 严格同一时复用 READ-WINNER adapter | 训练：仅原创 TRAIN36；考试：仅 LOCAL_REAL_SCREEN24（旧目录名 CONFIRM24），绝不进训练/选样/调参/改 gold | READ 家族选出赢家后 |
| RULE | 规则多少与原子规则 | 只改变规则条数或一条原子规则 | `RULE-0-MINIMAL`、`RULE-1-PLUS-ONE`、`RULE-2-PLUS-TWO`、`RULE-8-LEGACY` | 等待 OUT | 否；先做输入对照 | 短片段开发集 | READ、OUT 固定后 |
| EX | 示例 | 只改变示例的有无与选择方式 | `EX-0-NONE`、`EX-1-CONTRASTIVE-PAIR`、`EX-2-RETRIEVED-0TO2`、`EX-3-T0I0`、`EX-4-T0I1`、`EX-5-T1I0`、`EX-6-T1I1` | 等待 RULE | 条件式；推理臂胜出后才开训练 2×2 | 短片段 + 安全示例库 | RULE 完成后 |
| BG | 确认背景、中性背景与冲突背景 | 只改变目标段外背景卡 | `BG-0-NONE`、`BG-1-CONFIRMED`、`BG-2-NEUTRAL`、`BG-3-CONFLICT`、`BG-4-T0I0`、`BG-5-T0I1`、`BG-6-T1I0`、`BG-7-T1I1` | 等待 EX | 条件式；输入臂胜出后才开训练 2×2 | 短片段 + 有来源的确认背景 | EX 完成后 |
| PURPOSE | 任务目的 | 只改变是否加入任务目的 | `PURPOSE-0-NONE`、`PURPOSE-1-SHORT`、`PURPOSE-2-T0I0`、`PURPOSE-3-T0I1`、`PURPOSE-4-T1I0`、`PURPOSE-5-T1I1` | 暂停 | 条件式；当前不授权 | 短片段 | 有新证据时再议 |
| STATE | 确认前态 | 只改变确认前态 | `STATE-0-NONE`、`STATE-1-CONFIRMED-PREVIOUS` | 暂停 | 否 | 短片段 + 可追溯前态 | 当前不重开 |
| NAME | 输入前身份消歧 | 只改变是否提供确认别名或身份卡 | `NAME-0-NONE`、`NAME-1-CONFIRMED-ALIAS` | 条件式暂停 | 否；先做输入对照 | 远距离指代与明确姓名锚点数据 | 专门数据足够后 |
| MARK | 输入编号有无与密度 | 只改变编号有无与密度 | `MARK-0-NONE`、`MARK-1-FULL`、`MARK-2-REDUCED` | 已有诊断，后续条件式 | 否 | 短片段同源渲染 | READ、OUT 稳定后 |
| CITE | 是否要求输出证据编号 | 只改变是否提交 evidence_ids | `CITE-0-FACTONLY`、`CITE-1-WITH-IDS` | 后续 | 否；先做同 checkpoint 对照 | 带稳定 Txx 的短片段 | MARK 后仍需诊断时 |
| XUNIT | 单单元与跨单元证据 | 只改变完整证据是否跨单元 | `XUNIT-1-SINGLE`、`XUNIT-2-CROSS` | 后续 | 否 | 同源短片段 | CITE 后仍需解释时 |
| PLACE | 提示放置与回顾 | 只改变同一信息的放置位置或回顾方式 | `PLACE-1-SYSTEM`、`PLACE-2-USER-PRE`、`PLACE-3-AFTER-CHECKLIST`、`PLACE-4-FULL-THEN-RECAP` | 后续 | 否 | 短片段或完整章 | 提示内容先证明有用后 |
| LENGTH | 纯长度与 padding | 只改变无语义信息的长度 | `LENGTH-0-BASE`、`LENGTH-1-PADDED` | 后续 | 否 | 短片段 + 冻结中性 padding | 怀疑收益只是长度时 |
| TPOS | 目标事实处于头中尾 | 只改变目标事实在可读上下文的位置 | `TPOS-1-HEAD`、`TPOS-2-MIDDLE`、`TPOS-3-TAIL` | 后续 | 否 | 位置可机械控制的材料 | READ 显示位置信号时 |
| MIX | Semantic Core 训练占比 | 只改变训练混合比例 | `MIX-0-PCT`、`MIX-5-PCT`、`MIX-10-PCT` | 条件式训练 | 是 | 短片段训练教材 | 先 0% 对 5%；5% 赢才开 10% |
| PIPE | 抽取流程顺序 | 只改变阶段数与事实/证据先后 | `PIPE-1-ONE-STAGE`、`PIPE-2-FACTS-GOLD-ORACLE`、`PIPE-3-FACTS-PREDICTED`、`PIPE-4-FACTSFIRST-STAGE1`、`PIPE-5-FACTSFIRST-STAGE2`、`PIPE-6-EVIDENCE-GOLD-ORACLE`、`PIPE-7-EVIDENCE-PREDICTED`、`PIPE-8-EVIDENCEFIRST-STAGEA`、`PIPE-9-EVIDENCEFIRST-STAGEB` | 条件式，门未过 | 条件式；Oracle 门通过后才训练 | 短片段 + 共享分母 scorer | 指标合同与 Oracle 门冻结后 |
| CUT | 责任区粒度 | 只改变机械责任区粒度 | `CUT-10`、`CUT-20`、`CUT-30` | 完整章专项未跑 | 否；先零训练诊断 | 冻结完整章与切分前 gold | 材料与权限合格后 |
| META | 真实位置 metadata | 只改变无位置、真实位置或 nonce 位置 | `META-0-NONE`、`META-1-REAL`、`META-2-NONCE` | 完整章专项未跑 | 否 | 有真实章/块坐标的完整章 | 先冻结同一 WRNW 条件 |
| COREF | 后置指代还原 | 只改变是否在第二阶段解析已有事实中的指代 | `COREF-0-LOCAL-SURFACE`、`COREF-1-FULL-CHAPTER-RESOLVE` | 新登记，未排队 | 否；不是新的匹配 LoRA | 含远距离姓名锚点的完整章 + 局部目标段 | READ 固定且姓名诊断合同另行冻结后 |

## READ 输入形状写死

三臂只读范围严格嵌套：`TARGET ⊂ HALO ⊂ FULL_CHAPTER`。

共同尾部始终是完全相同的 `NUMBERED_TARGET_TXX` 加同一 evidence allowlist。前部只读块分别是：

- `READ-1-TARGET`：`TARGET_TEXT`
- `READ-2-HALO`：`LEFT_CONTEXT + TARGET_TEXT + RIGHT_CONTEXT`
- `READ-4-FULL-CHAPTER`：`FULL_CHAPTER_TEXT`，完整章天然包含 target 和 halo

FULL 后面不再额外追加一份 HALO。三臂里 target 都恰好出现两次：前部只读范围中一次，尾部编号责任段一次。三臂从同一个注册 base／parent 独立起跑；TRAIN36、更新数、训练配方、OUT-2、评分和解码都不变，只改 READ renderer／前部只读范围。训练结束后会得到三个不同 adapter，这三个 adapter 正是实验对象，不能写成评测时使用“同一 checkpoint”。

`READ-3-CURRENT-WINDOW` 只保留旧短窗口结果，不参加当前 1/2/4 新对照。若以后要测“整章后再摘要或重复 halo”，归入 `PLACE-4-FULL-THEN-RECAP`，不能冒充 `READ-4-FULL-CHAPTER`。

## 当前两轮顺序

Round 1 固定 OUT-2，只比 READ-1/2/4；同一个未微调 base 也分别回答三套题面，三个匹配 LoRA 则只答各自题面。Round 2 固定 READ-WINNER，只比 OUT-2/3/4；OUT-3/4 从同一个 base 独立训练，第一轮 OUT-2 共同格只有在合同、SHA、TRAIN36、训练配方、评分和解码逐项相同时才复用。

当前上限是 5 个训练配方／LoRA 组合，不是总模型调用数。base 的三套输入推理次数单独统计。

## 训练与考试分侧

- 训练教材：仅项目原创 TRAIN36。
- 考试题：仅 `LOCAL_REAL_SCREEN24`，旧目录名 `CONFIRM24` 只为追溯保留。
- 这 24 题可连续用于 READ、OUT 的 Demo 筛选与淘汰，但永不进入训练、选样、调参或 gold 修改。
- Round 1 看过结果后，它不再是一次性完全未见确认集；不得称为最终盲考或生产泛化证明。真正的最终结论以后另建未见题，当前不因此扩料或阻断 Demo。

## 已有结果只作开发筛选

- OUT 历史开发 F1：FULLQUOTE 0.7692、IDLIST 0.8936、IDRANGE 0.8043、IDQUOTE 0.8660。
- 旧短范围匹配 LoRA：TARGET_ONLY 0.7955、SMALL_HALO 0.8764、CURRENT_WINDOW 0.7816。CURRENT_WINDOW 只对应 READ-3，不等于完整章 READ-4。
- P3：极简基线 0.894；旧八规则 0.622，淘汰；任务目的 0.891，打平暂停；确认前态 0.825 且有 2 案泄漏，淘汰。
- P4 的 READ×CUT 六格只有 preflight/toy，模型推理为 0。

## 特殊组合

P4 的 READ×CUT 2×3 是唯一已经登记的小矩阵，旧六格可同时归 READ 和 CUT。它不是第 20 个家族，也不能拿来冒充短片段 READ 结果。

来源：Codex
