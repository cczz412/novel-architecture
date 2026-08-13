# WO-01 短片段责任范围合同

## 固定件

- 模型：本地离线代理 Qwen3-4B；
- checkpoint：C2_FULL update72，SHA `321d96c10f00389e557efbeb2d8e3dc1344071cc3cd663b51b8a8c2bd38ea5f9`；
- 开发集：Set B R03，24 题／48 facts，只作开发筛选；
- system：P3 C0 冻结 system，SHA `69b6263a06cf8db60b006b760772ff65fc50dff4132257d667ef4b76ffeac066`；
- 输出结构：P4.1 Schema，SHA `7c6a6fab7d32c9a8c04b10a09f37f8f9ac47308c9b12127bfceb231418dbcd14`。

上面最后一项只代表结构校验。事实、状态、说话人和 evidence 是否正确，仍由现有 scorer 分层判断。

## 三臂只允许变什么

三臂的 system、target 原文、Txx、Txx 顺序、evidence allowlist、case 顺序、gold 绑定、输出 Schema 和未来解码参数必须一致。

唯一允许变化的是两个只读区里的文本范围：

- `TARGET_ONLY`：左右只读区均显示“无”；
- `SMALL_HALO`：左侧取 target 前最后 8 个 Unicode 字符，右侧取 target 后最前 8 个 Unicode 字符；
- `CURRENT_WINDOW`：使用 canonical 中完整的 `read_only_before` 与 `read_only_after`。

## 小 halo 的机械规则

只按 canonical 已冻结的 `read_only_before` 和 `read_only_after` 字符位置取值，不做分句或语义判断。

- 左侧固定取 `read_only_before[-8:]`；
- 右侧固定取 `read_only_after[:8]`；
- 原字段不足 8 个 Unicode 字符时才取全部；
- 没有按 fact 数、evidence 长短、模型对错或题材选择大小；
- 不允许运行后更换字符数或逐题补字。

这是一条新冻结的位置机械规则，不冒充 DEV24 原有 atom，也不声称截取结果是完整语义句。

## 可写区与只读区防火墙

- 只有 `[Txx]` 属于合法 evidence ID；
- 只读上文使用隔离的 `[Bxx]`，只读下文不编号；
- `[Bxx]` 和未编号下文都不能进入 `evidence_ids`；
- 模型可见请求中不出现 arm、case ID、halo 大小、绝对坐标或 sidecar 字段；
- 隐藏 sidecar 才记录 arm、case、字符范围、来源 SHA、allowlist 和 gold 绑定 SHA。

## P3 C0 的继承边界

`CURRENT_WINDOW` 保留 P3 C0 的 system、编号只读上文、编号 target 和未编号下文。为了满足当前无泄漏工单，统一删除模型可见的 `【题号】＋case_id`，也不把 assistant gold 放入请求。

因此可以声称“上下文内容同源，去掉题号后 24/24 精确一致”，不能声称与旧 P3 C0 完整请求逐字相同。

## 原始字节与确定性

入口先读原始 bytes，再 strict UTF-8 decode，并验证重新编码与原 bytes 相同。不接受自动转码或换行归一化。相同输入必须连续构建两次逐字一致；树摘要以最终构建票为准。

长度护栏只统计模型可见 system／user 内容的 Unicode 字符、中文字符粗计、可见字符粗计和 UTF-8 bytes。本轮不加载 tokenizer，也不把这些字符数写成 token 数。

来源：Codex
