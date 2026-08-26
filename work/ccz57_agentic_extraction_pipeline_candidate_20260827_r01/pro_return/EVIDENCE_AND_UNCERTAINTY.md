# 中文长篇小说事实抽取：证据判读与不确定性清单

> 文档状态：咨询审查记录，不是正式模型评测报告。  
> 审查日期：2026-08-27。  
> 材料包：`ccz57_agentic_extraction_pipeline_pro_review_20260827_r01`。  
> 入口文件：`00_READ_ME_FIRST.md`、`01_BACKGROUND_AND_BOUNDARIES.md`。  
> 硬边界：四道本地题不是 Gold，不计算正式准确率、模型排名或“整体可用”；不替代 CCZ-57／CCZ-84。

## 结论摘要

✅ 包内本地探针能直接证明的是：

- 同一个冻结合同下，失败形态确实分层存在：运输／截断、身份、坏 JSON、Schema 空值、字段语义、说话人、关系边。
- JSON／Schema 通过不能证明事实值正确、证据承托、覆盖完整或关系正确。
- 多个结果能抽到因果两端，却没有稳定保留因果边。
- 最低思考在当前四题里经常增加 Token、耗时、截断和坏 JSON，没有显示稳定语义升级。
- 把输出上限从 4096 提到 8192 能缓解部分截断，但当前材料无法回答是否带来语义净改善。
- 身份闸能在旧模型 ID 与实时目录不一致时阻止静默换号。

⚠️ 包内不能直接证明的是：

- 哪个模型在真实中文长篇上更准；
- 反向覆盖、说话人专项、关系专项、独立 verifier 是否有净收益；
- 应设置多少轮、多少 Token、多少费用或什么置信阈值；
- 动机、伏笔和暗示怎样定义正式正确答案；
- 这套管线是否达到产品验收标准。

🔥 证据等级必须分开：**原始请求／回复与机器回执 > 包内观察记录 > 五份 Deep Research 的候选结论 > 尚未验证的设计推断。**

---

## 证据等级

| 等级 | 含义 | 本包例子 | 能做什么结论 |
|---|---|---|---|
| E0 冻结与完整性 | 文件、哈希、版本、清单可核对 | `MANIFEST.sha256`、`CONTENT_FREEZE.json`、`04_SNAPSHOT_RECEIPT.json` | 证明审查对象是哪一版，不证明内容正确 |
| E1 原始可观察证据 | 原始请求、原始响应、HTTP／模型身份／Token／finish reason | `03_LOCAL_PROBE/requests/`、`03_LOCAL_PROBE/responses/raw/`、`03_LOCAL_PROBE/responses/*.meta.json` | 证明某次调用实际发生了什么 |
| E2 机器派生与人工观察 | Schema 复检、运行回执、逐题观察 | `03_LOCAL_PROBE/05_运行回执.json`、`03_LOCAL_PROBE/04_逐题观察表.md` 等 | 证明对原始结果的特定检查／观察，仍受检查规则限制 |
| E3 研究报告候选 | 五份 Deep Research 综合结论 | `02_RESEARCH/RAW/*.md` | 提供设计候选，不能当已核实一手来源 |
| E4 本次网页独立复核 | 公开标准、官方文档、论文落地页 | 本文“外部网页复核” | 验证某些通用模式确有公开来源，不证明对目标任务有效 |
| U 未知 | 当前材料无法回答 | 正式 Gold、真实长篇、产品成本门槛 | 必须写“未知”或“需要本地验证” |

### 包完整性

本次审查对根目录 `MANIFEST.sha256` 执行校验，清单中的 504 个文件全部通过。这个结论只说明文件与冻结清单一致，不说明模型输出或研究报告主张正确。

包内也明确记录：

- 五份研究报告存在；
- 内部引用编号存在，但外部 URL／DOI 没有完整随 Markdown 保留；
- 本地四题不是 Gold；
- 不应把探针结果写成正式评分。

路径：`00_READ_ME_FIRST.md`、`04_SNAPSHOT_RECEIPT.json`、`02_RESEARCH/INTAKE/05_来源与主张索引.md`。

---

## A. 本地探针已经直接证明的现象

下面只写能回到包内原始文件或运行回执的现象。没有把“观察者预期事实”当正式 Gold。

## 1｜四题是合成探针，不是 Gold

**直接证据：**

- `03_LOCAL_PROBE/00_任务与边界.md`
- `03_LOCAL_PROBE/01_合成题面.json`

四题分别覆盖人物动作、状态变化、关系变化、明确因果链。`intended_facts_for_observer_only` 标明只供观察者使用，未发给模型。它们可以暴露失败形态，不能计算正式 precision／recall 或模型排名。

## 2｜冻结 Prompt、Schema、输入和身份可追踪

**直接证据：**

- `03_LOCAL_PROBE/02_冻结Prompt.md`
- `03_LOCAL_PROBE/frozen/system_prompt_novel_fact_extraction_v2.md`
- `03_LOCAL_PROBE/frozen/novel_fact_extraction_v2.schema.json`
- `03_LOCAL_PROBE/03_模型选择与身份.json`
- `03_LOCAL_PROBE/requests/*.json`

Schema 是 Draft 2020-12，要求顶层 `facts`；每条事实必有 `fact/status/evidence`，可选 `speaker` 一旦出现就必须非空。这个合同能判断结构，但没有定义语义 Gold。

## 3｜身份异常可以在发网前停止，且没有静默换号

冻结 Agent Plan 档案要求 `deepseek-v4-flash-modelhub`／`deepseek-v4-flash-260425`，实时目录中已没有该请求名；系统没有切到附近的新 ID，而是停止该模型，主采样次数为 0。

**直接证据：**

- `03_LOCAL_PROBE/03_模型选择与身份.json`
- `03_LOCAL_PROBE/05_运行回执.json`
- `03_LOCAL_PROBE/06_派生纠正回执.md`
- `03_LOCAL_PROBE/frozen/live_catalog_plans_model_list.json`

这证明身份闸在该次运行中生效，不证明所有通道都不会漂移。

## 4｜接口成功、JSON 可解析、Schema 合法是三件事

### JSON 可解析但 Schema 不合法

Doubao 2.1 Turbo：

- Q1 有 9 个空 `speaker`；
- Q2 有 11 个空 `speaker`；
- Q3／Q4 Schema 合法。

**路径：**

- `03_LOCAL_PROBE/04_逐题观察表.md`
- `03_LOCAL_PROBE/06_派生纠正回执.md`
- `03_LOCAL_PROBE/responses/raw/doubao_seed_2_1_turbo_Q1.stdout.bin`
- `03_LOCAL_PROBE/responses/raw/doubao_seed_2_1_turbo_Q2.stdout.bin`

官方 DeepSeek V4 Flash 的 Q2 也有 9 个空 `speaker`，说明该错误不是某一家模型独有。

**路径：**

- `03_LOCAL_PROBE/08_官方Flash非思考观察.md`
- `03_LOCAL_PROBE/responses/raw/deepseek_official_v4_flash_Q2.stdout.bin`

### 回包完成但 JSON 本身损坏

Doubao Lite Q2 的 `facts` 数组只合法收进第一条，后续字段掉到数组外，直接解析失败。

**路径：**

- `03_LOCAL_PROBE/10_AgentPlan第二批观察.md`
- `03_LOCAL_PROBE/responses/raw/doubao_seed_2_0_lite_Q2.stdout.bin`

### 内容是 JSON，但外层有代码围栏

GLM-5.2 Q1／Q2 在请求 `json_object` 的情况下仍包了 Markdown 围栏；直接 `json.loads` 失败，剥单层围栏后 Schema 合法。

**路径：**

- `03_LOCAL_PROBE/09_AgentPlan第二批运行回执.json`
- `03_LOCAL_PROBE/10_AgentPlan第二批观察.md`
- `03_LOCAL_PROBE/responses/raw/glm_5_2_Q1.stdout.bin`
- `03_LOCAL_PROBE/responses/raw/glm_5_2_Q2.stdout.bin`

这三类错误需要不同处理器，不能统一叫“格式失败”。

## 5｜Schema 合法仍可能有字段语义问题

Doubao Mini 与 SenseNova 的 Q2 把“沈北川没有立刻站起来”标为 `已发生`，而不是合同中的 `否定`。它们的 JSON／Schema 仍可合法。

**路径：**

- `03_LOCAL_PROBE/10_AgentPlan第二批观察.md`
- `03_LOCAL_PROBE/12_sensenova68_ling30_observe.md`
- `03_LOCAL_PROBE/responses/raw/doubao_seed_2_0_mini_Q2.stdout.bin`
- `03_LOCAL_PROBE/responses/raw/sensenova_6_8_flash_lite_Q2.stdout.bin`

Doubao Mini Q2 的原始 JSON 还出现重复 `status` 键；常见解析器会保留后值，Schema 复检可能看不到前一个异常文本。这说明还应保留原始字节和重复键检查，不能只存解析后的对象。

## 6｜Schema 合法仍可能漏说话人或过度填说话人

- 官方 Flash Q3 的直接引语没有 `speaker=乔米`，Schema 仍合法；
- 多个 Q4 结果记录“司机回复知道了”却没有 speaker；
- Ling Q2 给大量纯叙述事实填了 `speaker=旁白`，字段非空所以 Schema 不报错。

**路径：**

- `03_LOCAL_PROBE/08_官方Flash非思考观察.md`
- `03_LOCAL_PROBE/04_逐题观察表.md`
- `03_LOCAL_PROBE/12_sensenova68_ling30_observe.md`

这直接说明“speaker 非空”不等于说话人正确。

## 7｜因果两端存在，不等于因果关系被抽出

Q4 的多个结果包含：

- 温控器午前跳闸；
- 荔枝开始渗水；
- 裴小棠改成报损；
- 通知司机取消车；
- 司机熄火。

但不少结果只把它们列成并列事件，没有一条明确因果命题或关系边。

**路径：**

- `03_LOCAL_PROBE/04_逐题观察表.md`
- `03_LOCAL_PROBE/08_官方Flash非思考观察.md`
- `03_LOCAL_PROBE/10_AgentPlan第二批观察.md`
- `03_LOCAL_PROBE/12_sensenova68_ling30_observe.md`

非思考的 Doubao Mini／Lite 曾写出明确“因／因为”，说明关系边并非绝对抽不出；但该现象在不同模型和配置间不稳定，不能据四题计算关系准确率。

## 8｜最低思考在当前探针中没有显示稳定升级

同一冻结 Prompt、四题、温度 0、4096 输出上限下，包内直接观察到：

- Doubao Turbo Q1／Q2：completion 到 4096，只有 reasoning，最终 JSON 为空；
- MiniMax M3 Q1～Q4：多题 reasoning 吃满 4096，最终 JSON 为空；
- GLM-5.2 Q2／Q3、Ling Q1／Q3／Q4：截断或无合法最终 JSON；
- Qwen 低思考 Q2～Q4：字符串中的引号未转义，JSON 失败；
- SenseNova 低思考 Q2：同类引号错误；
- Doubao Mini／Lite 非思考 Q4 曾出现明确因果，最低思考后没有保留；
- 官方 Flash 低思考 Q2 从空 `speaker` 改为省略字段，Schema 得到改善，但 Q4 仍无明确因果；
- 多个通道 Token 和耗时明显上升。

**路径：**

- `03_LOCAL_PROBE/14_thinking_low_observe.md`
- `03_LOCAL_PROBE/13_thinking_low_agent_plan_partial.json`
- `03_LOCAL_PROBE/13_thinking_low_deepseek_partial.json`
- `03_LOCAL_PROBE/13_thinking_low_ling_partial.json`
- `03_LOCAL_PROBE/13_thinking_low_sensenova_partial.json`
- `03_LOCAL_PROBE/15_qwen_thinking_low_partial.json`
- `03_LOCAL_PROBE/15_glm53flash_thinking_low_partial.json`
- 对应 `03_LOCAL_PROBE/responses/raw/tl_*`

这能证明“最低思考不是本探针里的自动升级键”，不能证明所有模型、所有任务或更高档思考都无效。

## 9｜某些端点强制思考，不能伪造 on/off 对照

OpenRouter 上的 GLM 5.3 Flash 在关闭思考时返回“reasoning mandatory”类错误，后续非思考题没有继续调用；最低思考可调用。

**路径：**

- `03_LOCAL_PROBE/15_glm53flash_nonthinking_partial.json`
- `03_LOCAL_PROBE/15_glm53flash_thinking_low_partial.json`
- `03_LOCAL_PROBE/responses/raw/glm53_flash_openrouter_Q1.stdout.bin`

因此这类模型不能被当作同模型思考开／关 A/B。

## 10｜4096→8192 的冻结请求只改了输出上限

本次审查比较了包内 40 对 `tl_*` 与 `t8k_*` 请求 JSON。每对差异都只出现于：

- `body.max_tokens: 4096 → 8192`；或
- Agent Plan 命令参数与 `sampling.max_output_tokens: 4096 → 8192`。

Prompt、输入、模型、温度、思考档没有在请求中同时改变。

**路径：**

- `03_LOCAL_PROBE/requests/tl_*`
- `03_LOCAL_PROBE/requests/t8k_*`
- `03_LOCAL_PROBE/frozen/execute_authority_thinking_low_8192_20260827.json`

这使其具备“单变量请求”的外形，但每格只有一次调用、没有正式 Gold，仍不能给出正式语义因果结论。

## 11｜8192 能缓解部分截断，但不能保证完整或语义改善

包内机器回执显示：

- Doubao Turbo 的 Q1／Q2、Doubao Mini Q2、Ling Q1／Q3／Q4 在 4096 下不完整，在 8192 下得到可解析／Schema 合法输出；
- MiniMax M3 在 8192 下仍有 Q1／Q3 到 8192，Q4 也没有合法 JSON；
- SenseNova Q2、Qwen Q2～Q4 的引号型 JSON 错误在 8192 下仍存在；
- DeepSeek 8192 的 Q2／Q3 出现空 `speaker` Schema 问题，而 4096 低思考对应题曾合法；
- GLM 5.3 Flash 8192 的 Q3 出现空 `speaker` Schema 问题；
- 各 8192 低思考 partial 的机器字段没有标出 Q4 明确因果命中。

**路径：**

- `03_LOCAL_PROBE/13_thinking_low_*_partial.json`
- `03_LOCAL_PROBE/15_*_partial.json`
- `03_LOCAL_PROBE/17_t8k_agent_plan_partial.json`
- `03_LOCAL_PROBE/17_t8k_deepseek_partial.json`
- `03_LOCAL_PROBE/17_t8k_glm53flash_thinking_low_partial.json`
- `03_LOCAL_PROBE/17_t8k_ling_partial.json`
- `03_LOCAL_PROBE/17_t8k_qwen_thinking_low_partial.json`
- `03_LOCAL_PROBE/17_t8k_sensenova_partial.json`

可下的结论只有：**8192 是一个值得单独测试的截断变量，不能从当前样本把它写成语义增强。**

## 12｜大多数冻结调用保存了身份、重试、Token 和耗时

各轮回执显示主要采样均采用一次调用、重试 0，并保存请求／返回模型名、Token 和耗时；不同供应商字段完整度不完全相同。

**路径：**

- `03_LOCAL_PROBE/05_运行回执.json`
- `03_LOCAL_PROBE/07_官方Flash非思考运行回执.json`
- `03_LOCAL_PROBE/09_AgentPlan第二批运行回执.json`
- `03_LOCAL_PROBE/11_sensenova68_ling30_run.json`
- `03_LOCAL_PROBE/13_thinking_low_run.json`
- `03_LOCAL_PROBE/responses/*.meta.json`

这证明包内已有审计素材，不证明费用字段已统一或所有供应商可完全重放。

---

## B. 只有五份研究报告支持、但包内原始来源没有完整保留的候选

下面这些方向在五份报告中反复出现，但在材料包内部不能追到完整的外部 URL／DOI／具体代码版本。它们可以进入设计候选，不能写成已核实产品事实。

| 候选主张 | 报告路径 | 包内证据等级 | 为什么仍需验证 |
|---|---|---|---|
| 原始输出、事件轨迹和修复分支应追加保存，不覆盖 | `02_RESEARCH/RAW/01_成熟GitHub_Agent的迭代纠错实现__RAW.md`、`02_RESEARCH/RAW/04_生产Agent的失败恢复与停损__RAW.md` | E3 | 报告列出项目模式，但外部源码定位未完整保留 |
| checkpoint／pending write／durable request 可支持恢复和人机中断 | 同上 | E3 | 需要核对目标实现与版本，且小说抽取没有外部副作用场景 |
| 重试节点可能重放副作用，必须考虑幂等与“已发送但未知” | `02_RESEARCH/RAW/04_生产Agent的失败恢复与停损__RAW.md` | E3 | 目标任务主要是推理调用，副作用范围和风险不同 |
| 外部工具、测试、证据比纯自我反思更可靠 | `02_RESEARCH/RAW/02_Coding_Agent如何发现并修正错误__RAW.md`、`02_RESEARCH/RAW/03_一次生成与多轮自修的论文实证__RAW.md` | E3 | Coding 测试有明确 oracle，小说语义没有同等强度 oracle |
| 纯同模型自我修正可能退化正确答案 | `02_RESEARCH/RAW/03_一次生成与多轮自修的论文实证__RAW.md` | E3 | 包内没有保留论文 URL；目标任务也不是数学／推理基准 |
| 多轮任务分解可能帮助实体／关系抽取 | 同上 | E3 | 需要在中文长篇、同预算、同强 one-shot 基线上复现 |
| 错误应分成运输、结构、证据、覆盖、关系、解释层 | `02_RESEARCH/RAW/05_不同抽取错误该交给谁修__RAW.md` | E3 | 这是合理路由候选，但每层处理器的净收益未知 |
| 说话人应作为专项任务 | 同上 | E3 | 本地只证明 speaker 会错，没有证明专项模型会更好 |
| 端点已有时只补关系边 | 同上 | E3 | 本地 Q4 支持“问题存在”，处理方式仍需 A/B |
| 动机／伏笔／暗示应与客观事实分层 | 同上 | E3 | 只确定风险边界，评价标准和产品交互未知 |
| 停止应结合预算、无进展、震荡、回归，而不是只数轮次 | `02_RESEARCH/RAW/01_成熟GitHub_Agent的迭代纠错实现__RAW.md`、`02_RESEARCH/RAW/04_生产Agent的失败恢复与停损__RAW.md`、`02_RESEARCH/RAW/05_不同抽取错误该交给谁修__RAW.md` | E3 | 阈值与指纹定义需本地实现验证 |
| 上下文污染时应使用干净上下文 + 稳定工件，而不是不断追加历史 | `02_RESEARCH/RAW/04_生产Agent的失败恢复与停损__RAW.md` | E3 | 当前短题没有上下文污染探针 |
| 独立 verifier 可能优于修复器自审 | `02_RESEARCH/RAW/03_一次生成与多轮自修的论文实证__RAW.md`、`02_RESEARCH/RAW/05_不同抽取错误该交给谁修__RAW.md` | E3 | 独立模型也可能共同犯错；需要校准 false accept／reject |

### 研究报告的引用状态

包内入口文件已经明确警告：研究报告里保留了类似 `turn...` 的内部引用编号，但没有把完整外部来源链随 Markdown 一起冻结。因此：

- 不能把内部引用编号写成已核实一手来源；
- 不能用报告里的项目名单替代研究当日源码核验；
- 不能从报告直接抄精确性能数字当作目标任务证据；
- 可以把报告的交集转成候选架构和消融问题。

路径：`00_READ_ME_FIRST.md`、`04_SNAPSHOT_RECEIPT.json`、`02_RESEARCH/INTAKE/05_来源与主张索引.md`。

---

## C. 当前材料无法回答的问题

下列项目应明确标为“未知”或“需要本地验证”。

## 模型与准确率

- 真实中文长篇章节上的字段 precision／recall：**未知**。
- 哪个模型／供应商整体最好：**未知**。
- 模型在不同题材、文风、章节长度和角色密度上的稳定性：**未知**。
- 低思考、高思考、非思考的最佳组合：**未知**。
- 4096 与 8192 在非截断样本上的语义差异：**需要冻结 Gold A/B**。

## 证据与覆盖

- evidence locator 的规范化容忍范围：**需要定义**。自动容忍标点或空白可能掩盖非逐字证据。
- support verifier 的准确率、校准和误拒率：**未知**。
- 反向覆盖能提高多少显式事实召回：**未知**。
- 反向覆盖会增加多少重复、假项和解释性内容：**未知**。
- 长章节中“未覆盖锚点”的有效触发规则：**未知**。

## 专项处理器

- 说话人专项是否比主模型／规则／人工更好：**需要本地验证**。
- 因果 edge-only 是否比整包 regenerate 更好：**需要本地验证**。
- 时间、指代、状态变化、关系变化是否需要不同模型或只需不同 Prompt：**未知**。
- 专项窗口应读 2 句、1 段、整场还是整章：**未知**。
- 端点错误时，关系专项怎样拒绝而不是硬连边：**需要设计和 Gold**。

## 修复与验证

- 通用格式转录器能否在坏 JSON 上保持全部叶子值：**未知**。
- Patch-only 的 W→C／C→W 是否优于整包重写：**需要消融**。
- 同模型 verifier、独立模型 verifier、规则与人工的最佳组合：**未知**。
- verifier 冲突怎样裁决、阈值多大：**未知**。
- 正确项的正式定义和版本化 Gold：**尚未提供**。

## 状态与停损

- 同一错误允许几次尝试：**未知**。
- 无进展应按 1 次、2 次还是统计窗口判断：**需要运行数据**。
- 震荡检测的窗口和影响路径范围：**需要实现测试**。
- 成本、耗时、人工升级率的产品门槛：**未知**。
- 供应商“已发送但未确认”的查询能力与幂等 ID 支持：**各通道未知**。

## 产品可用性

- 作者是否愿意审阅 Patch 和证据：**未知**。
- 多轴状态是否会增加理解负担：**未知**。
- 人工升级率达到多少仍可接受：**未知**。
- 动机／伏笔解释怎样呈现才不会混成事实：**未知**。
- 最终是否满足 CCZ-57 或 CCZ-84：**未验收**。

---

## D. 六类“通过”必须分开

## 1｜格式合法

**问题：** 输出能否被 JSON parser 读取，是否符合 Schema？

**例子：**

- 围栏导致直接解析失败；
- 空 `speaker` 导致 Schema 失败；
- 未转义引号导致 JSON 失败。

**不证明：** fact、status、speaker、evidence 或关系正确。

## 2｜值正确

**问题：** 每个字段值是否符合标注规范？

**例子：** “没有立刻站起来”应如何标 status；“旁白”是否是正确 speaker。

**不证明：** evidence 真能承托，或整章没有漏抽。

## 3｜证据承托

**问题：** 给定 evidence 是否足以证明这条 fact、status、speaker 和关系？

**不证明：** 源文其他位置没有漏项。

## 4｜覆盖完整

**问题：** 正文中应该抽的显式事实有多少被覆盖？

**必须依赖：** 正式 Gold 或明确的覆盖标注。

**不证明：** 每条关系边都正确，也不证明产品成本可接受。

## 5｜关系正确

**问题：** 说话人、因果、时间、指代、状态转移、社会关系的端点与方向是否正确？

**例子：** Q4 的跳闸和渗水都在，不代表 `CAUSES` 已抽出。

**不证明：** 动机／伏笔解释正确。

## 6｜产品可用

**问题：** 在满足质量门槛时，调用数、Token、耗时、费用、人工率、可解释性和恢复能力是否可接受？

**不证明：** 某个单项指标达到最高。

### 建议展示格式

```text
请求：成功；身份：匹配；截断：否
JSON：通过；Schema：通过
字段值：已检查 8/10，1 条争议
证据定位：10/10；承托：8/10
显式覆盖：未知（无 Gold）
说话人：1 条缺失；因果：未通过；时间/指代：未检查
修复：W→C=1，C→W=0；新增重复=0
成本：2 次调用，6,200 tokens，人工 1 条
产品结论：部分成功，需要人工
```

不能压成一个“PASS”。

---

## E. 当前不能做的模型比较

包内样本包含多个模型和配置，但不能据此计算正式排名，原因包括：

- 只有四道合成短题；
- 没有正式 Gold；
- 不同供应商通道、思考能力、输出格式支持不同；
- 某些模型强制思考，不能构造同模型开／关；
- 每格通常只有一次调用，无法估计同配置波动；
- 4096 与 8192、思考开／关存在截断和格式混杂；
- 观察记录只标出部分目标现象，不是全量盲评；
- 费用口径没有统一。

因此本材料只能说“出现过某种错误”，不能说“模型 A 比模型 B 更准”或“模型 X 已可用”。

---

## F. 外部网页独立复核

这次额外检索了公开一手／官方材料，用来核对五份报告里的部分通用模式。它们不会把包内四题升级成正式证据。

### 结构与 Patch

- [RFC 6902: JSON Patch](https://www.rfc-editor.org/info/rfc6902/)：定义 `add/remove/replace/move/copy/test` 等局部 JSON 操作。可借鉴 Patch 外形，但小说抽取还需要基线哈希、证据、作用域、验证和人工决定。
- [JSON Schema Draft 2020-12 Validation](https://json-schema.org/draft/2020-12/json-schema-validation)：说明 Schema 验证针对实例结构约束。它支持把“Schema 合法”和“语义正确”分开。

### 状态、恢复与幂等

- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)：官方文档说明 checkpointer 可保存线程状态，用于恢复、故障容错和人机中断。
- [LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)：官方文档说明 interrupt 会从节点重跑，因此节点前的副作用应具备幂等性。
- [Temporal Activity Definition](https://docs.temporal.io/activity-definition)：官方文档说明重试会重新执行整个 Activity，建议把动作拆细以维持幂等。
- [Temporal Python Error Handling](https://docs.temporal.io/develop/python/best-practices/error-handling)：官方文档区分可重试与不可重试错误，并建议 Activity 幂等。

这些来源支持“保存状态、局部动作、受控重试”的工程原则，不决定目标任务的最佳模型或错误阈值。

### 自我修正、外部反馈与任务分解

- [Large Language Models Cannot Self-Correct Reasoning Yet](https://arxiv.org/abs/2310.01798)：报告无外部反馈的自我修正并不稳定，某些情形会退化。
- [CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing](https://arxiv.org/abs/2305.11738)：研究外部工具反馈参与验证和修正。
- [ChatIE: Zero-Shot Information Extraction via Chatting with ChatGPT](https://arxiv.org/abs/2302.10205)：把零样本信息抽取拆成两阶段、多轮问答任务。

这些材料支持把“纯自我再想一次”和“带外部证据／任务分解的修复”分开研究，但不能直接外推到中文长篇合同。

### 关系与说话人是独立任务

- [Zero-shot Temporal Relation Extraction with ChatGPT](https://aclanthology.org/2023.bionlp-1.7/)：把时间关系作为单独任务评估，并报告长距离一致性困难。
- [Formalization and Benchmarks for the Task of Quote Attribution](https://aclanthology.org/2024.lrec-main.1530/)：把引语与说话人配对作为独立任务，并强调可比评测设置。

这支持“关系／说话人需要单独切片和指标”，不证明某个专项模型一定优于主抽模型。

### 外部复核仍未完成什么

- 没有对五份 Deep Research 的每一条内部引用做逐条源码复核；
- 没有锁定所有 GitHub 项目在 2026-08-27 的精确 commit；
- 没有从外部论文推导中文长篇的预期提升幅度；
- 没有使用外部资料替代本地 Gold。

---

## G. 推荐的主张写法

### 可以写

- “本地四题中观察到空 `speaker`、坏 JSON、围栏、截断、状态标签错误和关系漏边。”
- “在冻结请求对中，4096→8192 只改变最大输出上限；部分截断得到缓解，但语义净收益未知。”
- “五份研究报告共同支持不可变原件、局部 Patch、外部验证和受控停止作为候选方向。”
- “需要在获批 Gold 上做单变量消融。”

### 不可以写

- “模型 X 准确率最高。”
- “最低思考一定更差／更好。”
- “8192 提高了推理能力。”
- “Q4 已证明关系专项有效。”
- “Schema PASS 表示抽取正确。”
- “Deep Research 内部引用已经是一手核实来源。”
- “这套方案已达到 CCZ-57／CCZ-84。”

---

## H. 关键路径总索引

### 入口与边界

- `00_READ_ME_FIRST.md`
- `01_BACKGROUND_AND_BOUNDARIES.md`
- `01_PROMPT_CHATGPT_PRO.md`
- `04_SNAPSHOT_RECEIPT.json`
- `CONTENT_FREEZE.json`
- `MANIFEST.sha256`

### 研究材料

- `02_RESEARCH/RAW/01_成熟GitHub_Agent的迭代纠错实现__RAW.md`
- `02_RESEARCH/RAW/02_Coding_Agent如何发现并修正错误__RAW.md`
- `02_RESEARCH/RAW/03_一次生成与多轮自修的论文实证__RAW.md`
- `02_RESEARCH/RAW/04_生产Agent的失败恢复与停损__RAW.md`
- `02_RESEARCH/RAW/05_不同抽取错误该交给谁修__RAW.md`
- `02_RESEARCH/INTAKE/05_来源与主张索引.md`
- `02_RESEARCH/INTAKE/06_增量结论.md`

### 本地探针定义

- `03_LOCAL_PROBE/00_任务与边界.md`
- `03_LOCAL_PROBE/01_合成题面.json`
- `03_LOCAL_PROBE/02_冻结Prompt.md`
- `03_LOCAL_PROBE/frozen/novel_fact_extraction_v2.schema.json`
- `03_LOCAL_PROBE/03_模型选择与身份.json`

### 运行与观察

- `03_LOCAL_PROBE/04_逐题观察表.md`
- `03_LOCAL_PROBE/05_运行回执.json`
- `03_LOCAL_PROBE/06_派生纠正回执.md`
- `03_LOCAL_PROBE/07_官方Flash非思考运行回执.json`
- `03_LOCAL_PROBE/08_官方Flash非思考观察.md`
- `03_LOCAL_PROBE/09_AgentPlan第二批运行回执.json`
- `03_LOCAL_PROBE/10_AgentPlan第二批观察.md`
- `03_LOCAL_PROBE/11_sensenova68_ling30_run.json`
- `03_LOCAL_PROBE/12_sensenova68_ling30_observe.md`
- `03_LOCAL_PROBE/13_thinking_low_run.json`
- `03_LOCAL_PROBE/14_thinking_low_observe.md`
- `03_LOCAL_PROBE/15_*_partial.json`
- `03_LOCAL_PROBE/17_t8k_*_partial.json`

### 原始请求与回复

- `03_LOCAL_PROBE/requests/`
- `03_LOCAL_PROBE/responses/raw/`
- `03_LOCAL_PROBE/responses/*.meta.json`

---

## 最终证据判定

当前材料足以支持建设一个**候选的、可审计的修复骨架**：不可变 Attempt、分轴诊断、局部 Patch、独立验证、版本化合并、预算与停止控制。

当前材料不足以支持自动启用反向覆盖、说话人专项、关系专项、独立模型 verifier 或思考档，也不足以确定任何模型排名、准确率、重试阈值和产品门槛。

因此推荐状态是：

```text
架构候选：可进入最小实现设计
语义专项：需要冻结消融
模型选择：未知
正式准确率：未知
产品可用性：未知
CCZ-57 / CCZ-84：未替代、未验收
```
