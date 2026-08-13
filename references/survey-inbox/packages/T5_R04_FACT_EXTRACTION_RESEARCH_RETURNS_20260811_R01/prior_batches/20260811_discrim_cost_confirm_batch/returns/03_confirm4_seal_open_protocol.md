✅ 结论可以直接写死：`CONFIRM4` 每个版本最多只有一次“有决策意义的开封批次”。

这里的“一次”不是一次 API 调用，而是一批事先登记好的调用：冻结候选、固定重复次数、一次性跑完，中途不得看成绩、换 Prompt、改评分器。只要 CONFIRM4 返回的任何信息被用于调整 Prompt、评分规则、候选或过门线，它对调整后的方案就已经烧掉了。

只看汇总分属于“部分烧掉”，比看逐条错误泄漏少，但不能继续叫完全未见；“先开一章、留三章”可以做，不过必须提前分成两个独立批次，且最好在书、作者、来源层面互不重叠。

这和你们现有的“参与过 checkpoint 或格式选择后只能叫 DEV”的纪律是同一套逻辑。

### 依据代号

| 代号 | 依据                                                                                                                                                                                                                                                                                     |
| -- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A  | [[Google：训练／验证／测试三分，测试集反复用于决策会磨损](https://developers.google.com/machine-learning/crash-course/overfitting/dividing-datasets)](https://developers.google.com/machine-learning/crash-course/overfitting/dividing-datasets)；[[ACL 2025：Prompt engineering 即使不改权重，也应视为训练过程](https://aclanthology.org/2025.latechclfl-1.5.pdf)](https://aclanthology.org/2025.latechclfl-1.5.pdf)                                                            |
| B  | [[Dwork 等：适应性地反复查询 holdout 会造成 holdout 过拟合](https://arxiv.org/abs/1506.02629)](https://arxiv.org/abs/1506.02629)；[[Generic Holdout：仅返回过／不过可以减少泄漏，但需要正式的信息预算协议](https://arxiv.org/abs/1809.05596)](https://arxiv.org/abs/1809.05596)                                                                                                                            |
| C  | [[OSF：预注册应当是分析前形成的只读、带时间戳计划](https://help.osf.io/article/330-welcome-to-registrations)](https://help.osf.io/article/330-welcome-to-registrations)；[[COS：看到结果后改变检验方法，应改称探索性分析](https://www.cos.io/initiatives/prereg)](https://www.cos.io/initiatives/prereg)                                                                                                                                |
| D  | [[Blum 与 Hardt：排行榜反馈会让提交方案依赖测试集；公开榜／私有榜是分层保留方案](https://proceedings.mlr.press/v37/blum15.pdf)](https://proceedings.mlr.press/v37/blum15.pdf)；[[Kaggle 官方规则](https://www.kaggle.com/docs/competitions-setup)](https://www.kaggle.com/docs/competitions-setup)                                                                                                                             |
| E  | [[scikit-learn：有关联的样本应按 group 隔离，不能把同一主体的样本拆进两边](https://scikit-learn.org/stable/modules/cross_validation.html)](https://scikit-learn.org/stable/modules/cross_validation.html)                                                                                                                                                                         |
| F  | [[NIST：SHA-256 等摘要用于检查文件是否被修改](https://csrc.nist.gov/pubs/fips/180-4/upd1/final)](https://csrc.nist.gov/pubs/fips/180-4/upd1/final)；[[RFC 3161：可信时间戳用于证明某份摘要在某时刻已经存在](https://www.rfc-editor.org/info/rfc3161/)](https://www.rfc-editor.org/info/rfc3161/)；[[NIST 日志管理](https://csrc.nist.gov/pubs/sp/800/92/final)](https://csrc.nist.gov/pubs/sp/800/92/final)与[[职责分离／双人规则](https://csrc.nist.gov/glossary/term/separation_of_duty)](https://csrc.nist.gov/glossary/term/separation_of_duty) |
| G  | [[Recht 等重新构建 ImageNet 测试集：测试冲突也可能来自抽样分布变化，而不只是过拟合](https://proceedings.mlr.press/v97/recht19a/recht19a.pdf)](https://proceedings.mlr.press/v97/recht19a/recht19a.pdf)                                                                                                                                                                            |

## CONFIRM4 封存／开封协议

下面可以直接抄进执行合同。

### 一、身份与使用次数

**CONFIRM4-01｜数据身份**

判别卷用于 Prompt、模型条件、解析器和评分规则的日常迭代，身份固定为 `DEV`。CONFIRM4 只用于验证已经冻结的晋级主张，不承担继续找错误、改 Prompt 或重新排名的职责。
依据：A。

**CONFIRM4-02｜Prompt 视同训练参数**

凡是根据某批数据的成绩或错误案例修改系统提示词、用户提示词、few-shot 示例、任务定义、思考档位或后处理规则，均视为使用该批数据完成了训练／调参。是否修改模型权重不影响这一判断。
依据：A。

**CONFIRM4-03｜一次开封的定义**

同一 `CONFIRM4_VERSION` 最多允许一次有决策意义的开封批次。该批次可以包含预先登记的多个 API 调用和随机重复，但必须在不向开发人员反馈任何中间结果的条件下一次性完成。
依据：A、B。

**CONFIRM4-04｜不存在通用的“三次机会”**

普通测试集纪律没有“最多可以安全看三次或五次”的固定数字。默认安全数字就是一次。若希望反复查询，必须另外设计带查询预算、有限反馈或噪声机制的 reusable holdout；简单地隐藏逐条结果、只显示精确总分，不等于已经采用这种机制。CONFIRM4 只有四章，不按可复用 holdout 处理。
依据：B、D。

### 二、冻结的评测对象

**CONFIRM4-05｜冻结的是完整条件，不只是模型名**

每个被测条件必须绑定：

* 厂商、接口、精确模型 ID 和版本；
* 系统／用户 Prompt 的逐字节 SHA；
* few-shot 示例及顺序；
* 上下文结构和只读背景；
* 思考开关、思考档位；
* temperature、top_p、seed、最大输出；
* Schema、解析器、后处理器版本；
* 重试、超时和失败处理；
* 正式评分器版本。

其中任何一项变化，都视为新条件。API 返回的实际模型版本与冻结版本不符时，按执行异常处理。

依据：A、C。

**CONFIRM4-06｜确认卷不再承担选冠军**

推荐在判别卷上冻结一个主候选，再用 CONFIRM4 做“是否过门”的检验。

若确实要带多个候选进入 CONFIRM4，必须预先登记固定选择树，例如“主候选通过则采用；主候选失败时才检查后备候选”。不得在开封后选择 CONFIRM4 分数最高者，再把该分数解释成对冠军的独立确认。
依据：A、B、D。

### 三、样本和 Gold 封存

**CONFIRM4-07｜按最高关联层隔离**

TRAIN、判别卷和 CONFIRM4 至少在书、作者、来源三个层级保持不交叉。若四章来自同一本书或同一作者，不得把四章当作四个完全独立样本；在极端情况下，有效独立 group 可能只有一个。
依据：E。

**CONFIRM4-08｜确认卷能力边界**

四章可以充当产品晋级硬门和独立复验信号，但不能仅凭大量事实条目，把有效样本数包装成几百个。条目之间受同一章节、人物和叙事结构影响。报告必须同时保留逐章结果；置信区间或 bootstrap 应按章或更高 group 重采样。
依据：A、E。

**CONFIRM4-09｜正文与 Gold 的两种合格做法**

允许任选一种，并在封存票中写明：

1. 由与 Prompt 开发隔离的标注人提前制作 Gold，随后将正文和 Gold 一起封存；
2. 先冻结全部模型输出，再由不知道候选身份、看不到模型预测的标注人按已冻结规则制作 Gold。

禁止先阅读 CONFIRM4 案例，再据此补写抽取规则、评分边界或 Gold 颗粒度。

依据：A、C。

### 四、无人看过的证据链

**CONFIRM4-10｜“无人看过”的操作定义**

“无人看过”不得写成无法核验的绝对表述，应写成：

> 自 `seal_at` 至 `open_at`，除名单中声明的数据保管人／Gold 标注人外，Prompt 作者、候选选择者、评分规则制定者、API 执行者及任何模型均未获得 CONFIRM4 正文或逐条 Gold。

原创作者、数据保管人等已知接触者必须如实列入 `known_viewers`。

依据：C、F。

**CONFIRM4-11｜哈希封存**

封存时至少生成：

* 每个正文文件的 SHA-256；
* Gold 文件 SHA-256；
* 整包明文 manifest SHA-256；
* 加密包 SHA-256；
* 文件大小、案例数和 opaque case ID；
* 书／作者／来源 group ID。

SHA 只能证明文件后来有没有变化，不能单独证明文件没人打开。
依据：F。

**CONFIRM4-12｜加密与职责分离**

正文和 Gold 应保存在加密包或受访问控制的存储中。密钥由未参与 Prompt 迭代的数据保管人持有；正式解密需执行负责人和见证人共同批准。普通目录中的 ZIP，即使有 SHA，也不足以证明无人读取。
依据：F。

**CONFIRM4-13｜时间证据**

封存 manifest、预注册和候选配置的摘要应提交到不可静默改写的位置，例如只读注册、远端签名提交或 RFC 3161 时间戳。仅保留本地 Git commit 的时间证明较弱。
依据：C、F。

**CONFIRM4-14｜访问与外发日志**

从封存起记录解密、下载、复制、导出和 API 请求事件。开封前由保管人检查：

* CONFIRM4 source ID 未出现在历史 API 请求账；
* 正文没有进入全文检索、向量库、RAG、IDE 云索引或自动预览；
* 没有未登记的明文副本；
* 访问日志没有非授权读取；
* 历史请求中没有对应正文或切片。

日志本身也应计算摘要并只追加、不覆盖。
依据：F。

### 五、开封硬门

**CONFIRM4-15｜预注册必须写全**

开封前必须冻结并带时间戳登记：

* 要验证的主张和预期方向；
* 主指标、辅助指标和硬门；
* 绝对过门线、相对基线要求；
* 格式失败、空输出、非法证据、截断如何计入；
* micro／macro／逐章怎样汇总；
* 排除规则和灰区处理；
* 候选数量与固定选择树；
* 重复次数、随机种子和统计方法；
* 允许反馈到什么粒度；
* 结果冲突时怎样处理。

“预计得多少分”可以作为非约束预测；真正必须冻结的是判定规则和过门线。
依据：C。

**CONFIRM4-16｜评分器冻结**

Gold、语义匹配规则、必抽／可选／禁抽定义、合并拆分规则、人工仲裁手册、评分代码和阈值必须分别有版本与 SHA。不得因某个候选“看起来其实答对了”而在开封后临时改尺子。
依据：A、C。

**CONFIRM4-17｜执行与失败规则冻结**

请求顺序、并发、会话是否无状态、缓存、超时、网络重试、HTTP 成功但空输出、格式失败、模型拒答和供应商限流处理必须提前写死。

只允许按预注册条件重试运输失败。空输出、格式错误、截断等模型结果不得通过修改 Prompt 后在同一 CONFIRM4 上补考。
依据：C。

**CONFIRM4-18｜开封前演练**

运行器、API 连接、日志、解析器和评分器必须先在合成数据或判别卷的同结构镜像上完整演练。不得用 CONFIRM4 的第一章测试“程序能不能跑”。
依据：A。

**CONFIRM4-19｜开封票**

只有下面项目全部为真才可开封：

* 候选条件已冻结；
* 评分器与 Gold 已冻结；
* 决策规则和过门线已冻结；
* 失败与重试规则已冻结；
* 预定反馈粒度已冻结；
* 判别卷迭代已正式停止；
* 演练通过；
* 预算和 API 版本确认；
* 封存 SHA 重算一致；
* 访问检查无异常；
* 执行负责人、保管人和见证人签字。

依据：C、F。

### 六、运行和结果披露

**CONFIRM4-20｜盲跑**

正式运行期间不得向 Prompt 作者或候选选择者展示正文、预测、逐章分数、候选排名或中间汇总。全部预注册调用完成后，才能按约定粒度统一披露。
依据：B、D。

**CONFIRM4-21｜开封后允许改什么**

开封后只允许：

* 不影响输入、输出和评分的文件名／展示排版修复；
* 按已登记规则执行运输重试；
* 从冻结原始输出生成已预注册的报告。

Prompt、模型条件、解析逻辑、Gold、评分规则、阈值、排除规则发生变化后，不得继续使用 CONFIRM4 为新条件签独立确认票。

若代码明显没有执行冻结公式，可以由不知道候选身份的人修复并保留修复前后结果；修复改变主结论时，正式状态记为 `INCONCLUSIVE`，不直接挑有利版本。
依据：A、C。

**CONFIRM4-22｜披露等级与烧毁状态**

| 已披露内容                 | 状态               | 此后允许用途                |
| --------------------- | ---------------- | --------------------- |
| 只有封存与执行回执，没有任何结果      | `EXECUTED_BLIND` | 仅完成同一预注册批次            |
| 只披露过／不过               | `USED_GATE`      | 可监控原冻结条件；不能确认据此修改的新条件 |
| 披露精确汇总分或排名            | `USED_AGGREGATE` | 作为历史回归集；不再是完全未见确认集    |
| 披露逐章成绩、预测或错误案例        | `BURNED_DETAIL`  | 转为 DEV／诊断集            |
| 逐条案例被用于修改 Prompt 或评分器 | `RETIRED_TO_DEV` | 只能开发、回归，不再承担确认职责      |

过／不过也会传递信息，只是比精确分和逐条错误少。
依据：B、D。

### 七、分层开封

**CONFIRM4-23｜允许分层，但必须提前拆身份**

“先一章、后三章”只有在开封前就登记为：

* `CONFIRM-PILOT1`：允许烧掉并用于修改；
* `CONFIRM-FINAL3`：只用于修改后的最终确认。

PILOT1 使用后永久退出确认集。FINAL3 必须在书、作者、来源层面与 PILOT1 尽可能独立；若四章来自同一本小说或同一作者，不得声称这种拆法获得了干净的独立确认。
依据：D、E。

**CONFIRM4-24｜本项目推荐**

只有四章时，不建议牺牲一章测试运输或格式。把程序演练放到判别卷或同结构合成卷；CONFIRM4 四章整体保留为一次开封批次。只有确实拥有四个独立来源 group，且事先就需要“两阶段决策”时，才考虑 1＋3。
依据：A、E。

## 判别卷与确认卷冲突时

| 情况                        | 合同处理                                      |
| ------------------------- | ----------------------------------------- |
| 冻结主候选通过 CONFIRM4 全部硬门     | 允许晋级；判别卷只作开发依据                            |
| 判别卷领先，但 CONFIRM4 未过门      | 当前晋级主张失败，不得用两卷平均分救回                       |
| 主候选过门，但 CONFIRM4 上另一候选分更高 | 若“重新排名”未预注册，该排名只算探索性发现                    |
| 执行违反冻结合同                  | 记 `INVALID/INCONCLUSIVE`；只按预注册重试，否则使用新确认卷 |
| 两卷差异来自书型、作者或章节结构          | 分别报告分布；不能笼统宣布某一卷“更真”                      |
| 确认结果确实反转开发结论              | 先记录“不确认／不晋级”，再允许查看错误；CONFIRM4 随即转 DEV     |

🔥 当前产品决策上，CONFIRM4 应控制“能不能晋级”，前提是它的抽样范围确实代表预先声明的生产目标。它独立性更强，不代表它天然比其他数据更有代表性。

第三卷可以有，但它的身份是“新鲜独立复验”，不是事后仲裁员：

1. 先把原确认结论记录为通过、失败或不确定；
2. 查看错误后，原 CONFIRM4 正式退为 DEV；
3. 完成必要修改；
4. 从新书／新作者／新来源建立 `CONFIRM_NEXT`；
5. 重新冻结候选、评分器和门线；
6. 用新卷检验新的主张。

不得把 DEV、CONFIRM4、第三卷反复加权，直到算出想要的结论。分布变化导致测试集分数冲突是现实问题，新卷的价值在于独立复验，不是多数表决。依据：A、C、G。

## 最常见的三种悄悄失效事故

| 事故             | 为什么容易漏掉                                      | 检查办法                                                         |
| -------------- | -------------------------------------------- | ------------------------------------------------------------ |
| 1. 把确认卷变成隐藏排行榜 | 团队只看总分、不看正文，于是误以为仍然“没污染”；但每轮总分都在指导 Prompt    | 对照首次结果披露时间和 Prompt／候选提交时间。任何行为条件版本晚于首次反馈，都不能再由同一 CONFIRM4 确认 |
| 2. 看到结果后移动尺子   | 修改匹配规则、把失败样本排除、改变必抽／可选边界，看起来像“修评分器”          | 比对 Gold、评分代码、阈值和仲裁手册 SHA；所有修改必须有时间早于开封的冻结票，否则只能标探索性          |
| 3. 正文通过旁路提前暴露  | 自动同步、系统预览、全文搜索、向量索引、API 调试日志和临时副本不会出现在正式实验表里 | 查加密状态、ACL、解密日志、文件副本、索引清单和 API 请求账；哈希只能查改动，不能替代访问日志和职责分离      |

最小审计 manifest 建议保留这些字段：

```text
dataset_id
dataset_version
status
sealed_at
opaque_case_ids
book_group_ids
author_group_ids
source_group_ids
plaintext_manifest_sha256
gold_sha256
encrypted_package_sha256
known_viewers
storage_location
access_control_list
key_custodian
preregistration_sha256
candidate_bundle_sha256
scorer_bundle_sha256
open_authorization_id
first_access_at
api_run_ids
request_response_hashes
disclosure_level
burn_status
deviations
witnesses
```

⚠️ 哈希＋见证＋日志能形成很强的“未发现提前访问证据”，但无法数学证明某个人从未私下看过或保留副本。合同应当承诺可核验的角色、权限和日志事实，不写无法审计的绝对保证。

来源：ChatGPT
