# 模型调用配置库

这个目录专门解决一个问题：以后换模型时，不再临时手写一份请求 JSON。

你可以直接理解成两层：

- `config/providers/` 管“从哪个平台、哪个地址、拿哪把钥匙、精确模型名是什么”。
- 这里管“这个模型具体怎样调用”：温度、思考档、JSON 方式、是否流式、要不要发送输出 token 上限。

当前候选模型已经分成五个固定档：

| 模型 | 推荐档 | 作用 |
|---|---|---|
| Qwen3.7 Flash | `qianwen_qwen3_7_flash_thinking_prompt_json` | 质量优先；思考开启，Prompt 要求 JSON，本地再验 Schema |
| Qwen3.7 Flash | `qianwen_qwen3_7_flash_json_object_no_thinking` | 格式优先对照；关闭思考，平台保证合法 JSON |
| DeepSeek V4 Flash | `agent_plan_deepseek_v4_flash_high_json_object` | Agent Plan 主力候选；High、温度 0.2、无客户端输出上限 |
| DeepSeek V4 Pro | `agent_plan_deepseek_v4_pro_high_json_object` | Agent Plan 强模型候选；High、温度 0.2、无客户端输出上限 |
| MiniMax M3 | `agent_plan_minimax_m3_thinking_json_object` | Agent Plan 异源对照；开启思考；JSON Object 只作渠道提示，允许精确单层围栏标准化 |

🔥 千问有两个档，不是重复配置。官方规定“思考开启”和
`response_format=json_object` 不能同时使用：

- 想保留推理能力，就不用平台 JSON 模式，改成本地解析和 Schema 验收。
- 想让平台强制给合法 JSON，就必须关闭思考。

所有档都不发送客户端输出 token 上限。这样不会再因为统一写死 8K，把长结果截成半截 JSON。Qwen 质量档里的 32K 是“思考过程预算”，不是最终正文上限。

火山 Agent Plan 还多一层容易踩坑的地方：请求模型名和响应模型名可能不同。例如 V4 Flash 请求写
`deepseek-v4-flash-modelhub`，响应应回
`deepseek-v4-flash-260425`。离线检查器会同时核对两边，禁止静默换模。

MiniMax M3 还有一个已经实测出来的区别：官方当前没有给 M3 承诺
`json_schema` 强制结构化输出。Agent Plan 的 `json_object` 只当请求提示，
不能写成平台硬保证。程序可以接受两种原始形状：

- 原始内容直接是 JSON 对象；
- 全文只包一层小写 `json` Markdown 围栏。

第二种只能生成单独的“标准化后通过”票据，原始 FAIL 不能改写。围栏外多一句
解释、围栏不完整、标签不是小写 `json`、顶层不是对象，都必须拒绝。

## 怎么检查

这一步只读配置，不发模型请求：

```bash
.venv/bin/python tools/model_call_profiles.py validate
.venv/bin/python tools/model_call_profiles.py list
```

查看某一档的完整内容：

```bash
.venv/bin/python tools/model_call_profiles.py show \
  agent_plan_deepseek_v4_flash_high_json_object
```

生成请求预览也不会发网。千问输入文件放 `messages`，Agent Plan 输入文件放
`prompt` 和可选的 `instructions`：

```bash
.venv/bin/python tools/model_call_profiles.py render \
  qianwen_qwen3_7_flash_thinking_prompt_json \
  --input /绝对路径/input.json
```

⚠️ 这些仍是隔离候选配置，没有接进现役 SenseNova 默认链。真实跑批还要有当前任务的明确开跑口令，并在发网前重新核对 Agent Plan 实时模型目录。

来源：Codex
