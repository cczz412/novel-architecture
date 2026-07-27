# 配置区

这里放两类不含密钥的配置：

- `providers/`：API 地址、模型白名单、密钥环境变量名。
- `batches/`：某一批测哪本书、多少章、用哪版提示词、最多允许多少次调用。

⚠️ 不要把 API Key 写进 JSON。现役默认链只认进程环境里的 `SENSENOVA_API_KEY`；隔离候选通道分别使用 `ARK_API_KEY`、`DASHSCOPE_API_KEY`、`TENCENT_TOKENHUB_API_KEY` 与 `LONGCAT_API_KEY`。前三把只从本仓钥匙串加载器临时注入；LongCat 继续由同级公共 API 池临时加载，不复制密钥进本仓。

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

现役默认链的密钥入口只有 `tools/sensenova_deepseek_key.sh`。共享环境加载脚本和外部项目加载器不得给现役默认链开跑；LongCat 独立横评是隔离例外，只读取同级公共 API 池的专用加载器，不接现役链。

DeepSeek 官方 API 已按 CZ 口径改成**默认永久禁用**。只有 CZ 在当前任务里明确、正向要求“用官方的API”时，才允许给那一次命令临时解锁；否定句、转述、模型名或只出现“官方API”字样都不授权。机器规则在 `providers/provider_access_policy.json`，加载器也会执行同一道拒绝闸。

```bash
# 只保存或检查历史钥匙，不代表允许调用
tools/deepseek_official_key.sh save
tools/deepseek_official_key.sh check
```

没有当轮明确授权时，`run` 会在读取钥匙前直接以退出码 77 拒绝。火山方舟／千问平台里的 DeepSeek 模型属于各自平台通道，不等于 DeepSeek 官方 API。

现有四个隔离候选通道如下：

- `providers/volcengine_ark_multi_model.json`：火山方舟普通按量接口，环境变量 `ARK_API_KEY`。
- `providers/volcengine_agent_plan.json`：火山方舟 Agent Plan 独立通道，环境变量 `VOLCENGINE_AGENT_PLAN_API_KEY`；每次必须明确指定精确模型，禁用 `auto`。
- `providers/qianwen_platform_multi_model.json`：千问 AI 平台标准按量接口，环境变量 `DASHSCOPE_API_KEY`。
- `providers/tencent_tokenhub_multi_model.json`：腾讯云 TokenHub 标准在线推理接口，环境变量 `TENCENT_TOKENHUB_API_KEY`。
- `providers/longcat_platform.json`：LongCat API 开放平台，环境变量 `LONGCAT_API_KEY`，密钥继续放在同级公共 API 池。

火山、千问、腾讯三把钥匙共用一个本地弹框入口，但各自存在不同的 macOS 钥匙串项目里：

```bash
# 火山方舟
tools/provider_keychain.sh save volcengine_ark
tools/provider_keychain.sh check volcengine_ark

# 火山方舟 Agent Plan（独立于普通按量接口）
tools/provider_keychain.sh save volcengine_agent_plan
tools/provider_keychain.sh check volcengine_agent_plan

# 千问 AI 平台标准按量接口
tools/provider_keychain.sh save qianwen_platform
tools/provider_keychain.sh check qianwen_platform

# 腾讯云 TokenHub 标准在线推理接口
tools/provider_keychain.sh save tencent_tokenhub
tools/provider_keychain.sh check tencent_tokenhub
```

LongCat 不重复存进本仓钥匙串，加载入口固定为 `/Users/a1234/挣钱/danmaku-psychology-workspace/06_operations/api-pool/scripts/longcat-env.zsh`。

千问的 Token Plan Key 通常以 `sk-sp-` 开头，端点与标准按量接口不同；当前弹框会拒绝把这类钥匙误存进标准配置。腾讯这里配置的是 `https://tokenhub.tencentmaas.com/v1` 标准在线推理接口，不是 `api.lkeap.cloud.tencent.com/plan/v3` Token Plan。四套隔离配置都没有默认模型，也没有接入现役链，只有明确指定平台和模型的任务才能调用。

模型横评的日常默认温度是 `0.2`。只有 0.2 条件下出现明显漂移、且当轮明确允许另开诊断轮时，才用 `0.0`；旧的 0.0 成绩只作历史条件账，不回写改名。Qwen3.7-Plus 的现役横评兼容档显式开启思考，思考预算为 32K；因为供应商不允许思考模式与 `response_format=json_object` 同用，最终正文改由本地 JSON、Schema 和证据锚机械闸验收。

DeepSeek V4 Flash 的日常路线继续走 SenseNova 免费次数通道。Agent Plan 中虽然也列有 `deepseek-v4-flash-260425`，但默认拒绝调用；只有 CZ 在当前任务里明确点名“用 Agent Plan 的 Flash”才可临时放行，避免无意消耗 AFP。Agent Plan 日常留给 V4 Pro、豆包及其他明确点名的对照模型。

发网前的两道闸不能混：加载器让子进程读到非空密钥，只代表“进程读取闸”通过；供应商对首个获批主采样请求返回正常响应，才代表“供应商认证闸”通过。不得另发试探请求。

旧供应商配置是历史实验留档，不作为现役入口，也不回写。

来源：Cursor（仓库治理窗）
