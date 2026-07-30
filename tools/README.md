# 工具入口怎么认

✅ 日常先从统一薄入口 `novel_pipeline.py` 进入。它不重写底层逻辑，只把现役批次、治理、检查、测试计划和模型横向试验放到同一个命令入口。

顶层 `--help` 目前只显示由 `zbatch.py` 接管的批次兼容命令；治理、检查、测试计划和横向试验命名空间以本页下表为准。具体参数只使用本页或治理说明里已经验证过的命令，不要假设每个命名空间的顶层 `--help` 都可用。

## 入口层

| 入口 | 这是干嘛的 | 会不会调模型 API |
|---|---|---|
| `novel_pipeline.py preflight` | 把现役批次命令原样转给 `zbatch.py` 做零调用预演 | 不会 |
| `novel_pipeline.py run` | 把获批批次原样转给 `zbatch.py` 执行 | 视当轮阶段而定 |
| `novel_pipeline.py governance` | 只读治理状态或重建生成索引 | 不会 |
| `novel_pipeline.py inspect` | 规则检查与语义分流 | 规则位不会；语义分流须看子命令和施工令 |
| `novel_pipeline.py test-plan` | 按变更范围给出该跑哪些测试 | 不会 |
| `novel_pipeline.py model-benchmark` | 隔离的模型横向试验入口 | 只有获批运行子命令会 |
| `zbatch.py` | 旧兼容入口，统一薄入口仍会转发到这里 | 视阶段而定 |

## 目录层

| 路径 | 角色 |
|---|---|
| `pipeline_common/` | 稳定公共工件：路径、SHA、JSON、运输等 |
| `zbatch_modules/` | 现役流水线模块；形成史看本目录 README，当前状态看模块登记册 |
| `_retired/` | 退役兼容原件；有兼容消费者时继续保留 |
| 根层 `*.py` | 现役入口、可复用组件、批次复现器或兼容件；身份不从文件名猜 |

工具身份只认 [`governance/tool_registry.json`](../governance/tool_registry.json)。测试存在、零引用、名字带旧道次，都不能单独作为删除／移动依据。

本次盘点后，根层 93 个 Python 实体已经逐件登记；另有一个 `z60` 相对兼容软链，不重复算实体。后续若新增根层 Python 却没同步登记，`tests/test_tool_registry.py` 会直接失败。

## 两个打包入口

| 工具 | 用途 | 保护线 |
|---|---|---|
| `simple_pack.py` | 小型 Prompt＋材料外发包；`--controlled-review` 是轻量摘要外审卫生门 | 普通模式保留旧行为；受控模式拒收符号链接、嵌套 ZIP、锁箱／金标／正文式材料名、密钥、绝对路径、非法 JSON 和超长行，并生成模型与发送核对单 |
| `chatgpt_review_pack.py` | 仓库结构与路线证据审查包 | 全仓用 profile；高频产品线用四层 route 取材地图；包内 manifest／SHA／来源票；包外验收票；所有回读通过后才落目标目录 |

打包成功只说明归档字节完整，不等于材料的语义结论已经审收。

小型摘要材料要发给 ChatGPT Pro 时，可以先把材料整理成一个平铺目录，再跑：

```bash
python3 tools/simple_pack.py \
  --prompt <Prompt.md> \
  --source-dir <平铺摘要材料目录> \
  --out-dir <全新输出目录> \
  --zip-name <名称.zip> \
  --controlled-review \
  --expected-model-family "GPT-5.6 Sol" \
  --expected-model-variant "Pro"
```

输出目录里会有 Prompt 副本、一个 ZIP、机械验收票和
`SEND_CHECKLIST.json`。这张清单只负责让浏览器发送前后核对模型、附件、Prompt
和对话状态；它不会自动发送，也不替代 `chatgpt_review_pack.py` 的全仓路线取材。

## 开跑前的保护线

- 旧批次配置和旧运行目录是历史证据，不随当前源码重钉 SHA。
- 新源码进入运行必须有新批次号、运行号和同批决定单；先过 `preflight`，再按施工令决定是否发网。
- `--stages` 只能取当轮白名单里的有序子集，不能越界或倒序。
- 批次专用脚本优先放在对应 `experiments/<实验>/`，不要继续堆到根层再靠事后补说明。
- 不知道一个工具是什么时，先查登记册；登记缺口只挂账，不自动删、不自动定性。

来源：Codex
