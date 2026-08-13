# WO-01 三臂 Demo 合同

这轮只回答一个小问题：同一段可写正文不变时，给模型看的只读周边从“没有”增加到“固定 8 字符”，再增加到“当前完整窗口”，事实抽取会怎么变。

- 模型固定为本地 Qwen3-4B 离线代理，checkpoint 固定为 C2_FULL update72；
- 三臂各 24 题，共同使用 DEV24 的 48 条事实；
- system、输出格式、target、Txx、gold、顺序和解码全部不变；
- 请求只含 system+user，runner 必须把两条完整送入，不得删掉 user；
- 未匹配 fact 按同题盲审，同题同文本跨臂只裁一次；
- 只报告事实语义、Schema、status、speaker、evidence、空题、重复、触顶和停止；
- 长度只沿用字符/bytes 粗计，不加载 tokenizer 做预算；
- 结果只用于 DEV24 的方案筛选，不是生产结论。

授权边界：CZ 只批准这一次本地 2 题 smoke 和通过后的 72 次零训练推理。0 自动重试；出现新运行错误立即停。没有 API、训练、Notion、Git 或默认切换授权。

来源：Codex
