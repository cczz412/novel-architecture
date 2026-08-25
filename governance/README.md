# 治理区

这里放当前状态、索引、模块状态、路线状态、合同和依赖关系，不复制大型运行工件。

- `INDEX.md`：人看的唯一一跳入口，由生成器维护。
- `CURRENT_STATE.json`：本地唯一机器可读当前执行状态真源；Notion 拍板回读后，只在这里解释“现在到哪”。`current_execution` 只放现在这道，`historical_context` 留审计历史，生成路牌不再把历史重印成当前任务。
- `route_registry.json`：实验路线状态登记册；没有明确重开凭证，换名字或版本号也不能复活退役路线。
- `control_plane.json`：稳定入口、正式指针和保护件；不再保存当前任务。
- `module_registry.source.json`：模块状态的人工审定源；生成器补齐现存路径和 SHA。
- `module_registry.json`、`dependency_map.json`：生成结果。
- `directory_registry.json`：顶层目录的身份、读取规则、生命周期和 Git 边界；只管容器，不管当前任务。
- `indexes/`：金标、银标、运行报告、材料和旧路牌的固定入口。
- `indexes/directory_map.md`、`indexes/new_file_routing.md`：由目录身份账生成的人看地图，禁止手改。
- `rule_check_registry.json`：18 类纯规则检查的程序入口账。
- `test_policy.json`：按模块、合同和风险选择测试范围的正式纪律。
- `tool_registry.json`：工具身份账；根层 Python 实体逐件登记，公共组件层、兼容软链和不逐件登记的分区另列说明。

唯一全仓测试命令：

```bash
cd "$(git rev-parse --show-toplevel)" && uv run --locked pytest -q
```

默认只收集 `tests/`，不会进入 `TEMP/`、`runs/`、`reports/`、`outbox/`。S-05-B
登记的 40 个历史节点会明确显示为 `deselected`，不计入日常验收，也不再用到期
`xfail` 拖住整仓测试。精确节点、24 个取件单元和外置包封签只认
`config/test_replay/historical_replays.json`；真回放必须由
`tools/historical_test_replay.py` 复制固定 Git 提交和已验 SHA 的材料包。

刷新命令：

```bash
uv run --locked python tools/novel_pipeline.py governance refresh
```

只检查生成结果有没有漂移：

```bash
uv run --locked python tools/governance_index.py --check
```

仓库重构只认两级机器票。一级票只校准 HEAD、治理索引、账序和脏路径，不能放行
Wave；CZ 选定路线并补齐配套口径后，二级票还要绑定精确写集、测试影响单和固定路径
冲突锁，才能把票面写明的一个 Wave 标成“机械条件满足”。

二级票不能只看一级票写着 `PASS`：它必须同时绑定原始一级计划，逐项核对一级票的
完整检查集，并拿当前现场重放一次。一级计划、一级票、CZ 决策票、测试影响单、冲突锁
和二级计划还要使用同一个授权上下文。CZ 决策来自当前任务内人工回读，不冒充密码学
签名；离开原任务上下文后不能单拿 JSON 自行放行。

二级 `PASS` 永远不等于自动授权：票面 `authorizes_wave` 固定为 `false`。它只会写明
哪个 Wave 的机械条件满足；真正动手还要在同一个任务里回读 CZ 的明确选择。这个边界
是故意保留的，因为本机 JSON 无法给自己制造可信数字签名。

Wave 1 修改治理生成器或它的测试时，精确写集必须包含会记录这些文件 SHA 的
`module_registry.json`。本波不准在主仓运行全量 `governance refresh`；只允许把生成
结果写到临时目录做逐字比对，再把实际发生字节变化的白名单文件落回主仓，避免无变化
的旧生成件也被整批重写。

目录身份账的权限低于当前状态、模块、工具、路线和外置对象登记。目录身份默认不向
子目录递归，不能拿“父目录叫实验区”覆盖某个已登记工具或模块的真实身份。新文件
先查 `indexes/new_file_routing.md`；没有合适位置就进 `work/<id>` 等待归位，不新造
`active/`、`staging/`、`frozen/`、`runtime/` 顶层目录。

```bash
uv run --locked python tools/governance_index.py \
  --baseline-plan <一级计划.json> \
  --baseline-output <TEMP下全新一级票.json>

uv run --locked python tools/governance_index.py \
  --wave-lock-request <冲突锁请求.json> \
  --wave-lock-output <TEMP下该Wave固定锁路径>

uv run --locked python tools/governance_index.py \
  --wave-plan <二级计划.json> \
  --wave-output <TEMP下全新二级票.json>

uv run --locked python tools/governance_index.py \
  --wave-completion-request <完成请求.json> \
  --wave-completion-output <TEMP下全新完成票v2.json>
```

机器闸自己采集 Git HEAD、脏路径和治理漂移，并在出票前后复核快照没有变化；调用者
不能传一份自称干净的快照绕过现场。票或锁实际写盘后还要再核一次；期间现场变化就
撤销刚写出的文件并硬停。每份受绑定 JSON 都只打开一次，同一份字节同时用于算 SHA
和解析内容；票写盘后还会重验本轮实际读过的全部证据 SHA，避免 TEMP 忽略文件在中途
被换掉。机器票和锁都只写
`TEMP/restructure_wave_preflight/`，拒绝覆盖旧票，也拒绝经过软链父目录写到仓外。
所有受绑定的输入也逐级拒绝父目录软链。输入文件若是硬链接，也会在读取内容前拒绝，
不能给私有文件换个允许路径的别名。S0 的 `materialize-only` 还必须绑定已通过的
Wave 1 实际二级计划、二级票、完整检查集、逐文件输出 SHA，以及可由 Git 回查并与
精确写集完全相等的起止提交；不能手写一对“票据 + 完成票”接续。写盘时逐级用真实
目录描述符打开父路径，父目录在检查后被换成软链也会硬停。S0 不等于断网预检通过，
也不授权移动、删除、Notion、模型 API 或外置清退。

完成票 v2 只干一件事：证明某个已完成 Wave 在两个 Git 提交之间改了哪些仓库文件。
请求只填起止提交和原二级计划／开工票引用，不接受自报输出，也不接收测试报告。工具
直接从 Git 历史对象取变更、普通文件 blob、Git blob SHA 和内容 SHA-256；当前工作树
后来改过同名文件，也不能替代历史提交里的字节。删除、改名、范围外文件、非祖先提交
或原票 SHA 漂移都会得到 `BLOCKED`；全过时状态是 `GIT_SCOPE_PASS`。

⚠️ `GIT_SCOPE_PASS` 不证明、也不评价测试有没有跑。当前 Wave 的测试仍由新基线和
测试影响单负责。各环节交接完成请求时照这个骨架填；`wave_plan` 和 `wave_receipt`
都是“仓库相对路径＋文件 SHA-256”，不要加 `outputs` 或测试字段：

```json
{
  "contract_version": "repository-restructure-wave-completion-request-v2",
  "completion_id": "<本次唯一编号>",
  "wave_id": "S0_MATERIALIZE_ONLY",
  "authorization_context_id": "<同任务授权上下文>",
  "pre_commit_sha": "<施工前40位Git提交>",
  "post_commit_sha": "<施工后40位Git提交>",
  "wave_plan": {"path": "<原计划路径>", "sha256": "<原计划SHA-256>"},
  "wave_receipt": {"path": "<原开工票路径>", "sha256": "<原开工票SHA-256>"}
}
```

`WAVE2_RULE_BUNDLES` 也只干一件事：为一个合成 JSON 试点准备“调用档合同＋提示词
清单＋上下文配方＋离线解析工具”。它沿用现有登记布局，不另造平行目录。唯一试点调用档是
`qianwen_qwen3_7_flash_json_object_no_thinking`，唯一试点工件编号是
`wave2_synthetic_json_probe_v1`。

候选写集固定为下面 22 个文件，任一增删都会被机器闸拒绝：

```text
config/model_call_profiles/contracts/README.md
config/model_call_profiles/contracts/contract_bundle.schema.json
config/model_call_profiles/contracts/qianwen_qwen3_7_flash_json_object_no_thinking/bundle.json
config/model_call_profiles/contracts/qianwen_qwen3_7_flash_json_object_no_thinking/request_envelope.schema.json
config/model_call_profiles/contracts/qianwen_qwen3_7_flash_json_object_no_thinking/response_envelope.schema.json
config/model_call_profiles/contracts/qianwen_qwen3_7_flash_json_object_no_thinking/normalization.json
config/prompts/README.md
config/prompts/prompt_manifest.schema.json
config/prompts/wave2_synthetic_json_probe_v1/prompt.md
config/prompts/wave2_synthetic_json_probe_v1/manifest.json
config/context_recipes/README.md
config/context_recipes/context_recipe.schema.json
config/context_recipes/wave2_synthetic_json_probe_v1.json
config/contracts/wave2_synthetic_json_probe_v1.schema.json
config/model_call_profiles/registry.json
config/model_call_profiles/README.md
config/README.md
tools/model_call_profiles.py
tests/test_model_call_profiles.py
tools/README.md
tests/README.md
governance/tool_registry.json
```

这 22 项全是精确文件路径，没有目录前缀权限。即使文件位于上面列出的合同目录或提示词
目录里，清单外的 `run.py`、`secret.env`、`part.json` 也会被拒绝；Git 不需要登记空目录。

读取范围也按文件逐项登记：只含仓库规则、`TEMP/restructure_wave_preflight`
下的受绑定票据、上面的候选写路径，以及规格列出的现役调用档、千问供应商规则和治理
输入。它不能读取整个 `config/`、`governance/`、`tests/` 或 `tools/`，像
`config/private/secret.json`、`.git/config` 这样的额外输入会在打开任何文件前被拒绝。
工具内部仍可调用 Git 核对历史，但计划不能把 `.git` 声明成业务输入。Wave 1 和 S0 的
旧读取范围不变。Wave2 还必须恰好声明一条 `S0_MATERIALIZE_ONLY` 完成票依赖；类型
错误或多出第二条依赖，也会在读取依赖内容前硬停。
Wave2 固定一级计划内部的 `bound_inputs` 也必须与一级基线的 6 个必绑输入完全相等；
多塞 TEMP 私有文件或少绑任一必需文件，都会在一级重放和文件读取前硬停。

六类票据只认下面这些固定槽位，不能拿别的 TEMP 文件冒充：

```text
一级计划：TEMP/restructure_wave_preflight/route-a-plus-wave2-20260730/BASELINE_PLAN_WAVE2_20260730.json
一级票：TEMP/restructure_wave_preflight/route-a-plus-wave2-20260730/BASELINE_RECEIPT_WAVE2_20260730.json
准备票：TEMP/restructure_wave_preflight/route-a-plus-wave2-20260730/WAVE2_PREPARATION_TICKET_20260730.json
冲突锁：TEMP/restructure_wave_preflight/locks/WAVE2_RULE_BUNDLES.lock.json
测试影响单：TEMP/restructure_wave_preflight/route-a-plus-wave2-20260730/WAVE2_TEST_IMPACT_20260730.json
S0 完成票：TEMP/restructure_wave_preflight/route-a-plus-s0-20260730/S0_MATERIALIZE_COMPLETION_V2_20260730.json
```

交接顺序是：

1. S0 提交后生成可重放的 `GIT_SCOPE_PASS` 完成票 v2。
2. 在新 HEAD 重新生成一级基线票；旧基线票不能沿用。
3. 新建 `repository-restructure-wave2-preparation-ticket-v1` 准备票，记录本任务
   的 `a`（S-02-A），并绑定本次 S0 完成票。旧 S0 决策票不能改写或复用。
4. 准备 Wave2 冲突锁、当前测试影响单和二级计划，再跑机械闸。
5. 即使二级票 PASS，也必须回到同一任务，请 CZ 另给一次明确的正向确认，才能开始写
   Wave2 候选文件。

当前 `a` 只说明可以补 S0 完成证据并扩建 Wave2 机器闸；准备票和二级 PASS 都不授权
写 Wave2 文件。能力字段必须与机器规格完全相等，多一个未知字段也会拒绝；预检、联网、
读密钥、发请求、模型 API、Notion 和外置清退始终不在本闸授权里。
本波不含 `config/experiment_assembly`：它还没进入当前目录身份账，可信签发要留到
Wave9 另开合同，不能顺手塞进 Wave2。

Wave2 规格还钉住本次真实 S0 的计划／开工票路径、文件 SHA 和起止提交；换一套自造票
会硬停。S0 历史输出必须与当前 HEAD 一一对应。只有
`governance/tool_registry.json` 可因扩建机器闸发生内容变化，但仍须是普通文件；
其余 S0 输出只要内容或 Git 模式变化、被替换或删除，Wave2 依赖检查就会阻断。

## Wave 5 外置旧账只读闸

Wave 5 只解决一件事：把三份旧 `MANIFEST.json` 读成结构化库存账。它不搬外置内容，
不跟随清单里的路径，也不把缺少逐项 SHA 的旧账说成“已经可以恢复”。

当前固定输入只有：

```text
同级外置仓/archive_batch_20260723/MANIFEST.json
同级外置仓/archive_batch_slim_20260723/MANIFEST.json
同级外置仓/archive_batch_slim_overlay_z94_20260723/MANIFEST.json
```

路径身份写成“同级外置仓＋批次相对路径”，不把某台机器的 `/Users/...` 地址写进正式
登记。机器闸会按仓库名称找到同级外置仓，只打开这三个固定文件；外置根、批次目录或
清单是软链接，清单是硬链接，文件超过 5 MiB，读取期间被替换，SHA 或 51／91／6
条目数变化，都会直接停。

Wave 5 使用独立的五个票据槽位：

```text
一级计划：TEMP/restructure_wave_preflight/route-a-plus-wave5-20260730/BASELINE_PLAN_WAVE5_20260730.json
一级票：TEMP/restructure_wave_preflight/route-a-plus-wave5-20260730/BASELINE_RECEIPT_WAVE5_20260730.json
授权票：TEMP/restructure_wave_preflight/route-a-plus-wave5-20260730/WAVE5_CONSTRUCTION_AUTHORIZATION_20260730.json
冲突锁：TEMP/restructure_wave_preflight/locks/WAVE5_EXTERNAL_ARCHIVE_READONLY.lock.json
测试影响单：TEMP/restructure_wave_preflight/route-a-plus-wave5-20260730/WAVE5_TEST_IMPACT_20260730.json
```

授权票必须原样记录 CZ 的 `B｜机器闸和实际扫描器连续施工`，绑定原 S0 决策票、三份
清单当前 SHA 和 148 条总数。二级票 PASS 后只允许施工精确写集里的离线扫描器、合同、
说明、新收据和新登记册。以下能力始终关闭：遍历外置真身、改旧清单、搬动或删除来源、
写存根、签发恢复通过、联网、读密钥、调用模型、写 Notion 和清退外置内容。

## S-06-A 仓库瘦身登记与只读体积闸

S-06-A 把 Wave 5 的三份旧清单盘点扩成全仓瘦身范围内的对象登记。机器真源是
`external_archive_registry.json`，人看入口是
`artifact_storage/README.md`。

登记范围分成四块：

- 主仓长期零件继续由各自配置、工具和目录登记管理；本册逐对象登记 13 个实验目录；
- 同级外置仓的 13 个顶层对象；
- 同级隔离实验区的 5 个工作区；
- 只接收复制式测试的同级测试工作区。

这份登记只管身份、位置、消费者和生命周期，不继承移动授权。`per_object_candidate`
表示“可以继续调查”，不是“已经允许外置”。消费者仍为 `open` 的实验程序继续留在主仓；
身份不足的目录连迁移候选都不能冒充。

只读检查：

```bash
uv run --locked python tools/repo_slim_inventory.py check
uv run --locked python tools/repo_slim_inventory.py report
```

体积只认 Git 索引按路径累计的 blob 字节。S-06-A 前精确基线是 18,841,846 字节，
10MB 目标当前仍为未达成。扫描 PASS 只表示登记、固定 SHA 和当前生效上限没有破；
不表示完成迁移、遍历过外置 payload、证明可恢复或解决 8 项旧冲突。

S-06-A 不提供硬上限激活能力。迁移票即使格式和 SHA 都合法，也必须等另行获批的外置
payload 逐文件验证器真正核过路径存在性与内容 SHA；当前只读扫描器不会越权代验。

## S-06-B 外置 payload 单件验证

S-06-B 用独立工具读取外置 payload，不扩张 S-06-A 扫描器的能力。一次命令只接一个
`artifact_id`。白名单、排除项和每个对象该读哪些合计字段，只认机器政策
[external_payload_validation_policy.json](external_payload_validation_policy.json)；
人读页不抄 target 名单，也不手写件数／字节数。

```bash
uv run --locked python tools/external_payload_validator.py check \
  --artifact-id historical-test-replay-s05b-v2
uv run --locked python tools/external_payload_validator.py report \
  --artifact-id historical-test-replay-s05b-v2
```

政策里标明排除的对象（缺逐项 SHA、旧 TEMP 外置根没有清单等）工具不会顺着旧绝对路径
猜位置。目标数量和排除名单以该政策文件当时的 `targets`／`exclusions` 为准。

PASS 只说明一个获准对象的 payload 文件集合、大小和内容 SHA 与固定清单一致。轻量报告
只保留对象编号、登记／政策／清单／验证器／安全读取助手 SHA、文件数、总字节和整组摘要，
不把几千条逐文件清单复制回主仓。它不证明包级元数据、消费者收口、指针可取回、可恢复
或独立备份，也不签迁移票、不移动或删除文件、不启用 10MB 硬门。

## S-06-C 轻量结论卡、仓外指针与按需取件计划

S-06-C 把“平时看结论”和“需要时取原件”分开。结论、位置和取件范围各认一份真源：

- `result_card.json` 只管实验目的、组装方式、短结论、质量裁决和证据边界；
- `external_pointer.json` 只钉外置对象编号和固定清单 SHA，不保存本机绝对路径；
- `external_archive_registry.json` 仍是对象实际位置真源；
- `retrieval_profile.json` 只登记命名取件组合；
- `artifact_retrieval_policy.json` 只决定哪些卡允许解析，不继承 S-06-A 或 S-06-B 的权限。

首批两张卡放在 `config/test_replay/result_cards/`，分别保留 S-05-B v1 的 38 过 2 败
和 v2 的 40 项通过。Markdown 是从同目录三份 JSON 生成的人看页，不能和机器卡分开手改。

```bash
uv run --locked python tools/experiment_artifact_retrieval.py check \
  --card-id s05b-historical-replay-v2
uv run --locked python tools/experiment_artifact_retrieval.py resolve \
  --card-id s05b-historical-replay-v2 \
  --selection-id full-replay-payload
```

`check` 只核卡片、指针、登记关系和固定 `MANIFEST`。`resolve` 只把已登记组合翻成确定性
复制计划并写到标准输出。当前工具没有复制、移动、删除、恢复、任意根、任意路径、glob
或目标目录参数；计划中的所有能力声明也固定写明“尚未复制、尚未迁移、尚未启用硬门”。

R02 仍是非终态活实验。它只作为禁止发现的对象编号写进政策，不进入卡片白名单，不扫描
`TEMP/`，也不读取它下面的任何文件。以后即使 R02 跑完，也必须另行审收后才能建立卡片。

真复制必须另开授权，不能让现有工作区复制器直接吃这份计划。后续复制执行器至少还要
绑定计划编号和全新运行号，逐项复核来源路径与目标路径都不重复，并在复制后核目标 SHA。
卡片继续扩容前，也要给替代关系补上“禁止自指、禁止成环”的全图检查。

旧 Wave 5 写集里的 `tools/external_archive.py` 没有被静默冒名施工。S-06-A 用新规格
明确承接只读库存与体积检查，正式入口是 `tools/repo_slim_inventory.py`；旧 Wave 5
票据仍只解释当时的候选写集，不倒签本轮结果。

## S-06-D-A 统一只读目录

统一入口现在可以把分散的寻路信息即时排成一张人看目录：

```bash
uv run --locked python tools/novel_pipeline.py catalog \
  [menu|status|models|experiments|artifacts|slim|all] [--json]
```

这张目录没有自己的状态账。它每次回读现有真源和登记册；体积栏目则即时调用原来的
`repo_slim_inventory.py`，不复制一份扫描结果长期保存。发生冲突时，当前状态仍只认
`CURRENT_STATE.json`，实验、模型、仓外对象和取件资格仍分别回各自登记册裁定。

几条边界不能混：

- `status` 只照读当前状态真源已经登记的内容，不根据 TEMP、运行目录或旧票猜 CMIN-B
  的当前状态；
- `models` 只列候选模型调用档和已登记规则组装包，不证明供应商在线、账号可用、已经
  获批调用或已经升成默认；
- `experiments` 只接已登记实验对象、路线和显式结论卡，不遍历整棵实验树后自判成败；
- `artifacts` 可以列已登记对象，但只有取件政策明示开放的卡片才有取件资格；它不接受
  任意对象，不输出本机仓外绝对路径，也不进入仓外 payload；
- `slim` 同时照出 10MB 目标和当前“不继续增长”的施工闸；前者尚未达成时，后者仍可能
  正常通过。

`catalog` 全部栏目都只读。它不复制、不移动、不删除、不恢复、不写 Notion，也不调用
模型。R02 仍是受保护的非目标：目录只保留“禁止发现”的边界，不进入或读取它的目录、
清单与 payload。

语义检查只分流：

```bash
uv run --locked python tools/novel_pipeline.py inspect preflight --input <检查批.json> --run-dir <试验目录>
uv run --locked python tools/novel_pipeline.py inspect run --input <检查批.json> --run-dir <试验目录>
```

计算本次该跑哪些测试：

```bash
uv run --locked python tools/novel_pipeline.py test-plan --spec <变更说明.json>
```

Notion 账序与队列仍是最终真源。本区只解决本地寻路和机械复现，不自行拍板状态。

## S-07-B-A／B-B 模型横评零调用作废包瘦身

S-07-B-A 只复制 5 轮状态为“零调用作废”的模型横评完整现场。来源固定在 Git 提交
`e3bcec6634a8fe1794793b13831205f78d766a41`，不是从正在变化的工作树临时抓取。

```bash
uv run --locked python tools/external_payload_validator.py check \
  --artifact-id model-benchmark-superseded-zero-call-s07ba-v1
```

机器应回报 86 个文件、1,664,821 字节。包与主仓在同一磁盘，只证明这份副本当前逐文件
完整，不能叫独立备份。

S-07-B-B 在删除前又把整包取到全新临时目录，文件数、总字节和逐字节比较全部一致。随后
只从这 5 个零调用目录移除 71 个已外置工件，共 1,657,195 字节；每轮保留
`benchmark.json`、`state.json` 和一张作废原因票，共 15 个文件。目录索引仍只读这些
小型身份件，真实得分轮、通用模型配置、运行器和测试没有进入本次删除范围。

轻量目录只负责寻路，不能再原地运行。要看完整冻结输入或准备件，先按外置对象编号
`model-benchmark-superseded-zero-call-s07ba-v1` 验包，再复制到新的临时目录；不要把
完整现场重新塞回日常主仓。主仓删除不改变同盘故障边界，也没有启用 10MB 硬门。

## S-07-C-A QEC 四模型终局记录轻量卡

这一波只收 2026-07-29 同一套 QEC 30 题终局对照。主仓机器卡在
`experiments/model_benchmarks/comparison_r2_qec_four_model_20260729.json`，人看表在
同目录 README；仓外对象 `r2-qec-four-model-score-sources-s07ca-v1` 保留 7 份原件，
包括执行、授权网络恢复、判分、最终成绩、正式报告、收口和成本补充账。

四条平台路线分别得到 13/30、9/30、6/30、3/30，但共同门槛是完整回答至少 15/30 且
关键错误不多于 10，所以全部未过，没有升默认或改默认链。原成绩卡没有精确 API
`model_id`；卡片只写当时的平台路线、模型展示名和终局记录，不外推模型家族能力。机器卡
的顺序只按完整回答数展示，不是综合排名或推荐顺序。

成本账登记整段长线 169 次请求、162 次有用量、7 次用量未知。2.813388 元只是账面登记
最低值，本包不能独立复算；成本账没有被收口票钉 SHA，r01～r11 的直接来源票也不在这
7 件原件里。7 件包同样不含 MiniMax M3 原成绩卡、原输出、共享题集、金标和判分器完整
绑定，所以只能核对终局收口声明，不能独立重判。23、28、41 等其他分母不并表，退役
TokenRhythm 也不恢复成当前渠道。

## S-07-F-A／F-B-A 千问 r05／r06 有分候选瘦身

这一波从固定提交 `1d919759f11b481a69eab1bdb1b7bfac5f4e0851` 分别复制两轮：

- r05 是结构化不思考档，温度 0.0；23 个评分位中严格命中 4、语义影子 7、有效召回 11；
- r06 是 32K 思考档，温度 0.2、思考预算 32,768；严格命中 3、语义影子 9、有效召回 12。

两轮各有独立外置对象和清单：r05 为 40 个文件、702,031 字节，r06 为 41 个文件、
714,081 字节。它们都是真实跑过的银标候选，但不是现役默认。

Z98 核验程序仍读取两轮的请求体和用量账；r06 还有平台成绩指针与 V02 请求指针。因此
S-07-F-A 当时只建副本，两轮消费者保持 `open`。S-07-F-B-A 又核明 60 个重件没有现役
消费者，并在两包复验通过后从主仓移除 r05／r06 各 30 件，共 1,259,208 字节。r05 留
10 件，r06 留 11 件，继续承接 Z98、平台配置、模型索引和 V02 指针；剩余轻量入口不得
删除，也不能原地复跑。完整历史现场仍从两个外置对象按需取回。

各波次不改变模型横评结果，不启用 10MB 硬门。外置包与主仓仍在同一磁盘，不是独立备份；
轻量目录不能原地运行。

## S-07-G-A／G-B-A Z66 三问法诊断回包瘦身

这一波从固定提交 `18281795703497760bf3fc090a771db1e1782574` 复制 Z66 三问法诊断回包。
原目录 tree 是 `20a1a3d7290b86a24756a79eec84ac5885722241`，外置对象共有 93 个文件、
1,240,575 字节。原始回包、全 Markdown 审阅副本和当时的 ZIP 有意原样保留，没有在复制时
去重或改写。

这批只是一组历史候选诊断，不是现役默认。`tools/z68_revised_request_pilot.py` 仍读取主仓
的一份第 3 章修正版请求 JSON，并核固定 SHA，因此消费者继续为 `open`。

S-07-G-A 只建同盘完整副本和轻量入口，没有移动或删除 93 个主仓源文件。S-07-G-B-A
在外置 93 件复验、完整取回和消费者扫描通过后，从主仓移除 88 个重件、1,200,070 字节。
主仓现在留 6 件、42,310 字节：一张轻量入口、四张身份票和 Z68 继续读取的请求 JSON。

旧 `package_diagnostic_returns.py` 不再默认把主仓轻量目录当完整包，历史重建或核验必须
显式传入目标目录。完整外置现物统一用对象编号逐文件验证。Z68 及 13 个后续工具仍会经它
读取保留的请求 JSON，所以消费者继续为 `open`，不得顺手再删。

## analysis_library 首批分析材料外置

这批主要解决一个问题：日常只看简短结论，不让原始 ZIP、解包文件和映射材料继续挤在
主仓里。主仓入口是 `analysis_library/pilot_batch_01/`，保留 7 份分析摘要、3 份验收
摘要、说明和仓外指针；平时从这里判断材料用途与结论。

需要追到原件时，按对象编号
`analysis-library-pilot-batch-01-cz-move-20260731-v1` 找到同级外置仓的
`analysis_library_pilot_batch_01_cz_move_20260731_v1/`，再运行：

```bash
uv run --locked python tools/external_payload_validator.py check \
  --artifact-id analysis-library-pilot-batch-01-cz-move-20260731-v1
```

外置现物共 242 个文件、23,895,907 字节；`MANIFEST.json` 的 SHA-256 是
`2e8ecee5a580a4926597093b41d0d9f70321bc7f67326f5790feacbd415fd5f0`。这份来源是
本地未跟踪目录快照，不是 Git 可重建包；内容还是候选分析，不代表人工审定。它和主仓处在
同一磁盘，也不是独立备份。

## 常检尺子（支线瘦身批件③写入）

- **主刀＝磁盘观感**；常检读三行＝除 TEMP 磁盘体量／Git tracked 体量／外置旁仓另算。
- 细则见 [hygiene_inspection_ruler.md](hygiene_inspection_ruler.md)（文档级；不改 check／`.py`）。
- ❌ 不再拿整仓 `du -sh .` 单数字判胖瘦。

## 收口纪律（第84道写入）

- **每收口一道，重跑 INDEX**：`uv run --locked python tools/novel_pipeline.py governance refresh`，再用 `uv run --locked python tools/governance_index.py --check` 验漂移。
- 本纪律写在本 README（不会被 refresh 覆盖）；不要手改 `INDEX.md`。

## 当前状态分层与新工件身份（九项第二道写入）

- 当前执行页只读 `CURRENT_STATE.json.current_execution`：任务、授权、运行、停点、下一动作、调用账和保护面。
- 历史任务、封存运行、旧问题与收口规则只放 `historical_context`。`INDEX.md` 只做稳定寻路；整体任务进度现场读取 Linear／GitHub，不再生成 `current_run.md`。
- 新生成工件的身份统一写仓库相对 POSIX 路径。主机本地绝对路径若确需留作排障，只能单放 `*_host_local` 字段，不能当身份、不能参与跨机器 SHA 清单。
- 本规则从九项第二道起生效；Notion 登记的旧账 `198处／36文件` 只作授权基线，不回改，也不把本轮不同范围的扫描数冒充成该母数。

## 环境锁与历史回放

- 默认复现环境由根目录 `.python-version`、`pyproject.toml`、`uv.lock` 三件共同锁定为 Python 3.12.12。基础环境只含现役测试与代码检查；停用的 MiniCPM／微调依赖不进入默认锁。
- 日常仍保留现役 Homebrew Python 全链命令作等价对照；新环境可用 `uv sync --locked` 后复验。
- 40 项历史测试恢复只走便携夹具小包：保留仓库相对路径，带逐文件 SHA，在干净 checkout 中证明 40 项全部真跑通过。不得为省事把大型旧运行目录塞回主仓。
- review／replay 双包与外发工程证据清单见 [`config/review_pack/README.md`](../config/review_pack/README.md)。外发调查包必须带 commit、环境锁、manifest、原始响应索引和 SHA 清单。

## 状态收口纪律（第86道写入）

- 第86道之后的新运行，只要主运行落了 `main/hard_stop.json`、检查员等子运行在本层落了 `hard_stop.json`，或形成获批收口票，就必须同步顶层 `run_manifest.json`、`governance/CURRENT_STATE.json`，再刷新并检查治理索引。
- Z80、Z83 既有运行目录已经封存，不回写。旧顶层 `prepared` 与后续票据冲突时，由 `CURRENT_STATE.json` 对外裁定。
- 硬停只认对应运行本层的 `hard_stop.json` 级票据，顶层必须引用。Z80 v1.3 是历史例外：旧目录没有这张票且禁止回写，所以只用目录外成绩裁定票记“失败后退役”，不伪造硬停票。

## 密钥入口与双闸（第86道写入）

- 现役加载入口只有 `tools/sensenova_deepseek_key.sh`。共享环境加载脚本和外部项目加载器都标记退役；历史记录不删。
- 进程读取闸只证明子进程能读到非空密钥，回执不得显示密钥。
- 供应商认证闸只由首个获批主采样请求的正常响应证明。不得把“密钥存在”写成“认证通过”，也不得另发试探请求。

## 检查停手线（第86道写入）

- 两份相互独立的证据给出同一结论就停，不再做第三份同义核验。
- 先看输出实际结构，再写解析命令；解析失败时先修字段路径，不重复跑原任务。
- 同一停点同时运行的子任务最多 3 个；已有子任务仍在运行时，不补派同义任务。

## 工具身份与出生门槛（第87道写入）

- `tools/` 根层每个实体 Python 文件只认一种主要身份：现役总入口、可复用组件、批次复现器、退役兼容件。证据不足时标“待定”端 CZ，不从文件名、测试存在或零引用自行推断去留。
- 长期通用工具只有满足下面四条才准新增：
  1. 已有两个互相独立的使用场景，或已有一位明确的下一消费者。
  2. 输入短且稳定；核心逻辑不写死道次编号、批次目录或用户绝对路径。
  3. 输出格式、覆盖规则、失败方式说得清；相同输入可以复跑并解释一致性。
  4. 有 `--check` 或只读预演、有定向测试，并在创建时同步登记 `tool_registry.json`。
- 新的批次专用脚本不再进入 `tools/` 根层：能走现有总入口的，使用总入口加规格单；不能走的，放在 `reports/<批次>/` 或 `experiments/<试验>/`，沿用试验目录合同。
- 违反门槛却新增到 `tools/` 根层时，要把事实追加到 `tool_registry.json` 的违规账，不能靠事后补文档抹掉。
- 第87道三件裁定工具此后若出现第二个互相独立使用场景（非同道次），并补齐定向测试，可直接机械转正“可复用组件”并报告登记册新 SHA；默认登记器的实际默认推广仍须另拍。
- 第87道只登记，不治理：不删、不移、不改现有 Python；公共能力抽提、批次复现器归位、历史兼容归档和统一入口扩建都要另拍。

来源：Cursor（仓库治理窗）
