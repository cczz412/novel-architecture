# 动作身份与幂等｜合同原文迁入

> 交付身份：仅文档迁入审阅稿。本批尚未执行主存切换，运行能力仍按 GitHub 已合代码与各自授权判断。
> 来源：[CCZ-89｜M1 动作身份、请求封存与项目级幂等合同（Codex）](https://linear.app/ccz/document/4e7563eb6d19)（文档 ID：`d9380e9e-f16e-44dc-b525-0da52dc6b787`）。
> 原版本：m1-action-request-v1；author-workspace-canonical-json-v1；2026-08-24 冻结稿＋08-25 扩展。
> 原文区 SHA-256：`6d75dd4246b7db7274ea33ab5f4103cc343afa4509b428166bdfc416bc447dd4`。
> 来源、批准回执、历史状态差异及本批互链见 [迁移索引](CCZ184_CONTRACT_MIGRATION_R01.md)。

## 原文区

下方保留本次读取的完整 Markdown 原文，包括原有版本、日期、字段、示例与链接。原文里的“当前代码”“待批准”等描述属于其记载水位；迁移说明与原文分开，不借此重定语义。

<!-- CCZ184_SOURCE_BEGIN -->
> 执行身份：Codex
> 冻结日期：2026-08-24
> 对应票：[CCZ-89](https://linear.app/ccz/issue/CCZ-89/子票m1-动作身份请求封存与项目级幂等)
> 上游证据：[CCZ-87｜关键存储语义原始来源核对（Codex）](<https://linear.app/ccz/document/ccz-87%E5%85%B3%E9%94%AE%E5%AD%98%E5%82%A8%E8%AF%AD%E4%B9%89%E5%8E%9F%E5%A7%8B%E6%9D%A5%E6%BA%90%E6%A0%B8%E5%AF%B9codex-0a8b17726873>)
> GitHub 代码真值：`main@5b4321c8ccf68f419fc0d5de5d8bba50702a79bd`

## 结论

这张票冻结一个很小但关键的合同：

**在第一笔 raw 或 metadata 正式写入前，小说辅助产品必须先把“这是哪个项目的哪次动作、请求内容是什么、允许写哪些对象、以哪一代为 base”保存成一份不可变、项目私有的动作意图记录。**

这份记录可以叫“动作意图”，机器字段可叫 `ActionIntent`。它只证明动作身份和精确计划已经封存，不代表内容已经被 generation 接纳，也不代表作者可以继续下一步。

当前切片的决定如下：

* 动作唯一范围是“作者身份＋项目身份＋动作号”；同一项目的所有动作共用一套动作号空间。
* 动作种类 `M1_PERSIST` 进入请求承诺。同一个动作号换成别的动作种类，也算换请求并稳定冲突。
* 当前 M1 已经拿到完整 bytes，所以在内存里就能算出整批 raw、metadata、receipt 和精确 mutations；不需要“先写一部分再补计划”。
* 当前项目私有边界使用版本化的规范 JSON 加普通 SHA-256，不引入 HMAC 和密钥管理，也不宣称符合 RFC 8785。
* ActionIntent 一旦持久化，该动作号在项目存续期内不自动删除、不允许换请求复用。
* ActionIntent 会封住 base pointer 和精确 target spec。[CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 可以从这份 target spec 派生 generation 身份并决定接纳／终态规则，但不能换 base、换 mutations 或重做 receipt plan。

这份合同不授权改代码。[CCZ-81](https://linear.app/ccz/issue/CCZ-81/待前置m1-raw-接纳恢复与诚实-ready) 仍要等 [CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力)、[CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留)、[CCZ-90](https://linear.app/ccz/issue/CCZ-90/子票m1-acceptedreadydegraded-诚实读回)、[CCZ-85](https://linear.app/ccz/issue/CCZ-85/合同父票m1-raw-动作终态generation-接纳与-orphan-恢复) 和实施验收入口就绪。

## 当前输入、输出和产品缺失

当前 M1 读取已经完整进入内存的 raw bytes、metadata、绑定好的作者与项目身份、动作号、预期版本和准备写入的结构化结果，能够计算不可变对象身份，并在后面写出 raw、input manifest 和 module state。

本票输出：

* 一份项目私有、不可变的 ActionIntent；
* 一套按输入顺序封存的精确 raw／metadata receipt plan；
* 一份稳定的请求承诺；
* “新动作、同请求重放、同号换请求冲突、动作记录无法证明”四类判断；
* 交给 [CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力) 和 [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 的固定 action 引用、base 和 target spec。

小说辅助产品还缺少在任何 raw 写入前，把一次动作的项目范围、请求身份和精确对象计划长期保存并进行版本判断的能力。这会卡住作者安全重试导入：产品无法判断是在恢复原动作，还是同一个动作号已经换了内容，也无法保证冲突请求在写对象前被拦住。

## GitHub 当前代码告诉我们的事

当前代码已经有一部分项目级幂等能力，但检查位置太晚：

* operation receipt 按作者和项目保存在项目目录里，同一项目的所有模块共用动作号空间；
* 当前 `request_sha256` 覆盖动作号、完整 mutations、规范化预期版本，以及可选 guard versions；
* 同项目、同动作号、同 `request_sha256` 会重放旧回执；同动作号换请求会报 `OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST`；
* raw blob 和 metadata 放在作者级共享对象池，回执没有项目号、动作号或接纳阶段；
* `persist_m1_result` 已经校验完整 bytes，却先逐个 `store_immutable`，之后才进入 operation 重放、冲突和版本检查。

所以现在可能出现：新 raw 已经写出，随后才发现同动作号换了请求，或预期版本早已过期。正式合同必须把动作登记提前到第一次 raw 写入之前。

代码入口：

* [动作号与回执路径](<https://github.com/cczz412/novel-architecture/blob/5b4321c8ccf68f419fc0d5de5d8bba50702a79bd/novel-mvp/mvp/workspace.py#L544-L552>)
* [当前请求承诺和重放检查](<https://github.com/cczz412/novel-architecture/blob/5b4321c8ccf68f419fc0d5de5d8bba50702a79bd/novel-mvp/mvp/workspace.py#L694-L805>)
* [当前 operation receipt 字段](<https://github.com/cczz412/novel-architecture/blob/5b4321c8ccf68f419fc0d5de5d8bba50702a79bd/novel-mvp/mvp/workspace.py#L852-L887>)
* [作者级 raw 对象与 receipt 字段](<https://github.com/cczz412/novel-architecture/blob/5b4321c8ccf68f419fc0d5de5d8bba50702a79bd/novel-mvp/mvp/workspace.py#L931-L972>)
* [M1 先写 raw、后 commit 的顺序](<https://github.com/cczz412/novel-architecture/blob/5b4321c8ccf68f419fc0d5de5d8bba50702a79bd/novel-mvp/mvp/ingest_workspace.py#L133-L200>)

## 1. 动作身份和作用域

动作唯一键固定为：

`作者身份＋项目身份＋动作号`

规则如下：

* 作者和项目身份只能来自已经认证并绑定的 `AuthorWorkspace`，调用方不能自报或覆盖。
* 相同动作号在不同作者或不同项目中，是不同动作。
* 同一项目里，动作号跨模块、跨动作种类共用一套空间；`action_kind` 是请求承诺的一部分，不是另一套命名空间。
* 相同内容使用不同动作号，仍是两个动作。作者级物理 blob 可以按内容复用，但动作记录不能合并，项目读取权限也不能互通。
* 动作号缺失、格式非法、项目绑定无法证明时，在任何 ActionIntent、raw、metadata、generation 或 current 写入前拒绝。
* ActionIntent 尚未创建之前，如果输入校验或 expected version 检查失败，本次没有形成已登记动作；修正请求后可以重新发起。
* ActionIntent 一旦持久化，同一动作号只能重放这份请求。后面即使崩溃、竞争失败或尚未接纳，也不能换内容复用。

## 2. 请求承诺覆盖什么

“请求承诺”是用来判断重试是不是同一件事的摘要。它不是“当前项目状态”的摘要，所以不把后来读到的新 base 混进同请求比较。

请求信封 `m1-action-request-v1` 必须覆盖：

* 合同版本和规范化规则版本；
* `action_kind=M1_PERSIST`；
* 绑定得到的作者身份、项目身份和动作号；
* 按原始输入顺序排列的 upload slots；
* 每个 slot 的完整预计算 immutable receipt：blob 身份、对象种类、raw SHA-256、字节数、metadata SHA-256；
* `input_manifest` 和 `module_state` 两份精确 mutation payload 的 SHA-256；
* 规范化后的 expected versions；版本号和可选 payload SHA 都要进入；
* 如果当前动作使用 guard versions，也要按同样方式进入。

以下内容不能进入同请求判断：

* 时间戳、临时文件路径、进程号、随机数、重试次数和日志字段；
* 本轮后来读到的 current pointer；
* [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 才会定义的接纳结果、父链结果或终态；
* 任何会让同一逻辑请求每次计算出不同值的运行时信息。

raw 身份必须按原始 bytes 计算，不能先统一换行、改编码或重新保存文本。输入列表顺序保留；JSON 对象键顺序不影响结果。

## 3. 规范化和哈希

当前私有切片冻结 `author-workspace-canonical-json-v1`：

* JSON 对象键按字典序排列；
* 列表顺序保留；
* UTF-8 编码，不把非 ASCII 字符改成转义形式；
* 使用紧凑分隔符；
* 文末保留一个换行，与当前工作区 canonical bytes 保持一致；
* 拒绝 NaN、Infinity 和其他非有限数字；
* bytes 不直接进入 JSON，只能以 raw SHA-256 和 size 表示；
* 规范化规则的版本必须写进请求信封。

请求承诺是：

`SHA-256(canonical_bytes(request_envelope))`

这不是 RFC 8785／JCS。RFC 8785 只作为确定性 JSON 的外部参考；当前项目继续沿用兼容现有代码的独立规则，并用版本号防止以后跨语言迁移时把两种算法混在一起。

当前记录留在项目私有区，不进入外部 API、遥测或跨项目材料，因此使用普通 SHA-256。HMAC 不是加密，也不能替代读取授权；本切片不增加密钥保存、轮换和旧记录验证负担。将来如果 commitment 要离开私有边界，另开票设计 HMAC 和密钥版本。

## 4. 固定规范化测试向量

输入信封：

```json
{"action_kind":"M1_PERSIST","author_id":"a_00000000000000000000000000000000","expected_versions":{"input_manifest":{"sha256":null,"version":0},"module_state":{"sha256":null,"version":0}},"mutation_payload_sha256":{"input_manifest":"4444444444444444444444444444444444444444444444444444444444444444","module_state":"5555555555555555555555555555555555555555555555555555555555555555"},"normalization_profile":"author-workspace-canonical-json-v1","operation_id":"op-demo-001","project_id":"p_11111111111111111111111111111111","schema_version":"m1-action-request-v1","upload_slots":[{"immutable_receipt":{"blob_id":"i_00000000000000000000000000000000_raw_upload_2222222222222222222222222222222222222222222222222222222222222222","content_sha256":"2222222222222222222222222222222222222222222222222222222222222222","kind":"raw_upload","metadata_sha256":"3333333333333333333333333333333333333333333333333333333333333333","size":12},"slot":0}]}
```

上面这一行结尾还要带一个换行。预期 SHA-256 是：

`76a4a565a7488b108474b8a06ec405d9856afcb2ccf95f073d488dd9d6bd2dc8`

实现时必须另外证明：

* 只调整 JSON 对象键顺序，摘要不变；
* 调整 upload slot 顺序、raw bytes、metadata、mutation 或 expected versions 中任一项，摘要都变化；
* 非有限数字在写 ActionIntent 前被拒绝。

## 5. ActionIntent 封存什么

ActionIntent 是项目私有、不可变的完整记录。为了避免“两份文件只写成一份”的新故障窗口，当前最小切片把私有 receipt plan 直接放进 ActionIntent；以后若拆成独立对象，必须使用内容寻址并让 intent 在同一笔耐久创建里绑定 plan SHA。

| 内容 | 必填 | 进入请求承诺 | 对外可见 | 后续读取者 |
| -- | -- | -- | -- | -- |
| schema 和规范化版本 | 是 | 是 | 可返回版本号 | [CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力)、[CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) |
| 作者、项目、动作号 | 是 | 是 | 只返回调用方自己提交的动作号 | [CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力)、[CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) |
| 动作种类 | 是 | 是 | 可返回固定种类 | [CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力)、[CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) |
| request SHA-256 | 是 | 它是承诺结果 | 不进普通日志或安全摘要 | [CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力)、[CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) |
| upload slots 和完整 receipts | 是 | 是 | 否 | [CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力) |
| 精确 mutations 及各自 payload SHA | 是 | 摘要进入 | 否 | [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) |
| 规范化 expected／guard versions | 是 | 是 | 只返回稳定冲突类别 | [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) |
| 创建时的 base pointer 与 manifest SHA | 是；空项目可为 null | 否 | 否 | [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) |
| sealed target spec 和 target spec SHA | 是 | 否 | 否 | [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) |
| target generation ID | 不回写 ActionIntent | 否 | 否 | 由 [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 从 sealed target spec 确定性派生 |
| raw bytes、正文、临时路径 | 禁止保存 | 不适用 | 否 | 需要时由受限对象读取能力取得 |
| ACCEPTED／READY／DEGRADED 等状态 | 禁止由本票写入 | 不适用 | 不适用 | [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留)、[CCZ-90](https://linear.app/ccz/issue/CCZ-90/子票m1-acceptedreadydegraded-诚实读回) |

sealed target spec 必须固定：

* base generation ID 与 base manifest SHA；
* 完整 receipt plan；
* exact mutations；
* expected／guard versions；
* action kind、动作号和 request SHA；
* generation schema 版本占位。

[CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 可以冻结 generation schema、从 target spec 派生 generation ID、执行 current 条件切换并重建终态，但不能改动这份 spec。这样重放不会静默 rebase 到后来出现的新 current。

## 6. 创建顺序

正常新动作必须按这个顺序：

1. 在内存中完成整批 M1 输入校验和 JSON 可序列化检查。
2. 纯计算每个 raw SHA、size、metadata descriptor SHA 和完整 immutable receipt。
3. 用预计算 receipts 组装精确 `input_manifest`、`module_state` mutations 和请求信封。
4. 计算请求承诺；到这里仍然是零持久写入。
5. 进入项目独占边界，先处理已有 prepare／receipt，再按动作号查已有 ActionIntent 和旧版操作证据。
6. 如果是全新动作，读取 current，校验 expected／guard versions，封住 base pointer 和 target spec。
7. 用 create-if-absent 写 ActionIntent；完成文件同步、目录同步和内容读回。只有耐久性和完整性都能证明，才算创建成功。
8. 离开登记边界后，只允许发布 ActionIntent receipt plan 中列出的 raw 和 metadata。
9. 对象发布完成后，把同一个 action 引用交给 [CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力) 做动作私有的完整读取验证。

任何一步在 ActionIntent 确认前失败，正式 raw／metadata／generation／current 必须零新增。ActionIntent 写入结果如果无法证明，停止处理；重试时先读回，不能猜成未创建。

## 7. 四类调用行为

| 场景 | 必须发生 | 明确禁止 |
| -- | -- | -- |
| 正常新动作 | 先耐久创建 ActionIntent，再发布 sealed plan 中的对象；返回同一 action 引用 | 先写 raw 后登记；宣称已经接纳或 READY |
| 同动作同请求重放 | 返回原 ActionIntent 和原 plan；只补齐原 plan 中缺失的对象；不重新读取 current 来换 base | 生成第二套 plan、换 target spec、把新 current 当新 base |
| 同动作换请求 | 在任何新 raw／metadata／generation／current 写入前稳定报 `OPERATION_ID_REUSED_WITH_DIFFERENT_REQUEST` | 覆盖旧 intent、先写新内容再报错、暴露旧请求摘要 |
| ActionIntent 无法证明 | 零新增对象写入并返回稳定安全拒绝 | 猜成全新动作、重放成功、接纳成功或可清理 |

同请求重放还分两种：

* 只有 ActionIntent：沿用原 base、target spec 和 plan，继续补齐对象，再交给 [CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力)。
* 下游已经有可证明的 durable terminal：返回原逻辑结果；terminal 的字段和重建规则由 [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 冻结。

## 8. 崩溃点

* ActionIntent 持久化前崩溃：没有可证明的动作记录；重试可以重新走全新动作检查。
* ActionIntent 已持久化、对象尚未写：重试读回原计划并继续。
* 只写了部分对象：重试只核对并补齐原计划里的对象；不能增加新 slot。
* 对象全部写完、尚未交给 [CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力)：重试返回同一 action 和同一 plan，再进入验证。
* ActionIntent 或 plan 损坏：停止写入，返回“动作身份无法证明”的安全错误；不猜成冲突、成功或未接纳终态。

ActionIntent 和 plan 在 [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 产生 durable terminal 前不得删除。当前最小切片不建设自动清理；ActionIntent 一旦存在，动作号在项目存续期内不复用。

## 9. 作者级对象复用和项目隔离

* 物理 raw blob 继续允许在同一作者范围按内容去重。
* 项目 A 的 ActionIntent 不能让项目 B 读取同一个作者级 blob。
* 对象已经存在，只能说明物理内容可能可复用，不能证明某项目动作拥有验证权，也不能证明已经被 generation 接纳。
* 同动作同请求重放遇到已存在对象时，仍要核对完整 receipt 和 bytes；具体授权读取由 [CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力) 冻结。
* 普通诊断、安全摘要和冲突错误不返回 raw SHA、metadata SHA、对象路径、source name、正文或可跨项目猜测的内容身份。

## 10. 旧版 operation receipt 兼容

当前 main 已经可能留下“有旧 receipt／generation、没有 ActionIntent”的动作。施工时不能把这些动作号当成空闲：

* 在零 raw 写入的纯计算阶段，可以用预计算 receipts 和 exact mutations 重算当前旧版 commit request SHA。
* 旧 receipt 的作者、项目、动作号和 request SHA 都能与本次请求匹配时，返回原旧结果，不创建第二个逻辑动作。
* 能证明 request SHA 不同，按同动作换请求稳定冲突。
* 发现旧 generation、prepare 或 receipt 线索，但无法证明同请求或异请求时，返回动作身份无法证明；不能创建新 ActionIntent，也不能复用动作号。
* 是否把已接纳旧动作迁移为新终态记录，由 [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 处理；[CCZ-89](https://linear.app/ccz/issue/CCZ-89/子票m1-动作身份请求封存与项目级幂等) 不伪造历史 ActionIntent。

## 11. 明确不包含

* 不处理流式输入和“先占位、后封存”；这是 [CCZ-93](https://linear.app/ccz/issue/CCZ-93/后备支线流式上传动作占位与-receipt-plan-封存) 后备支线。
* 不建设或抽象云对象存储；这是 [CCZ-92](https://linear.app/ccz/issue/CCZ-92/后备支线云对象存储适配能力证明与条件写) 后备支线。
* 不讨论 multipart、ETag 或云端条件写的实现。
* 不给 HMAC 增加密钥生命周期。
* 不判断对象是否被 generation 接纳。
* 不定义 ACCEPTED、READY、DEGRADED、RECOVERY_BLOCKED、父链赢家、逻辑回滚或 orphan 处理。
* 不允许自动删除 ActionIntent、receipt plan 或未接纳对象。

## 12. 交给下游的边界

* [CCZ-94](https://linear.app/ccz/issue/CCZ-94/子票待接纳-raw-的授权验证能力) 只能按已持久 ActionIntent 和 sealed receipt plan 读取、验证待接纳 raw；不能接受调用方临时塞入任意 digest，不能换 plan，也不能提前赋予 current 权限。
* [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 读取固定 base 和 target spec，冻结 generation schema、确定性派生 target、执行 current 条件切换，并定义 durable terminal、父链和恢复；不能静默 rebase。
* [CCZ-90](https://linear.app/ccz/issue/CCZ-90/子票m1-acceptedreadydegraded-诚实读回) 不读取 ActionIntent 来直接宣称 READY；它按 [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留) 的接纳历史和本次实际内容验证输出诚实状态。
* [CCZ-85](https://linear.app/ccz/issue/CCZ-85/合同父票m1-raw-动作终态generation-接纳与-orphan-恢复) 汇总这些子合同后，才能解除 [CCZ-81](https://linear.app/ccz/issue/CCZ-81/待前置m1-raw-接纳恢复与诚实-ready) 的合同阻塞。

## 13. [CCZ-89](https://linear.app/ccz/issue/CCZ-89/子票m1-动作身份请求封存与项目级幂等) 验收条件

本票只有同时满足下面条件，才算合同冻结完成：

* 动作身份明确是作者＋项目＋动作号，动作种类进入请求承诺；
* 第一次 raw／metadata 正式写入前，ActionIntent 已经耐久写成并读回；
* 字段级合同标明必填、是否进入请求承诺、是否私有和下游读取者；
* 规范化算法有版本、固定字节规则和固定 SHA 测试向量；
* raw、metadata、mutations、expected versions 任一变化都会改变请求承诺；
* 只改变 JSON 对象键顺序不会改变请求承诺；
* 同请求重放不会生成第二套 receipt plan，也不会换 base 或 target spec；
* 同动作换请求在任何新对象写入前稳定冲突；
* 四个崩溃点都有明确续跑边界；
* 不同项目不能读取彼此的 ActionIntent 或 plan；
* 旧 receipt／generation 没有被误判成空闲动作号；
* 文档没有冻结 [CCZ-88](https://linear.app/ccz/issue/CCZ-88/子票generation-接纳终态重建与父链保留)／[CCZ-90](https://linear.app/ccz/issue/CCZ-90/子票m1-acceptedreadydegraded-诚实读回) 的状态，也没有把 [CCZ-92](https://linear.app/ccz/issue/CCZ-92/后备支线云对象存储适配能力证明与条件写)／[CCZ-93](https://linear.app/ccz/issue/CCZ-93/后备支线流式上传动作占位与-receipt-plan-封存) 带入当前建设范围。

来源：Codex

## [CCZ-97](https://linear.app/ccz/issue/CCZ-97/合同子票作品建档表默认项目名类型主角必填与档案版本) 作品档案扩展（2026-08-25）

初始请求承诺加入规范化 profile body、profile identity 和 project profile mutation；同一动作内档案发生实际变化必须稳定冲突。`PROJECT_PROFILE_UPDATE` 使用同一动作号空间。项目壳的默认回退名不进入请求承诺，也不参与动作身份。

关联合同：[CCZ-97 作品档案合同](<https://linear.app/ccz/document/ccz-97%E4%BD%9C%E5%93%81%E5%BB%BA%E6%A1%A3%E8%A1%A8%E9%BB%98%E8%AE%A4%E9%A1%B9%E7%9B%AE%E5%90%8D%E7%B1%BB%E5%9E%8B%E4%B8%BB%E8%A7%92%E5%BF%85%E5%A1%AB%E4%B8%8E%E6%A1%A3%E6%A1%88%E7%89%88%E6%9C%AC%E5%90%88%E5%90%8Ccodex-95c53ae186c4>)。

来源：Codex
<!-- CCZ184_SOURCE_END -->

来源：Codex
