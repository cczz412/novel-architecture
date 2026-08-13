# READ Round1｜本地 LoRA Demo

这轮只回答一个问题：同一套 TRAIN36、同一答案写法、同一训练配方下，模型读目标段、小邻域或完整章节，哪种方案更少漏事实、更少越界。

三臂都从同一个 Qwen3-4B 原始模型独立开始，依次训练 READ-1、READ-2、READ-4。每臂36题、714条事实，固定跑288 iteration，也就是72次参数更新；不续训、不调参、不把真实24题放进训练。

运行顺序：

```bash
/opt/homebrew/opt/python@3.12/bin/python3.12 run_read_round1.py prepare
/opt/homebrew/opt/python@3.12/bin/python3.12 run_read_round1.py train-all
/opt/homebrew/opt/python@3.12/bin/python3.12 run_read_round1.py infer-base-all
/opt/homebrew/opt/python@3.12/bin/python3.12 run_read_round1.py infer-lora-all
uv run --locked python score_read_round1.py pre
```

训练和答卷写入 `runs/T5_R04_READ_CONTEXT_ROUND1_LORA_DEMO_R01/`。推理固定 greedy、temperature 0、最大输出2048、0重试；每条考试请求完整发送 system+user，答案和 Gold 不进模型请求。

预评分只把归一化后完全相同的事实机械配对，其余预测按同题去重后进入人工语义队列。人工裁决完成前，语义分只是下界，不宣称最终 F1。C06、C18 的姓名还原只进独立诊断，不进入共同主分。

边界：本机训练与推理已获 CZ 本轮授权；API、Notion、Git、生产默认和真实24训练均为0。真实24仍是本机筛选考试材料，不上传、不发布。

来源：Codex
