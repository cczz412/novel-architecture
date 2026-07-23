# 小说架构实验仓

> 人看当前状态只走 [治理索引](governance/INDEX.md)，机器读取当前任务／运行状态只走 [当前状态真源](governance/CURRENT_STATE.json)；Notion 账序与队列仍是最终真源。下面保留仓库背景和历史用法，不再承担当前任务路牌。

✅ 这个仓库现在同时承担两件事：继续打磨“大纲中枢”设计，以及把设计放进真实小说里批量测试。

你可以直接理解成一条流水线：

```text
材料入站 → 登记并验哈希 → 零调用预演 → API 运行 → 核锚/压薄/折叠 → 对撞报告 → 打包待上传
```

## 目录怎么认

| 目录 | 这是干嘛的 |
|---|---|
| `foundation/` | 04 批整棵全文根基，仍是真源材料区 |
| `work/` | 正在施工或只读引用的设计稿、执行单、提示词 |
| `intake/` | 新材料和外部回包的收件登记区；原件可入库，也可只登记旧路径 |
| `config/` | 测试批次和 API 路由配置；绝不放密钥 |
| `runs/` | 每次 API 运行的请求、原始回包和中间工件，按运行编号隔离 |
| `reports/` | 给人看的核锚、压薄、折叠、对撞和回执 |
| `outbox/` | 已打包、等待上传 Notion 或发给外部窗口的文件 |
| `tests/` | 不花 API 额度的机械测试 |
| `tools/` | 清版打包器和 Z 批测试运行器 |
| `TEMP/` | 旧批次与临时材料；暂不迁移，避免一次性搬乱 |

## Z 批怎么跑

先跑不花 API 额度的机械测试：

```bash
cd /Users/a1234/挣钱/小说架构 && PYTHONPATH=. /opt/homebrew/opt/python@3.11/bin/python3.11 -m pytest -q tests
```

这条是全仓唯一测试启动命令：固定工作路径、固定 Python 3.11，只收集 `tests/`，不会扫进 `TEMP/`。

再做零调用预演。这里必须使用**当轮新建、SHA 与当前源码一致**的配置：

```bash
python3 tools/zbatch.py preflight --config config/batches/<当轮新配置>.json
```

`D-MOD-002`、`Z00p`～`Z00s` 等旧配置是当时运行配方的历史证据，不是永远追随当前源码的模板。源码 SHA 变化后，旧配置预演失败是保护机制正常生效；不要回写旧配置追新 SHA，也不要在没有新批次号和同批决定单时自行造一张正式配置。

当前固定运输路径只接受 SenseNova `deepseek-v4-flash`。预演不要求加载 API 密钥，也不会调用模型。

现役密钥加载入口只有本仓 `tools/sensenova_deepseek_key.sh`。共享环境加载脚本和外部项目加载器都已退役；历史记录保留，但不再作为开跑入口。

DeepSeek 官方 API 已按 CZ 口径改成默认永久禁用：没有 CZ 在当前任务里的明确正向要求“用官方的API”，加载器会直接拒绝。否定句、转述、只报模型名都不能解锁；详细机器规则见 `config/providers/provider_access_policy.json`。

火山方舟和千问 AI 平台另有隔离的多模型配置：`config/providers/volcengine_ark_multi_model.json` 与 `config/providers/qianwen_platform_multi_model.json`。它们只登记端点和模型白名单，没有接入现役默认链；钥匙统一由 `tools/provider_keychain.sh` 放进 macOS 钥匙串。

确认报告停点已经允许扩大后，用仓库内的弹框把钥匙保存到本机钥匙串：

```bash
tools/sensenova_deepseek_key.sh save
```

正式运行必须使用当轮新拍的配置，并通过项目工具只把钥匙交给这一次命令：

```bash
tools/sensenova_deepseek_key.sh run \
  python3 tools/zbatch.py run --config config/batches/<当轮配置>.json
```

运行中断后，用同一条命令加 `--resume`，已经成功落盘的阶段不会重复调用。

发网前要分开过两道闸：

- 进程读取闸：本仓加载器启动的子进程能读到非空密钥；回执只记通过／未通过，不显示密钥。
- 供应商认证闸：首个获批主采样请求得到供应商正常响应才算通过；只“看见密钥存在”不算通过，也不另发试探请求。

⚠️ 运行器底层只从进程环境里的 `SENSENOVA_API_KEY` 读取，但现役流程只允许本仓加载器临时注入。请求落盘时会明确去掉密钥和 Authorization。

X01 第1～20章的新链与 `extract_v1.3` 同范围对照已经完成；严格净收益为 `+2`，按预写门槛触发翻案重议，当前仍不升默认、不铺 X02～X04。最新本地判词见 `reports/Z00u_extract_v1.3同范围对照_20260718/判词.md`。

来源：Cursor（仓库治理窗）
