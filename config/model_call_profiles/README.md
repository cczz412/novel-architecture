# 模型调用配置库

这个目录专门解决一个问题：以后换模型时，不再临时手写一份请求 JSON。

你可以直接理解成两层：

- `config/providers/` 管“从哪个平台、哪个地址、拿哪把钥匙、精确模型名是什么”。
- 这里管“这个模型具体怎样调用”：温度、思考档、JSON 方式、是否流式、要不要发送输出 token 上限。

Wave 2 又把一套调用需要的零件拆成四层，每层只管一件事：

- `contracts/<profile_id>/` 管这个 API 的请求外壳、响应外壳和严格解析规则。
- `config/prompts/<prompt_id>/` 管提示词正文及它的 SHA 清单。
- `config/context_recipes/<recipe_id>.json` 管这些零件按什么顺序组成上下文。
- `config/contracts/<contract_id>.schema.json` 管任务结果最终必须长什么样。

API 合同可以被多个任务复用，所以它不会反向引用某个 Prompt 或试验。上下文配方
才是总装入口：它单向选定一个调用合同、一个 Prompt 和一个任务结果 Schema。

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

## 怎么自取一整套离线零件

查看已经登记的规则包：

```bash
.venv/bin/python tools/model_call_profiles.py list-bundles
.venv/bin/python tools/model_call_profiles.py show-bundle \
  wave2_synthetic_json_probe_v1
```

把规则包解析成 S0 复制器能直接使用的六字段清单：

```bash
.venv/bin/python tools/model_call_profiles.py resolve-bundle \
  wave2_synthetic_json_probe_v1
```

输出中的每一项都有用途、仓库来源、工作区目标、字节数和 SHA。它不会复制文件，
也不会创建目录。把这些项目放进试验自己的 `materialize_plan.json`，再由
`tools/experiment_workspace.py materialize` 一次性复制。试验程序和合成输入也应
作为独立项目写进同一份计划，运行时不能回头引用主仓文件。

⚠️ `resolve-bundle` 的整份输出不是物化计划，不能直接用管道传给复制器。它只开出
`items` 这张领料单。计划还要由新试验的责任窗口补齐下面这些现场证据：

| 计划字段 | 从哪里取得 |
|---|---|
| `plan_id`、`run_id`、`revision` | 新试验自己的编号、运行号和修订号 |
| `expected_head_sha` | 冻结计划时的 `git rev-parse HEAD` |
| `s0_receipt` 四项 | 针对同一个 Git 提交新生成的 S0 机械票、Wave 计划及各自 SHA；旧提交的票不能复用 |
| `materializer_bundle_sha256` | 当前复制器代码整包 SHA |
| `allowlist_contract_id`、`allowlist_contract_sha256` | 当前 S0 复制白名单的固定编号和 SHA |
| `capability_limits` | S0 复制器规定的“只复制”能力边界 |
| `items` | `resolve-bundle` 输出里的规则包项目，再加本试验自己的程序和合成输入；合并后按 `destination` 对全部项目重新排序 |

复制器整包 SHA、白名单 SHA 和准确的能力边界不要手抄，可以在冻结计划时从同一份
复制器代码读取：

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from tools.experiment_workspace_modules.contracts import (
    ALLOWLIST_CONTRACT_ID,
    CAPABILITY_LIMITS,
    allowlist_contract_sha256,
    materializer_bundle_sha256,
)

print("allowlist_contract_id =", ALLOWLIST_CONTRACT_ID)
print("allowlist_contract_sha256 =", allowlist_contract_sha256())
print("materializer_bundle_sha256 =", materializer_bundle_sha256(Path.cwd()))
print("capability_limits =", json.dumps(CAPABILITY_LIMITS, sort_keys=True))
PY
```

能交给复制器的完整骨架如下。尖括号只是说明位，不能原样留在正式 JSON 里：

```json
{
  "contract_version": "experiment-materialize-plan-v1",
  "plan_id": "<新试验计划编号>",
  "run_id": "<新运行号>",
  "revision": 1,
  "expected_head_sha": "<冻结计划时的 40 位 Git SHA>",
  "s0_receipt": {
    "path": "TEMP/restructure_wave_preflight/<当前窗口>/<S0机械票>.json",
    "sha256": "<S0机械票 SHA256>",
    "wave_plan_path": "TEMP/restructure_wave_preflight/<当前窗口>/<S0计划>.json",
    "wave_plan_sha256": "<S0计划 SHA256>"
  },
  "materializer_bundle_sha256": "<上面命令输出的复制器整包 SHA>",
  "allowlist_contract_id": "experiment-materialize-allowlist-v1",
  "allowlist_contract_sha256": "<上面命令输出的白名单 SHA>",
  "capability_limits": {
    "delete_source": false,
    "external_removal": false,
    "materialize_only": true,
    "model_api": false,
    "network": false,
    "notion_write": false,
    "physical_move": false,
    "preflight": false
  },
  "items": [
    "<展开 resolve-bundle 的 items，补试验程序与合成输入，再按 destination 重排全部项目>"
  ]
}
```

正式计划只能放在 `experiments/<试验编号>/`；写完后再运行
`tools/experiment_workspace.py materialize --plan ...`。如果还没有与当前 Git 提交
一致的 S0 机械票，就停在领料单，不得拿旧票拼计划。这里只取解析结果中的
`items`；外层的规则包编号、状态和能力说明用于核对，不能整包嵌入物化计划。

当前 `wave2_synthetic_json_probe_v1` 只是合成 JSON 探针。它选用
`qianwen_qwen3_7_flash_json_object_no_thinking` 格式对照档，不会改变
Qwen 的全局推荐档，也不会替换 SenseNova 现役默认链。

⚠️ 这些仍是隔离候选配置，没有接进现役 SenseNova 默认链。真实跑批还要有当前任务的明确开跑口令，并在发网前重新核对 Agent Plan 实时模型目录。

来源：Codex
