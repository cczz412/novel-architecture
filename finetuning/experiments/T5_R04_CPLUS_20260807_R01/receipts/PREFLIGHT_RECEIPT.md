# T5 R04 C+｜PREFLIGHT_RECEIPT

- 回执日期：2026-08-07
- 回执状态：`PREFLIGHT_COMPLETE_BLOCKED_BEFORE_STAGE_1`
- 边界：只做材料身份、真源、冲突和后续可执行性核对；没有抽数、训练、考试、模型调用、Notion 写入或 Git 操作。

## MATERIAL_VISIBILITY

- ZIP／仓库是否可见：可见。
- C+ 施工文件 ZIP：`/Users/a1234/Downloads/T5_R04_CPLUS_CODEX_BRIEF_20260807.zip`
- ZIP SHA-256：`6534b2733633870d1769a6f64a41257a25e0b5cf6b60805409decb3acddd9db2`
- ZIP 验收：CRC 通过；根目录严格 2 个 Markdown；无绝对路径、父目录穿越或第二层目录。
- 根因回包 ZIP：`/Users/a1234/Downloads/T5_R04_AC_ROOT_CAUSE_CANDIDATE_20260807.zip`
- 根因回包 SHA-256：`e303db4a2bbe671cb92935cfcecbe066adfa4746ac4a9e037ddb975be694cf90`
- 根因回包身份：`CANDIDATE_PENDING_LOCAL_VERIFICATION`；可作阶段 1 的证据与实验设计来源，不是 CZ 最终判词。

### 顶层目录

- 主仓：`/Users/a1234/挣钱/小说架构`
- 微调控制面：`finetuning/`
- 当前 A/C 重资产实验：`/Users/a1234/挣钱/小说架构_隔离实验/T5_R04_A_C_FORMAT_COMPARE_20260807_R01`
- 当前 C+ 候选预检票：`TEMP/T5_R04_CPLUS_PREFLIGHT_20260807_R01/`

### 已读关键文件

- `governance/CURRENT_STATE.json`
- `finetuning/CURRENT.json`
- `finetuning/experiments/T5_R04_AC_FORMAT_COMPARE_20260807_R01/MANIFEST.json`
- `finetuning/experiments/T5_R04_AC_FORMAT_COMPARE_20260807_R01/SUMMARY.md`
- `finetuning/experiments/T5_R04_AC_FORMAT_COMPARE_20260807_R01/DECISION.md`
- `governance/progress/t5-r04-a-curriculum-quality-mainline.md`
- `governance/progress/t5-r04-cross-window-material-selection-lock.md`
- 当前实验的封版数据票、分割锁、训练执行锁、四阶段训练票、41 题封版票、旧 48 题完整性票和考试运行锁。
- C+ ZIP 内两份 Markdown 全文。

## CURRENT_ACTIVE_TRUTH

### 当前主办页

- 全仓机器当前状态仍由 `governance/CURRENT_STATE.json` 管，但它当前指向另一条 R2 A8 路线，不授权 T5 R04 C+ 施工。
- 微调域当前入口由 `finetuning/CURRENT.json` 指向 `T5_R04_AC_FORMAT_COMPARE_20260807_R01`，只是导航入口，明确不能授权训练或转正。
- 仓库当前没有 `active/requirements/t5_r04_cplus/`，也没有其他已生效的 C+ 正式主办页。
- 因此，两份 C+ Markdown 当前只能登记为候选合同，不能直接升成 runtime 规则。

### 与本文件一致项

- A/C 当前每臂母集 398 行；实际训练 350 行＝正向 278＋特殊 72。
- 旧冻结卷每臂 48 题；当前 R03 卷每臂 41 题、355 条金标；二者身份分开。
- 第一阶段与最终阶段 A/C 权重都保留，可做“只换 checkpoint”的零重训证伪。
- A/C 的人工语义字段应只维护一份，C 类格式应从 A 机械派生。
- 新增选材仍应执行作者／书籍上限、片段去重和正常／特殊比例控制。
- 新书材料当前可做候选分析，不因来源在榜单里就自动获得训练资格。

### 冲突项

1. **正式主办页缺失**：C+ 文件要求挂入现有 active；本仓没有该 active。未拍前不得开阶段 1，更不得开 500 本抽数。
2. **A 路牌数字漂移**：`t5-r04-a-curriculum-quality-mainline.md` 仍写旧的 585 行 A 身份；当前实验真实来源已是 A v2.7 正向 314 行，源 SHA `3c7cfddbb7971a9a5e6739b17ed00b9a546bad21ca7946f38b5de95557b45f67`，再加特殊 84 行组成每臂 398 行母集。旧页不能继续充当当前数据分母。
3. **新旧比例冲突**：现有路牌建议新增材料约 60%～70% 来自较新网文；C+ 候选合同建议 75%～85%。需要一处正式拍板，不能边挑边改。
4. **同章取样冲突**：现有共同锁要求同书取 2～4 段时来自不同章节；C+ 候选允许特殊情况下同章最多 2 个窗口。正式拍板前沿用现有更严格口径，不在同章收两窗。
5. **权利状态未清**：新书榜单当前登记为 `RIGHTS_PENDING_FOR_TRAINING`。它可建候选池、做本地结构分析，但不能进入真实训练 manifest。
6. **胜负阈值缺失**：未找到 C-1／C-2／C-3 探针和后续 A/C-2 对照的 `DECISION_THRESHOLDS.md`。跑结果前必须冻结。
7. **作者级考试隔离还不完整**：当前锁已登记 41／48 题来源书籍，但未来 500 本池所需的统一 `author_id`、笔名归一和作者级排除锁尚未建立。

## LOCKED_ASSETS

### 当前训练集

- 当前实验 MANIFEST：`a1729b5492170da493be51e5e745f7607c1f60b11bd16acef8ce36934569b80d`
- A 全量 398 行：`73b1fcea929894a4b9c92dd3b53bf84b5e93a34e05cc3a61afc41c3cf727aa42`
- C 全量 398 行：`b84d0bc964ecc87fbd55d740aea483522f0e9dfbefaaeb820bf5d31d2f6e0945`
- A 正向训练 278 行：`59e3c96fa12b9c56165ca99e13dad4cb2a73dc580ee83da236b4641e87723eb4`
- A 特殊训练 72 行：`81a84c6128f4e956bfaaf7be11d1bc5ebbc1ab1d1910761a96fe691a22e5dbae`
- C 正向训练 278 行：`9a9144a4ae12eeb9d157395727674e45b562e271eabf3aaff94ca405cfc94967`
- C 特殊训练 72 行：`ef6e7303e862e53cf0e92984bab34a85bab8ca62dd0be708d013588453966cac`
- 分割锁：`3ccad8cd2c4e1dcb33aa4dcfc99e9ac90f6f52918707860f6a095e5ef741d7b9`

### 当前 41 题

- A 题面：`d307b52ca1809b1776cba38a8f2ede85d1ba3226ac770b7ebbab96977b3fc8fa`
- C 题面：`5d0b5c60593183ba31dc8c6f91e2668db055ca3f1f5905086d892b3e98950a34`
- A 金标：`343e5bb2d90a9c37a9820d089ceb8874f9f0515eec287ed580cb00b0d4bf340a`
- C 金标：`8624d06353abbf333baae9c9446a70cbd7438c065321dbf783aee5e6ef9ea543`

### 旧 48 题

- A 题面：`3c42924b1f245c8f967d497f38b6dbe5a883ef352f4287d77a7b336e77dafe6e`
- C 题面：`ac961ccfaa8311433dd741273859ee38841372d9472377349e6a99309646bdbf`
- A 金标：`6d5643eb45e0bdf60172902a9b472da1f71c538741f1faa3bd6d15b789972364`
- C 金标：`7830e65cad7ec5751808899737793838bc53f1980b0599e4366d062687bf6f77`

### stage1 checkpoint

- A stage1：`1e2f5e736f9d913819b835b21533626915a0e569f23242a7a15b8c1655fb3cdf`
- C stage1：`206886963a2de9553a6c7a8824db2bb12cbb0509834d695d6a8a54807fc28f3e`

### final checkpoint

- A final：`e1217ec79657cd12cce2d273154db2da1c118a034dceca7a23975cddb27d9b74`
- C final：`35595e49156cbe8c39ca5f90729f06deea16ca6bd12456cca7edabed43cd7175`

### evaluator

- 当前考试器：`/Users/a1234/挣钱/小说架构_隔离实验/T5_R04_A_C_FORMAT_COMPARE_20260807_R01/tools/ac_exam_r03_runner.py`
- SHA-256：`8a390af537919943ff477ccb98e99deb16ea614af18fa617ab2760c76a029603`
- 边界：根因回包已指出它会混合格式失败、严格字符串匹配和部分错杀；阶段 1 可以保留它复现旧读数，但必须并列增加新的诊断层，不能用修复后的新分数改写旧成绩。

## P0_DECISIONS_NEEDED

- C2_UNIT／C2_EXACT：**未拍**。Codex 推荐 `C2_UNIT`；A 保留字符级证据，C 返回最小覆盖单元，并单列字符覆盖率和额外带入量。
- 近年小说年份口径：**未拍**。仓内只有比例建议，没有稳定年份边界。
- 近年材料占比：**冲突待拍**。现有 60%～70%，候选合同 75%～85%。
- 来源权利状态口径：候选分析可使用 `RIGHTS_PENDING_FOR_TRAINING`；真实训练只收 `TRAINING_CLEARED`。新 500 本池尚未获得训练放行。
- 胜负阈值是否已有主办页：**没有**。探针和正式 A/C-2 对照阈值必须在看结果前新建并冻结。
- C+ 正式承接位置：**未拍**。建议接到微调域下的新 experiment／candidate requirement，不另造全仓第二个治理中心；在拍板前保持 TEMP 候选身份。

## PROPOSED_NEXT_ACTION

- 唯一下一动作：由 CZ 对上面 P0 项作一次正式拍板，并明确将两份 C+ 候选合同挂到哪个现役主办入口。拍板完成后只开阶段 1 的三个单变量证伪；仍不启动全量抽数。

## WORK_STARTED

- NO

## PREFLIGHT_CHECKS

- `python3 tools/finetuning_control.py verify-current`：PASS。
- `python3 tools/finetuning_domain.py check`：PASS。
- 当前 MANIFEST 机械读数：398／350＝278＋72／旧 48／当前 41／355／82 均可从实物复算。
- 四份 runtime 训练输入与 sealed 文件：BYTE_IDENTICAL。
- 本回执未修改任何冻结资产。

来源：Codex
