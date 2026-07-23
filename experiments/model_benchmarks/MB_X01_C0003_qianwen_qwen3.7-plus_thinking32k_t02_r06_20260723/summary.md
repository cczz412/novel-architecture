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

本轮是“thinking_32k_prompt_json＋temperature=0.2”条件成绩。供应商兼容差异见 `prepared/compatibility_diff.json`，不能把它冒充成所有参数完全相同的纯模型单变量。

基线：retry03 DeepSeek V4 Flash 严格 6/23、有效 20/23；Z89 DeepSeek V4 Pro 严格 10/23、有效 20/23。

本轮仍是候选银标，不改默认链，不自动升模型。

来源：Codex
