<!-- MIRROR-DECLARATION-BEGIN -->
本文件是只读镜像，不是真源。
真源：Notion 页「章结构保存与固定读取｜正式合同 R01」
页面地址：https://www.notion.so/3da5cadc4d0f818db55afc75364b5ef5
页面标识：3da5cadc4d0f818db55afc75364b5ef5
导出时刻：2026-09-16T18:25:06.933729+00:00
镜像正文 SHA-256：de109a22be0e5db5161100e79a274cfb3224ee9a46a724bc7bdb15abc4c52e7e
禁止在本文件上修改合同内容。需要改合同时：先在 Notion 页出修订版，再重新导出本文件并更新上面的时刻与 SHA-256。
本文件内容与 Notion 页不一致时，一律以 Notion 页为准，并立即停下回报。
<!-- MIRROR-DECLARATION-END -->
**先看人话图解：** <mention-page url="https://app.notion.com/p/3da5cadc4d0f81f6a70ed160a895297f">章结构合同｜大白话与五张管线图</mention-page>。五张彩色 Mermaid 图讲清总位置、K01—K03 分工、合同五块、操作顺序和以后接入的顺序。本条只增加阅读入口，合同与附件保持原样。
采用原话：<mention-page url="https://app.notion.com/p/3da5cadc4d0f811eb16dd46e43403405"/>；工程边界台账：<mention-page url="https://app.notion.com/p/3da5cadc4d0f81588a1eeceb533ca677"/>；原采用稿：<mention-page url="https://app.notion.com/p/3da5cadc4d0f818fa757d510248fa4fd"/>。
这份合同把 EA01—EA03 写成了具体的保存、版本、权限和读取规则。首批要交付的行为是：作者明确登记一个编辑分支，保存结构候选第一版，再保存第二版，仍能准确查看第一版；查看不改变当前选择，也不产生故事采用或章节结算。
<callout icon="✅" color="green_bg">
	**2026-09-14 18:35｜CZ 已将本稿整体转正为正式合同，不逐条审。**
	CZ 逐字原话（渠道：Notion 聊天，直接对 Notion 说，不是经 Codex 转述）：「正式合同候选 R01 整体转正为正式合同，不逐条审。三条限定：一、允许后续按实施发现出修订版，不重走全审；二、容量各项为未实测初值，按实测证据走受控配置调整；三、合同转正不等于接通，K01—K03 仍 BLOCKED，实际权限链与运行入口另行验收。接下来可以按此合同排工程票与代码写集；旧数据仍不迁移。」
	转正范围与三条限定：
	- **范围**：本稿全文、汇总 Schema、逐字段目录（284 处）、规范规则、容量候选、验收场景一并转正为正式合同 R01。未经逐条审查是 CZ 明示选择，不得记为"已逐条核准"。
	- **限定一｜可修订**：后续实施中发现问题可出修订版，不重走全审；修订仍须登记版本与原因。
	- **限定二｜容量为未实测初值**：16MiB 集合、128 对象、256 版、128KiB 单版本、256KiB 写请求、32KiB 写响应、50 引用、100 业务项、256KiB 读响应、300 秒 grant 等均未做真实规模实测，按实测证据走受控配置调整，不得暗中删历史或换宿主。
	- **限定三｜转正不等于接通**：K01、K02、K03 的 `integration_status` 仍为 `BLOCKED`。实际宿主会话、任务/工作卡许可、当前权限与撤权路径、结构归属与读写运行入口均未接通，须另行验收；合同生效不得被引述为权限或能力已具备。
	- **后续授权**：可按本合同排工程票与代码写集。旧数据仍不迁移；r5 整版、G/H、believes 及强消费者仍未开放。
	未变：原 F001—F197 基线与 F006 原冲突计数不变；GitHub 工程基线 `c18736ded3388e36acea4ed4911d2a45fc4994fc`。
	登记：Notion
</callout>
<callout icon="🔧" color="orange_bg">
	**2026-09-17 02:05｜R01.1 窄范围修订（已生效）**
	CZ 逐字原话（渠道：Notion 聊天，直接对 Notion 说，不是经 Codex 转述）：「都同意」。所答两问为：① 合并 PR #370（R01 只读镜像入仓）；② 出 R01.1 窄范围修订。本条依转正限定一「允许后续按实施发现出修订版，不重走全审」执行，是该限定的首次启用。
	**修订缘由**：本页 §5 要求提交途中故障须按证据区分 `NOT_COMMITTED`、`COMMITTED`、`UNKNOWN`；而附件汇总 Schema 在 `#/$defs/StructureWriteResponse/allOf/22/then/properties/commit_state/enum` 处对 `STORAGE_IO_ERROR` 只允许 `UNKNOWN`。二者冲突，实施方无法自行选择。Codex 已在锁定环境做最小探针复现：同一份完整错误响应仅替换 `commit_state`，`UNKNOWN` 通过，另两值均被原 Schema 拒绝，且唯一失败点即该枚举。
	**R01.1 条文（适用范围：仅 ****`STORAGE_IO_ERROR`**** 的 ****`commit_state`**** 取值，不涉及任何其他条款）**
	1. 该码的 `commit_state` 允许 `UNKNOWN`、`NOT_COMMITTED`、`COMMITTED` 三值；汇总 Schema 中「只允许 `UNKNOWN`」的约束同步放宽为这三值。
	2. 默认值为 `UNKNOWN`。仅当提交结果证据可信时才允许给出确定值：`COMMITTED` 须回读到该操作已提交的记录；`NOT_COMMITTED` 须确认不存在任何预备物理写入残留。两者均须在响应中留下判定所依据的那一次回读。证据不足一律 `UNKNOWN`，不得推测、不得默认。
	3. 不变更项：`ERROR` 结果仍不得携带成功业务数据；`COMMIT_READBACK_FAILED` 保持独立含义，不被本条吸收；不新增任何回执字段；其余错误码取值范围不变；本条不涉及段二，不改 `integration_status`，K01—K03 仍为 `BLOCKED`。
	4. 附件冲突处置：本页附件 ZIP 为历史原件，不重打包、不改哈希（仍为 `3285d9df2c58545b20d6242c45bedf68ce2bed0e7595d0d1099247b5f361fb8a`）。包内 Schema 与本条冲突时，**以本条为准**。
	**配套动作**：本页为真源，已先改。仓库只读镜像 `novel-mvp/contracts/CHAPTER_STRUCTURE_SAVE_AND_PINNED_READ_R01.md` 须重新导出，更新声明块中的导出时刻与镜像正文 SHA-256，并同步更新 `CHAPTER_STRUCTURE_SAVE_AND_PINNED_READ_R01.MIRROR.json` 的 `exported_at` 与 `mirror_body_sha256`。镜像刷新完成前，不得依据旧镜像实施本条。
	登记：Notion（CCZ-190 同步登记）
</callout>
**原候选身份说明（转正前状态，保留备查）**：EA01—EA03工程边界已由CZ采用；本稿的具体字段、机器名、容量和权限绑定当时仍为合同候选。编制轮次中未改现役合同、产品代码或旧记录，未开票、迁移或运行产品测试。
CZ原话：“同意 EA01—EA03，按采用稿及上述澄清编制正式合同候选，明确字段、权限和验收；继续不开票、不改代码、不迁移。”原话和采用范围已单独登记；本稿不把此前的Notion建议口令冒充作者批复，也不采用r5整版。
## 1. 合同由哪些文件共同组成
<table header-row="true">
<tr>
<td>文件</td>
<td>用途与身份</td>
</tr>
<tr>
<td>`CHAPTER_STRUCTURE_CONTRACT.schema.json`</td>
<td>本轮唯一汇总机器形状：共享类型、输入/存储分支、五个写动作、一个读动作、响应和私有许可记录。可以解析和检查形状，尚未成为现役合同</td>
</tr>
<tr>
<td>`NEW_FIELD_CATALOG.json`、`.csv`、`逐字段合同表.md`</td>
<td>从同一Schema展开的逐字段目录，列类型、必填、可空、值域、引用、缺失处理及指针；不是原F001—F197的重分类</td>
</tr>
<tr>
<td>`NORMATIVE_RULES.json`及本页</td>
<td>Schema不能独自证明的顺序、摘要、当前权限、CAS、幂等、原子性和零业务写入规则；实现时必须同时满足</td>
</tr>
<tr>
<td>`CAPACITY_CANDIDATE.json`</td>
<td>首批明确的候选上限；这些值尚未做规模实测</td>
</tr>
<tr>
<td>`examples/`、`SCHEMA_ILLUSTRATION_CHECK.json`</td>
<td>合成请求、版本、存储和响应，以及形状反例。只做文档结构和算术核对，不是运行通过记录</td>
</tr>
<tr>
<td>`permission_draft/ACCEPTANCE_CASES_CANDIDATE.json`</td>
<td>后续真实入口验收的主链与26条场景要求，覆盖原9场景和跨类型摘要断言</td>
</tr>
<tr>
<td>`兼容与来源边界.md`</td>
<td>F006、旧句子键、十账能力、C9、两种取件码、来源分支及既有含义的边界</td>
</tr>
</table>
四个 `*_draft/` 目录保留辅助编制输入与证据。它们不另外发布机器合同；跨稿不一致按本页及汇总Schema的集中决定处理。尤其以本页的 `structure_content`、临时编号映射、授权引用和许可作用域为准。
## 2. 归属与一次定名的候选
<table header-row="true">
<tr>
<td>用途</td>
<td>本稿拟定</td>
<td>与现役关系</td>
</tr>
<tr>
<td>业务归属</td>
<td>`CHAPTER_STRUCTURE`</td>
<td>章业务内的新结构候选职责，已采方向；这个具体注册值仍候选</td>
</tr>
<tr>
<td>对象类型</td>
<td>`CHAPTER_STRUCTURE_VERSION`</td>
<td>新结构对象，不能冒充C11书稿或某本旧账条目</td>
</tr>
<tr>
<td>唯一受限逻辑键</td>
<td>`chapter_structures`</td>
<td>拟增入AuthorWorkspace白名单；现役尚无此键</td>
</tr>
<tr>
<td>逻辑文件名</td>
<td>`chapter_structures.json`</td>
<td>只供后端登记，业务不直接拼路径读写，实际存储仍由原后端负责</td>
</tr>
<tr>
<td>唯一写入口</td>
<td>`apply_structure_write`</td>
<td>拟在章结构专用模块中增加；不是当前可调用函数</td>
</tr>
<tr>
<td>固定读取入口</td>
<td>`read_structure_versions`</td>
<td>拟新增专用入口，直接消费同一归属的指定版本；不是公共v1/v2或C9适配</td>
</tr>
<tr>
<td>许可提供方</td>
<td>`StructureAccessProvider`</td>
<td>拟新增受信宿主适配，复用共同调用的权限范围含义；实际绑定尚未接通</td>
</tr>
</table>
新增字段使用 `snake_case`，新枚举用大写下划线，单引用以 `_ref` 结尾、多引用以 `_refs` 结尾。固定协议标识仍用清楚的版本字符串；复制的现役枚举保留原拼写，不全库改名。
两条业务入口的候选签名为 `apply_structure_write(workspace, access_context, action_grant, request)` 和 `read_structure_versions(workspace, access_context, action_grant, request)`，都放在拟新增的章结构专用模块中，由同一归属提供版本。前三项只由受信宿主组装；模型工具只提交对应请求。完整ActionGrant的JSON形状只用于私有审计/核验，不能据一个可复制的JSON取得调用资格。实际模块、白名单键和provider均未写入仓库。
“句子”指记录表达的那句话，唯一字段为 `text`；“书稿”指小说文字。新键 `structure_content` 是整份结构容器，避免用裸 `content` 与旧句子别名混淆。收到的原材料中的 `content`、其他原键或字面量保持原样，不能变成第二个可编辑句子键。
本体中的 `FactItem` 只表示本版实际保存的候选片段及来源联系，不是替换C3/C4的事实语义新合同。它不直接用于世界属性、认识或规则求值。原事实的语义仍随原引用或材料保留；这条首批读取只交付候选本体，不借机开放强消费者。
## 3. 固定身份、本体和来源
完整结构引用采用七项：`project_id`、`branch_id`、`owner`、`object_type`、`id`、`rev`、`content_sha256`。作品号沿现役受信 `p_` 加32位hex，作者号沿 `a_` 加32位hex；新编辑分支为 `eb_` 加32位hex，结构对象为 `cs_` 加32位hex。新身份只由合法写入口签发，不能由文件名、章序、Git分支、操作号或存储代际代替。
每个版本是 `{ref, structure_content, save_operation_id}`。本体固定包含合同标识、事实候选列表、选中事实及顺序、呈现安排、收到的材料、来源分型与依据引用。各自含义如下：
<table header-row="true">
<tr>
<td>本体字段</td>
<td>保存什么</td>
<td>不产生什么</td>
</tr>
<tr>
<td>`fact_items`</td>
<td>本版的局部片段号、`text`和真实来源/材料联系</td>
<td>正式f-ID、事实采用或客观属性贡献</td>
</tr>
<tr>
<td>`selected_facts`</td>
<td>指向本版片段的局部引用；`seq`按明确选择严格1..n，沿用 `author_selected_order`</td>
<td>来源原有顺序证明；不从文件行号补序</td>
</tr>
<tr>
<td>`presentation_items`</td>
<td>本版呈现文字、所指成员及来源</td>
<td>新事实发生次数、G/H关系或已写书稿</td>
</tr>
<tr>
<td>`materials`</td>
<td>实际收到的原文字串、原字节摘要、提交身份、接收时间与来源说明</td>
<td>对原主张的核实、外部来源的修订权</td>
</tr>
<tr>
<td>`source_bindings`</td>
<td>真实已知的四种来源分支，以及定位解析状态和分支详情</td>
<td>第五种猜测来源；“已解析”不代表“已证实”</td>
</tr>
<tr>
<td>`basis_refs`</td>
<td>原生引用的显式分型，保留原合同形状与值</td>
<td>为旧来源补`owner`、整数版本或假C11</td>
</tr>
</table>
局部片段/材料/来源联系/呈现号分别为 `fi_`、`mt_`、`sb_`、`pi_` 加32位hex。它们只在外层结构版本的范围内定位，不能拿去当跨版本正式事实身份。列表中的局部ID唯一，引用必须在正确的类型列表中命中。
来源类型仍只有 `PROSE_EXTRACTION`、`AUTHOR_DECLARATION`、`SYSTEM_PROPOSAL`、`CHAPTER_LOCAL_DELTA`。不知道来源类型时可保留真实材料和原引用，不能造 `UNKNOWN` 第五类或把旧 `ledger_entry` 自动改成作者声明。
`RESOLVED`只表示可信来源路径已核清所指来源身份或定位；`UNRESOLVED`必须有真实原因及实际收到的材料。明确无权、假证明或已证实的摘要冲突不能降级成未解析来绕过拒绝。
作者声明可以定位到真实收到的作者原话，无须C11或外部核实。接受片段和作者签字只有确实存在时才填写；保存候选不会生成它们。旧书稿摘录没有合法版本/锚时仍标未解析，不补空锚；系统生成记录不替代作者签字；章局部增量不得把正在签发的自身版本写成其已存在来源，更不能伪造结算回执。
**只阻断不满足条件的那项用途。** 未解析材料可获准保存、查看；依赖它做采用、结算或求值时，分别检查所选用途真正要求的证据与许可，不自动把整次章CI变成硬阻断。
## 4. 版本签发、摘要与临时编号
F006处理严格限定：**只对新结构类型签正整数 ****`rev`****，旧对照的F006冲突计数不变。** 第一版为实际成功保存的1；新内容成功保存才增加一版。选回旧版、退役或同操作重放不增加内容版本。当前选择、最大已签发版、对象状态水位和工作区容器版本分别记录，互不替代。
结构摘要的唯一预像是：`{identity:{project_id,branch_id,owner,object_type,id,rev}, structure_content:StructureContent}`。它排除自身 `content_sha256`、`save_operation_id`、当前选择、退役提示、权限和读写回执；外部引用本身的摘要仍包含在本体内。容器摘要、书稿摘要、对象摘要和读取依据摘要不能互换。
规范JSON采用严格UTF-8、无BOM；键按解码后的Unicode码点排序；数组保留顺序；无多余空白，末尾恰好一个LF并计入摘要/字节数。保持非ASCII文字、原换行和Unicode形态，不trim或归一化。解码前拒绝重复键、孤立代理字符、NaN/Infinity及不能无损处理的数字。新机器整数在明确安全范围内，不让bool冒充；合法旧整数超出本批实现可无损表示的范围时，保留原材料并拒绝该强类型消费，不把它说成旧合同非法，也不强转舍入。
原材料的 `raw_content_sha256` 只对原始文字UTF-8字节计算，不额外加LF。材料片段用零基、Unicode码点、前闭后开的坐标，并校验切片摘要；不混用UTF-16或文件行号。
创建/保存请求中的新局部记录可以使用 `NEW:<candidate_scope>:<local_key>`。本稿把承接位置落定为：
- `CREATE_OBJECT`和`SAVE_VERSION`的 `action_input` 必填 `candidate_scope`；CREATE另填 `new_object_ref`，它必须是同`scope`的NEW引用。
- CREATE中新增对象及局部定义都用NEW。SAVE保留本对象历史中真实已知的局部ID，新局部定义用同`scope` NEW。一个占位号只能定义一次、只属一种类型；无定义、跨`scope`或类型冲突都拒绝。
- 写入口在成功提交中一次签发ID，仅替换合同明确的局部标识/引用位置。原文里的NEW字样不改，原生外部引用不改；不签发正式世界实体或事实ID。
- 稳定成功结果的 `local_id_map` 保存 `{placeholder, local_kind, resolved_id}` 列表，按placeholder码点顺序固定，最多128项。五种`kind`是结构对象、事实片段、材料、来源联系、呈现片段；REGISTER/SELECT/RETIRE为空列表。
- 同操作重放返回相同映射，不重复分配ID。请求摘要计算在替换前，内容摘要在替换后。持久本体的类型化ID/引用不含NEW；历史映射中的placeholder和原材料字面量是明确例外。
## 5. 五种写动作及失败边界
所有写请求都带固定合同/版本、`operation_id`、`action`、`expected_container`和唯一对应的 `action_input`。作者、作品、许可上下文从受信组装层提供，不接受请求自授。
<table header-row="true">
<tr>
<td>动作</td>
<td>请求重点</td>
<td>一次成功的效果</td>
</tr>
<tr>
<td>`REGISTER_BRANCH`</td>
<td>作者明确显示名；容器预期0/null</td>
<td>首批只登记一个真实编辑分支，不建空结构对象</td>
</tr>
<tr>
<td>`CREATE_OBJECT`</td>
<td>已登记分支、`scope`、NEW对象、完整本体输入</td>
<td>原子生成对象、r1、选择r1及固定映射</td>
</tr>
<tr>
<td>`SAVE_VERSION`</td>
<td>最大版引用、对象状态水位、当前选择、完整新本体及`scope`</td>
<td>保存最大版+1并选择新版；旧版全部保留</td>
</tr>
<tr>
<td>`SELECT_VERSION`</td>
<td>上述三项预期及同对象已存目标版</td>
<td>只改当前选择；不复制一份新内容、不采用事实</td>
</tr>
<tr>
<td>`RETIRE_OBJECT`</td>
<td>上述三项预期</td>
<td>独立标退役；不删除旧版、不改变其内容摘要</td>
</tr>
</table>
写前核权限、类型和真实来源资格；然后在原工作区受限键内核完整状态及摘要。新动作核容器版本/SHA及对象的最大版、选择、状态水位。提交使用原 `commit_guarded` 的同代能力，权限提供方另保证当次许可与撤权的接纳顺序。容器、对象和操作记录必须一致，读到坏状态不能按空集合重建。
保存请求须提供完整本体，不能自动从当前或最大版补字段。当前选r1、最大已到r3时，新保存仍发r4；选回r1不复制r4。首批没有恢复ACTIVE、改分支、分叉、合并、物理删除或正式结算动作。
所选事实顺序不是严格1..n时，写动作以 `REJECTED/SEQ_NOT_TOTAL_ORDER` 拒绝，提交状态为 `NOT_COMMITTED`。这是既定数据硬门在新写入口的表达，不接受带问题绕过或静默补序；不额外修改章CI的输出状态或必检项。
成功操作固定主体、原许可引用、完整请求摘要和稳定业务结果。摘要包含真实作者/作品、执行主体及完整业务请求，排除临时grant/session。重新取得许可不会改变同一业务请求的身份；调用者也不能为“重试”擅自改原CAS字段或操作内容。
已提交同操作、相同主体和请求，在重新核当前权限后先回原结果，再谈新CAS和增量容量。不同请求或主体同号拒绝。新操作内容与最大版完全相同、选择没有变化或对象已退役时，按明确拒绝码返回，不新增业务版本/状态/操作记录。
`StructureWriteResponse`把业务结果与当前观察水位分开：同操作重放的 `result`相同，`replayed=true`；`container_observation`可以已经前进。结果不内嵌包含自身的容器SHA。保存成功只表示候选已保存，不能改说已采用、已兑现或已结算。
校验拒绝发生在提交前时，零新增业务写入且不调用后端commit。提交途中故障可能已有预备物理写入，结果必须区分 `NOT_COMMITTED`、`COMMITTED`、`UNKNOWN`；不能笼统声称所有失败都物理零写。状态不明先走原恢复边界核原操作，不能换号重建、补成功或自动删日志。本稿只承诺明确已提交操作的幂等，不增加永久回滚终态数据库。
## 6. 权限与真实提供路径
现有Router消费principal字符串并做作者映射，工作区HMAC保护已签发句柄。这些不能独自证明登录、任务许可或撤权。共同调用合同已有 `PERMISSION_SNAPSHOT v1` 和范围交集的正式语义，但其共同调用runtime未开放。
首批候选为本地受信宿主内的 `StructureAccessProvider`。它复用“点名目标 ∩ 当前任务/有效Focus ∩ 权限快照 ∩ 章结构合同”的含义，不另建多人共享或代理转授权体系。模型拿不到Router、签发入口和工作区通用写入口。
<table header-row="true">
<tr>
<td>候选接口</td>
<td>必须提供的事实</td>
<td>实际绑定状态</td>
</tr>
<tr>
<td>`resolve_author_session`</td>
<td>宿主实际认证主体、执行者、会话代际、到期和撤销状态</td>
<td>这条产品链未核到真实绑定；不能固定填auth:cz或猜进程用户</td>
</tr>
<tr>
<td>`resolve_workflow_permit`</td>
<td>实际任务/工作卡原件、作者授权版本、范围、阶段与有效期</td>
<td>未核到current提供路径；不得用引用形状代替原件</td>
</tr>
<tr>
<td>`resolve_permission_snapshot`</td>
<td>原权限快照及独立的当前策略/撤权/范围查询</td>
<td>原合同语义可复用，实际current查询仍须接入</td>
</tr>
<tr>
<td>`issue_action_grant`</td>
<td>对已验证请求和接收者签发私有许可与不可伪造上下文</td>
<td>新候选接口；不注册为模型工具</td>
</tr>
<tr>
<td>`authorize_action`、`with_current_authorization`</td>
<td>初次核范围，并把提交/交付接纳与撤权排成确定顺序</td>
<td>新候选接口；做不到顺序保证就不开启动作</td>
</tr>
</table>
`StructureAccessContext`是进程内不透明能力对象，不能由JSON、同名类或hash字符串重建。`ActionGrant`是其私有不可变许可记录；序列化样例只说明字段，不能取得权限。
本稿集中关闭原辅助表里未展开的引用形状：权限快照、Focus、任务许可、工作卡、作者动作统一使用新提供方局部的 `AuthorityRecordRef={provider_ref,record_kind,record_ref,record_sha256}`。`record_ref`必须精确定位实际来源的不可变版本，摘要核原件；仍另查当前有效性。这是新provider内部定位合同，不是通用故事`Ref`，也不是声称原任务系统已经有这四字段。提供方无法解析真实原件时不得签发；不能用候选键凑出“已有服务”。
许可的执行主体字符串与材料中的 `ActorRef`用途不同：前者区分AUTHOR/CONTROLLED_AGENT的实际执行许可，后者区分AUTHOR/SYSTEM材料来源。SYSTEM来源不能自动变成获许可代理。身份、动作、对象、NEW范围、接收者、任务/工作卡、原授权、请求摘要和有效期必须同时绑定。
<table header-row="true">
<tr>
<td>动作</td>
<td>作者本人</td>
<td>受控代理</td>
</tr>
<tr>
<td>登记分支</td>
<td>当前初始化任务和明确登记动作</td>
<td>首批不开放</td>
</tr>
<tr>
<td>新建/保存候选</td>
<td>当前工作卡和作者流程许可，预览包含自动选新版的效果</td>
<td>只代存作者已批准的精确请求，不自行扩大目标或内容</td>
</tr>
<tr>
<td>改选/退役</td>
<td>当前工作卡及独立明确动作</td>
<td>首批不开放</td>
</tr>
<tr>
<td>固定查看</td>
<td>当前查看许可；不为只读强制造写作卡</td>
<td>当前任务/工作卡许可，实际模型接收时必须获MODEL交付许可</td>
</tr>
</table>
`GrantScope.target_mode`集中定为四种：`INITIALIZE_BRANCH`只准登记分支、创建对象数0；`NEW_OBJECT`只准本操作创建一个对象；`EXISTING`必须列非空精确引用；`REPLAY_COMMITTED`只准回读指定已提交操作及其实际目标，不再分配新身份。空数组不能解释成全选。
重放丢失回执的CREATE/REGISTER时，宿主须先持有“核指定操作”的当前许可，由原归属在受信侧核同一主体/原请求，私下解析该操作实际发出的分支或对象，再绑定最终重放许可。这个中间核对不向模型泄露对象存在性，不重新按NEW创建，也不要求作者猜出丢失的ID。最终对象重放许可必须含实际目标；REGISTER重放只涉及实际已登记分支，不伪造结构`Ref`。
每个grant只绑定一个规范请求，最长300秒，并取会话、任务和原权限更早的期限；每次调用和已提交重放仍查当前许可。进入受信执行区时检查期限与撤权：撤权先完成则不执行动作；有限原子动作先被接纳则完成本次提交/交付，后来的撤权作用于后续动作。已提交事实不因随后撤权被倒写，已交付字节不能声称收回。进程重启使旧不透明上下文失效，重新从实际宿主及权限路径签发。
当前这些实际绑定仍缺。它们已有明确候选接口和字段，但不能因此声明可用。新能力只登记到章结构专属注册，**不得进入十账capability snapshot**；合同文件存在、Schema样例通过或工具安装均不能开放动作。
## 7. 固定版本读取
读请求固定为 `{contract,version,request_id,action:READ_PINNED,structure_refs}`。只收非空的完整结构引用，保持请求顺序；不支持current、路径、自然语言、自动展开、搜索或分页。
读取顺序是：先核当前身份/范围和输入限额，再请求原归属从一次受信存储视图提供指定旧版；逐项核完整身份、内容协议、版本、SHA、来源及请求覆盖；形成完整响应，交付前再核授权接纳。当前编辑选择前进不改变指定旧版。退役状态由同次视图独立返回，不改旧内容、不复活对象；真缺失、坏摘要或越权分别拒绝，绝不退回current。
相同对象同一版本却摘要不同的请求互相矛盾，整体拒绝；重复完全相同的引用也按明确输入规则拒绝，不静默去重。每个成功项含 `structure_ref`、`structure_content`、`retired_notice`，不返回整个操作审计或自动展开外部依赖。受众无权看完整本体而尚无合格裁剪能力时，拒绝该完整对象，不交半份却自称完整。
成功清单必须一一覆盖请求和数据；来源清单按完整引用规范顺序排列，数据保持请求顺序。每项含全部身份，不能只交一个聚合SHA来代替字段。读取依据摘要绑定本次返回引用、退役观察和实际授权依据；它不含自身摘要或响应字节数字段。存储代际只作读视图观察，不是作品分支或对象修订。
`OK`要求完整非空数据和真实权限依据。原四态保留含义，但本点名读取没有合法EMPTY输出场景；缺版本不算空成功。任何REJECTED/ERROR都为 `data=null`、来源清单空、零返回对象/业务项；作者/作品/存储代际和私有依据遮蔽。失败文字按固定码表给出，不拼接输入、原文或堆栈。
本独立入口不调用旧公共v1中互相冲突的pinned失败回执校验路径，也不修改该旧问题。已有十账、C9、rh_、G/H、认识接口和报告游标的关闭范围继续有效。
## 8. 首批候选上限
<table header-row="true">
<tr>
<td>限制</td>
<td>本稿候选值</td>
<td>触限处理</td>
</tr>
<tr>
<td>结构集合规范UTF-8</td>
<td>16MiB</td>
<td>拒绝新保存；保留历史，不清理腾空间</td>
</tr>
<tr>
<td>单作品结构对象</td>
<td>128</td>
<td>不自动新建第二宿主</td>
</tr>
<tr>
<td>单对象版本</td>
<td>256</td>
<td>不覆盖/压掉旧版</td>
</tr>
<tr>
<td>成功操作记录</td>
<td>4096</td>
<td>不删除旧幂等记录；合法已提交重放不新增记录</td>
</tr>
<tr>
<td>完整单版本记录</td>
<td>128KiB</td>
<td>含`Ref`、本体与保存操作号，不只算句子</td>
</tr>
<tr>
<td>完整写请求</td>
<td>256KiB</td>
<td>提交前拒绝</td>
</tr>
<tr>
<td>完整写响应</td>
<td>32KiB</td>
<td>提交前检查预期结果；提交后故障不能谎报未提交</td>
</tr>
<tr>
<td>临时编号映射</td>
<td>128项/操作</td>
<td>不截断映射、不重复造号</td>
</tr>
<tr>
<td>读引用数</td>
<td>50</td>
<td>明确拒绝，不自动分批</td>
</tr>
<tr>
<td>读业务项</td>
<td>100</td>
<td>版本数＋各本体fact_items、presentation_items、materials三数组长度；选择/来源证明不重复计项</td>
</tr>
<tr>
<td>完整读响应</td>
<td>256KiB</td>
<td>所有字段、失败外壳及末尾LF都计入；超限整体拒绝</td>
</tr>
<tr>
<td>短期grant</td>
<td>最长300秒</td>
<td>取真实上游更早期限；过期不接纳</td>
</tr>
</table>
单版本保存同时满足“1＋三数组长度≤100”，保证它能被完整点读；批量合计仍可能超限。原样材料里的JSON数组不自动变成正式业务成员，不能把事实成员挪成材料就声称相同强用途已满足；全部材料仍计UTF-8字节。
完整响应字节数包含自身计数字段。先算其余SHA，再从计数0迭代至实际规范编码长度不再变化，最多8轮；实际交付就是这一份字节。失败的业务项为0，但响应字节数必须是正的实际值。无法收敛或生成完整合格结果时交付有界错误，不截断原成功数据。
这些是明确的候选初值，尚未做真实小说规模或性能实测。容器保留历史会增长，提交时会重写集合；本稿没有把128对象/256版本承诺成任意长篇都足够。后续如要调整上限须按实际容量证据改受控配置/合同，不能暗中删历史或换宿主。
## 9. 验收要求与本轮实际检查
主链使用完整合成数据：REGISTER后容器1；CREATE保存并选r1后容器2、对象状态1；SAVE保存并选r2后容器3、对象状态2；READ请求r1仍返回r1，当前选择保持r2，所有业务数据不变。r1与r2的句子、顺序和摘要各自不同；重放CREATE回同一r1与映射，观察水位可以是3。
26条后续工程场景覆盖原9场景、跨类型摘要、NEW映射、同操作不同请求、容器/对象CAS、容量边界、UTF-8计数、无权遮蔽、读中撤权、退役历史、恢复未知与只读零业务写入。都要求从真实宿主权限、原结构归属和新读写入口走通；不能只跑Schema或旧current测试冒充接通。
本轮只核JSON Schema自身合法性、引用可解析、合成正反例形状、固定摘要和完整字节算术。另保留一个“形状合法但`seq`跳号”的反例，明确它仍须被语义规则拒绝；Schema通过不代表该对象可交付或可采用。没有运行产品或效果测试。
## 10. 当前采用与下一停点
EA01—EA03已采用，本稿具体字段、拟名、容量、首批权限范围及provider局部定位形状仍待合同审查。原F001—F197基线与F006冲突计数不变；新逐字段目录的数量是接口/输入/回执字段定义展开数，不是新增相同数量的故事通用字段。
本稿给出了具体候选，不再以“以后定”代替字段和行为。尚未接通的是实际宿主会话、任务/工作卡、当前权限与撤权提供路径，以及新的结构归属和读写运行入口。这些是后续有授权工程写集要连接和验证的内容，不能靠本轮文档或合成对象宣布解除。
继续不开票、不改现役合同/产品代码、不迁移，不开放r5整版、G/H、believes或强消费者。已有采用台账只记录工程边界，不把本稿具体合同倒签成已采用。
来源：Codex
## 完整附件和核验
完整ZIP含144个文件，923,201字节。70份工程来源与固定提交blob一致；汇总Schema含89个类型定义，逐字段目录展开284处接口字段位置，原F001—F197和F006冲突计数不变。22个合成形状及摘要/字节算术已核，26条工程场景仍待真实入口验证，未运行产品测试。
SHA-256：`3285d9df2c58545b20d6242c45bedf68ce2bed0e7595d0d1099247b5f361fb8a`。
<file src="file://%7B%22source%22%3A%22attachment%3Ab8c9b611-ca3e-4f98-bccd-5aa2133902e9%3ACHAPTER_STRUCTURE_FORMAL_CONTRACT_CANDIDATE_20260914_R01.zip%22%2C%22permissionRecord%22%3A%7B%22table%22%3A%22block%22%2C%22id%22%3A%22a24cf9ef-b77d-46da-951d-1d5896720457%22%2C%22spaceId%22%3A%227065cadc-4d0f-8121-b113-0003bee0846d%22%7D%7D">CHAPTER_STRUCTURE_FORMAL_CONTRACT_CANDIDATE_20260914_[R01.zip](http://R01.zip)</file>
逐字段合同表已在本页下方四个子页完整列出，回读共284个编号，无缺号或重复；机器表与完整原件在ZIP中。
来源：Codex
<page url="https://app.notion.com/p/3da5cadc4d0f8164b3f4f15e7d06cf8c">逐字段合同｜1/4（候选）</page>
<page url="https://app.notion.com/p/3da5cadc4d0f81bb843bfe60c4defce5">逐字段合同｜2/4（候选）</page>
<page url="https://app.notion.com/p/3da5cadc4d0f81ca917ac384abd4c1ba">逐字段合同｜3/4（候选）</page>
<page url="https://app.notion.com/p/3da5cadc4d0f81039356e80719b2eb1e">逐字段合同｜4/4（候选）</page>
<page url="https://app.notion.com/p/3da5cadc4d0f81f6a70ed160a895297f">章结构合同｜大白话与五张管线图</page>
