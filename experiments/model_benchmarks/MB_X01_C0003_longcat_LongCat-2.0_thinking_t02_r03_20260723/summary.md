# LongCat r03 中断硬停轮｜轻量结论

这轮测试的是 `longcat_platform` 的 LongCat-2.0，在
`neutral_extract_x01_ch0003_v3_t02` 阶段使用 `thinking_prompt_json` 档、温度 0.2
做一次候选采样。进程在写入首次尝试占用票后异常终止，本地没有 HTTP 结果、原始模型回答
或 usage。

结论只能写到这里：

- 模型回答数是 0；
- 模型目录查询联网 1 次且精确型号存在；正式请求的网络结果仍未知；
- 请求预留 1 条、完成尝试账 0 条、原始回答 0 条、usage 记录 0 条（用量未知）；
- 网络结果未知，不能宣称供应商没有收到请求；
- 没有 usage，也没有模型质量成绩；
- 原运行编号禁止重跑、修补或补登记成绩。

主仓只保留：

- `benchmark.json`：模型、供应商和运行条件；
- `state.json`：硬停状态与原因编号；
- `transport/hard_stop.json`：正式硬停票；
- `transport/interruption_forensics.json`：中断取证；
- 本结论卡。

完整 28 文件现场在外置对象
`model-benchmark-longcat-r03-interrupted-s07da-v1`。来源提交是
`62d942e6cf05c7722826c1648436a2eb15708563`，目录 tree 是
`0b005bfed980cf0e30210d1690bdcb2d0be67bb7`，清单 SHA-256 是
`6921fd3c28b3719846592cd076198685221ea48f279494d2b9026c86e945e68e`。

查看完整原件前先核包：

```bash
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id model-benchmark-longcat-r03-interrupted-s07da-v1
```

S-07-D-B 从主仓移除 24 个已经封存的重件，共 552,370 字节。外置包和主仓仍在同一磁盘，
不等于独立备份；轻量目录只负责寻路，不能在原地执行 `verify`、`run`、`audit` 或
`score`。

来源：Codex
