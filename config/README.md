# 配置区

这里放两类不含密钥的配置：

- `providers/`：API 地址、模型白名单、密钥环境变量名。
- `model_call_profiles/`：每个模型固定怎样调用，包括温度、思考档、JSON
  方式、流式方式与输出上限策略。
- `prompts/`：可复用提示词正文及它的 SHA 清单。
- `context_recipes/`：只记录上下文怎么拼，不保存某次已经拼好的完整上下文。
- `background_board_upload/`：登记当前三块共同背景怎样编译成单层手工上传 ZIP。
- `contracts/`：任务输入输出等可复用 JSON 结构约束。
- `batches/`：某一批测哪本书、多少章、用哪版提示词、最多允许多少次调用。
- `test_replay/`：退出日常验收的历史测试节点、取件范围和外置回放包封签。

⚠️ 不要把 API Key 写进 JSON。现役默认链只认进程环境里的 `SENSENOVA_API_KEY`；普通火山按量、千问与腾讯候选通道分别使用 `ARK_API_KEY`、`DASHSCOPE_API_KEY` 与 `TENCENT_TOKENHUB_API_KEY`，只从本仓钥匙串加载器临时注入。Agent Plan 只认 ArkCLI 的 `agent-plan_cn-beijing_personal` profile，不再从项目钥匙串重复注入另一把 Key。

当前正式接口只用 `config/providers/sensenova_modular_v1.json`：模型钉死为
`deepseek-v4-flash`，不允许运行时切到其他模型。

本机钥匙放在 macOS 钥匙串，仓库只保存不含密钥的加载工具：

```bash
# 弹出隐藏输入框，保存或更新钥匙
tools/sensenova_deepseek_key.sh save

# 只确认钥匙存在，不显示内容
tools/sensenova_deepseek_key.sh check

# 临时加载钥匙并执行命令；命令结束后，不污染后续终端
tools/sensenova_deepseek_key.sh run python3 tools/你的运行器.py
```

`run` 后面只接本仓可信运行器；被运行的命令及其子进程会在本次执行期间看到密钥环境变量。

现役默认链的密钥入口只有 `tools/sensenova_deepseek_key.sh`。共享环境加载脚本和外部项目加载器不得给现役默认链开跑。

CZ 自 2026-08-01 起已对 DeepSeek 官方 API 给出**长期授权**。今后当前任务明确要求运行 DeepSeek 官方模型时，不再逐次询问 CZ；但每条命令仍要带机器执行票，防止脚本误调。官方通道不得自动调用、不得扩大题目或次数、不得作为失败回退路线，也不得改掉默认链。机器规则在 `providers/provider_access_policy.json`。

```bash
# 保存或检查官方 API 钥匙，不显示钥匙内容
tools/deepseek_official_key.sh save
tools/deepseek_official_key.sh check
```

`run` 没有本条命令的机器执行票时，会在读取钥匙前以退出码 77 拒绝；执行端可直接设票，不需再询问 CZ。火山方舟／千问平台里的 DeepSeek 模型属于各自平台通道，不等于 DeepSeek 官方 API。

现有隔离候选通道如下：

- `providers/volcengine_ark_multi_model.json`：火山方舟普通按量接口，环境变量 `ARK_API_KEY`。
- `providers/volcengine_agent_plan.json`：火山方舟 Agent Plan 独立通道，凭证只由 ArkCLI 的 `agent-plan_cn-beijing_personal` profile 管理；每次必须明确指定精确模型，禁用 `auto`，调用前清掉 `ARK_API_KEY` 等环境覆盖。
- `providers/qianwen_platform_multi_model.json`：千问 AI 平台标准按量接口，环境变量 `DASHSCOPE_API_KEY`。
- `providers/tencent_tokenhub_multi_model.json`：腾讯云 TokenHub 标准在线推理接口，环境变量 `TENCENT_TOKENHUB_API_KEY`。

普通火山按量、千问、腾讯三把钥匙共用一个本地弹框入口，但各自存在不同的 macOS 钥匙串项目里：

```bash
# 火山方舟
tools/provider_keychain.sh save volcengine_ark
tools/provider_keychain.sh check volcengine_ark

# 千问 AI 平台标准按量接口
tools/provider_keychain.sh save qianwen_platform
tools/provider_keychain.sh check qianwen_platform

# 腾讯云 TokenHub 标准在线推理接口
tools/provider_keychain.sh save tencent_tokenhub
tools/provider_keychain.sh check tencent_tokenhub
```

Agent Plan 不走上面的项目钥匙串，它由 ArkCLI profile 自己同步和选择套餐 Key：

```bash
arkcli profile keys refresh --profile agent-plan_cn-beijing_personal
arkcli profile keys list --profile agent-plan_cn-beijing_personal --format json
```

千问的 Token Plan Key 通常以 `sk-sp-` 开头，端点与标准按量接口不同；当前弹框会拒绝把这类钥匙误存进标准配置。腾讯这里配置的是 `https://tokenhub.tencentmaas.com/v1` 标准在线推理接口，不是 `api.lkeap.cloud.tencent.com/plan/v3` Token Plan。四套隔离配置都没有默认模型，也没有接入现役链，只有明确指定平台和模型的任务才能调用。

模型横评的日常默认温度是 `0.2`。只有 0.2 条件下出现明显漂移、且当轮明确允许另开诊断轮时，才用 `0.0`；旧的 0.0 成绩只作历史条件账，不回写改名。Qwen3.7-Plus 的现役横评兼容档显式开启思考，思考预算为 32K；因为供应商不允许思考模式与 `response_format=json_object` 同用，最终正文改由本地 JSON、Schema 和证据锚机械闸验收。

新模型横评统一从 `model_call_profiles/` 选择固定调用档。Qwen3.7 Flash
走千问 AI 平台；DeepSeek V4 Flash、DeepSeek V4 Pro 与 MiniMax M3
已经备好 Agent Plan 候选档。它们都没有替换 SenseNova 现役默认链，仍须由当前任务明确下达开跑口令。

一套新测试不要从运行目录反向拼配置。先用
`tools/model_call_profiles.py resolve-bundle <规则包编号>` 取得带 SHA 的零件清单，
再把清单和当次程序、输入一起写进 S0 物化计划。复制完成后，后续环节只读工作区
副本；主仓继续作为零件真源，但不会被测试过程回写。

Agent Plan 目录里的请求模型名和响应模型名可能不同。例如
DeepSeek V4 Flash 请求写 `deepseek-v4-flash-modelhub`，返回应核对
`deepseek-v4-flash-260425`。不得拿返回名替代实时目录中的请求 ID。

发网前的两道闸不能混：加载器让子进程读到非空密钥，只代表“进程读取闸”通过；供应商对首个获批主采样请求返回正常响应，才代表“供应商认证闸”通过。不得另发试探请求。

旧供应商配置是历史实验留档，不作为现役入口，也不回写。

来源：Cursor（仓库治理窗）
