# WO-01 三套匹配 LoRA Demo

三臂都使用同一 Qwen3-4B base、同一 C2 输出合同、同一 Set A 24 条内容和 gold，只改变模型可见的只读上下文范围：只给目标区、固定 8 字符邻域、完整当前窗口。

三臂分别从 base 独立训练，不互相续训。训练配方逐项复用 M1 C2_FULL：288 iterations、72 optimizer updates、batch 2、gradient accumulation 4、16 layers、learning rate 3e-5、seed 20260802、rank 32、scale 0.125、save every 96、packing off。

DEV24 Set B R03 只考试、不训练。每个 LoRA 只接收和自己训练格式相同的 24 道题。主指标是可恢复事实语义 F1；Schema、status、speaker、evidence、复读和触顶分开报告。

本轮是本地 Demo，只用于淘汰明显差方案。0 API、0 Notion、0 Git、0 默认或生产改动。

来源：Codex
