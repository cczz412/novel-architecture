# 模型横向试验总结｜MB_X01_C0003_qianwen_qwen3.7-plus_thinking32k_t02_r06_20260723

✅ 本轮只替换 M04 的供应商／模型插槽；模型可见消息、正文、证据目录、Prompt 与金标均未改。

| 项目 | 结果 |
|---|---|
| 阶段 | X01 第3章中性事件抽取·v3冻结请求·默认温度0.2 |
| 供应商／模型 | qianwen_platform／qwen3.7-plus |
| 兼容档 | thinking_32k_prompt_json |
| 单次采样 | 是，未重跑挑结果 |
| 机械三闸 | PASS |
| 严格命中 | 3/23 |
| 有效召回 | 12/23 |
| 表面覆盖 | 15/23 |
| 锚不托 | 3 |
| Token | 18862 |

## 横向读法

本轮是“thinking_32k_prompt_json＋temperature=0.2”条件成绩。完整兼容差异只在外置原件
包中保留，不能把它冒充成所有参数完全相同的纯模型单变量。

基线：retry03 DeepSeek V4 Flash 严格 6/23、有效 20/23；Z89 DeepSeek V4 Pro 严格 10/23、有效 20/23。

本轮仍是候选银标，不改默认链，不自动升模型。

## 当前怎么取原件

S-07-F-B-A 后，主仓只留身份、请求体、正式成绩、用量和最小调用审计票，并因 V02 仍有
静态指针而保留 `transport/request.json`，共 11 件。完整输入、模型原始回答、判分过程和
随包程序在外置对象 `model-benchmark-qwen-r06-thinking32k-scored-candidate-s07fa-v1`。
先回主仓运行：

```bash
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id model-benchmark-qwen-r06-thinking32k-scored-candidate-s07fa-v1
```

当前轻量目录不能原地复跑。`receipt.md` 中的结果目录描述记录的是 2026-07-23 当时的完整
现场，当前存放位置以本节和外置对象登记册为准。

来源：Codex
