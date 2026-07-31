# 模型横向试验通道

这块只解决一件事：同一份冻结输入需要换不同供应商或模型时，不再临时找文件、复制运行器和猜输出位置。

## 固定流水

```text
阶段配置（正文／证据目录／Prompt／金标指针均钉 SHA）
  → 供应商兼容适配（差异必须明账）
  → 零调用准备与双次机械复验
  → 单次正式采样
  → 中性事件机械闸
  → 从原始响应／尝试账／usage 重建完工审计
  → 金标逐条语义复核
  → 横向成绩单与总结
```

这条通道替换的是 M04“API 运输／模型插槽”。M03 请求内容保持冻结，M05 仍接收 `neutral-events-v1`，因此不会改现役默认链。

## 每轮固定位置

```text
experiments/model_benchmarks/<benchmark_id>/
  benchmark.json              # 本轮身份：阶段、供应商、模型、兼容档
  inputs/                     # 冻结输入副本与来源 SHA
  prepared/                   # 唯一请求、兼容差异账、零调用验收票
  transport/                  # 实发请求、原始响应、尝试账、usage、不可变检查点
  candidate/                  # 模型 JSON、中性事件、程序核对账
  scorecard/                  # 机械闸、金标逐条判词、正式候选成绩
  summary.md                  # 给人看的横向结论
  receipt.md                  # 本轮调用、红线与回退说明
```

## 零调用作废轮怎么找

S-07-B-B 已把 5 轮从未发网的旧准备现场改成轻量历史。每轮在主仓只留三件：

- `benchmark.json`：这轮测谁、用什么条件；
- `state.json`：一句作废原因、调用次数、联网次数和替代轮编号；
- `prepared/superseded_by_*.json`：当时为什么换新编号的详细说明。

完整输入、准备件和随包程序在外置对象
`model-benchmark-superseded-zero-call-s07ba-v1`。它的清单 SHA-256 是
`71b75da89c8f45c2296ff316c6638ce5ef3c2ba1299c86516666d958516c65ad`，实际位置只从
[`governance/external_archive_registry.json`](../../governance/external_archive_registry.json)
读取。先用下面的命令核对外置原件，再按对象编号取到新的临时目录：

```bash
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id model-benchmark-superseded-zero-call-s07ba-v1

retrieval_dir=$(mktemp -d /tmp/model-benchmark-history.XXXXXX)
cp -R \
  ../小说架构_外置仓/model_benchmark_superseded_zero_call_s07ba_20260731_v1/payload \
  "$retrieval_dir/payload"
diff -qr \
  ../小说架构_外置仓/model_benchmark_superseded_zero_call_s07ba_20260731_v1/payload \
  "$retrieval_dir/payload"
```

这 5 轮没有模型质量分：共同结论只是“模型调用 0、联网 0、旧准备件失效”。不要拿它们和
真正跑过的成绩比较，也不要在轻量目录里直接执行 `verify`、`run`、`audit` 或 `score`；
需要历史审计时，先从外置对象复制完整现场。作废票里“旧目录原样留档”的句子记录的是
2026-07-23 开票时的动作；S-07-B-B 之后的当前存放事实，以本页和外置对象登记册为准。

## LongCat r03 中断硬停轮怎么找

S-07-D-A 已从固定提交 `62d942e6cf05c7722826c1648436a2eb15708563` 把 r03 的完整
现场复制到外置对象 `model-benchmark-longcat-r03-interrupted-s07da-v1`。包内有 28 个
普通文件、555,559 字节，清单 SHA-256 是
`6921fd3c28b3719846592cd076198685221ea48f279494d2b9026c86e945e68e`：

```bash
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id model-benchmark-longcat-r03-interrupted-s07da-v1
```

这轮不是“零调用作废轮”。正式采样在写入首次尝试占用票后异常终止；本地模型回答是 0，
但网络结果未知，也没有 usage 或质量分。S-07-D-A 只建立副本；S-07-D-B 在验包、完整
取回和消费者复核通过后，从主仓移除 24 个重件、552,370 字节。当前目录只留
`benchmark.json`、`state.json`、两份硬停证据和 `summary.md`，不能在原地执行。

## QEC 30题四模型历史终局对照

这张表只比较 2026-07-29 同一套 QEC 30 题。机器真源是
[`comparison_r2_qec_four_model_20260729.json`](comparison_r2_qec_four_model_20260729.json)。

| 当时的平台路线／模型展示名 | 完整回答 | 关键错误 | 已观测 Token | 本轮新调用 | 表内估算费用 |
|---|---:|---:|---:|---:|---:|
| 火山 Agent Plan／MiniMax M3 | 13/30 | 27 | 87,792 | 0，复用旧 30 次 | 0.921816 元 |
| SenseNova／DeepSeek V4 Flash | 9/30 | 24 | 108,828 | 30 | 0.326484 元 |
| 火山 Agent Plan／DeepSeek V4 Pro | 6/30 | 23 | 122,318 | 30 | 1.100862 元 |
| 千问平台／Qwen 3.7 Flash | 3/30 | 19 | 174,309 | 30 | 0.522927 元 |

共同门槛是完整回答至少 15/30，且关键错误不多于 10；四条路线全部未过，所以没有升默认，
也没有改默认链。表格只按“完整回答数”从高到低展示，不是综合排名，也不是推荐顺序；
Qwen 的关键错误更少，也不能据此单独过双门。这里记录的是“当时的平台路线＋模型展示名＋
终局收口记录”，不是模型家族总榜。原成绩卡没有供应商接受的精确 API `model_id`，7 件包
也没有自包含 Prompt、配置、金标和判分器绑定，本页不会猜完整运行条件。

成本分三层看：

- 最终有效比较中新跑三条路线，表内估算合计 1.950273 元；
- 加上复用的 MiniMax M3 历史比较账，合计 2.872089 元；
- 整段比选长线登记 169 次请求，其中 162 次有用量、7 次用量未知；成本补充账登记的最低值
  是 **2.813388 元**。本包不能独立复算 r01～r11；接受这份账面记录时，真实总额不低于
  2.813388 元，上限未知。再计入复用的 M3 历史账，账面最低值是 3.735204 元。

90 和 169 不是两套互相打架的调用账：90 是进入最终有效三模型比较的逻辑结果；整段长线
还含前面作废的 78 次请求，以及 r12／r13 的 91 次网络请求，其中 1 次是获准恢复请求。

这些费用由历史价格表乘已观测 Token 算出，不是平台账单对账。成本补充账本身没有被收口
票钉 SHA，r01～r11 的直接成本来源票也不在本次外置包，所以不能把下限写成精确总费用。

7 份原件在外置对象 `r2-qec-four-model-score-sources-s07ca-v1`，清单 SHA-256 是
`fbd4ce59b96f14b635235d194ff1f921b98d6f57d41f6493d16676261c0a5834`：

```bash
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id r2-qec-four-model-score-sources-s07ca-v1
```

这 7 份原件用来核对终局收口文件怎样声明执行、授权恢复、判分、成绩和成本，不是四模型
原始输出包，也不能独立重判。MiniMax M3 的原成绩卡和原输出、四条路线共享题集、金标与
判分器的完整绑定件都不在包内；需要重新评分时，不能只拿这份轻量包开工。

23 项单章抽取、28 项开发集、41 项退役渠道审计都不能并入这张表。TokenRhythm 已退役，
本页不把它列成可选渠道，也不继承它的历史成绩。

## 换模型时只填四项

```bash
python3 tools/novel_pipeline.py model-benchmark prepare \
  --stage neutral_extract_x01_ch0003_v3_t02 \
  --provider qianwen_platform \
  --model qwen3.7-plus \
  --profile thinking_32k_prompt_json \
  --benchmark-id MB_X01_C0003_qianwen_qwen3.7-plus_thinking_t02_20260723
```

准备件通过后才可发网：

```bash
tools/provider_keychain.sh run qianwen_platform \
  python3 tools/novel_pipeline.py model-benchmark run \
  --benchmark-id MB_X01_C0003_qianwen_qwen3.7-plus_thinking_t02_20260723
```

模型名必须已经登记在供应商配置中、标记可调用，并且与所选兼容档做过精确配对验证；三项缺一项都会在建立试验目录前拒绝。工具不会猜相近型号，也不会自动换供应商。每轮目录只写一次，失败或硬停后另开新编号，禁止原位覆盖。

## 一次完整换模怎么走

```bash
# 1. 先看目前能用的阶段、供应商、精确模型名和兼容档
PYTHONPATH=.:tools python3 tools/novel_pipeline.py model-benchmark list

# 2. 只造冻结请求，不发网；prepare 会连续机械复验两次
PYTHONPATH=.:tools python3 tools/novel_pipeline.py model-benchmark prepare \
  --stage neutral_extract_x01_ch0003_v3_t02 \
  --provider qianwen_platform \
  --model qwen3.7-plus \
  --profile thinking_32k_prompt_json \
  --benchmark-id <新编号>

# 3. 发网前随时重验；任何输入、现役保护件或关键运行代码漂移都会拒绝发送
PYTHONPATH=.:tools python3 tools/novel_pipeline.py model-benchmark verify \
  --benchmark-id <新编号>

# 4. 明确授权某个模型后，只发这一臂的一次样张
tools/provider_keychain.sh run <供应商> \
  env PYTHONPATH=.:tools python3 tools/novel_pipeline.py model-benchmark run \
  --benchmark-id <新编号>

# 5. 成功样张会自动做完工重建；也可以以后从原始响应和运输账重新核一遍
PYTHONPATH=.:tools python3 tools/novel_pipeline.py model-benchmark audit \
  --benchmark-id <新编号>

# 6. 语义判词完成后登记成绩，再刷新总索引
PYTHONPATH=.:tools python3 tools/novel_pipeline.py model-benchmark score \
  --benchmark-id <新编号> \
  --adjudication experiments/model_benchmarks/<新编号>/scorecard/adjudication_completed.json
PYTHONPATH=.:tools python3 tools/novel_pipeline.py model-benchmark index
```

你可以直接理解成：`stage` 决定“从哪拿什么料、考哪一段”，`provider＋model＋profile` 决定“把同一份料交给谁、用什么兼容参数”，`benchmark-id` 决定“这次所有结果放哪”。换模型时不再碰现役默认链，也不复制一份专用脚本。

## 每次发网前固定检查

- 精确模型 ID 已登记，供应商默认仍关闭；禁止自动换成相近模型。
- 只允许 `list` 里直接列出的“模型＋兼容档”组合；这里表示允许进入首轮兼容试验，不冒充已经实跑验证。已登记但没有允许档的模型只能看，不能发网。
- 阶段合同、正文、证据目录、Prompt、金标指针和来源 SHA 均未漂移。
- 模型可见消息与基线逐字相同；金标编号、答案和判分词入窗为 0。
- 供应商不得不改的字段逐项进入兼容差异账，成绩标签把温度、思考档等条件写清楚。
- 钥匙只从系统钥匙串临时进入环境变量，不写请求件、运行目录或 Git。
- 现役保护件、供应商配置、适配合同、阶段合同和关键运行代码在发网前再核一次。
- 一臂一命令、一轮一个新目录；成功、失败或硬停都不允许原位重跑挑结果。

## 默认温度与思考档

新建模型横评默认用 `neutral_extract_x01_ch0003_v3_t02`：温度是 0.2，一次采样，不重跑挑好结果。温度 0 只在 0.2 出现明显飘移、且当前任务明确授权时另开诊断轮，不能回改历史成绩。

Qwen3.7-Plus 现用 `thinking_32k_prompt_json` 兼容档：显式打开思考，思考额度护栏是 32,768 token。千问的思考模式与 `response_format=json_object` 不兼容，所以请求不带这个字段；回包还必须真的出现非空思考内容，否则不能登记成思考成绩。模型返回的最终正文仍要通过本地 JSON、格式和证据锚三道检查，失败就硬停，不叫第二个模型来修。

旧的 Qwen3.7-Plus 无思考、温度 0 轮保留为历史条件成绩，不改名、不覆盖、不冒充新默认轮。

## 腾讯 TokenHub 怎么试

腾讯这里接的是标准 TokenHub 在线推理通道 `https://tokenhub.tencentmaas.com/v1`，不是 Token Plan 个人套餐通道。两者的地址、钥匙和账单都分开，不能混用。

发网前除了常规零调用验收，还要先查 `/models`：精确模型 ID 必须在当前钥匙下存在且状态是 `online`，不允许自动换相近型号；目录原始响应和验收票都会钉进不可变检查点。腾讯思考档不同时发送 `response_format`，最终 JSON 由本地闸验收。目前允许进入首轮小说抽取兼容试验的组合会在 `model-benchmark list` 里直接列出。`hy-role`、`minimax-m3`、`minimax-m2.7` 虽然已登记，但官方能力表没标结构化输出，因此暂时没有可运行的事实抽取兼容档。

钥匙仍只走 macOS 钥匙串：

```bash
tools/provider_keychain.sh save tencent_tokenhub
tools/provider_keychain.sh check tencent_tokenhub
```

这两条只保存或检查钥匙，不调模型，也不改现役默认链。

## LongCat-2.0 怎么试

LongCat 只接官方 OpenAI 兼容端点，精确模型名是 `LongCat-2.0`。发网前会先访问 `/models`，只确认当前钥匙下存在这个精确 ID；官方目录不提供 `online` 状态，所以不能套用腾讯的状态闸。

兼容档 `thinking_prompt_json` 显式打开 `thinking.type=enabled`，沿用温度 0.2 与输出上限 32K。官方参数表没有 `reasoning_effort`、`response_format`、`json_schema` 和 `n`，因此都不发送；文档里的 JSON 只表示 HTTP 请求体与响应信封，不等于模型正文有硬 JSON 保证。冻结 Prompt 已明确要求只输出一个 JSON 对象，回来后必须直接通过本地严格解析、Schema 和证据锚检查。一次采样由请求只发一次和响应必须只有一个 `choice` 两道程序闸保证。

官方模型详情虽列出工具调用能力，但这不等于结构化输出合同。本横评不借工具调用包一层 JSON；若以后要测 `response_format` 或工具调用兼容性，应另开参数探针，不能混进质量样张。

密钥不复制进本仓，继续从同级公共 API 池加载：

```bash
source /Users/a1234/挣钱/danmaku-psychology-workspace/06_operations/api-pool/scripts/longcat-env.zsh
env PYTHONPATH=.:tools python3 tools/novel_pipeline.py model-benchmark run \
  --benchmark-id <LongCat新编号>
```

这条命令只给当前子进程临时带入 `LONGCAT_API_KEY`；请求件、回包和 Git 都不得出现密钥。

## 模型版本怎么认

模型配置钉的是供应商接受的精确 `model_id`，响应里实际返回的模型名、日期、请求和原始回包也会随轮保存。如果供应商只给 `qwen3.7-plus` 这类别名，它背后的权重可能由供应商更新，本地无法把隐藏版本号猜出来；这种成绩只能写成“该日期的该别名条件成绩”。供应商若提供带日期或版本号的固定模型 ID，严格版本横比应优先用固定 ID，并另开新试验编号。

## 哪些东西可以变

- 必须显式变化：供应商、精确模型 ID。
- 允许的兼容变化：只来自 `config/model_benchmarks/provider_adapters.json`，逐项进入兼容差异账。
- 不允许变化：模型可见消息、章节正文、证据目录、Prompt、判分金标、单次采样纪律。

不同兼容档的成绩必须带条件标签，不能假装成纯模型单变量。例如 Qwen3.7-Plus 的新思考档会移除不兼容的 `response_format`、不被千问识别的 `reasoning_effort`以及本轮不设的 `max_tokens`，同时新增显式思考开关与 32K 思考护栏；这些都会逐项进入兼容差异账。这个档目前只验证了 `qwen3.7-plus`，不能直接套给同平台的 Max、DeepSeek、GLM 或 Kimi。新模型先补一次自己的兼容档和零调用验收，之后才进入可运行组合。温度等阶段固定值必须写进成绩条件。

来源：Codex
