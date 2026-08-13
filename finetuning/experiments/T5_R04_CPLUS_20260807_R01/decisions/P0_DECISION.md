# T5 R04 C+｜P0 拍板与顺序施工授权

- **决定日期**：2026-08-07
- **决定状态**：`CZ_APPROVED_PENDING_REPOSITORY_REGISTRATION`
- **导入后状态**：`ACTIVE_STAGE_1_AUTHORIZED`
- **施工方式**：`AUTO_ADVANCE_BY_STAGE_GATE`
- **准备者**：ChatGPT
- **决定授权来源**：CZ 在当前对话中明确委托拍板
- **适用范围**：T5 R04 A／C+ 格式路线、C+ 合同冻结、新数据候选池与首轮 A／C-2 对照
- **不代表**：C 已胜出、模型已可用、新 500 本已取得训练权、允许立即全量抽数

## 一、绑定材料

本决定只承接下列已验收材料：

| 材料 | SHA-256 | 身份 |
|---|---|---|
| `PREFLIGHT_RECEIPT.md` | `5a2529258dfe4b6244880c21b007f8accef6831b925e021e88f85e0ac09dddcd` | 阶段 0 预检回执 |
| `T5_R04_CPLUS_CODEX_BRIEF_20260807.zip` | `6534b2733633870d1769a6f64a41257a25e0b5cf6b60805409decb3acddd9db2` | C+ 候选施工合同 |
| `T5_R04_AC_ROOT_CAUSE_CANDIDATE_20260807.zip` | `e303db4a2bbe671cb92935cfcecbe066adfa4746ac4a9e037ddb975be694cf90` | 高可信候选根因报告，不是历史成绩改写票 |

预检已确认：当前实验每臂母集 398 行，实际训练 350 行＝正向 278＋特殊 72；旧 48 与当前 41／355／82 身份分离；A/C stage1 与 final checkpoint 均存在。

---

# 二、P0 正式拍板

## P0-01｜C+ 证据合同：采用 `C2_UNIT`

✅ **拍板：C+ 正式候选采用 `C2_UNIT`，当前不做 `C2_EXACT`。**

### A 人工真源继续保存

```text
fact
status
speaker
exact_evidence_text
exact_evidence_spans
source identifiers
```

### C-2 训练与生产候选只输出

```json
{
  "facts": [
    {
      "fact": "……",
      "status": "计划",
      "evidence_ids": ["B01", "T01", "T02"],
      "speaker": "……"
    }
  ]
}
```

### 固定含义

- `Bxx`：负责区前紧邻的证据桥接单元；
- `Txx`：本段负责区；
- 只读上文、只读下文不编号，不能作为证据；
- `evidence_ids` 必须按正文顺序排列、去重；
- 最后一个 evidence ID 必须是 `Txx`；
- 每个窗口重新从 `B01/T01` 编号；
- 全局唯一定位由 `sample_id + local_id` 完成；
- 模型不输出全局书号、章节号、字符坐标、锚字或省略号；
- 后台回填整个证据单元的逐字原文；
- A 的字符级证据继续用于审计，不声称 C-2 是字符级无损压缩。

### `C2_EXACT` 的处理

`C2_EXACT` 暂不进入当前主线。未来只有在产品明确要求“模型直接返回与 A 完全相同的字符起止”时，才另开二阶段截取或偏移量实验。不得把坐标、双锚或字符偏移偷偷塞回 C-2。

---

## P0-02｜“近年小说”时间口径

✅ **拍板：T5 R04 本轮固定把 2022-01-01 至 2026-08-07 首次公开发表的作品定义为“近年目标作品”。**

判断字段按优先级使用：

1. `first_publication_date`；
2. 无精确日期时使用可核实的 `first_publication_year`；
3. 只有最近更新时间、完结时间或再次上架时间，不能据此算近年；
4. 首发年份不明时标记 `DATE_UNKNOWN`，不计入近年配额。

辅助分层：

| 层级 | 首发时间 | 用途 |
|---|---|---|
| `RECENT_TARGET` | 2022-01-01～2026-08-07 | 主体来源 |
| `MID_AGE` | 2019-01-01～2021-12-31 | 补过渡文风和独特结构 |
| `LEGACY` | 2018-12-31 及以前 | 只保留独特、清楚、不可替代案例 |
| `DATE_UNKNOWN` | 无法核实 | 可进候选池，不满足近年配额 |

该日期边界只服务本轮 T5 R04，不自动随年份滚动。以后要改必须新建决定，不得边选边变。

---

## P0-03｜新旧材料比例

✅ **拍板：采用 80% 近年目标材料作为中心值，正式允许区间为 75%～85%。**

这项决定取代旧路牌中的 60%～70%，只对 C+ 新主线生效，不改写旧实验历史。

### 分母怎么数

```text
recent_ratio
= RECENT_TARGET 的已接收训练窗口数
÷ 全部已接收训练窗口数
```

固定规则：

- 以“规范训练窗口”计数，不以 fact 数计数；
- A 与 C-2 是同一窗口的两个视图，只计一次；
- 正常、特殊、低密度窗口都进入同一来源年代分母；
- 只统计通过质量验收且具备训练资格的窗口；
- 被淘汰、仅候选、重复视图和 sealed test 不进入分母。

批次允许短期波动：

- 单个约 200 窗口批次可暂时落在 70%～90%；
- 每次真实 LoRA 前，累计训练集必须回到 75%～85%；
- 中心目标保持 80%，不能为了碰上限专门剔除高价值旧案例。

同时报告作者数、作品数和窗口数三种分布。若窗口比例与作品比例相差超过 10 个百分点，必须解释是否被少数作品集中贡献拉歪。

---

## P0-04｜新 500 本的训练权

⚠️ **拍板：不做整包口头放行，不把 `RIGHTS_PENDING_FOR_TRAINING` 自动改成 `TRAINING_CLEARED`。**

### 可以继续做

`RIGHTS_PENDING_FOR_TRAINING` 材料可以用于：

- 建候选书目与作者归一表；
- 记录题材、年份、文本形态和潜在槽位；
- 本地切段器结构检查；
- 选择候选窗口；
- 形成不进入训练的候选 A 标注和质量审计；
- 估算覆盖缺口。

### 不可以做

未清权材料不得进入：

- 真实训练 manifest；
- 正式 dev；
- 最终 sealed test；
- 对外宣称可训练的数据集；
- 任何把候选结果混作已训练资产的统计。

### 训练放行最小字段

每个可训练来源必须记录：

```text
rights_status = TRAINING_CLEARED
rights_basis
rights_evidence_id
rights_scope
cleared_at
cleared_by
expiry_or_review_date
```

缺一项就继续留在候选通道。训练 manifest 应由程序拒绝非 `TRAINING_CLEARED` 行，不能靠人工记忆。

### 不让权利问题卡死整条路线

采用双通道：

```text
候选通道：RIGHTS_PENDING 可继续建池、切段、选样、审计
训练通道：只接收逐项 TRAINING_CLEARED 的窗口
```

不必等 500 本全部清权。任一批达到训练所需数量并全部清权后，可进入对应阶段。

---

## P0-05｜C+ 正式承接位置

✅ **拍板：在微调域建立新的正式工作实验，不另建全仓第二治理中心。**

正式路径：

```text
finetuning/experiments/T5_R04_CPLUS_20260807_R01/
```

推荐根结构：

```text
00_ROUTE_MAP.md
MANIFEST.json
RUN_STATE.json
decisions/
  P0_DECISION.md
  DECISION_THRESHOLDS.md
contracts/
receipts/
stage_1_root_cause/
stage_2_cplus_contract/
stage_3_format_probe/
stage_4_candidate_pool/
stage_5_pilot_dataset/
stage_6_ac2_pilot/
```

挂接规则：

- 两份 C+ 候选合同复制到 `contracts/`，保留原 SHA；
- 本文件登记为 `decisions/P0_DECISION.md`；
- 第二份阈值文件登记为 `decisions/DECISION_THRESHOLDS.md`；
- `PREFLIGHT_RECEIPT.md` 进入 `receipts/`；
- 当前 A/C 实验登记为 `upstream_read_only`，不移动、不改写；
- 不修改 `governance/CURRENT_STATE.json`，避免干扰当前全仓另一主线；
- 通过现有微调控制工具把 `finetuning/CURRENT.json` 的导航入口切到新 C+ 实验，并记录前任实验 ID；
- 若控制工具或 schema 不允许这项更新，立即停在 `CONTROL_PLANE_BLOCKER`，不得手改绕过。

旧 `t5-r04-a-curriculum-quality-mainline.md` 的 585 行数字只保留历史身份。Codex 应添加“当前数字已迁移”的非破坏性提示或在新 `00_ROUTE_MAP.md` 明确标记它不再是当前 A/C/C+ 分母真源，不能重写旧实验正文。

---

## P0-06｜同章取样冲突

✅ **拍板：当前新主线执行更严格规则——同一作品的已接收训练窗口必须来自不同章节。**

本轮不开放“同章最多两个窗口”的常规例外。原因是首批目标是增加独立信息量，而不是把同一场景切成多行。

未来只有 dev 明确出现某种稀有结构缺口，且别章无法补齐时，才可单独提交例外票。例外不得在首批 200～300 窗口中使用。

---

## P0-07｜A/C 胜负阈值

✅ **拍板：采用随包第二份 `DECISION_THRESHOLDS`。**

核心原则：

- 严格文本 F1 继续保留，但不是唯一主指标；
- C-2 只有在事实语义基本不劣于 A，同时显著减少输出和生成病理时才可胜出；
- 输出短不能抵消事实错误；
- A 证据是字符级，C-2 证据是单元级，必须映射到共同字符覆盖指标后再比较；
- 当前 41 题只用于阶段 1 根因证伪，不再承担新 A/C-2 胜负判定；
- 旧 48 永远不进入当前成绩分母。

---

# 三、顺序施工授权

Codex 在完成仓库登记后，可以按下列闸门连续推进，不必每一步重新向 CZ 询问。只有触发阻断条件时才停。

## 阶段 1｜三个零训练根因证伪

**现在授权。**

只运行：

1. stage1 checkpoint 对 final checkpoint；
2. A 22 个触顶案 `2048 → 4096`；
3. 旧 C 题面范围标记改写。

不得新增训练，不得使用旧 48，不得同时改其他解码参数。

完成且机械验收通过后，自动进入阶段 2。

## 阶段 2｜冻结 C2_UNIT、切段器、映射和评分合同

**预授权。**

使用 30～50 个现有高质量、权利状态合规的窗口做机械原型。不得开 500 本全量抽数。

通过第二份文件中的硬闸门后，自动进入阶段 3。

## 阶段 3｜C-1／C-2／C-3 小探针

**预授权。**

只做固定小探针，不做三套完整训练。若结果落在灰区，按预设默认规则选择 C-2；不得跑完后临时改阈值。

通过后，冻结唯一 C 候选。

## 阶段 4｜500 本候选池与作者级分割

**预授权建立候选池，不等于授权训练。**

先做作者归一、来源年份、权利状态和 train/dev/test 作者级锁，再选窗口。当前 41、旧 48 及其来源作者全部排除。

## 阶段 5｜首批约 100 本、200～300 窗口

**预授权候选选样、切段、A 标注、复审和 C-2 机械派生。**

真实训练所用窗口必须全部 `TRAINING_CLEARED`。若清权不足，可以继续候选施工，但不能偷偷降低训练权标准。

## 阶段 6｜首轮 A／C-2 成对 LoRA

**条件授权。**

只有同时满足下面条件才可自动开训：

- C2_UNIT 合同与 atomizer 已冻结；
- 训练／dev 作者隔离完成；
- 计划进入 run 的每个窗口均 `TRAINING_CLEARED`；
- A/C-2 可从同一 canonical window 机械成对生成；
- `PROBE_RECIPE`、seed、训练顺序、评分器和解码在看结果前冻结；
- 不再采用“正向训完再单独用特殊覆盖”的旧两阶段顺序。

首轮使用**单一混合训练 manifest**：正常、特殊和低密度样本保持同一 schema、字段顺序、容器和 EOS，按固定 seed 分层打散。若以后要研究两阶段顺序，另开单变量实验。

---

# 四、自动停工条件

出现任一情况，状态改为 `BLOCKED_REQUIRES_DECISION`：

- 控制面无法合法登记新实验；
- A 与 C-2 的 `fact/status/speaker` 不一致；
- 切段两次运行结果或 SHA 不一致；
- unit map 不能逐字反向还原；
- C-2 需要人工逐条修答案，而不是程序全量重建；
- B 区按金标挑选；
- 当前 41、旧 48 或其来源作者进入新训练／dev／test；
- 同一作者跨 split；
- 任何非 `TRAINING_CLEARED` 窗口进入训练；
- 同一对照里同时改了格式以外的变量；
- 原始输出、日志、SHA 或 manifest 缺失；
- 决策指标在看到结果后被修改；
- 首轮 A/C-2 仍采用旧的“正向→特殊覆盖”而没有单独实验授权。

---

# 五、Codex 收到后的第一动作

只做仓库登记，不立刻跑模型：

1. 创建 `finetuning/experiments/T5_R04_CPLUS_20260807_R01/`；
2. 导入两份决定、两份合同和预检回执；
3. 写 `00_ROUTE_MAP.md`、`MANIFEST.json`、`RUN_STATE.json`；
4. 用现有控制工具更新微调域导航；
5. 运行域校验；
6. 回传 `P0_IMPORT_RECEIPT.md`，包含全部路径、SHA、状态和唯一下一动作；
7. 校验通过后直接执行阶段 1，不再等待新的口头确认。

推荐回执状态：

```text
P0_IMPORTED_STAGE_1_AUTHORIZED
```

来源：ChatGPT
