# P4｜责任区 splitter 规格

## 命名

- `P4-GRAN-10`：每个完整章目标约 10 个责任区；
- `P4-GRAN-20`：目标约 20 个；
- `P4-GRAN-30`：目标约 30 个。

这里故意带 `P4-GRAN-` 前缀，避免和仓内旧 `G10` 路线混淆。目标数不是强行切成恰好 N 块；如果完整句子／对话轮数量不足，实际区数取可用原子单元数。

## 输入和输出

输入必须是已通过资格闸的完整章原始 bytes、来源身份、预期原章 SHA。入口直接 `read_bytes` 后核 SHA，再用 strict UTF-8 解码；禁止 universal-newline 归一化。`text.encode("utf-8")` 必须和原 bytes 完全一致，非严格 UTF-8 失败且不自动转码。splitter 输出：

- 来源 SHA；
- Unicode 字符总数与 UTF-8 字节总数；
- 稳定原子单元 ID；
- 每个单元的绝对字符起止和 UTF-8 字节起止；
- 稳定责任区 ID；
- 每个责任区的单元列表、绝对范围和逐字原文；
- 请求区数与实际区数。

所有范围统一使用左闭右开 `[start, end)`。

## 原子单元规则

1. 只在完整句末、换行或完整对话轮结束处切分；
2. `“……。”某人说。` 视为一个完整对话轮，不在引号后把归属语拆开；
3. 句末标点在引号内时，等待引号闭合；后面紧跟归属语时，继续等到归属语句末；
4. 空白必须并入相邻单元，不能丢字节；
5. 没有句末标点的剩余尾段整体保留；
6. 超长句、超长对话轮不再二次劈开，允许单元超过平均预算；
7. 原子单元拼接必须逐字重建原章。

## 从原子单元分成责任区

对每个粒度，先计算 `min(目标区数, 原子单元数)`。然后按 UTF-8 累计字节目标做确定性均衡，只能在原子单元边界落刀；距离相同时固定选更靠前的边界，并保证剩余每区至少一个原子单元。

这个算法不接收 gold 参数，也不读取模型输出。人工不得为某章修改切点。

稳定 ID：

- 原子单元：`U0001`、`U0002`……；
- 责任区：`P4-GRAN-10-Z001`、`P4-GRAN-20-Z001`、`P4-GRAN-30-Z001`……；
- 尾部局部 evidence ID：每个责任区内重新从 `T01` 开始；
- 局部 ID 必须保存到全章稳定单元 ID 和绝对范围的映射。

这张映射只进 evaluator／audit sidecar。模型可见尾部行严格只有 `evidence_id` 和 `text`；不得出现粒度、区序、稳定单元 ID 或 char／byte 坐标。

## gold 只在切完后进入

冻结 gold sidecar 至少要有 `fact_id` 和每条 evidence 的原章绝对字符范围。切完后机械判断：

- 全部 evidence 位于同一责任区：`WITHIN_ONE_RESPONSIBILITY_ZONE`；
- 单个 evidence span 与多个责任区相交，或同一 fact 的不同 evidence 分处多个区：`CROSS_RESPONSIBILITY_ZONES`；
- 逐字回填失败或没有被完整责任区覆盖：`UNMAPPABLE_OR_NOT_FULLY_COVERED`，该章硬停。

分类函数不能改变 splitter 输出。跨区事实不创建假唯一归属。

三种粒度都分类后，机械冻结：全部章级 gold、三种粒度各自 contained 集、三者共同 contained 交集。跨粒度胜负只能使用共同交集和 all-gold 两套固定分母；各粒度自己的 contained 集只作诊断。

## 双跑与失败门

同一输入、同一代码、同一配置连续运行两次：

- splitter JSON 必须逐字节一致；
- source SHA、单元、区边界、ID、gold 分类与渲染对必须一致；
- 两个模型 payload 递归扫描不得出现 sidecar 审计字段或 LOCAL/FULL treatment label；
- 把 LOCAL 的 READ_CONTEXT 文本替换成 FULL 后，模型 payload canonical bytes 必须一致；
- 任一原文字节缺失、重复或改写，失败；
- 任一 char/byte 范围不能回填，失败；
- splitter 调用 gold 决定边界，失败；
- 人工修改单章输出，失败。

当前原型只在 `tests/fixtures/toy_chapter.txt` 上做机械验收，不读取真实小说正文。

来源：Codex
