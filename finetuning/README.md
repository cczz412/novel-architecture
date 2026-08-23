# 微调这条路，放弃了

✅ 结论：本仓 **不再做微调训练**。Git 里不再留训练集、考卷、权重、正线实验包。本地另有保底仓，真要翻旧件去那里。

你可以直接理解成：试了很久「把小模型微调成抽事实的专才」，这条线停了。当前指针只指向一个空落点，任何训练、晋升授权都是关的。

## 现在 Git 里还留什么

1. **此路不通的落点**：[CURRENT.json](CURRENT.json) 指向 [T5_R04_LINE_ABANDONED_20260823_R01](experiments/T5_R04_LINE_ABANDONED_20260823_R01/)。里面没有教材、没有权重，就是一块路牌。
2. **试过不行的结果票**：Prompt 这样写好还是那样写好、剂量加一点会不会复读。这些主要是本机 **Qwen 3 4B（MLX）** 跑出来的，不是 Deepseek，也不是豆包当考官。清单见 [experiments/README.md](experiments/README.md)。
3. **中间桥工具包**：初筛、预飞、认分器。暂时留着给别的实验借用，后期要整顿。同样写在 experiments 的 README 里。
4. **豆包停在这儿**：P0 只写过生产路牌，没有当过这批 Prompt 对照的考官。原件还在 experiments 里，不当现行训练入口。

❌ 不要从本目录再开训练。没有明确许可就是不能训练。

## 日常怎么认

- 人看结论：本页。
- 机器认当前实验：[CURRENT.json](CURRENT.json)。
- 兼容旧路牌：[references/t5-r04/README.md](../references/t5-r04/README.md)（派生视图，删了能重建；历史目录还在 `route_catalog.json` 里指路，原件多半已不在本 Git）。

来源：CZ 2026-08-23 拍板；#99
