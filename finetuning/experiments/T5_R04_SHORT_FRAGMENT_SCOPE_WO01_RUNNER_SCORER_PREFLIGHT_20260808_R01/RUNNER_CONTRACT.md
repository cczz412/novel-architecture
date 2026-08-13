# WO-01 专用 Runner 合同

## 为什么不能复用旧入口

P3 旧请求是 system＋user＋assistant gold，旧 runner 用 `messages[:-1]` 去掉 gold。WO-01 请求只有 system＋user，两者数据结构不同。

新入口只接受恰好两条消息，角色必须依次为 system、user。实际运行和 TEST_ONLY 演练共同调用 `serialize_messages(tokenizer, messages)`，整个列表原样传给 `apply_chat_template`，禁止切片。

## 启动前必须同时通过

- R01 manifest SHA：`e4efced726b066002cb91630b77d21ef7a22cf2eb05ef7e4aca59a2482ae694f`；
- 三份请求及隐藏 sidecar SHA；
- C2_FULL update72 checkpoint 与 adapter config SHA；
- P4.1 Schema SHA；
- tokenizer config、tokenizer 文件与 chat template 文本 SHA；
- 基础模型 `MODEL_RECEIPT.json` 的 SHA 与 revision；正式运行在 load 前重新核 13 个成员的 bytes/SHA，包含 3 个权重分片、index、config、generation config 和 tokenizer；
- 72 条 `arm + row_index` 对应 sidecar，模型可见层不提供 case/gold；
- 另行 CZ 运行票满足 `RUN_AUTHORIZATION_SCHEMA.json`，并锁定唯一 run ID、三臂顺序、72 请求身份摘要和唯一输出目录。

任一漂移直接硬停，不重试、不换模型、不回退 P3 runner。

## 运行目录和一次性授权

正式工件只能写入：

```text
/Users/a1234/挣钱/小说架构/runs/T5_R04_SHORT_FRAGMENT_SCOPE_WO01_R01/<run_id>/
```

路径会同时做逐字比较和 `resolve()` 后的祖先检查；根外路径、`..`、符号链接逃逸都会硬停。claim 也只写在这个运行根下，不回写本预检目录。

模型加载前先写不可覆盖的起始票。同 run ID 已有 claim，或唯一目录已有 start/success/abort 任一工件，都禁止再次使用。失败会保留 `RUN_ABORTED_RECEIPT.json`，不会自动重试；重开必须使用新工单和新授权票。

运行前和每题前都检查系统空闲内存；低于 8% 硬停。MLX 的 wired/memory/cache 上限固定为 20/22/1 GiB，每题后清缓存，并在成功票记录峰值内存、前后内存快照和整臂耗时。

## 固定解码

```text
greedy
temperature = 0
max output = 1024
retry = 0
```

当前 `validate` 和 `dry-run` 不加载模型。`run` 只有通过独立授权票后才会延迟导入 MLX、加载 checkpoint。

来源：Codex
