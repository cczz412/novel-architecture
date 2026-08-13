# READ 家族 TRAIN36 构建说明

这批文件只供本地 Demo 训练。训练材料只有14个项目原创故事的 TRAIN36；真实 LOCAL_REAL_SCREEN24 没有进入任何训练文件。

- 题目：36题
- 候选事实：714条
- READ-1：前部只读目标段
- READ-2：前部只读目标左右各最多180个 Unicode 字符
- READ-4：前部只读完整原章，不额外追加 halo
- 模型可见正文已剥离独立的文末署名“来源：Codex”及相邻尾空白；raw source SHA和目标坐标不变
- 三臂的 system、尾部编号目标、证据允许表和 assistant 逐题一致
- 每题目标在前部只读范围出现一次，并在尾部编号负责区再出现一次
- 长度只按模型可见 Unicode 字符粗计，没有加载 tokenizer

## 模型可见字符粗计

| arm | min | median | max | mean |
|---|---:|---:|---:|---:|
| READ-1-TARGET | 2606 | 3745.5 | 4845 | 3797.694 |
| READ-2-HALO180 | 2802 | 3985.5 | 5145 | 4061.778 |
| READ-4-FULL-CHAPTER | 4162 | 5544.5 | 6902 | 5452.361 |

## 四个 JSONL SHA-256

- `TRAIN36_GOLD_36.jsonl`：`4ed02087b5a9b9f952f1fa80b02a60f0f6c7ed2db3ac65d955dc97e3219b3ef9`
- `READ_1_TARGET_TRAIN36.jsonl`：`84ad6f7886b372334b008d49cc2f3343afdd6b98d83a24a00d604ae49b8f09e0`
- `READ_2_HALO180_TRAIN36.jsonl`：`09fdbc52f7131f1a2a60552740ce28430e418ed84c858f0f997abda16e4a7c5e`
- `READ_4_FULL_CHAPTER_TRAIN36.jsonl`：`93b3ab7e9beed9a6f54df751400ba2ac65cfd5a18f1865da01c7c0c81540ed4a`

这只是候选训练渲染，不代表正式生产训练集，也不授权本轮启动训练。

来源：Codex
