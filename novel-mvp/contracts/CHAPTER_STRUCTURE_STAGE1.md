# 章结构保存与固定读取：段一交付说明

执行身份：Codex。
依赖的问题键与版本：`架构.核心结构与操作协议v0.1`；[正式 R01 与 R01.1、R01.2](https://app.notion.com/p/3da5cadc4d0f818db55afc75364b5ef5)；[CCZ-190](https://linear.app/ccz/issue/CCZ-190)。

这一段负责保存结构候选、保留旧版、按指定引用取回旧版。保存、选择、退役不表示采用故事事实、兑现安排或章节结算。

## 七项写集怎样交接

| 部分 | 输入 | 输出 | 保存位置 | 怎样交给下一站 | 谁在用 |
| --- | --- | --- | --- | --- | --- |
| 受限键 | 受信工作区 | chapter_structures | AuthorWorkspace 原后端；逻辑文件名仅后端登记 | 业务按逻辑键访问 | 结构内核 |
| 五种写动作 | 工作区、许可挂接点、请求 | 固定写响应 | 同一集合的对象、历史与成功操作记录 | 完整引用、稳定结果及编号映射 | 受信宿主 |
| 固定读取 | 非空完整引用列表 | 请求顺序不变的版本及退役提示 | 同一次存储快照；只读 | 指定 r1 就取 r1，不退回 current | 获准接收者 |
| 权限挂接点 | 实际宿主提供方的未来绑定 | 当前拒绝 CAPABILITY_UNAVAILABLE | 不保存伪会话或伪许可 | 未绑定时在探查对象前拒绝 | 两个入口 |
| 固定名称 | R01 已定名称 | CHAPTER_STRUCTURE、CHAPTER_STRUCTURE_VERSION、structure_content | 专属代码与 Schema | 不进入十账能力快照 | 保存与读取组件 |
| 身份及版本 | 保存动作内核输入 | 随机身份、内容版本、状态水位 | 原对象和不可变历史 | 七项完整引用共同定位 | 保存、重放、读取 |
| 摘要及局部编号 | 原请求、完整内容、实际材料 | 规范摘要、严格顺序、固定映射 | 版本与成功操作记录 | 原材料 NEW 字样保持原样 | 内核和离线测试 |

实现位置：

- `mvp/chapter_structure_workspace.py`：入口、保存/读取内核及响应。
- `mvp/chapter_structure_contract.py`：类型、规范字节、摘要、顺序、局部引用与 NEW 替换。
- `mvp/chapter_structure_access.py`：抽象提供方和不透明上下文的挂接类型。
- `mvp/workspace.py`：受限键，以及 R01.2 必需的私有只读物理核查。核查不是新模型工具、回执字段或对外审计接口，业务不拼物理路径。
- `config/chapter_structure/capacity.json`：十三条受控配置。
- `CHAPTER_STRUCTURE_FIELD_MAP.json`：NC001—NC284 逐项对应。

## 离线检查与真实权限

本段没有实现权限提供方的真实返回，也没有“永远允许”的测试权限服务。require_bound_access 当前始终拒绝；JSON、同名对象或客户端构造不能取得权限。两个入口已有取得绑定后的执行路线，真实签发与安装仍属段二。

正向测试直接检验私有保存内核，使用合成作品、材料和执行者。它验证保存行为，不证明合成身份具有真实授权。公开入口另测未绑定时拒绝、零对象探查，没有伪造权限五接口。

许可、Focus、作者动作等字段在 284 表里标为 SHAPE_ONLY_REAL_PROVIDER_UNBOUND。格式登记不表示原件存在或当前许可有效。

K01—K03 仍 BLOCKED，integration_status 不改。真实权限链、撤权及 26 条工程场景未运行；不开放强消费者或迁移。

## R01.2 的实际核查

发生提交 I/O 故障后，回读到相同操作和请求摘要的成功记录才报 COMMITTED。提交前无准备日志、故障后物理核查与提交前一致且无新增残留，才报 NOT_COMMITTED。其余报 UNKNOWN，不以“当前指针未变”推断“物理零写”。

证据保存在持有内核的受信进程对象中，与操作号和请求摘要关联；不进入响应。它不是永久恢复账，不承诺跨进程保存诊断列表。重启后的判断须重新核查实际存储；正式接入的宿主须持有诊断对象，不能销毁证据却继续宣称确定态有据。

底层已明确提交但业务回读失败，仍用 COMMIT_READBACK_FAILED，不伪造 OK。

## 容量配置

以下全部是**未实测初值**，没有真实长篇容量或性能实验。改变限制须有证据、版本和原因；不得删历史或换宿主。当前 Schema 保留 R01 初始范围，放宽时须一并对齐其约束，不得只改一份形成矛盾。

| 配置位置 | 初值 |
| --- | --- |
| owner.container_max_utf8_bytes | 16 MiB |
| owner.objects_max | 128 |
| owner.versions_per_object_max | 256 |
| owner.committed_operations_max | 4096 |
| owner.version_record_max_utf8_bytes | 128 KiB |
| owner.write_request_max_utf8_bytes | 256 KiB |
| owner.write_response_max_utf8_bytes | 32 KiB |
| owner.business_items_per_version_max | 100 |
| max_new_id_mappings_per_operation | 128 |
| read.max_input_refs | 50 |
| read.max_returned_business_items | 100 |
| read.max_response_bytes | 256 KiB |
| grant_max_lifetime_seconds | 300；真实时效核验仍属段二 |

完整请求、版本、集合、响应分别计数；读业务项按“版本本身＋事实、呈现、材料三数组”计算。已有操作重放不重复消耗新增容量。读请求和响应仍检查本次限额。

## 定点读取留痕

CZ 在 Codex 当前对话明确授权：“允许定点只读，核清后继续」”。原消息时间和 ID 未取得，不以记录时间冒充。

仅提取 R01 附件内固定提交 c18736de 的以下局部规则，未导入或调用旧公共 v1 整包回执校验器：

| 来源 | 核对内容 |
| --- | --- |
| validate_ledger_read_tool_contract.py L147—L162 | 投影带编译版本与输入摘要；非投影禁止两项；目录快照账名为 null；其他来源需账名；章节修订只认章节账 |
| C11_CHAPTER_REVISION_LEDGER.md L87—L115 | 章节号、修订号、书稿摘要；指定修订的 Unicode 码点坐标 |
| validate_c11_chapter_revision_ledger.py L284—L302、L676—L685 | 历史身份不得被 current 顶替；锚须核指定文字与切片摘要 |
| TRACEABLE_PROVENANCE_SEAL.md L74—L112 | 保留原来源身份；材料身份与章节版本不同；wrapper 不重新发号 |

复制格式及静态对应关系与实际来源核验分开。静态规则已写入，实际来源存在性、外部引文及权限仍须真实提供路径；候选保存不能替代这些证明。

## 段一验收定位

计分沿票面：0 未动；25 能跑但不落盘；50 可重启；75 反例正确拒绝；100 重放与并发稳定。下表仅针对段一离线范围，不给段二计分。

| 判据 | 进度 | 不应发生 | 夹具 |
| --- | --- | --- | --- |
| 登记、两次保存、读旧版、重放 | 100 | 读 r1 返回 r2；重启丢历史 | test_stage1_register_create_save_read_replay；test_stage1_same_operation_conflicts_and_concurrency |
| 业务结果与观察水位分开 | 100 | 水位前进改写原结果或重分配身份 | 主链重放及并发夹具 |
| 三态与两侧核查证据 | 100 | 报确定态却无对应证据；残留误报零写 | test_stage1_io_commit_state_evidence；test_stage1_io_leftover_not_reported_not_committed；test_stage1_post_fault_recovery_preserves_old_version |
| seq 硬门 | 100 | 跳号被补齐、落盘或绕过 | test_stage1_seq_gap_rejected |
| 284 字段对照 | 100 | 缺号、漂移、同义另造；许可形状冒充权限 | test_stage1_field_catalog_mapping；test_stage1_provider_unbound_closed |
| 十三条配置 | 100 | 触限写入、删历史、重放被当新增 | 容量组夹具；并发主链使用同一配置 |
| 接入边界 | 100 | 离线成功冒充真实权限可用 | test_stage1_provider_unbound_closed |

测试只用合成短句，不包含小说书稿或逐句引文。代码、离线测试、PR 与 main 合并的状态分别以本次交付回执为准。

来源：Codex
