# WO-01｜短片段责任范围三臂预检

✅ 这张工单只把材料和未来运行合同封好，没有调用模型，也没有训练。

它要查的是一件很具体的事：同一段可写正文完全不动，只改变模型能读到多少周边文字，会不会影响事实抽取。

三臂是：

- `TARGET_ONLY`：只显示可写 target；
- `SMALL_HALO`：增加 target 前最后 8 个 Unicode 字符和后最前 8 个 Unicode 字符；
- `CURRENT_WINDOW`：保留 DEV24 现有的全部只读上文和下文。

24 题都有独立的上文、target 和下文，target 及 Txx 可逐字机械恢复，所以 24/24 可以生成公平请求。小 halo 只按原文字符位置截取，不看 gold，也不按旧模型错题调大小。它只是固定 8 字符邻域，不冒充完整语义句。

两次相邻比较都真正改变了 24/24 题：target-only 到小邻域增加固定范围只读字；小邻域到当前窗口继续扩大只读范围。可写 target、Txx、gold 和评分分母始终不动。

本轮长度只按 Unicode 字符、中文字符粗计、可见字符粗计和 UTF-8 bytes 报告。它只说明上下文范围有明显增减，不声称是等 token 因果实验，也没有在最终构建中加载 tokenizer。

P3 C0 原题面会显示 case ID，问题文件还带 assistant gold。WO-01 按当前工单把 case ID、arm 和 gold 全部移到隐藏 sidecar；模型只看到同一个 C0 system、同一个编号 target 和不同范围的只读上下文。因此这里的 `CURRENT_WINDOW` 是“P3 C0 去掉可见题号后的同源请求”，不是旧 P3 请求的逐字复印件。

当前身份：`PASS_WO01_PREFLIGHT_24_OF_24_READY_NO_RUN_AUTHORITY`。

它不授权 72 次推理，不允许修改 DEV24，也不能把开发集结果写成最终盲考结论。

来源：Codex
