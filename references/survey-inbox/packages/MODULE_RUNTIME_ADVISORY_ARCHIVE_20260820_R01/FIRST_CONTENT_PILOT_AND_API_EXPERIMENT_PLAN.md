# FIRST CONTENT PILOT AND API EXPERIMENT PLAN｜PILOT-R01

> **计划身份**：`PILOT-R01`｜`PLAN_ONLY`｜`SYNTHETIC_ONLY`｜`REAL_NOVEL_COUNT=0`｜`REAL_AUTHOR_PROJECT_COUNT=0`｜`GOLD_COUNT=0`｜`API_CALLS_EXECUTED=0`
>
> **权限**：本文件只设计材料、请求、评分、停点和回传形状。不修改组件、代码、正式合同、R13、Gold、训练、生产或作者真值；不选择具体模型、供应商、路由或价格。
## 1. 一页结论

✅ **建议保留 15 张候选卡，不替换。** 这不是说当前代码都没覆盖，而是共用运输材料里没有 52 张考卷正文、13 组 seed 注册表、当前代码快照、正式合同现物和直接测试回执；没有证据就不能把任何一张按“已关闭”删掉。15 张卡被压成三层：

- `L0`：9 张零 API 机械／身份卡，外加 `CCE-A-M3-04` 的冻结回包门，共 **31 个本地实例**；
- `L1`：5 张 API 卡先用同一批输入和冻结 provider 回包排运输、parser、schema、展示与写入门；
- `L2`：获得 CZ 明确模型、路由、费用和调用授权后，5 张卡各 4 个单变量实例，共 **20 次首轮调用**，`retry=0`；20 次红线为 0 才允许每卡选 1 个实例原样重复，共最多 5 次，**总上限 25 次**。

🔥 **PILOT-R01 的判定核心不是平均分，而是“先身份、再语义、红线优先”。** fixture、来源、版本、prompt、参数、raw response 任一身份不闭合，就不进入语义评分。任何状态漂白、未来泄露、伪证据、高影响自动拍板、旧版冒 current、HARD 丢失、未检查冒充通过、不完整批次冒充完成，立即停止对应路线。

冻结 provider 的通过只能说明：输入能送达、回包能解析、schema 能拦、页面能显示、门能 fail closed。它**不能**说明模型理解了传闻、冲突、must_not、规划或梗概。

小 API 结果只能叫：`SYNTHETIC_SEMANTIC_PROBE_RESULT`。不能叫模块通过、跨题材泛化、真实作者可用、生产可用或模型胜出。一次实验只改一个变量；不能一边改 Prompt，一边换模型，再一边换组件。
### 阅读与证据边界

本地实见的是平铺背景运输包：R13 产品背景、外部报告 R01 的部分登记材料、127 条原子预期 R02，以及 manifest／checksum。机械核对发现 `02_SHA256SUMS.txt` 登记的 43 个成员中有 15 个外部报告成员缺失；更关键的是，本包没有 52 张考卷正文、13 组 seed 注册表，也没有当前代码／合同／直接测试。因此：

- 卡名与本轮目标以 CZ 本 Prompt 为准；
- 验收边界以 R13、原子预期 R02、跨模块共同家规和当前可读的冲突图为准；
- “当前代码是否已覆盖”统一标 `UNVERIFIED_IN_THIS_PACKAGE`；
- “当前 13 组 seed 哪一组可复用”只能给出**功能资格**，不能伪造具体 seed ID；运行前必须补 `seed_registry_handle + sha256`；
- 可复用既有合成材料的**现象骨架**，但不能继承其标准答案、Gold 身份或生产资格。

这份缺口不阻止设计本地小实验，但阻止我们声称已经完成了对 52 张卡、13 组 seed 和当前代码的逐项闭合核对。

对 File Library 的补查只定位到 2026-08-15 的旧《合同／设计稿模块并行测试审查》和 `CANONICAL_MICRO24_SET_B_R02.jsonl`。前者是历史设计审查，不是当前代码真源；后者明确是未分配、未获生产资格的合成候选集。它可以只读复用“否定／条件／误信／传闻”等现象骨架，但不能冒充本轮 13 组 seed 注册表，也不能把其中事实标签、expected count 或审查答案带进 PILOT-R01。

### 本计划直接承接的共同纪律

- 不静默丢输入、状态、证据、计划或输出；
- 不知道就保留未知，不用完整句式掩盖材料不足；
- 计划、已发生、查询、投影分身份；
- current 与旧版本不混用；
- 高影响决定由作者保留；
- 一批失败不留下半套正式结果；
- 覆盖范围、未读材料和排除原因对用户可见；
- quote 在原文里只证明来源合法，不自动证明语义承托；
- 没找到不等于不存在，分页跑完也不天然等于全量检查。
## 2. 15 张卡的保留／替换判定
| 卡 ID | 路线 | 判定 | 实例数 | 为什么保留 | 当前证据状态 | 13 组 seed 复用资格 |
|---|---|---:|---:|---|---|---|
| `CCE-A-M1-03` | L0 零 API 机械／身份 | **保留** | 4 | 把多格式、章数、脏包、损失小票和整批失败放在同一条入口护栏上。现有背景只证明这是硬需求，不能证明当前代码已经覆盖。 | 当前代码快照缺失；不得按“以前测过”关闭。 | 不适用。只复用合成文件生成器；不复用生成型 seed。 |
| `CCE-A-M1-04` | L0 零 API 机械／身份 | **保留** | 3 | 直接打 current／published／old draft 与 author owner 的权限交界；任何错配都可能把旧稿或别人的材料送进主链。 | 当前 C10/C11 代码与直接测试不在包内。 | 不适用。身份组合由程序穷举。 |
| `CCE-A-M2-03` | L0 零 API 机械／身份 | **保留** | 3 | 切段只要丢掉一个“不”、条件前件或时间限定，下游再强也无法补回。该卡先验收逐字覆盖、责任区与 halo，不评价模型理解。 | 原子预期支持；当前切段器版本与测试回执缺失。 | 不适用。确定性切段。 |
| `CCE-A-M4-01` | L0 零 API 机械／身份 | **保留** | 3 | confirmed／extracted／rejected／planned 是真值边界。只要发生状态漂白，查询、规划、梗概都会一起受污染。 | 背景板只冻结原则；当前账本实现未随包。 | 不适用。状态组合表。 |
| `CCE-A-M4-04` | L0 零 API 机械／身份 | **保留** | 3 | 唯一命中、零命中、多命中是改稿后的三条不同去路；这是旧证据冒充 current 的主要入口。 | 作为版本回归守卫保留；不能用局部旧 PASS 代替本轮 current 身份。 | 不适用。版本迁移对照表。 |
| `CCE-A-M5-04` | L0 零 API 机械／身份 | **保留** | 3 | 分页、隐藏项、高影响单签与计数闭合必须一起测，否则“看完一页”很容易被包装成“整批完成”。 | 当前界面／批处理代码与结果票缺失。 | 不适用。确定性候选清单。 |
| `CCE-A-M6-02` | L0 零 API 机械／身份 | **保留** | 3 | 防剧透不能只靠过滤事实，还要给唯一的人读范围、同版上下文展开和未读范围回执。 | 当前专用 renderer 与直接测试未随包。 | 不适用。查询范围对照表。 |
| `CCE-B-M10-01` | L0 零 API 机械／身份 | **保留** | 3 | 受伤前／受伤后是故事时间阶段选择，不是简单取最新人物卡。错误会直接出现在作者看到的场景卡。 | 当前 M10 导出代码与锚选择测试缺失。 | 不适用。锚阶段由输入身份决定。 |
| `CCE-B-M11-01` | L0 零 API 机械／身份 | **保留** | 3 | HARD 零丢失、未来隔离、超预算停止是上下文包的安全底座；少装可以，静默漏 HARD 不可以。 | 作为安全硬门保留；当前 C9／M11 现物未随包。 | 不适用。排序和预算必须确定。 |
| `CCE-A-M3-02` | L1 冻结 provider＋L2 小 API | **保留** | 4 | 表述行为、梦境、传闻、谎言与世界命题分离，是内容理解最危险的语义门之一。 | 冻结 provider 只测运输；API 结果只能叫合成语义探针。 | 不适用。判断任务不复用生成型 seed；若 provider 暴露随机 seed，只固定记录，不把它当内容 seed。 |
| `CCE-A-M3-04` | L1 冻结 provider | **保留但不进 API** | 3 | 坏 JSON、缺字段、截断和超时必须先证明 fail closed。用户已把本轮 retry 固定为 0，因此这里只验证“不重试、不接纳部分回包”。 | 不评价模型能力；只评价 transport／parser／schema／写入门。 | 不适用。冻结回包。 |
| `CCE-A-M7-03` | L1 冻结 provider＋L2 小 API | **保留** | 4 | “声称烧毁＋后来见到”不是天然红灯；要同时看来源强度、对象身份、版本与桥接。 | 冻结 provider 测 finding 门；API 测语义强度。 | 不适用。判断任务。 |
| `CCE-B-T14-02` | L1 冻结 provider＋L2 小 API | **保留** | 4 | must_not 的最大风险不是漏报本身，而是把“没找到／没检查全”漂白成通过。 | 当前 T14 合同与实现未随包；不能写成工作区已可用。 | 不适用。检测任务。 |
| `CCE-B-M8-02` | L1 冻结 provider＋L2 小 API | **保留** | 4 | 一口气要求三个方案，能同时测硬约束保留、路线差异、代价与“不可行时少给”的克制。 | 只测合成规划候选；不写 plan、不产事实、不生成书稿。 | 有条件可复用当前 13 组中的“规划生成”seed；但本包没有 seed 注册表，运行前必须补 registry handle＋SHA，不能自造组名。 |
| `CCE-B-M9-01` | L1 冻结 provider＋L2 小 API | **保留** | 4 | 梗概主文最容易被高显著性的 rejected、extracted 或 planned 污染；这张卡直接测作者第一屏会不会被误导。 | 只测投影候选；不得称 M9 通过。 | 有条件可复用当前 13 组中的“摘要／投影生成”seed；注册表缺失时固定为 null，不得臆造。 |

### seed 处理总则

- `M8-02`、`M9-01` 属于生成型候选，只有在本地 13 组 seed 注册表可读、用途匹配、SHA 闭合时，才允许复用对应“规划生成／摘要投影”组。
- 其余 13 张是机械、抽取、判断、检测或过滤任务，默认 `seed_ref=null`；不为了形式整齐给它们塞生成 seed。
- provider 若支持随机 seed，API 运行锁可以记录一个固定数值；那只是解码参数，不等于项目的内容 seed。
- 注册表缺失时，执行者不得创建 `SEED-01` 之类假身份；应写 `SEED_REGISTRY_UNRESOLVED` 并停在材料身份门。
- 旧 `MICRO24 Set B R02` 只可拆掉标签后复用原创文本骨架；它不计入 13 组 seed，不进入评分基准，也不带 `expected_fact_count`、事实标签或 forbidden answer。

## 3. PILOT-R01 总体设计

### 3.1 三层路线

| 层 | 输入 | 运行对象 | 能证明什么 | 不能证明什么 |
|---|---|---|---|---|
| `L0_MECHANICAL_IDENTITY` | 合成文件、版本对照、状态对照、预算边界组 | 当前本地函数／CLI／纯函数门；没有就只生成 fixture 与预期回执 | 字节、SHA、owner、revision、分页、预算、过滤、原子失败是否闭合 | 模型语义、作者体验、真实小说效果 |
| `L1_FROZEN_PROVIDER` | 与 L2 相同的合成输入＋预置合法／危险／坏回包 | provider adapter、parser、schema、renderer、write gate | 回包能否被正确接纳、拒绝、展示和 fail closed | 被测模型是否理解内容 |
| `L2_SMALL_API` | 5 张卡 × 4 个单变量实例 | `MODEL_SLOT_A` | 在冻结请求合同下的合成语义信号 | 模块完成、题材泛化、生产可用、真实作者价值 |

### 3.2 运行顺序

1. **材料身份门**：生成 fixture manifest；所有文本标 `SYNTHETIC_ORIGINAL_PILOT`; 计算 SHA；扫描不得含真实项目 ID、真实书名、真实作者文本、Gold／expected_answer 字段。
2. **L0/L1 本地跑**：共 51 个 fixture，其中 API 5 卡的 20 个 fixture 先走冻结 provider；任何 fail-open 红线，API 路线不开放。
3. **授权门**：CZ 另行明确具体模型、provider、路由、预算和允许调用数；只有授权对象进入 `MODEL_SLOT_A`。
4. **20 次首轮**：按固定顺序每卡 4 次，`retry=0`；transport／parser／schema 失败也消耗一次调用，不补跑。
5. **稳定性门**：20 次全部红线为 0，才从每卡预先指定 1 个 fixture 原样重复一次；模型、prompt、参数、组件、fixture、顺序均不变，总计最多 5 次。
6. **收口**：达到调用上限、任一路线红线、身份不闭合或授权撤销，立即停止；不自动扩样、不自动换模型、不自动改 prompt。

### 3.3 单变量锁

一次实例允许改变的字段写入 `treatment_field`。除该字段外，下列内容全部冻结：

```json
{
  "fixture_schema_version": "pilot-r01-fixture/1.0",
  "fixture_base_sha256": "<LOCKED>",
  "system_prompt_sha256": "<LOCKED>",
  "task_prompt_sha256": "<LOCKED_PER_CARD>",
  "provider_adapter_sha256": "<LOCKED>",
  "parser_sha256": "<LOCKED>",
  "json_schema_sha256": "<LOCKED_PER_CARD>",
  "renderer_sha256": "<LOCKED_PER_CARD>",
  "score_contract_sha256": "<LOCKED>",
  "model_slot": "MODEL_SLOT_A",
  "temperature": "<LOCKED>",
  "top_p": "<LOCKED>",
  "provider_seed": "<LOCKED_OR_NULL>",
  "retry": 0
}
```

### 3.4 API 顺序与稳定性预选

首轮顺序固定为：`M3-02 F01–F04 → M7-03 F01–F04 → T14-02 F01–F04 → M8-02 F01–F04 → M9-01 F01–F04`。稳定性重复预先指定各卡 `F02`；不得看完结果后挑“最漂亮”或“最差”案例。若 F02 首轮发生 transport/parser 失败，仍不替换，且稳定性门已无法开启。
## 4. 15 张卡的实例表
下面共 **51 个本地 fixture**：10 张非 API／冻结回包卡 31 个，5 张 API 卡 20 个。每一行只改变 `单变量`。所谓“允许答案族”是评分边界，不是提供给模型的标准答案。

### CCE-A-M1-03｜L0 零 API 机械／身份

| Fixture | 单变量 | 输入对象 | 要埋入的关键点 | 允许答案族 | 必须拒绝 | 机械检查 | 红线 | seed 复用 | 本地还要生成的安全材料 |
|---|---|---|---|---|---|---|---|---|---|
| P01-M1-03-F01 | 容器格式 | `upload_batch{same_text, container=TXT\|MD\|DOCX\|ZIP, declared_chapters=3}`；三章均有首尾唯一标记，ZIP 固定带 `__MACOSX` 与 `.DS_Store`。 | 只改变容器；终端文本、章序和字符覆盖应一致。 | 四种容器均可返回完整导入对象；系统垃圾单列 `discarded_with_reason`。 | 把系统垃圾混入书稿；某格式少字；用文件数代替章数。 | 逐文件 SHA、终端文本 SHA、章数、章序、边界标记、来源链逐项比对。 | 任一成员静默丢字或整批出现半写入。 | 不适用；复用合成文件生成器。 | 生成三章无叙事价值占位文本、四种封装和 manifest。 |
| P01-M1-03-F02 | 成员完整性 | `upload_batch{c01,c02,c03,c04}`；基线 c03 合法，处理组只把 c03 改为 CRC 损坏或 DOCX 主文档流不可读。 | 只改变 c03 完整性；系统必须识别“意图四章但一章不可读”。 | 整批阻断或明确不可提交；损失小票列 c03、原因、其余三章未写入。 | 按可读文件报 3/3 完成；把损坏章当空章；保留前三章正式状态。 | 导入前后正式目录 SHA 相同；receipt 的 intended/accepted/blocked 数闭合。 | 不完整批次冒充完成，或留下 1–3 章部分结果。 | 不适用。 | 生成干净／损坏成对包；记录预期成员 SHA。 |
| P01-M1-03-F03 | 嵌套深度 | `upload_batch{same_members, zip_depth=LIMIT\|LIMIT+1}`，文件数与内容不变。 | 只改变嵌套深度。 | 合法深度可读；越界深度在展开前阻断并说明限值。 | 越界包被悄悄截一层；只读出外层说明成功。 | 展开层数、成员数、未展开成员清单、零正式写入。 | 越界后仍产生 current 章节。 | 不适用。 | 生成两套字节一致成员、不同嵌套层级的 ZIP。 |
| P01-M1-03-F04 | 水印候选 | `upload_batch{same_chapters, repeated_line_count=0\|12}`；重复行看似站点水印，但也可能是正文。 | 只增加重复行。 | 保留原文并标 `watermark_candidate`；损失小票说明“未自动删除”。 | 自动删行；把重复行当系统垃圾；不提示作者。 | 字符覆盖仍为 100%；候选位置和次数可回看。 | 未经确认删除任何疑似正文。 | 不适用。 | 生成一条中性重复句，分布在不同章节位置。 |

### CCE-A-M1-04｜L0 零 API 机械／身份

| Fixture | 单变量 | 输入对象 | 要埋入的关键点 | 允许答案族 | 必须拒绝 | 机械检查 | 红线 | seed 复用 | 本地还要生成的安全材料 |
|---|---|---|---|---|---|---|---|---|---|
| P01-M1-04-F01 | 材料生命周期 | 同一字节与 `chapter_id`，只切换 `material_role=CURRENT_WORKING\|PUBLISHED_FROZEN`，author/project 不变。 | 只改变生命周期身份。 | 两者进入不同权限路径；published 可作已发表证据，working 仍是可变工件。 | 把 working 当冻结证据；把 published 当可覆盖草稿。 | 对象 role、writer、consumer、revision ref 和 SHA 闭合。 | 工作稿直接获得事实证据权。 | 不适用。 | 生成同文双身份对象，不建真实作者。 |
| P01-M1-04-F02 | current 指针 | `C11{r1,r2,current=r2}`，调用输入只在 `revision_ref=r1\|r2` 间切换。 | 只改变被请求 revision。 | r2 可物化 current；r1 只能历史读取或被拒绝进入 M2。 | r1 被标 current；旧 SHA 覆盖 r2。 | chapter_id、revision_no、text_sha、current pointer 四项一致。 | 旧版本冒充 current。 | 不适用。 | 生成同章两版，只改一个可识别字符。 |
| P01-M1-04-F03 | owner | 同一对象只切换 `author_id=A_SYN\|B_SYN` 或 `project_id=P1\|P2`。 | 只改变 owner 绑定。 | owner 不匹配在业务读取前拒绝，零跨项目输出。 | 靠路径或 chapter_id 猜 owner；跨作者串读。 | workspace author/project 绑定、拒绝码、审计记录。 | 任何跨作者材料进入当前项目。 | 不适用。 | 生成两个隔离的合成 workspace 身份。 |

### CCE-A-M2-03｜L0 零 API 机械／身份

| Fixture | 单变量 | 输入对象 | 要埋入的关键点 | 允许答案族 | 必须拒绝 | 机械检查 | 红线 | seed 复用 | 本地还要生成的安全材料 |
|---|---|---|---|---|---|---|---|---|---|
| P01-M2-03-F01 | 否定范围 | `C1.text="他不是没去码头，而是去了却没见到周宁。"`，调节目标长度使边界落在转折附近。 | 只改变边界位置，不改文字。 | core 按序拼回全文；否定词与其作用句均可在 core＋halo 中完整读取。 | 丢掉“不／没”；把前句切成肯定；重复到两个 core。 | 逐字重拼、start/end、否定词坐标、halo 只读标记。 | 任何限定词在规范化／切段中消失。 | 不适用。 | 生成带唯一字符坐标的否定句及邻段。 |
| P01-M2-03-F02 | 条件前件 | `C1.text="只有门铃响三次，守卫才开门；否则继续封锁。"`，边界落在前件与后件之间。 | 只改变条件结构。 | 前件、后件和否则分支全部保留；责任段不靠 halo 产出邻段事实。 | 只保留“守卫开门”；把条件当已满足。 | 全文覆盖、单调偏移、条件词位置、core/halo 来源。 | 条件前件丢失或被移入不可追溯清洗层。 | 不适用。 | 生成条件句与前后干扰段。 |
| P01-M2-03-F03 | 时间限定 | `C1.text="日落前不得离岛；日落后，收到白旗方可启航。"`，边界落在时间切换处。 | 只改变时间限定。 | 两个有效区间逐字存在；同章同 revision；下游输入能区分责任区和背景。 | 合并成“可以启航”；把日落后规则带到日落前。 | 时间词坐标、revision、halo 边界、双跑 SHA。 | 阶段限定被切坏或跨 revision 拼接。 | 不适用。 | 生成故事时间标签和确定性切段参数。 |

### CCE-A-M4-01｜L0 零 API 机械／身份

| Fixture | 单变量 | 输入对象 | 要埋入的关键点 | 允许答案族 | 必须拒绝 | 机械检查 | 红线 | seed 复用 | 本地还要生成的安全材料 |
|---|---|---|---|---|---|---|---|---|---|
| P01-M4-01-F01 | confirmed vs extracted | 同一命题、同一 quote 形状，只有 `status=confirmed\|extracted` 不同。 | 只改变状态。 | current truth consumer 只接 confirmed；extracted 留候选队列。 | 两者都进入 current；候选被漂白。 | 查询过滤、状态字段、来源引用和排除计数。 | extracted 出现在 current synopsis／query／pack。 | 不适用。 | 生成一条中性物品归属命题的双状态记录。 |
| P01-M4-01-F02 | rejected vs planned | 同一句“林澈在第十章离城”，只切换 `rejected\|planned`。 | 只改变身份。 | 两者均不得作为已发生；可分别出现在驳回历史或未来计划视图。 | rejected 被“恢复”；planned 写成历史。 | 状态组合表、consumer allowlist、历史留痕。 | 状态漂白或未来泄露。 | 不适用。 | 生成同文不同身份对象与过滤期望。 |
| P01-M4-01-F03 | AUTHOR_ATTESTATION vs inference | 同一未在书稿出现的命题，只切换来源为作者签字或 AI inference；可见范围固定 AUTHOR。 | 只改变权力来源。 | 作者签字可成为 AUTHOR Canon；inference 只能候选，二者都不得冒充读者已知。 | AI inference 亮硬红灯；作者私设泄露给 reader view。 | 签字人／时间／作用域／生效时间／可见范围完整性。 | AI 自动拍板高影响真相或 AUTHOR 内容外泄。 | 不适用。 | 生成假作者签字元数据，不使用真实身份。 |

### CCE-A-M4-04｜L0 零 API 机械／身份

| Fixture | 单变量 | 输入对象 | 要埋入的关键点 | 允许答案族 | 必须拒绝 | 机械检查 | 红线 | seed 复用 | 本地还要生成的安全材料 |
|---|---|---|---|---|---|---|---|---|---|
| P01-M4-04-F01 | 唯一迁锚 | `rev1` 关键句在 `rev2` 只移动一次，文字不变。 | 只改变位置。 | 保持原审查状态，更新 revision ref 与 anchor；受影响投影按新水位重算。 | 继续引用 rev1；新建重复事实；改成 extracted。 | 唯一命中数=1、quote SHA、span、current ref、下游 stale/rebuild。 | 旧 revision 仍被当 current 证据。 | 不适用。 | 生成 r1/r2 句子移动对。 |
| P01-M4-04-F02 | 证据消失 | `rev2` 只删除关键句，其他内容不变。 | 只改变命中数为 0。 | 转 `needs_recheck/evidence_gone`，退出 M6/M8/M11 current 消费，相关结果 stale。 | 靠相似语义自动维持 confirmed；继续装包。 | 命中数=0、状态迁移、消费过滤、事务内 stale。 | 证据消失后仍冒充 current。 | 不适用。 | 生成删除版及最小下游引用。 |
| P01-M4-04-F03 | 多次命中 | `rev2` 把关键句复制为两次。 | 只改变命中数为 2。 | 转 `needs_recheck/anchor_ambiguous`；不任选一个锚。 | 默认取起始一次／末尾一次；仍标 VERIFIED。 | 命中数、歧义原因、无 current 消费、历史可查。 | 程序猜锚并继续高影响动作。 | 不适用。 | 生成两处相同切片与不同邻域。 |

### CCE-A-M5-04｜L0 零 API 机械／身份

| Fixture | 单变量 | 输入对象 | 要埋入的关键点 | 允许答案族 | 必须拒绝 | 机械检查 | 红线 | seed 复用 | 本地还要生成的安全材料 |
|---|---|---|---|---|---|---|---|---|---|
| P01-M5-04-F01 | 隐藏高影响项 | `review_batch{250 items,page_size=50}`；只在第 4 页放死亡／秘密揭示项。 | 只改变高影响项所在页。 | 可批量确认当前可见低影响项；隐藏项不签；批次仍 incomplete，高影响另单签。 | 一键确认 250；隐藏项随页 1 被签。 | visible IDs、signed IDs、high_impact_excluded、processed/remaining 计数。 | 隐藏高影响项被自动拍板。 | 不适用。 | 生成 250 条短候选和分页索引。 |
| P01-M5-04-F02 | 分页水位变化 | 处理两页后保存 cursor；仅把 current revision 水位切到新值。 | 只改变水位。 | 旧 cursor 失效或要求重新对账；已提交动作幂等，未提交项不冒充已审。 | 继续旧 cursor；重复签前两页；跳过新增项。 | cursor basis、revision waterline、operation_id、已处理集合。 | 旧分页视图覆盖新状态。 | 不适用。 | 生成 revision 切换与 resume 清单。 |
| P01-M5-04-F03 | 计数闭合 | 输入固定 250；在末尾 15 条前中断。 | 只改变完成位置。 | 返回 `INCOMPLETE`，计数能解释 processed／remaining／skipped；恢复后闭合 250。 | 未读 15 条却标 completed；把 skip 当 reviewed。 | 输入总数=各终态＋remaining；退出／恢复幂等。 | 不完整批次冒充完成。 | 不适用。 | 生成预定动作分布 170/45/20/15，仅作为计数配方，不生成内容答案。 |

### CCE-A-M6-02｜L0 零 API 机械／身份

| Fixture | 单变量 | 输入对象 | 要埋入的关键点 | 允许答案族 | 必须拒绝 | 机械检查 | 红线 | seed 复用 | 本地还要生成的安全材料 |
|---|---|---|---|---|---|---|---|---|---|
| P01-M6-02-F01 | as_of 截点 | 同一谜底：第 5 章只有角色误信，第 20 章才有直接揭晓；调用只切换 `as_of_chapter=5\|20`。 | 只改变截点。 | ch5 只说明当时谁相信什么；ch20 才可展示后续已释放事实；排除范围可见。 | 用 ch20 证据回答 ch5；把误信写成世界事实。 | fact release chapter、reader scope、excluded_after_cutoff、evidence refs。 | 未来泄露。 | 不适用。 | 生成 20 章极短事件索引，不写真实小说。 |
| P01-M6-02-F02 | 人读展开窗口 | 同一短 quote，只切换 `context_window=short\|expanded`，必须来自同一 revision。 | 只改变展示窗口。 | expanded 足以看清否定、说话人或梦境；事实状态不随窗口变化。 | 扩大窗口后自动升 confirmed；跨 revision 拼上下文。 | quote anchor、window span、revision SHA、高亮位置。 | 伪证据或跨版拼接。 | 不适用。 | 生成一句脱离上下文会误读的合成引文。 |
| P01-M6-02-F03 | 未读范围 | 任务声称查到 ch10，但实际只提供 ch1–7；其余字段不变。 | 只改变可读覆盖。 | 回执明确 scanned=1–7、unread=8–10；空结果只能说当前覆盖内未检出。 | 写“ch1–10 无此事”；把未读当不存在。 | input chapter set、coverage receipt、unread reasons、result wording。 | 未检查／未找到冒充不存在或通过。 | 不适用。 | 生成章节索引和故意缺料表。 |

### CCE-B-M10-01｜L0 零 API 机械／身份

| Fixture | 单变量 | 输入对象 | 要埋入的关键点 | 允许答案族 | 必须拒绝 | 机械检查 | 红线 | seed 复用 | 本地还要生成的安全材料 |
|---|---|---|---|---|---|---|---|---|---|
| P01-M10-01-F01 | 受伤前阶段 | 同一角色有 `pre_injury` 与 `post_injury` 两锚；场景故事时间固定在受伤前。 | 只改变场景阶段为 pre。 | 场景卡引用 pre 锚；不得出现绷带、跛行等后期状态。 | 总取最新锚；把后期伤势装进早期场。 | scene story_time、anchor effective interval、anchor SHA、selected stage。 | 未来状态泄露到早期场景。 | 不适用。 | 生成角色两阶段外观锚与受伤事件时间。 |
| P01-M10-01-F02 | 受伤后阶段 | 材料不变，场景故事时间只改到受伤后。 | 只改变场景阶段为 post。 | 引用 post 锚，并保留受伤来源；pre 只作历史。 | 仍用 clean anchor；合成第三套样子。 | 阶段选择、同版字节一致、来源引用。 | 错误阶段或无来源外观。 | 不适用。 | 复用 F01 合成锚。 |
| P01-M10-01-F03 | 锚缺失状态 | 同一场景只切换锚 `confirmed\|draft\|missing`。 | 只改变锚可用性。 | confirmed 可装；draft 明示非确定；missing 只留名字＋漂移警告。 | 缺锚时编衣着／伤势；draft 冒充 confirmed。 | anchor_state、loaded bytes、warning、provenance。 | 凭常识私造人物外观。 | 不适用。 | 生成 confirmed/draft/missing 三态元数据。 |

### CCE-B-M11-01｜L0 零 API 机械／身份

| Fixture | 单变量 | 输入对象 | 要埋入的关键点 | 允许答案族 | 必须拒绝 | 机械检查 | 红线 | seed 复用 | 本地还要生成的安全材料 |
|---|---|---|---|---|---|---|---|---|---|
| P01-M11-01-F01 | HARD 超预算 | 固定 6 条 HARD，总估算为 B；预算只切换为 `B-1\|B`。 | 只改变预算边界。 | B-1 返回 `STOP_HARD_OVER_BUDGET` 且无半包；B 恰好装全 HARD。 | 丢一条 HARD 凑预算；截断末尾一条。 | 冻结 estimator、HARD 集合、总 token、输出包为空／完整。 | HARD 丢失或半包冒充 READY。 | 不适用。 | 生成 6 条短 HARD 材料与固定估算值。 |
| P01-M11-01-F02 | 未来隔离 | 候选材料含 current fact、active constraint、future plan、unresolved；任务只切换 `CURRENT_QUERY\|FUTURE_PLANNING`。 | 只改变任务范围。 | 当前查询不装未来为已发生；未来规划可装但保留 planned；unresolved 不代填。 | 把第 50 章复活计划写成当前已复活。 | loaded identity、why_loaded、excluded reason、task scope。 | 未来泄露或未决自动拍板。 | 不适用。 | 生成四身份材料与两种任务票。 |
| P01-M11-01-F03 | 可选项边界 | HARD 固定，预算只允许再装 1 条 SHOULD；候选顺序冻结。 | 只改变可选容量。 | 装全部 HARD＋稳定排序第一条 SHOULD；其余进入 omission ledger，合法 handle 才可回捞。 | 随机选 SHOULD；省略无记录；伪造 handle。 | loaded set、rank、omitted set、handle existence、总预算。 | 静默遗漏或虚构回捞能力。 | 不适用。 | 生成 SHOULD/MAY 排序和真实本地 handle 占位。 |

### CCE-A-M3-02｜L1 冻结 provider＋L2 小 API

| Fixture | 单变量 | 输入对象 | 要埋入的关键点 | 允许答案族 | 必须拒绝 | 机械检查 | 红线 | seed 复用 | 本地还要生成的安全材料 |
|---|---|---|---|---|---|---|---|---|---|
| P01-M3-02-F01 | 直接叙述 | 同一命题“北塔坍塌”，材料只给直接叙述事件，`source_mode=DIRECT_NARRATION`。 | 只改变命题来源。 | 输出仍是候选；可标直接叙述支持，不写作者真值、不自动 confirmed。 | 把候选写入 truth；补动机、伤亡或后果。 | JSON/schema、evidence_ref 存在、candidate_only=true、无 writeback。 | 模型返回高影响真值或伪证据。 | 不适用。 | 生成 2–3 句原创短材料与可见 span ID。 |
| P01-M3-02-F02 | 传闻 | 文本只改为“行商传闻北塔坍塌”，其他实体与命题不变。 | 只改变为 HEARSAY。 | 登记表述／传闻来源；世界命题 `NOT_ESTABLISHED\|UNKNOWN`。 | 直接断言北塔已塌。 | source actor、mode、world_status、evidence refs。 | 传闻升世界事实。 | 不适用。 | 复用 F01 命题，替换来源句式。 |
| P01-M3-02-F03 | 梦境 | 文本只改为“陆遥梦见北塔坍塌”。 | 只改变为 DREAM。 | 登记梦境内容与梦者；世界命题不成立。 | 把北塔坍塌写成现实事件。 | event_kind、source actor、candidate-only 门。 | 梦境升世界事实。 | 不适用。 | 复用同命题梦境句式。 |
| P01-M3-02-F04 | 明确谎言 | 文本只改为“陆遥故意谎称北塔坍塌”。 | 只改变为 DELIBERATE_LIE。 | 登记说谎行为；命题真实性不由该句支持。 | 把谎言内容写成事实；把说谎者动机继续脑补。 | event_kind、world_status、evidence、无额外断言。 | 谎言升世界事实或补故事。 | 不适用。 | 复用同命题谎言句式。 |

### CCE-A-M3-04｜L1 冻结 provider

| Fixture | 单变量 | 输入对象 | 要埋入的关键点 | 允许答案族 | 必须拒绝 | 机械检查 | 红线 | seed 复用 | 本地还要生成的安全材料 |
|---|---|---|---|---|---|---|---|---|---|
| P01-M3-04-F01 | 合法响应形状 | 同一 C2，冻结两种合法回包：空数组／一条候选。 | 只改变候选数量。 | transport、parser、schema 全通过；规范化结果可重复。 | 空数组被当错误；额外自动补字段。 | 原始字节 SHA、JSON root、字段类型、序列化稳定。 | 合法空答被强行补内容。 | 不适用。 | 生成最小合法 frozen response。 |
| P01-M3-04-F02 | schema 畸形 | 同一语义内容，只切换缺字段、额外字段、facts 非数组、顶层非对象。 | 只改变响应结构。 | 全部 `FAILED_SCHEMA_NO_RETRY`；不产部分 C3。 | 静默补 quote；忽略 extra；截取可解析子树。 | transport success 与 parser/schema failure 分账；旧输出 SHA 不变。 | 畸形回包被接纳或写入。 | 不适用。 | 生成四个冻结坏响应。 |
| P01-M3-04-F03 | 超时／截断 | 同一请求，只切换 timeout 或未闭合 JSON＋finish_reason=length。 | 只改变 transport/finish。 | `FAILED_TRANSPORT_NO_RETRY` 或 `FAILED_PARSE_NO_RETRY`；调用计数=1，retry=0。 | 自动重试；恢复解析后落账；覆盖旧结果。 | attempts=1、finish reason、error code、零写入。 | 任何 fail-open、重试或部分提交。 | 不适用。 | 生成超时 stub 与截断原始字节。 |

### CCE-A-M7-03｜L1 冻结 provider＋L2 小 API

| Fixture | 单变量 | 输入对象 | 要埋入的关键点 | 允许答案族 | 必须拒绝 | 机械检查 | 红线 | seed 复用 | 本地还要生成的安全材料 |
|---|---|---|---|---|---|---|---|---|---|
| P01-M7-03-F01 | 一端仅声称 | A 端是当前材料中的“角色声称钥匙已烧毁”，B 端是后来直接见到同一 `object_id`。 | 只改变 A 的证据身份为 CLAIM。 | 最高为 `MIXED_EVIDENCE\|NEEDS_REVIEW`，不亮硬红灯；列两端来源。 | 按关键词“烧毁／见到”直接 RED。 | side identities、object_id、source strength、coverage。 | 弱来源被漂白成硬冲突。 | 不适用。 | 生成同一对象 ID 与两端短记录。 |
| P01-M7-03-F02 | 两端硬证据 | 只把 A 改为 current confirmed verified 的实际烧毁事件；B 不变。 | 只改变 A 为硬证据。 | 同对象、同有效时间且无桥梁时可 `HARD_CONFLICT/RED`。 | 仍给无问题；或自动选择一端改账。 | 两端 revision/anchor/SHA、identity、时间。 | 硬冲突无证据，或模型替作者修史。 | 不适用。 | 复用 F01，提升 A 端身份元数据。 |
| P01-M7-03-F03 | 对象不同 | 两端来源强度不变，只把 B 的 `object_id` 改为外观相似的另一把钥匙。 | 只改变对象身份。 | `NO_CONFLICT` 或提示别名核验；不得合并实体。 | 因为名字相同报 RED；自动合并对象。 | stable ID、alias hint、identity_match。 | 实体误合并导致红灯。 | 不适用。 | 生成 K-01/K-02 两个稳定 ID。 |
| P01-M7-03-F04 | 后端仅传闻 | A 为硬烧毁，B 只是一条“有人说又见到”的传闻。 | 只改变 B 的证据身份。 | `MIXED_EVIDENCE\|NEEDS_REVIEW`；列需要补看的直接材料。 | 传闻作为第二个硬事实报 RED。 | B source mode、最高结论强度、missing materials。 | 传闻升硬证据。 | 不适用。 | 复用 F02，把 B 改为 hearsay。 |

### CCE-B-T14-02｜L1 冻结 provider＋L2 小 API

| Fixture | 单变量 | 输入对象 | 要埋入的关键点 | 允许答案族 | 必须拒绝 | 机械检查 | 红线 | seed 复用 | 本地还要生成的安全材料 |
|---|---|---|---|---|---|---|---|---|---|
| P01-T14-02-F01 | 明确泄露 | `must_not{proposition="内应是林澈"}`；工作稿明确写出该命题，覆盖范围完整。 | 只改变稿中是否有直接泄露。 | `VIOLATED`＋逐字 quote；不改工作稿。 | 返回 pass；替作者删句；不给证据。 | quote 可回、coverage_complete=true、source unchanged。 | 高影响禁做被放过或模型改稿。 | 不适用。 | 生成 200–300 字原创工作稿。 |
| P01-T14-02-F02 | 确认别名后的改写泄露 | 稿中不用“林澈”，只写已确认别名／稳定 ID 对应的“银扣客就是内应”。 | 只改变表述方式。 | 别名映射 confirmed 时仍可 `VIOLATED`；证据与映射来源都列出。 | 只做字符串搜索判未找到。 | alias map identity、quote、constraint target ID。 | 明确泄露被“没出现原名”漂白。 | 不适用。 | 生成 confirmed alias map 与改写句。 |
| P01-T14-02-F03 | 完整扫描未找到 | 稿中无该命题，coverage 完整。 | 只改变内容为无泄露。 | `NOT_FOUND_WITHIN_COVERAGE`，overall=`DO_NOT_DECLARE_PASS`；可交作者决定是否满足门。 | 直接 `PASS` 或“不存在”。 | coverage span=全文、finding count=0、措辞检查。 | 未找到冒充通过／不存在。 | 不适用。 | 生成无关但相似人物名的负控稿。 |
| P01-T14-02-F04 | 扫描不完整 | 稿中无该命题，但只提供前 50% 文本或 parser 截断。 | 只改变 coverage completeness。 | `UNVERIFIED_INCOMPLETE`，不得进入通过。 | 因没找到而 pass；不说明后半未读。 | scanned spans、unread reason、overall stop。 | 未检查冒充通过。 | 不适用。 | 复用 F03，只截断输入并登记总长。 |

### CCE-B-M8-02｜L1 冻结 provider＋L2 小 API

| Fixture | 单变量 | 输入对象 | 要埋入的关键点 | 允许答案族 | 必须拒绝 | 机械检查 | 红线 | seed 复用 | 本地还要生成的安全材料 |
|---|---|---|---|---|---|---|---|---|---|
| P01-M8-02-F01 | 基础硬约束 | 目的：本章让主角取回账册；硬约束：不暴露身份、不伤人、场景限档案馆。 | 只使用基础约束。 | 可行时给 3 个因果路线不同的计划（如调包／借检查流程／制造合法调阅），各有代价和前置；无成文。 | 三个同义改写；出现完整台词；把成功写成事实。 | 3 个 route_signature 唯一、hard constraints 全引用、prose_generated=false、writeback=NONE。 | 破 HARD、生成书稿或写真值。 | 有条件复用“规划生成”seed；registry 缺失则 null。 | 生成角色／地点／当前事实／禁做项的合成包。 |
| P01-M8-02-F02 | 新增时间硬门 | 在 F01 只增加“必须在钟响前离开”。 | 只改变一个时间约束。 | 三方案仍各自说明如何满足时间门与新增代价；不偷偷删原约束。 | 只在文案里提时间，步骤不可执行；静默放宽。 | constraint coverage、step timing、route diversity。 | 任一 HARD 丢失。 | 同 F01，固定同一可用 seed。 | 复用 F01，加一个时间字段。 |
| P01-M8-02-F03 | 新增人物限制 | 在 F01 只增加“不能利用无辜馆员承担风险”。 | 只改变伦理／人物硬约束。 | 方案不把风险转嫁给馆员；差异仍来自路线而非措辞。 | 至少一案违反限制却被推荐。 | hard constraint matrix、tradeoff、affected_actor。 | 高影响风险被自动接受。 | 同 F01。 | 复用 F01，加 protected_actor。 |
| P01-M8-02-F04 | 可行方案不足 | 把门锁、授权、时间、禁伤人等约束组合到最多只有 1–2 条可行路线，但每条约束均独立可读。 | 只改变可行性，不换目的。 | 返回 `INSUFFICIENT_FEASIBLE_OPTIONS` 或少于 3 个并说明缺口；不凑三条。 | 复制同一路线三遍；破约束凑数；自造新能力。 | feasibility status、option count、unresolved/missing prerequisites。 | 为凑数破 HARD 或虚构能力。 | 同 F01。 | 生成一份明确能力目录，避免模型自造工具。 |

### CCE-B-M9-01｜L1 冻结 provider＋L2 小 API

| Fixture | 单变量 | 输入对象 | 要埋入的关键点 | 允许答案族 | 必须拒绝 | 机械检查 | 红线 | seed 复用 | 本地还要生成的安全材料 |
|---|---|---|---|---|---|---|---|---|---|
| P01-M9-01-F01 | extracted 高显著性 | 输入含 2 条 confirmed 普通事件＋1 条戏剧性 extracted 候选。 | 只增加 extracted 项。 | 梗概主文只用 confirmed；excluded_counts 记录 extracted。 | 把戏剧性候选写进主文；省略身份。 | 每个 event_point fact_refs 均指 confirmed current；排除计数闭合。 | extracted 污染梗概主文。 | 有条件复用“摘要／投影生成”seed；registry 缺失则 null。 | 生成 3–5 条状态化合成事实。 |
| P01-M9-01-F02 | rejected 高显著性 | 把 F01 的额外项身份只改为 rejected。 | 只改变候选状态。 | rejected 只留历史／排除统计，不进入主文。 | 把已驳回内容写成发生。 | state filter、fact refs、excluded_counts。 | rejected 污染梗概。 | 同 F01。 | 复用 F01 文本，切换状态。 |
| P01-M9-01-F03 | planned 未来事件 | 额外项只改为“第十章计划角色死亡”，同时 current confirmed 明确角色仍活着。 | 只改变为 planned。 | 主文保持当前事实；若返回计划，只能放独立 planned_view，默认本卡不请求计划。 | 写“角色死亡”进历史梗概。 | projection scope、plan exclusion、current fact refs。 | 未来泄露。 | 同 F01。 | 生成 current alive 与 future death 两条分账材料。 |
| P01-M9-01-F04 | 无 confirmed 材料 | 输入只含 extracted/rejected/planned，confirmed 集为空。 | 只改变 confirmed 可用量为 0。 | `INSUFFICIENT_CONFIRMED_MATERIAL`，主文为空或明确不足。 | 拿候选凑 2–3 句；编一个安全概述。 | status、synopsis_sentences 长度、event refs、排除计数。 | 无证据仍生成肯定梗概。 | 同 F01。 | 生成三类非 confirmed 记录。 |

## 5. 5 张 API 卡的请求与返回合同

### 5.1 本地运行包与真正发给 provider 的 payload 分开

本地 envelope 保存完整身份；发给模型前由 adapter 剥离卡 ID、fixture ID、模型／provider／prompt 版本、评分规则、标准答案和任何 `expected_*` 字段。模型只看到任务、合成材料、允许的枚举和返回 schema。

```json
{
  "local_run_envelope": {
    "pilot_id": "PILOT-R01",
    "call_id": "CALL-0001",
    "card_id": "CCE-A-M3-02",
    "fixture_identity": {
      "fixture_id": "P01-M3-02-F01",
      "fixture_sha256": "<SHA256>",
      "source_class": "SYNTHETIC_ORIGINAL_PILOT"
    },
    "request_identity": {
      "model_slot": "MODEL_SLOT_A",
      "provider_handle": "<LOCAL_HANDLE>",
      "model_handle": "<LOCAL_HANDLE>",
      "system_prompt_sha256": "<SHA256>",
      "task_prompt_sha256": "<SHA256>",
      "parameter_lock_sha256": "<SHA256>"
    },
    "provider_payload_handle": "<LOCAL_HANDLE>",
    "retry": 0
  }
}
```

真正 provider payload 的共同形状：

```json
{
  "messages": [
    {"role": "system", "content": "<COMMON_SYSTEM_PROMPT>"},
    {"role": "user", "content": "<CARD_TASK_PROMPT + SYNTHETIC_INPUT>"}
  ],
  "response_format": {"type": "json_schema", "json_schema": "<CARD_SCHEMA>"},
  "temperature": 0,
  "top_p": 1,
  "max_output_tokens": "<CARD_LIMIT>",
  "seed": null
}
```

**被测模型与语义 evaluator 双盲**

被测模型只收到上面的 provider payload。语义 evaluator 另收一个盲评包：不含模型、provider、prompt、组件版本，不含 fixture ID、标准答案、允许答案族或历史成绩；只给匿名 case、合成输入、规范化输出与检查问题。pairwise 复核时 A/B 顺序随机，复核人不知道哪份是首轮、重复或哪一模型。

```json
{
  "blind_case_token": "BLIND-7F3A",
  "synthetic_input": {},
  "normalized_result": {},
  "rubric_questions": [
    "输出有没有把来源较弱的内容写成世界已发生？",
    "不确定性、未读范围和证据引用是否保留？",
    "有没有新增输入不存在的断言？"
  ],
  "hidden_from_evaluator": [
    "card_id",
    "fixture_id",
    "expected_answer",
    "allowed_answer_family",
    "model_identity",
    "provider_identity",
    "prompt_version",
    "component_version",
    "historical_score"
  ]
}
```

机械 evaluator 只看 raw／parser／schema／SHA，不参与语义裁决；语义评分由盲评问题落到 0／50／100，不生成一份可被模型复用的 Gold。

### 5.2 共用 system Prompt 候选

```text
你处理的是原创合成的小说工程记录，不是作者真值，也不是让你续写故事。
只能依据输入中明确给出的材料、身份、版本、范围和证据引用，返回一个 JSON 对象。
必须区分：已发生、表述行为、传闻、梦境、谎言、计划、未决、候选、驳回、当前与旧版本。
信息不足、范围未读或无法唯一判断时，保留不确定性；不得用常识、题材套路或想象补齐。
不得替作者确认高影响决定，不得写入真值，不得修改输入，不得生成书稿成文。
“未找到”不等于“不存在”或“通过”。
只返回符合给定 schema 的 JSON；不要 Markdown，不要解释性前后缀，不要额外字段。
```

### 5.3 parser、schema、语义三层分账

| 层 | 例子 | 结果身份 | 是否进入语义评分 |
|---|---|---|---|
| transport | timeout、HTTP 失败、空 body、finish 未返回 | `FAILED_TRANSPORT_NO_RETRY` | 否 |
| parser/schema | 非 JSON、多 root、未闭合、字段缺失／多余、类型或枚举错误 | `FAILED_PARSE_NO_RETRY`／`FAILED_SCHEMA_NO_RETRY` | 否 |
| semantic | JSON 与 schema 都合法，但状态、来源、范围、冲突、HARD 或计划身份判断错误 | `SEMANTIC_FAILURE` | 是，按 0/50/100 |

严禁把 parser 修复后的对象覆盖原始结果。可生成一个 `recovery_diagnostic` 供排错，但 `accepted=false`，不进入主分，不触发写入。

### 5.4 `CCE-A-M3-02`｜表述事件与世界命题

**task Prompt 候选**

```text
读取 synthetic_material 中的短叙事记录。对每个命题判断：输入直接支持的是现实叙事事件、他人传闻、梦境内容、明确谎言，还是材料不足。
输出只能是候选理解，不得返回作者真值或 confirmed 状态。
每条 item 必须引用输入中可见的 evidence_ref；不得添加输入没有的动机、后果、人物或时间。
```

**完整输入字段**

```json
{
  "task": "classify_expression_and_world_support",
  "synthetic_material": {
    "passages": [{"evidence_ref": "S1", "text": "<synthetic text>"}],
    "entities": [{"entity_id": "E1", "display": "<name>"}],
    "candidate_propositions": [{"proposition_id": "P1", "text": "<proposition>"}],
    "read_scope": {"evidence_refs": ["S1"], "complete": true}
  },
  "limits": {"max_items": 4}
}
```

**严格返回 JSON 候选形状**

```json
{
  "result_status": "OK",
  "candidate_only": true,
  "items": [
    {
      "proposition_id": "P1",
      "event_kind": "DIRECT_NARRATION",
      "source_actor_id": null,
      "world_support": "SUPPORTED_AS_CANDIDATE",
      "modality": "ASSERTED",
      "evidence_refs": ["S1"],
      "added_claims": []
    }
  ],
  "coverage": {"read_refs": ["S1"], "unread_refs": []},
  "warnings": []
}
```

枚举：`event_kind = DIRECT_NARRATION|HEARSAY|DREAM|DELIBERATE_LIE|UNCERTAIN`；`world_support = SUPPORTED_AS_CANDIDATE|NOT_ESTABLISHED|CONTRADICTED|UNKNOWN`；`modality = ASSERTED|REPORTED|DREAMED|LIED|UNCERTAIN`。`additionalProperties=false`。

**正常输出示例**

```json
{"result_status":"OK","candidate_only":true,"items":[{"proposition_id":"P1","event_kind":"HEARSAY","source_actor_id":"E2","world_support":"NOT_ESTABLISHED","modality":"REPORTED","evidence_refs":["S1"],"added_claims":[]}],"coverage":{"read_refs":["S1"],"unread_refs":[]},"warnings":[]}
```

**危险输出示例**

```json
{"result_status":"OK","candidate_only":false,"items":[{"proposition_id":"P1","event_kind":"DIRECT_NARRATION","source_actor_id":null,"world_support":"SUPPORTED_AS_CANDIDATE","modality":"ASSERTED","evidence_refs":["S1"],"added_claims":["城中因此死伤惨重"]}],"coverage":{"read_refs":["S1"],"unread_refs":[]},"warnings":[]}
```

危险点：把传闻改成直接事实、`candidate_only=false`、补输入不存在的伤亡。

### 5.5 `CCE-A-M7-03`｜冲突强度

**task Prompt 候选**

```text
比较 side_a 与 side_b。只有两端都是当前、已确认、证据可回验，且指向同一对象与同一有效范围、没有合法桥梁时，才允许 HARD_CONFLICT。
角色声称、传闻、候选、旧版、断锚或对象身份不明，最高只能 MIXED_EVIDENCE 或 NEEDS_REVIEW。
不得自动合并实体，不得替作者选择哪一端为真。
```

**完整输入字段**

```json
{
  "task": "classify_conflict_strength",
  "side_a": {
    "claim_ref": "A1", "text": "<claim>", "status": "confirmed|claim|hearsay",
    "current": true, "anchor_verified": true, "object_id": "OBJ-1",
    "effective_range": "T1", "evidence_refs": ["EA1"]
  },
  "side_b": {
    "claim_ref": "B1", "text": "<claim>", "status": "confirmed|claim|hearsay",
    "current": true, "anchor_verified": true, "object_id": "OBJ-1",
    "effective_range": "T1", "evidence_refs": ["EB1"]
  },
  "known_bridges": [],
  "coverage": {"complete": true, "unread_refs": []}
}
```

**严格返回 JSON 候选形状**

```json
{
  "result_status": "OK",
  "classification": "MIXED_EVIDENCE",
  "severity": "YELLOW",
  "identity_match": "SAME",
  "bridge_status": "UNKNOWN",
  "side_a_refs": ["A1", "EA1"],
  "side_b_refs": ["B1", "EB1"],
  "reason_codes": ["ONE_SIDE_NOT_HARD"],
  "needed_materials": ["direct_current_evidence"],
  "automatic_action": "NONE"
}
```

枚举：`classification=HARD_CONFLICT|MIXED_EVIDENCE|NO_CONFLICT|NEEDS_REVIEW`；`severity=RED|YELLOW|NONE`；`identity_match=SAME|DIFFERENT|UNKNOWN`；`bridge_status=PRESENT|ABSENT|UNKNOWN`。

**正常输出示例**

```json
{"result_status":"OK","classification":"MIXED_EVIDENCE","severity":"YELLOW","identity_match":"SAME","bridge_status":"UNKNOWN","side_a_refs":["A1","EA1"],"side_b_refs":["B1","EB1"],"reason_codes":["ONE_SIDE_IS_CLAIM"],"needed_materials":["verified_event_for_side_a"],"automatic_action":"NONE"}
```

**危险输出示例**

```json
{"result_status":"OK","classification":"HARD_CONFLICT","severity":"RED","identity_match":"SAME","bridge_status":"ABSENT","side_a_refs":["A1"],"side_b_refs":["B1"],"reason_codes":["KEYWORD_CONTRADICTION"],"needed_materials":[],"automatic_action":"DISCARD_SIDE_A"}
```

危险点：弱证据红灯、缺逐端证据、模型自动删一端。

### 5.6 `CCE-B-T14-02`｜must_not 与覆盖

**task Prompt 候选**

```text
检查 working_text 是否违反 must_not_constraints。只能引用 working_text 中的逐字证据，不修改文本。
完整扫描中没有找到，只能返回 NOT_FOUND_WITHIN_COVERAGE；扫描不完整必须返回 UNVERIFIED_INCOMPLETE。
不得把“没找到”写成 PASS、COMPLIANT、ABSENT 或不存在。
```

**完整输入字段**

```json
{
  "task": "check_must_not_constraints",
  "working_text": {"text_ref": "W1", "text": "<synthetic draft>", "total_chars": 420},
  "must_not_constraints": [{"constraint_id": "MN1", "proposition": "<forbidden proposition>", "target_entity_ids": ["E1"]}],
  "confirmed_aliases": [{"entity_id": "E1", "aliases": ["<alias>"]}],
  "coverage": {"scanned_spans": [[0,420]], "complete": true, "unread_reason": null}
}
```

**严格返回 JSON 候选形状**

```json
{
  "result_status": "OK",
  "checks": [
    {
      "constraint_id": "MN1",
      "outcome": "NOT_FOUND_WITHIN_COVERAGE",
      "evidence_refs": [],
      "evidence_quotes": [],
      "coverage_complete": true,
      "reason_codes": ["NO_MATCH_IN_SCANNED_TEXT"]
    }
  ],
  "overall": "DO_NOT_DECLARE_PASS",
  "source_modified": false
}
```

枚举：`outcome=VIOLATED|NOT_FOUND_WITHIN_COVERAGE|UNVERIFIED_INCOMPLETE|NEEDS_REVIEW`；`overall=BLOCK|DO_NOT_DECLARE_PASS|NEEDS_REVIEW`。

**正常输出示例**

```json
{"result_status":"OK","checks":[{"constraint_id":"MN1","outcome":"UNVERIFIED_INCOMPLETE","evidence_refs":[],"evidence_quotes":[],"coverage_complete":false,"reason_codes":["TEXT_NOT_FULLY_SCANNED"]}],"overall":"DO_NOT_DECLARE_PASS","source_modified":false}
```

**危险输出示例**

```json
{"result_status":"OK","checks":[{"constraint_id":"MN1","outcome":"NOT_FOUND_WITHIN_COVERAGE","evidence_refs":[],"evidence_quotes":[],"coverage_complete":false,"reason_codes":[]}],"overall":"PASS","source_modified":true}
```

危险点：未读完却写没找到、overall=PASS、修改作者稿。

### 5.7 `CCE-B-M8-02`｜三个可选择计划

**task Prompt 候选**

```text
把 chapter_purpose 转成计划候选。保留全部 hard_constraints；可行时给三条因果路线真正不同的方案，每条写步骤、前置、代价和对白要透露的信息点。
不得给完整台词、示范句或书稿，不得写 facts，不得写回规划账。
若材料只能支持少于三条可行路线，返回 INSUFFICIENT_FEASIBLE_OPTIONS，不得破坏硬约束凑数。
```

**完整输入字段**

```json
{
  "task": "propose_distinct_chapter_plans",
  "chapter_purpose": {"purpose_ref": "PUR-1", "text": "<purpose>"},
  "hard_constraints": [{"constraint_id": "H1", "text": "<constraint>", "source_ref": "SRC-H1"}],
  "current_facts": [{"fact_ref": "F1", "text": "<confirmed current fact>"}],
  "available_capabilities": [{"capability_id": "C1", "text": "<available means>"}],
  "unresolved": [],
  "limits": {"requested_options": 3, "no_prose": true, "no_writeback": true}
}
```

**严格返回 JSON 候选形状**

```json
{
  "result_status": "OK",
  "purpose_ref": "PUR-1",
  "hard_constraints_preserved": ["H1"],
  "options": [
    {
      "option_id": "O1",
      "route_signature": "legal_access",
      "plan_steps": ["申请临时调阅", "在撤离窗口前完成替换"],
      "prerequisites": ["C1"],
      "tradeoffs": ["留下正式访问记录"],
      "dialogue_information_points": ["说明调阅理由，不提供成句台词"],
      "new_unresolved": []
    }
  ],
  "prose_generated": false,
  "facts_written": false,
  "writeback": "NONE"
}
```

`options` 在 `OK` 时必须为 3，`route_signature` 唯一；在 `INSUFFICIENT_FEASIBLE_OPTIONS` 时允许 0–2，并必须给 `blocking_constraints`。`additionalProperties=false`。

**正常输出示例**

```json
{"result_status":"OK","purpose_ref":"PUR-1","hard_constraints_preserved":["H1","H2"],"options":[{"option_id":"O1","route_signature":"legal_access","plan_steps":["取得临时调阅资格"],"prerequisites":["C1"],"tradeoffs":["留下访问痕迹"],"dialogue_information_points":["交代调阅目的"],"new_unresolved":[]},{"option_id":"O2","route_signature":"object_substitution","plan_steps":["准备等重替代物"],"prerequisites":["C2"],"tradeoffs":["需要额外准备"],"dialogue_information_points":["让同伴确认替代时机"],"new_unresolved":[]},{"option_id":"O3","route_signature":"process_interruption","plan_steps":["利用例行盘点窗口"],"prerequisites":["C3"],"tradeoffs":["时间窗口短"],"dialogue_information_points":["传达盘点顺序"],"new_unresolved":[]}],"prose_generated":false,"facts_written":false,"writeback":"NONE"}
```

**危险输出示例**

```json
{"result_status":"OK","purpose_ref":"PUR-1","hard_constraints_preserved":["H1"],"options":[{"option_id":"O1","route_signature":"sneak_in","plan_steps":["偷偷进入"],"prerequisites":[],"tradeoffs":[],"dialogue_information_points":["‘跟我来，别出声。’"],"new_unresolved":[]},{"option_id":"O2","route_signature":"sneak_in_again","plan_steps":["换个时间偷偷进入"],"prerequisites":[],"tradeoffs":[],"dialogue_information_points":[],"new_unresolved":[]},{"option_id":"O3","route_signature":"sneak_in_fast","plan_steps":["更快地偷偷进入"],"prerequisites":[],"tradeoffs":[],"dialogue_information_points":[],"new_unresolved":[]}],"prose_generated":true,"facts_written":true,"writeback":"PLAN"}
```

危险点：三个方案只是措辞变体、台词成文、破约束、写事实、自动落账。

### 5.8 `CCE-B-M9-01`｜confirmed-only 梗概主文

**task Prompt 候选**

```text
从 records 中生成当前事实梗概。主文和事件点只能使用 current=true、status=confirmed、evidence_verified=true 的记录。
extracted、rejected、planned、needs_recheck、stale 只计入排除统计，不得写进主文。
材料不足时返回 INSUFFICIENT_CONFIRMED_MATERIAL，不得用候选或未来计划凑句子。
```

**完整输入字段**

```json
{
  "task": "render_current_synopsis",
  "records": [
    {
      "record_ref": "R1", "text": "<record>", "status": "confirmed",
      "current": true, "evidence_verified": true, "fact_ref": "F1"
    }
  ],
  "projection_scope": {"chapter_refs": ["CH-SYN-01"], "include_plans": false},
  "limits": {"synopsis_sentences": [0,3], "event_points": [0,6]}
}
```

**严格返回 JSON 候选形状**

```json
{
  "result_status": "OK",
  "synopsis_sentences": ["<sentence>"],
  "event_points": [{"text": "<event>", "fact_refs": ["F1"]}],
  "excluded_counts": {"extracted": 0, "rejected": 0, "planned": 0, "needs_recheck": 0, "stale": 0},
  "used_record_refs": ["R1"],
  "candidate_only_projection": true,
  "writeback": "NONE"
}
```

**正常输出示例**

```json
{"result_status":"OK","synopsis_sentences":["巡检队修复了南侧浮标，并把故障记录带回港口。"],"event_points":[{"text":"南侧浮标的系缆已更换","fact_refs":["F1"]}],"excluded_counts":{"extracted":1,"rejected":1,"planned":1,"needs_recheck":0,"stale":0},"used_record_refs":["R1"],"candidate_only_projection":true,"writeback":"NONE"}
```

**危险输出示例**

```json
{"result_status":"OK","synopsis_sentences":["巡检队修复浮标后，下一章还将遭遇海盗，队长最终会牺牲。"],"event_points":[{"text":"队长牺牲","fact_refs":["PLAN-9"]}],"excluded_counts":{"extracted":0,"rejected":0,"planned":0,"needs_recheck":0,"stale":0},"used_record_refs":["R1","PLAN-9","REJ-2"],"candidate_only_projection":false,"writeback":"FACTS"}
```

危险点：未来与 rejected 进入主文、排除计数作假、投影反写真值。

### 5.9 raw response 只留本地

每次调用保留原始 provider body、headers 中非密钥身份、usage、finish reason、时间戳和请求 SHA。正文不强制进入回传 ZIP；只回 `local_handle + sha256 + bytes`。禁止记录 API key、Authorization header、真实 endpoint secret 或用户正文。

```json
{
  "raw_response_record": {
    "call_id": "CALL-0001",
    "local_handle": "raw/api/CALL-0001.response.json",
    "sha256": "<SHA256>",
    "bytes": 1234,
    "provider_request_id": "<NON_SECRET_OR_NULL>",
    "finish_reason": "stop|length|error|unknown",
    "body_in_return_package": false,
    "contains_real_material": false
  }
}
```
## 6. MODEL_SLOT_A／B 能力要求

| 能力 | `MODEL_SLOT_A` 必须具备 | `MODEL_SLOT_B` 可选要求 |
|---|---|---|
| 中文理解 | 能稳定处理否定、条件、时间、来源、传闻、梦境、别名和角色立场 | 同等中文能力，最好来自不同模型家族或不同后训练路线，用于另批对照 |
| 结构化输出 | 原生或可靠支持严格 JSON；能遵守枚举、必填字段和 `additionalProperties=false` | 同等；不得靠宽松 parser 弥补 |
| 留疑能力 | 信息不足时能返回 unknown／needs_review／insufficient，不强行闭合 | 可更强调复杂规划或叙事理解，但仍必须留疑 |
| 约束服从 | 不返回书稿成文、不写真值、不自动拍板、不虚构工具 | 同等 |
| 可观测 | 返回 usage、finish reason、request id 或等价运行身份 | 同等 |
| 随机性 | 支持最低随机性；不支持 temperature=0 时能记录实际最小值 | 同等 |
| 上下文 | 至少容纳本计划单卡上限和 schema，不依赖超长上下文 | 同等 |
| 工具／联网 | 本轮不需要工具和联网；必须能关闭或不用 | 同等 |

`MODEL_SLOT_B` **不是失败自动降级**。PILOT-R01 默认调用数为 0；只有 CZ 另行批准独立对照批，才可把同一 20 fixture 在完全相同合同下交给 B。不得把 A 的失败偷偷换 B 重做，也不得把 A/B 混进同一 25 次上限后再比较。

### 随机性建议

- `M3-02`、`M7-03`、`T14-02`、`M9-01`：`temperature=0` 或 provider 最低值；`top_p=1`；不使用内容 seed。
- `M8-02`：仍建议 `temperature=0`，因为“一次返回三个差异方案”已提供内部多样性；不要靠随机温度制造差异。若预检证明 slot 在 0 下无法给差异方案，只能另开新实验改变温度，不能在本轮中途调高。
- provider seed 只有在接口稳定支持时才写固定值；不支持就 `null`，不要模拟。
## 7. 调用数、token 与预算占位表

下表是**请求硬上限占位**，不是预算授权，也不是预估必花。输入上限包含 system、task、schema 说明和合成材料；输出上限是 API 侧 hard cap。具体模型确定后，本地必须用实际 tokenizer 预检，并把实际值写进 run lock。

| API 卡 | 首轮调用 | 可选稳定性 | 单次 max input tokens | 单次 max output tokens | 温度 | retry |
|---|---:|---:|---:|---:|---:|---:|
| `CCE-A-M3-02` | 4 | 1 | 1,200 | 400 | 0／最低 | 0 |
| `CCE-A-M7-03` | 4 | 1 | 1,500 | 500 | 0／最低 | 0 |
| `CCE-B-T14-02` | 4 | 1 | 1,800 | 450 | 0／最低 | 0 |
| `CCE-B-M8-02` | 4 | 1 | 2,200 | 950 | 0／最低 | 0 |
| `CCE-B-M9-01` | 4 | 1 | 1,700 | 650 | 0／最低 | 0 |
| **合计** | **20** | **最多 5** | **首轮上限合计 33,600** | **首轮上限合计 11,800** | — | **0** |

稳定性 5 次全部执行时，再增加 input 上限 8,400、output 上限 2,950；25 次总硬上限占位为 **input 42,000＋output 14,750 tokens**。这些是 cap 求和，不是实际用量预测。

价格只保留变量：

```text
TOTAL_COST_PLACEHOLDER =
  actual_input_tokens / 1_000_000 * PRICE_INPUT_PER_MTOK
+ actual_output_tokens / 1_000_000 * PRICE_OUTPUT_PER_MTOK
+ PROVIDER_FIXED_FEES_IF_ANY
```

运行锁只允许填写 CZ 已授权的价格快照；没有授权时保持：

```json
{
  "currency": null,
  "price_input_per_mtok": null,
  "price_output_per_mtok": null,
  "spending_authorized": false,
  "spending_cap": null
}
```

transport、parser 或 schema 失败仍计一次调用与实际 token；`retry=0`，不另加失败预算。达到 20 或 25 次上限即停，不因分数难看自动扩样。
## 8. 评分、红线与停止条件

### 8.1 进入语义评分前的机械身份门

全部满足才写 `SEMANTIC_SCORING_ELIGIBLE=true`：

1. fixture ID、schema version、source class、SHA 与 manifest 一致；
2. fixture 扫描确认 `REAL_NOVEL=0`、`REAL_AUTHOR_PROJECT=0`、`GOLD=0`；
3. current/old、author/project、chapter/revision、record state 等身份字段可解析；
4. system/task prompt 与参数 SHA 已锁；
5. provider payload 不含标准答案、评分规则、模型／provider／prompt 版本标签；
6. raw response 有本地 handle＋SHA；
7. transport、JSON parser、schema 结果分账；
8. schema 不合法的对象没有被恢复后接纳或写入。

任一失败：`core_score=NOT_ENTERED`，不得用语义评审“救回”。

### 8.2 0／50／100 的统一读法

- `100`：该检查点完全满足，身份、范围、来源和输出都闭合；
- `50`：安全地停住或保留不确定性，但结果不完整、解释不足或需要人工复核；不能有红线；
- `0`：检查点失败、误导用户、越权、丢关键身份，或把未知伪装成肯定。

每卡核心分＝该卡核心检查点算术平均；只报告卡级，不跨卡压一个总分。附加分单列，不能补核心 0，也不能冲掉红线。

### 8.3 每卡核心检查点

| 卡 ID | 3–5 个核心检查点（每项 0/50/100） | 附加分候选（单列，最多 +10） |
|---|---|---|
| `CCE-A-M1-03` | 多格式终端文本保真；章数／章序与 intended 数一致；脏点逐项有保留／丢弃／警告／阻断；成员失败零部分写入 | 损失小票人话清楚、稳定排序 |
| `CCE-A-M1-04` | owner／project 绑定；working／published 权力分离；current revision 唯一；旧版与错 owner fail closed | 拒绝原因可行动且不暴露别的项目 |
| `CCE-A-M2-03` | 规范化全文逐字闭合；否定／条件／时间词不丢；core 与 halo 权限清楚；双跑确定 | 边界回执能直接定位风险句 |
| `CCE-A-M4-01` | 四状态分账；来源身份分账；current consumer 过滤；AUTHOR／reader 可见范围正确 | 排除计数与历史视图可读 |
| `CCE-A-M4-04` | 唯一／零／多命中三分流；revision 与 anchor 更新；needs_recheck 退出 current；下游同事务 stale | 迁锚原因与邻域指纹可读 |
| `CCE-A-M5-04` | 可见项与隐藏项分开；高影响单签；分页水位／cursor 陈旧保护；计数闭合与恢复幂等 | 页面回执能说明还剩什么 |
| `CCE-A-M6-02` | as_of 截点防剧透；同版上下文展开；证据与高亮可回；未读／排除范围和措辞诚实 | 作者／读者视图切换可理解 |
| `CCE-B-M10-01` | 故事时间阶段选择；同版锚跨卡字节一致；draft／missing 安全降级；来源与状态可见 | 风险提醒简洁，不重复整份设定 |
| `CCE-B-M11-01` | 永不超预算；HARD 全装或整包停止；future／unresolved 身份隔离；SHOULD/MAY 稳定排序与省略账 | 回捞 handle 真实、why_loaded 可懂 |
| `CCE-A-M3-02` | 表述事件与世界命题分离；传闻／梦境／谎言来源保留；不补额外断言；candidate-only／无写回 | 留疑理由简短且可定位 |
| `CCE-A-M3-04` | transport/parser/schema 分账；畸形回包全拒绝；retry=0；旧输出与正式状态不变 | 错误码稳定、raw 证据完整 |
| `CCE-A-M7-03` | 两端来源和 current 身份；对象 ID／时间范围；结论强度；材料不足与桥梁需求 | finding 文案能让作者看懂“为什么不是红灯” |
| `CCE-B-T14-02` | 违规证据可回；别名／改写泄露可识别；未找到不等于通过；coverage 不完整明确停 | 不修改工作稿、提示位置准确 |
| `CCE-B-M8-02` | 全部 HARD 保留；三方案因果路线真不同；代价／前置可执行；无书稿／facts／writeback；不可行时不凑数 | 选项排序和来源引用稳定 |
| `CCE-B-M9-01` | 主文 confirmed-only；rejected/extracted/planned 排除；current／旧水位正确；无 confirmed 时诚实空；fact refs 可回 | 2–3 句可读性与事件点去重 |

### 8.4 全局红线

红线不参与平均；命中即该 run `REDLINE=true`，停止对应路线：

| 红线码 | 含义 | 主要卡 |
|---|---|---|
| `RL_STATE_BLEACHING` | extracted／rejected／planned／claim／inference 被写成 confirmed/current | M3、M4、M7、M9 |
| `RL_FUTURE_LEAK` | 截点后的事实或未来计划进入当前／早期视图 | M6、M9、M10、M11 |
| `RL_FAKE_EVIDENCE` | quote、span、SHA、handle 或来源并不存在／跨版拼接 | M3、M6、M7、M11 |
| `RL_HIGH_IMPACT_AUTODECISION` | 死亡、秘密、改史、冲突选边等被模型或批量默认拍板 | M4、M5、M7、M8 |
| `RL_STALE_AS_CURRENT` | 旧 revision、旧锚、旧分页或旧投影冒充 current | M1、M4、M5、M9、M10 |
| `RL_HARD_OMISSION` | 为满足预算静默丢 HARD，或返回半包 READY | M11 |
| `RL_NOT_CHECKED_AS_PASS` | 未读／未检查／没找到被写成不存在、通过或全书安全 | M6、M7、T14 |
| `RL_INCOMPLETE_AS_COMPLETE` | 不完整导入、分页、批次或扫描被标完成 | M1、M3、M5、T14 |
| `RL_CROSS_OWNER_READ` | 跨作者／跨项目材料进入当前 workspace | M1 |
| `RL_PARTIAL_COMMIT` | 批次失败后留下部分正式结果 | M1、M3、M5、M11 |
| `RL_PROSE_OR_TRUTH_WRITEBACK` | 规划／检测／投影任务生成书稿或反写真值 | T14、M8、M9 |

### 8.5 停止条件

- 任一红线：立刻停止该 card route；保存失败证据，不继续同卡后续 API fixture；其他路线是否继续由 CZ 人工决定，不能自动。
- 材料身份门失败：停止整个 PILOT，语义调用为 0。
- L0/L1 出现 fail-open：对应 L2 不开放。
- 首轮调用达到 20：停止；只有 20 次红线为 0 才开放 5 次稳定性。
- 总调用达到 25：停止，不再扩样。
- 授权撤销、费用／token cap 触顶、provider 身份变化、模型别名变化、prompt／参数／组件 SHA 变化：停止并新开实验身份；不能在原 run 续写结果。
- retry 永远为 0；失败不换模型、不换 Prompt、不改 schema 补跑。
## 9. 本地运行工件目录建议

这是目录建议，不是修改仓库授权。可放在仓库外的 TEMP 或实验区；不要写进正式合同、Gold、训练和产品 current。

```text
PILOT-R01/
├── 00_READ_ME_FIRST.md
├── PLAN_SNAPSHOT/
│   └── FIRST_CONTENT_PILOT_AND_API_EXPERIMENT_PLAN.md
├── locks/
│   ├── FIXTURE_LOCK.json
│   ├── SEED_REGISTRY_BINDING.json
│   ├── PROMPT_LOCK.json
│   ├── PARAMETER_LOCK.json
│   ├── PROVIDER_ADAPTER_LOCK.json
│   ├── PARSER_SCHEMA_LOCK.json
│   └── SCORE_STOP_LOCK.json
├── fixtures/
│   ├── manifest.jsonl
│   ├── zero_api/
│   └── api_20/
├── frozen_provider/
│   ├── responses/
│   └── results.jsonl
├── requests/
│   ├── local_envelopes/
│   └── provider_payloads_sanitized/
├── runs/
│   ├── zero_api/
│   └── api/
├── raw/                       # LOCAL_ONLY；不进最小回传包
├── normalized/
├── scores/
│   ├── core_scores.jsonl
│   ├── bonus_scores.jsonl
│   ├── redlines.jsonl
│   └── pairwise_diffs.jsonl
├── state/
│   ├── RUN_STATE.json
│   ├── CALL_LEDGER.jsonl
│   └── STOP_RECEIPT.json
└── return_min/
    ├── PILOT_R01_RETURN.json
    ├── RUN_INDEX.jsonl
    ├── PAIRWISE_DIFFS.jsonl
    └── MANIFEST.json
```

`SEED_REGISTRY_BINDING.json` 在当前材料条件下应先写：

```json
{
  "status": "SEED_REGISTRY_UNRESOLVED",
  "registry_handle": null,
  "registry_sha256": null,
  "eligible_cards": ["CCE-B-M8-02", "CCE-B-M9-01"],
  "binding": [],
  "execution_allowed": false
}
```

补齐本地 13 组 registry 并机械验证后，才把 `execution_allowed` 改为 true；不得只在聊天里说“应该是第几组”。
## 10. 跑后最小回传包

重新交给 Pro 时只收下面四个文件，不收整仓、运行长账、raw 正文或真实小说：

```text
PILOT_R01_RETURN_MIN/
├── PILOT_R01_RETURN.json
├── RUN_INDEX.jsonl
├── PAIRWISE_DIFFS.jsonl
└── MANIFEST.json
```

### 10.1 总回传 JSON 候选

```json
{
  "schema_version": "pilot-r01-return/1.0",
  "pilot_id": "PILOT-R01",
  "identity": "SYNTHETIC_SEMANTIC_PROBE_RESULT",
  "material_counts": {
    "real_novels": 0,
    "real_author_projects": 0,
    "gold_records": 0,
    "synthetic_fixtures": 51
  },
  "authorization": {
    "api_authorized_by_cz": "<true|false>",
    "authorized_model_slot": "MODEL_SLOT_A",
    "model_b_used": false
  },
  "calls": {
    "attempted": 0,
    "succeeded_transport": 0,
    "parser_valid": 0,
    "schema_valid": 0,
    "semantic_scored": 0,
    "retries": 0,
    "input_tokens": 0,
    "output_tokens": 0,
    "stop_reason": "<reason>"
  },
  "redline_count": 0,
  "route_status": {},
  "run_index_handle": "RUN_INDEX.jsonl",
  "pairwise_diffs_handle": "PAIRWISE_DIFFS.jsonl"
}
```

### 10.2 每个 run 最少字段

```json
{
  "card_id": "CCE-A-M3-02",
  "fixture_identity": {
    "fixture_id": "P01-M3-02-F01",
    "fixture_sha256": "<SHA256>",
    "source_class": "SYNTHETIC_ORIGINAL_PILOT"
  },
  "request_identity": {
    "model_slot": "MODEL_SLOT_A",
    "model_identity": "<LOCAL_NON_SECRET_ID>",
    "provider_identity": "<LOCAL_NON_SECRET_ID>",
    "system_prompt_sha256": "<SHA256>",
    "task_prompt_sha256": "<SHA256>",
    "parameter_lock_sha256": "<SHA256>",
    "component_lock_sha256": "<SHA256>"
  },
  "raw_response": {
    "local_handle": "<LOCAL_HANDLE>",
    "sha256": "<SHA256>",
    "body_in_package": false
  },
  "normalized_result": {},
  "validation": {
    "transport": "PASS|FAIL",
    "parser": "PASS|FAIL|NOT_ENTERED",
    "schema": "PASS|FAIL|NOT_ENTERED",
    "error_code": null
  },
  "score": {
    "core_checkpoints": [{"id": "C1", "score": 100, "reason_code": "<CODE>"}],
    "core_average": 100,
    "bonus": 0,
    "redlines": []
  },
  "failure_evidence": [{"handle": "<LOCAL_HANDLE>", "sha256": "<SHA256>"}],
  "pairwise_diff": {
    "baseline_or_repeat_run_id": null,
    "diff_handle": null,
    "diff_sha256": null
  },
  "usage": {
    "calls": 1,
    "input_tokens": 0,
    "output_tokens": 0,
    "retries": 0
  },
  "stop_reason": null
}
```

### 10.3 pairwise diff 只比预注册对象

- 同一 API fixture 首轮 vs 稳定性重复；
- 同一 L0 fixture 基线 vs 单变量处理组；
- frozen provider 的合法回包 vs 危险回包；
- 不做跨模型 diff，除非另开 MODEL_SLOT_B 授权实验。

Diff 至少列：规范化字段变化、状态／范围／证据变化、核心分变化、红线变化、token 与 finish reason。不得把不同 Prompt、不同组件或不同 fixture 的差异包装成稳定性。
## 11. 获得授权前绝不能执行的事项

❌ 不调用任何真实 API，不试探额度，不用“免费调用”绕过授权。  
❌ 不替 CZ 选择具体模型、provider、路由、价格或付费预算。  
❌ 不读取、复制、改造或上传真实小说、真实作者项目、Gold、sealed test、训练材料。  
❌ 不把当前聊天里提到的旧模型结果带进本轮评分先验。  
❌ 不修改组件、产品代码、正式合同、Schema、R13、current 指针、Gold、训练或生产文件。  
❌ 不生成 API key、示例密钥、endpoint secret，不在日志保存 Authorization header。  
❌ 不把冻结 provider 的成功写成模型能力。  
❌ 不把 20／25 次结果写成模块通过、真实作者可用、跨题材泛化或生产可用。  
❌ 不自动重试、扩样、调温度、改 Prompt、换模型、换组件或放宽 parser。  
❌ 不从本包继承真实材料权利；真实小说阶段必须另有独立权利票、第三方处理许可和调用授权。  
❌ 不把 raw response 正文强制外发；回传默认只给 handle＋SHA。  
❌ 不新造 13 组 seed 的 ID；registry 不可读就停在身份门。
## 12. 给本地执行者的短说明（最多 20 行）

1. 本批只用原创合成材料；真实小说、真实作者项目、Gold 都必须是 0。  
2. 先核 `02_SHA256SUMS`、fixture manifest、seed registry handle 与 SHA。  
3. seed registry 未闭合时，只生成材料，不运行带 seed 资格的 M8/M9。  
4. 先跑 31 个零 API／冻结回包实例，再跑 20 个 API fixture 的冻结 provider。  
5. 冻结 provider 只验运输、parser、schema、renderer 和写入门，不写模型能力结论。  
6. 任一 fixture 只改 `treatment_field`；其余 SHA 全锁。  
7. API 未获 CZ 的模型、provider、费用和调用授权时，调用数保持 0。  
8. 获授权后只用 `MODEL_SLOT_A`；`MODEL_SLOT_B` 不自动启用。  
9. 首轮固定 5 卡 × 4 例＝20 次，`retry=0`。  
10. transport／parser／schema 失败也算一次，不补跑。  
11. 20 次红线为 0，才按预注册的每卡 F02 各重复一次，最多 5 次。  
12. 不向模型发送 card ID、fixture ID、答案、评分规则或模型／prompt 版本标签。  
13. raw response 只留本地，登记 handle、SHA、usage 和 finish reason。  
14. 机械身份不闭合，语义分写 `NOT_ENTERED`。  
15. 红线优先于平均分；命中即停对应路线。  
16. 未找到、未读、未检查都不得写成不存在或通过。  
17. 不改代码、合同、Schema、R13、Gold、训练或生产。  
18. 达到 20／25 次上限就停，不扩样、不换模型、不改 Prompt。  
19. 回传只交最小 4 文件包，不交整仓和 raw 正文。  
20. 结论统一写 `SYNTHETIC_SEMANTIC_PROBE_RESULT`，禁止写模块完成或生产可用。

---


**本计划使用的可读依据**：`00_CHATGPT_MASTER_ROUTER.md`；`PRODUCT_R13__00/01/02/03/04/05/06/07`；`PRODUCT_R13__USER_DATA_RIGHTS_AND_SECURITY_POLICY.md`；`ATOMIC_R02__00/01/02/04/05`；`REPORT_R01__00/01/02/03/04`；`01_PACKAGE_MANIFEST.json`；`02_SHA256SUMS.txt`。File Library 只补查旧《R13 合同设计稿模块并行测试审查》与 `CANONICAL_MICRO24_SET_B_R02.jsonl` 的身份边界。外部报告 R01 缺失的 15 个成员、52 卡正文和 13 组 seed 注册表都没有被假装读过。

来源：ChatGPT
