# LongCat r01 中断硬停轮｜轻量结论卡

这轮测试的是 `neutral_extract_x01_ch0003_v3_t02` 阶段，供应商是
`longcat_platform`，模型是 `LongCat-2.0`，调用档是 `thinking_prompt_json`，
温度为 0.2。它只是一轮候选测试，不是默认配置。

## 能确认什么

- 正式采样写入一次尝试占用票后，进程被 SIGKILL 终止，退出码为 137。
- 本地模型回答数是 0；网络结果未知，不能说供应商没有收到请求。
- 用量未知；原记录中没有调用完成票、原始回答或用量行。
- 模型目录查询发生过 1 次联网，但它不是正式模型回答。
- 本轮没有质量分，不能拿来判断 LongCat 的抽取效果。
- 原运行禁止重跑、补票或晋级。

## 主仓保留什么

- `benchmark.json`：模型、阶段、调用档和温度身份。
- `state.json`：硬停状态和禁止重跑规则。
- `transport/hard_stop.json`：回答数、网络、用量和硬停原因。
- `transport/interruption_forensics.json`：退出码、占用票和运输结果未知的取证。
- 本结论卡：给人快速判断是否值得继续查。

Z57 旧合同测试需要的历史程序已经原字节复制到
`tests/fixtures/z57_frozen_neutral_extract_20260723/neutral_extract.py`。夹具大小为
8,465 字节，SHA-256 是
`f567ebef481dc33775ba7974c09744d185d6b8fa2b7b5e947e0be89f145dd7a7`。

## 完整现场去哪取

- 外置对象：`model-benchmark-longcat-r01-interrupted-s07ea-v1`
- 来源提交：`0550e45c9c4cafbda905e8d436f883d04c5e818b`
- 来源目录 tree：`130d9cda5b73041ab83453ca639d3eb8c1ae2a1b`
- 完整规模：28 个文件、550,603 字节
- 清单 SHA-256：`f20195d1684447eac8361af86d7b420c1333c35aa9bada7548e28957436b5a10`

回主仓核验：

```bash
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id model-benchmark-longcat-r01-interrupted-s07ea-v1
```

S-07-E-B-B 在外置验证、完整取回和消费者复核通过后，从主仓移除 24 个重件、
547,439 字节。当前轻量目录不能原地运行；需要历史审计时，应先按对象编号取回完整现场。
外置包和主仓仍在同一磁盘，所以它不是独立备份。

来源：Codex
