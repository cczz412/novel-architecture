# P4｜Wide Read, Narrow Write 输入合同

## 这份合同管什么

这轮只冻结责任区粒度实验的输入边界，不运行模型，也不决定生产默认。

`C0` 只是本次 P4 的固定实验对照。它不是生产 Prompt，也不能证明 P3 暂停的规则、任务目的、前态、背景卡、示例或位置 metadata 永远无效。

P3 真正跑过的 C0 已绑定在 `P4_C0_SOURCE_BINDING.json`：24 条请求文件、原 renderer、system prompt、user 请求来源和输出合同都有路径与 SHA。P4 不手写近似 C0。未来 runner 必须从绑定件读取并核 SHA；当前玩具代码只能使用明确标成 `TOY_ONLY_NOT_P3_C0` 的假 Prompt。

WRNW 必然会把 P3 的 user 布局改成“未编号阅读区 + 尾部编号责任区”，所以不能谎称新 user 请求与 P3 C0 逐字一样。允许改变的是这一个已预注册的布局；P3 C0 的 system 和输出合同不变。

## 输入由两块组成

### READ_CONTEXT

- 是未编号、只读的阅读前缀；
- 只帮助理解人物、指代和上下文；
- 其中没有合法 evidence ID；
- 模型不得用这里的文字支持新事实；
- `LOCAL_READ` 使用固定机械 halo；`FULL_CHAPTER_READ` 使用完整章；
- 两种模式都必须把目标责任区原文无编号地展示一次。

### RESPONSIBILITY_EXCERPT

- 固定放在输入尾部；
- 只给当前责任区编号；
- 当前责任区原文在这里以编号形式再展示一次；
- 允许证据表只列本区 `Txx`；
- 每条新事实只能引用当前允许表中的 ID；
- READ_CONTEXT、相邻区和章内其他位置都不能产生合法 evidence ID。

模型可见的每一行只能有 `evidence_id` 和 `text`。下面这些全部留在 evaluator／audit sidecar，不能进入模型请求：粒度名、责任区号、稳定原子 ID、绝对 char／byte 坐标、局部 ID 到全章 ID 的映射、LOCAL/FULL arm 名。

你可以直接理解成：模型可以读宽一点，但只能在尾部这一小块里落笔和举证。

## 六臂唯一变量

六个未来诊断臂是：

| 阅读范围 | 责任区粒度 |
|---|---|
| LOCAL_READ | P4-GRAN-10 |
| LOCAL_READ | P4-GRAN-20 |
| LOCAL_READ | P4-GRAN-30 |
| FULL_CHAPTER_READ | P4-GRAN-10 |
| FULL_CHAPTER_READ | P4-GRAN-20 |
| FULL_CHAPTER_READ | P4-GRAN-30 |

同一粒度的 LOCAL/FULL 两臂，模型可见 payload 只有 `READ_CONTEXT.text` 允许不同。arm 名和读取范围只写隐藏 run manifest。把 LOCAL 的该文本替换成 FULL 文本后，两份模型 payload 必须 canonical bytes 一致。

下面这些也必须逐字一致：

- 当前责任区；
- 尾部编号及允许 ID 表；
- `C0` system prompt；
- 输出合同；
- 题目顺序；
- 模型、权重、tokenizer、chat template；
- 解码参数、最大输出和 retry；
- evaluator 与章级 gold。

两种阅读方式都让目标责任区出现两次：READ_CONTEXT 内无编号一次，尾部编号一次。不能让重复次数成为隐藏变量。

## LOCAL_READ 的固定 halo

预注册规则为：目标责任区前一责任区 + 目标责任区 + 后一责任区；章首、章尾自然截短。halo 只看 splitter 产出的相邻关系，不读 gold、模型结果或人工判断。

如果后续认为 halo 大小要改，必须新开实验 revision，不能在本轮看到成绩后修改。

## 当前首轮明确排除

- 任务目的说明；
- 确认前态；
- 人物／别名背景卡；
- 正例、反例或 minimal pair；
- 章节序号；
- 第几责任区；
- 相对位置；
- 缓存策略变化。

这些变量都可能另有价值，但放进这轮会让“阅读范围”和“责任区粒度”混在一起。

## gold 与跨区事实

gold 必须在 splitter 运行前冻结，并绑定完整章绝对字符范围。splitter 不得读取 gold 决定边界。

入口先读原始 bytes、直接算 SHA，再用 strict UTF-8 解码；禁止经 `read_text()` 做换行归一化。解码后重新编码必须逐字节还原，非严格 UTF-8 直接判资格失败，不自动转码。

切分完成后才做机械分类：

- 所有合法 evidence 完整落在同一责任区：进入干净主指标；
- evidence 落在多个责任区：登记为跨区事实；
- 任一 evidence 不能回填原章或不在责任区完整覆盖：硬停该章。

跨区事实不能按“第一条证据起点”塞进某一区，也不能从最终可用性判断里消失。单个 evidence span 自身跨边界，或同一 fact 的不同 evidence 分处多区，都算跨区。

跨粒度比较固定报告两套不可漂移的分母：

1. 共同可抽交集：只含在被比较的所有粒度中都完整落在单一区的 gold；
2. 整章 all-gold：同一份完整章全部 gold。当前合同无法合法产出的跨区事实在这一层记未召回。

每个粒度自己的“区内事实成绩”只能诊断，不能决定胜负。跨区事实不进入共同交集，但必须进入 all-gold recall／F1 和最终可用性门。

当前预注册的后续处理候选只有三类，P4 不拍其中任何一个：

1. 扩大责任区；
2. 新建明确的跨区证据合同；
3. 交由复杂案例升级路线。

## 工程假设边界

“整章可以缓存、所以 FULL_CHAPTER_READ 更省钱”只是待验证工程假设。P4 不测缓存，也不登记成本收益。

本地 Qwen 2B/4B 只是离线试验代理。六臂即使跑完也只能选诊断候选；生产晋级必须经过独立 holdout，并在另行授权后由 Doubao Mini/Lite 复验。

来源：Codex
