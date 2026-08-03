# C-min-B 重新冻结实验合同｜给 ChatGPT Pro 的提示词

你现在是“实验合同重冻大夫”，不是路线拍板人，也不是模型执行器。

## 先认唯一现行真源

请严格按下面顺序读包，不能只按文件名模糊搜索：

1. `00_ROUTE_MAP.md`
2. `01_current_truth/TEMP/chatgpt_review_cycles/cmin_b_contract_refreeze_20260730_r01/TRUTH_SNAPSHOT.md`
3. `01_current_truth/TEMP/chatgpt_review_cycles/cmin_b_contract_refreeze_20260730_r01/B_WORK_ORDER.md`
4. `01_current_truth/TEMP/chatgpt_review_cycles/cmin_b_contract_refreeze_20260730_r01/EVIDENCE_BOUNDARIES.md`
5. `01_current_truth/config/review_pack/prompts/cmin_b_contract_refreeze.md`

上面第 2～4 项是本轮唯一现行语义真源。包内其他同名 `TRUTH_SNAPSHOT.md`、旧路线的 `01_current_truth/`、MiniMax V2.3/V2.4 材料以及两份旧 ChatGPT 回包，全部只是历史证据，不能覆盖 2026-07-30 21:00 的 C-min-B 拍板。

## 已拍板、不得改判的路线

- C-min 路线＝B。
- 复用已经冻结的 V4 Flash 骨架，V4 Flash 新抽取调用＝0。
- Qwen 3.7 Flash 承担 6 次严格定窗修补。
- 判别岗只能在 Qwen 3.7 Flash、V4 Flash、程序三者之间分工。
- MiniMax M3 不得回到本轮默认链，只能作为未来升级兜底的历史对照。
- 总物理模型调用不超过 9 次，不能叠加历史预算。
- 0 自动重试；跑中不得换模型、补跑、改判据或看成绩后重配岗位。

你可以根据包内实测证据决定“程序、Qwen、V4 Flash 各判什么”，但不能推翻路线 B，也不能替 CZ 批准升级。

## 包里的证据怎么用

包内包含程序选择器、Qwen 盲清单与思考预算、Qwen 小批判别、V4 Flash、V4 Pro、MiniMax M3 的完整候选输出与评分，也包含 MiniMax V2.3 三书失败诊断、V2.4 零调用护栏、旧外审原始回包和四模型 30 题成绩。

必须区分五类读数：

1. 四模型 30 题答题终验分；
2. 旧 R2 开发覆盖分；
3. 三题材 12 项候选判别分；
4. MiniMax V2.3 的 3/5、5/5、6/6 失败诊断读数；
5. 尚未产生的 C-min-B 六窗口正式成绩。

前四类只能帮助定岗位和冻结归因规则，不能伪装成第五类。若某项关键判断缺少直接证据，请写“材料不足”，不要补想象。

## 你要完成的工作

- 把“V4 Flash 冻结骨架 0 新调用＋Qwen 3.7 Flash 6 次严格定窗修补＋便宜判别岗”写成可机械执行的预注册合同；
- 根据包内已测数据，在 Qwen、V4 Flash、程序之间给出唯一的判别岗分工；
- 冻结六个窗口与三种题材的映射、输入哈希、窗口所有权、调用顺序、物理调用记账、停止条件、状态机、增量安全闸和只读评分器；
- 把晋级线逐项写成机器可判定规则：三题材各净增受支持事实至少 1、六窗合计至少 6、被接受的无依据新增 0、正确旧事实误删 0、语义弱化 0；
- 若便宜判别岗导致不过线，在成绩单中单列“判别岗档位”归因，作为未来申请 MiniMax 升级的证据；本轮不能自行升级或补跑；
- 对涉及的组件填写“便宜模型可达水平／升级条件／升级价”三字段；没有足够价格证据时写 `PRICE_EVIDENCE_MISSING`；
- 每个关键判断引用包内相对路径、运行编号、字段或读数，至少给出一条可核查证据。

## 禁止事项

- 不执行任何模型调用；
- 不修改评分判据、金标、默认链或现役配置；
- 不把候选成绩写成正式达标；
- 不把 19 个组件与“第13章10条＋第19章9条旁路记录”混为一谈；
- 不要求读取包外正文、R2 封签金标或答案锁箱；
- 不让模型直接删除、写入正式账或签完成票；
- 不用自动重试、失败后同修订补跑或根据结果临时换模型；
- 不猜价格，不伪造尚未运行的六窗口成绩。

## 回包格式

请生成一个可下载 ZIP，文件名：

`CMIN_B_ChatGPT_Pro_review_20260730.zip`

ZIP 根目录直接包含：

1. `00_MAIN_REPORT.md`
2. `01_CMIN_B_PREREGISTRATION.md`
3. `02_CMIN_B_FROZEN_CONTRACT.json`
4. `03_WINDOW_AND_CALL_LEDGER.json`
5. `04_SCORING_AND_ATTRIBUTION.md`
6. `05_TOOL_CONTRACT_FIELDS.md`
7. `06_LOCAL_EXECUTOR_HANDOFF.md`
8. `07_EVIDENCE_TRACEABILITY.json`
9. `SHA256SUMS`

不要再套第二层 ZIP。所有 JSON 必须能解析。聊天正文可以简短，完整内容以 ZIP 内文件为准；不要把关键证据只藏在思考过程里。

来源：Codex
