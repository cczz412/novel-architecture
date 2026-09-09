# 作品档案｜合同原文迁入

> 交付身份：仅文档迁入审阅稿。本批尚未执行主存切换，运行能力仍按 GitHub 已合代码与各自授权判断。
> 来源：[CCZ-97｜作品建档表、默认项目名与作品档案版本合同（Codex）](https://linear.app/ccz/document/95c53ae186c4)（文档 ID：`3d63099b-5d4c-4fc5-a37f-fe5c75d3588b`）。
> 原版本：author-workspace-project-profile-v1；2026-08-25 整理稿。
> 原文区 SHA-256：`ce49f6b1f9dc36658b52e96e118e4037d6771c52445c57005cd63d9537ca1cb3`。
> 来源、批准回执、历史状态差异及本批互链见 [迁移索引](CCZ184_CONTRACT_MIGRATION_R01.md)。

## 原文区

下方保留本次读取的完整 Markdown 原文，包括原有版本、日期、字段、示例与链接。原文里的“当前代码”“待批准”等描述属于其记载水位；迁移说明与原文分开，不借此重定语义。

<!-- CCZ184_SOURCE_BEGIN -->
> 执行身份：Codex
> 整理日期：2026-08-25
> 对应票：[CCZ-97](https://linear.app/ccz/issue/CCZ-97/合同子票作品建档表默认项目名类型主角必填与档案版本)
> 父合同：[CCZ-85](https://linear.app/ccz/issue/CCZ-85/合同父票m1-raw-动作终态generation-接纳与-orphan-恢复)
> CZ 已确认：类型与主角设定必填；平台、介绍、创作想法、未来规划等选填且可后补；小说暂未命名时使用默认项目名，后续可以改名。
> GitHub 代码真值快照：main@5b4321c8ccf68f419fc0d5de5d8bba50702a79bd
> 边界：本合同不自动授权 GitHub 施工。

## 结论

作品建档不是上传旁边的一组临时备注。它和原稿一起组成后续抽取真正读取的“当前项目版本”。

新项目第一次正式入库固定走：

**创建稳定项目身份 → 校验建档表 → 封存原稿与作品档案请求 → 验证本动作全部新内容 → 生成同时引用原稿和档案的 fixed target generation → current 条件切换 → 抽取按同一水位读取原稿与档案。**

作者可以晚点补平台、介绍、创作想法和未来规划，也可以改名、改类型或改主角设定。每次正式修改都产生新作品档案版本和新 generation，不覆盖历史，也不要求重新上传没有变化的原稿。

## 当前输入、输出和产品缺失

当前新版项目 metadata 读取项目号、作者、显示名和创建时间，能够输出作者项目列表并安全打开项目。

当前 M1 读取完整 raw bytes、metadata、动作号和预期版本，能够输出不可变原稿、input manifest、module state、generation 回执和安全摘要。

小说辅助产品还缺少收集、长期保存、版本判断、读取和传递作品档案的能力。这个缺失会卡住作者正式入库和后续抽取：原稿虽然已经保存，小说辅助产品仍不知道作品类型、主角设定、目标平台和作者规划，也无法说明一次抽取使用的是哪一版作品信息。

本票读取：

* 绑定好的作者与项目；
* 稳定 project ID 和项目壳的默认显示名；
* 作者填写的作品建档表；
* 首次入库时的完整原稿与 metadata；
* 后续档案修改时的 current generation 和上一版档案；
* 动作号、expected base 和 sealed target spec。

本票输出：

* 一份版本化、不可变的作品档案；
* 作者可见的有效作品名或稳定默认名；
* profile revision、profile identity 和 parent profile identity；
* 初次原稿＋档案共同接纳结果，或后续 profile-only generation；
* 交给抽取模块的同代“原稿＋作品档案”输入；
* 不泄露作品内容的安全状态。

## 1. 项目身份、默认名和小说名

项目内部身份固定使用稳定 project ID。小说名、默认名、类型、平台和主角都不能参与权限身份、存储路径、对象 key、动作唯一键或跨项目判断。

项目壳创建时必须保存一个稳定默认显示名：

* 作者没填小说名时，项目列表显示默认名，例如“未命名小说 3”；
* 默认名在创建时生成并持久化，不能每次打开按当前时间重新计算；
* 默认名的精确后缀属于界面实现细节，但要让同一作者的多个未命名项目容易区分；
* 默认名不能暴露内部 project ID、内容 digest、路径或作者隐私；
* 多个项目即使同名，也只靠 project ID 区分。

作者填写的小说名是作品档案里的可选字段：

* 小说名存在时，它是作者界面的主要项目显示名；
* 小说名为空时，回退到项目壳的稳定默认名；
* 小说名可以添加、修改或清空；
* 改名不能改变 project ID、作者绑定、路径或历史 generation；
* 项目壳里的默认名只做回退，不冒充作者已经确认的小说名。

作者界面的有效显示名固定为：

**当前已接纳作品档案的小说名；没有小说名时使用项目壳默认名。**

项目列表需要读取这一安全投影。档案无法可靠读取时，继续显示项目壳默认名和恢复提示，不能使用损坏档案里的标题。

## 2. 作者填写的最小表单

首次正式接纳原稿时必填：

* **主类型 primary genre**：非空。界面可以给常见类型选项，也必须允许“其他／自定义”；
* **主角／核心人物设定 protagonist brief**：非空文本。不强制填写姓名；“群像”“无固定主角”或尚未命名的核心人物都可以，但要写清作品准备围绕谁或哪组人物展开。

选填并允许后补：

* 小说名；
* 细分类型标签，例如“都市＋高武”“都市＋脑洞”；
* 目标平台，可不填、可后补、可自定义，或暂未决定；
* 作品介绍；
* 创作想法；
* 未来规划；
* 预计篇幅或更新规划；
* 其他补充。

类型预设清单和平台预设清单不是这张合同的固定枚举。作者自定义值必须能够保存，避免产品分类表反过来卡住建档。

作品档案采用版本化格式 **author-workspace-project-profile-v1**。作者填写的正文和内部版本信封分开：

作者正文至少包含：

* novel title，可空；
* primary genre，必填；
* genre tags，可空；
* protagonist brief，必填；
* target platforms，可空；
* synopsis，可空；
* creative intent，可空；
* future plan，可空；
* length／update plan，可空；
* notes，可空。

内部版本信封至少绑定：

* schema version；
* project ID；
* profile revision；
* profile body SHA-256；
* parent profile identity；第一版为空；
* 写入动作 identity；
* request commitment；
* 作者和项目绑定；
* 创建时间只用于显示，不进入“同一作者内容是否相同”的判断。

字段规范化规则必须版本化。JSON 键顺序或换行格式等无语义变化不能把同一请求变成不同请求；类型、主角或文字内容真的改变时必须得到不同请求承诺。

## 3. 草稿和正式档案

创建一个空项目壳时，不要求作者已经想好类型或主角。项目可以先存在，列表显示稳定默认名。

在 ActionIntent 创建前，作者可以反复修改建档表。此时只是界面草稿：

* 不算 accepted 作品档案；
* 不进入抽取；
* 不产生 READY；
* 不因为每输入一个字就创建 generation。

本合同不要求建设跨设备草稿自动保存。未来要做长期草稿保存，需要单独定义草稿权限、版本和清理规则。

后端只有在类型和主角设定都通过校验后，才允许登记首次正式入库 ActionIntent。必填项缺失时：

* 在任何正式 raw、metadata、profile object、generation 或 current 写入前拒绝；
* 已有 current 保持不变；
* 作者可以继续编辑表单后重新提交。

## 4. 初次原稿与作品档案共同接纳

第一次正式入库动作固定把原稿和作品档案一起封存。

[CCZ-89](https://linear.app/ccz/issue/CCZ-89/子票m1-动作身份请求封存与项目级幂等) 的请求承诺必须加入：

* profile schema version；
* 完整规范化 profile body；
* profile body SHA-256；
* profile object receipt／payload identity；
* project profile mutation；
* 原有 raw／metadata receipts、input manifest 和 module state mutations。

同一动作号只有在原稿、档案、base 和 target spec 全部相同时才是同一请求重试。同一动作号、同一原稿，但类型、主角、小说名、平台或规划发生实际变化时，是换请求，必须在新增正式对象前稳定冲突。作者要用新动作号提交修改后的内容。

ActionIntent 耐久确认后，raw、metadata 和 profile object 可以分别发布。它们在 current 切换前都只是待接纳对象，不能交给抽取模块使用。

[CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力) 的动作绑定验证范围由 sealed action kind 决定：

* 初次原稿入库：全文验证本动作全部 raw、metadata 和 profile object；
* 同时修改原稿和档案：验证本动作全部新增或改变的对象；
* 调用方不能自由传档案路径、digest、receipt 或缩小验证集合；
* 档案缺失、截断、schema 错、作者／项目／动作绑定错，或内容与 sealed request 不一致时，不得创建可接纳 generation，也不得推进 current。

profile 结构校验和必填项校验在 ActionIntent 前先做一次；对象发布后还要按动作重新完整读回，不能拿内存里的原值冒充持久化验证。

[CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 的 fixed target generation 必须同时绑定：

* 当前原稿清单与 raw／metadata receipts；
* 当前 project profile revision、profile identity 和 profile object receipt；
* parent generation；
* ActionIntent、request、receipt plan 和 target spec identity。

只有 current 从 sealed base 条件切换到这个 fixed target，原稿和作品档案才同时成为项目当前内容。不能给原稿和档案各设一个 current 指针。

## 5. 后续修改作品档案

第一次接纳后，下面动作都属于作品档案更新：

* 添加、修改或清空小说名；
* 修改主类型或细分标签；
* 修改主角／核心人物设定；
* 添加、修改或清空平台、介绍、创作想法、未来规划、篇幅／更新规划和备注。

档案更新使用新动作类型 **PROJECT_PROFILE_UPDATE**、新动作号和新 generation：

* 类型和主角在每一版正式档案里仍必须非空；
* 生成新的不可变 profile object；
* parent profile identity 指向上一版；
* generation 继承父代完全相同的 raw／metadata receipts 和其他未修改 entries；
* target spec 只允许改变 project profile entry；
* current 仍通过 sealed base → fixed target 条件切换；
* 旧作品档案和旧 generation 保留，不原地覆盖。

只改作品档案时，[CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力) 必须：

* 全文验证新 profile object；
* 证明继承的 raw／metadata 集合与父 generation 完全相同；
* 不强迫重新全文读取所有旧 raw bytes；
* 不把这次 profile 验证冒充“当前原稿 READY”。

这样即使旧 raw 当前受损，作者仍能修正类型、主角或规划。新档案可以被接纳，但项目整体仍由 [CCZ-90](https://linear.app/ccz/issue/CCZ-90/子票m1-acceptedreadydegraded-诚实读回) 诚实显示原稿 DEGRADED。

两个档案更新竞争同一 base 时只允许一个赢家。输家不能自动接到新 current，也不能静默合并；作者要读取最新档案后用新动作重新提交。

内容与 current 完全相同时可以不建空 generation；动作终态沿用 [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留)／[CCZ-89](https://linear.app/ccz/issue/CCZ-89/子票m1-动作身份请求封存与项目级幂等) 已冻结语义，同一动作的重放结果仍要稳定。

## 6. 旧项目补建档

本合同生效前已经合法接纳 raw、但 generation schema 中没有 project profile 的项目，不算损坏，也不能直接报 DEGRADED。

这类项目固定显示：

**profile status = NEEDS_INITIAL_PROFILE**

同时保留已经证明的原稿历史接纳和当前原稿可用性。历史抽取可以继续查看；作者可以打开项目、查看原稿状态并补建档。任何新的 profile-aware 抽取必须先补齐类型＋主角，不能用模型猜默认值。

补建档使用 profile-only child generation：

* parent 是现有 current；
* 完全继承父代 raw／metadata receipts；
* 新增第一版 project profile；
* 不要求重新上传原稿；
* raw 已受损时仍允许补档，补档后整体继续诚实显示 raw DEGRADED；
* 补档中断时旧 current 不变；
* 必填项仍缺失时零正式写入。

项目壳还没有任何 accepted generation 时，显示：

**profile status = NOT_YET_ACCEPTED**

新格式 generation 声明引用 profile、但 profile object 缺失、损坏或绑定错误时，才显示：

**profile status = DEGRADED**

合法且完整的当前 profile 显示：

**profile status = READY**

这四种状态不能混：

* NOT_YET_ACCEPTED：空项目壳；
* NEEDS_INITIAL_PROFILE：旧项目合法缺少新档案；
* READY：当前档案完整可用；
* DEGRADED：应该存在的当前档案损坏。

## 7. 抽取模块怎样读取

抽取开始时必须锁住同一组水位：

**project ID＋current generation ID＋manifest SHA＋raw manifest identity＋project profile revision／identity**

完整使用读取固定执行：

1. 捕获 P0 current；
2. 从 P0 manifest 读取并验证 current project profile；
3. 全文读取并验证全部 current M1 raw／metadata；
4. 组装“原稿＋作品档案”内部输入；
5. 再读 P1 current；
6. 只有 P0 == P1 且原稿和档案都通过，才把整包输入交给抽取模块；
7. P0 != P1 时丢弃整包内容并重试；
8. 任一部分失败时不返回半份输入。

抽取产物必须在内部记录：

* current generation identity；
* raw manifest identity；
* project profile revision 和 identity；
* 抽取合同版本。

作者后来改名、改类型、改主角或补规划，不会改写旧抽取产物当时使用的档案。产品可以提示“作品档案已更新，建议重新抽取”，但本票不自动重跑、不自动删除旧抽取结果。

作品档案属于作者提供的背景，不等于原稿事实：

* 类型、主角、介绍和未来规划可以帮助理解和消歧；
* 事实抽取仍以原稿写明内容为准；
* 未来规划与现有原稿冲突时，两种来源必须分开保存；
* 不能把作者计划冒充“原稿已经发生”。

## 8. 安全读回与作者界面

作者自己的当前项目页面可以显示：

* 有效作品名或稳定默认名；
* 主类型和细分标签；
* 主角／核心人物设定；
* 目标平台；
* 作品介绍、创作想法、未来规划和其他补充；
* 当前 profile revision；
* 原稿历史接纳、当前原稿可用性和 profile status。

项目列表只显示安全投影：

* 有效显示名；
* 创建时间；
* 可选的粗粒度类型和状态。

普通日志、诊断、遥测、跨项目错误和未授权结果不得显示：

* 小说名；
* 类型和标签；
* 主角设定；
* 平台；
* 介绍、想法、规划和备注；
* 文件名；
* raw／profile 正文；
* 路径、对象 key；
* receipt、blob identity；
* profile／raw／request／generation digest 或前缀；
* 其他项目是否存在。

作品档案采用与原稿相同的作者和项目权限边界。它叫 metadata 或 profile，不代表可以降低保护等级。

作者／项目绑定失败时，在查询档案或对象存在性前统一拒绝。

## 9. 和现有合同的修改关系

[CCZ-89](https://linear.app/ccz/issue/CCZ-89/子票m1-动作身份请求封存与项目级幂等) 增加规范化作品档案快照、profile object receipt、profile mutation 和 PROJECT_PROFILE_UPDATE 动作类型。

[CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力) 的 sealed action validation 增加 profile object；验证集合由动作类型固定，不能由调用方缩小。

[CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 的 generation identity、manifest、父链和恢复证据增加 profile revision／identity；profile-only generation 继承父代 raw entries。

[CCZ-90](https://linear.app/ccz/issue/CCZ-90/子票m1-acceptedreadydegraded-诚实读回) 的 cheap summary 增加 profile status 和安全投影；full-use read 在同一 P0／P1 水位返回原稿＋档案整包。旧项目 NEEDS_INITIAL_PROFILE 不冒充 DEGRADED。

[CCZ-85](https://linear.app/ccz/issue/CCZ-85/合同父票m1-raw-动作终态generation-接纳与-orphan-恢复) 的主流程改为“封存原稿＋档案请求 → 验证两者 → 同 generation 接纳 → 同水位读回”，并把本票加入批准条件。

[CCZ-81](https://linear.app/ccz/issue/CCZ-81/待前置m1-raw-接纳恢复与诚实-ready) 只有在 GitHub 当前施工票明确扩展写集后，才能实现作品档案保存、版本接纳和传递。当前 GitHub #123 仍带 needs-cz，没有 status:ready，不能把本合同当成代码授权。

[CCZ-91](https://linear.app/ccz/issue/CCZ-91/验收子票m1-raw-动作崩溃与并发故障注入) 增加作品档案发布、重放、并发、损坏、旧项目补档、同水位读回和隐私故障注入。

[CCZ-80](https://linear.app/ccz/issue/CCZ-80/ccz-15-首票新版项目列表与打开入口) 的项目列表需要从“只读 project.json.display_name”升级为“当前 profile 小说名存在时优先，否则使用项目壳默认名”。项目读取失败时不能使用损坏标题。

[CCZ-33](https://linear.app/ccz/issue/CCZ-33/gh92-待办产品边界登记一个项目一本小说跨项目番外多视角时间线迁移后置研究) 的“一项目一本小说”边界继续成立；跨项目番外、多视角和时间线迁移仍在后备研究范围。

## 10. [CCZ-91](https://linear.app/ccz/issue/CCZ-91/验收子票m1-raw-动作崩溃与并发故障注入) 必须增加的验收场景

* 不填小说名，但类型和主角完整，初次入库成功并显示稳定默认名；
* 补写、修改或清空小说名后 project ID 不变；
* 同名项目不串档、串权限或串原稿；
* 类型或主角为空时在 ActionIntent 前拒绝，current 不变；
* 群像、无固定主角或主角未命名仍能合法建档；
* raw 与 profile 各持久点崩溃时不出现半接纳；
* generation 已写、CAS 前崩溃，或 CAS 后 terminal 丢失，能够恢复准确的原稿＋档案组合；
* 同动作、同 raw、同档案重试稳定；
* 同动作、同 raw、档案变化时零新增正式写入并稳定冲突；
* profile-only update 生成新 generation，继承 raw，不要求重传；
* 两个档案更新竞争同一 base 只有一个赢家；
* 原稿入库与档案更新竞争时不自动把输家 rebase；
* raw 已损坏时仍能接纳档案更新，但整体继续显示 DEGRADED；
* 旧项目 NEEDS_INITIAL_PROFILE 能补档，补档崩溃时旧 current 不变；
* 新格式 profile 缺失、截断、schema 错或绑定错误时 DEGRADED；
* full-use read 期间 current 变化时整包丢弃，不能混代；
* 默认名重开后稳定，且不泄露内部 identity；
* 作者页面可以显示档案，日志和跨项目错误不得泄露。

## 11. 不在本票里的内容

* 不固定平台商业规则或平台专属写作模板；
* 不锁死一套类型枚举；
* 不用模型自动猜类型或主角来绕过作者必填；
* 不建设跨设备草稿自动保存；
* 不自动重跑抽取；
* 不自动删除旧档案、旧 generation 或旧抽取结果；
* 不建设跨项目迁移；
* 不修改 GitHub 代码、分支或 PR；
* 不把 Linear 合同完成当成施工授权。

## 12. [CCZ-97](https://linear.app/ccz/issue/CCZ-97/合同子票作品建档表默认项目名类型主角必填与档案版本) 完成条件

本票只有同时满足下面条件，才算合同完成：

* 默认项目名稳定、持久且不参与内部身份；
* 小说名可空、可改、可清空，project ID 永远不变；
* 主类型和主角设定在首次正式入库及每版正式档案中必填；
* 平台、介绍、想法、规划和其他内容选填且可后补；
* 首次原稿和档案通过同一 generation／current 接纳；
* 后续 profile-only update 不要求重传或全文重读旧 raw；
* 同动作换档案稳定冲突；
* old project 使用 NEEDS_INITIAL_PROFILE，不误报 DEGRADED；
* 抽取在同一 current 水位读取原稿和档案；
* 抽取产物记录 profile revision；
* 作者背景与原稿事实分开；
* 安全读回和日志边界明确；
* [CCZ-85](https://linear.app/ccz/issue/CCZ-85/合同父票m1-raw-动作终态generation-接纳与-orphan-恢复)、81、91 和相关子合同都接入本票；
* GitHub 施工边界明确。

来源：Codex
<!-- CCZ184_SOURCE_END -->

来源：Codex
