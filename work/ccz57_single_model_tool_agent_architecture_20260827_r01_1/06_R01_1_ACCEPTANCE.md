# R01.1 候选验收合同

## 文档机械验收

- 本目录 Markdown 均为 UTF-8；
- 所有 JSON 代码块可解析；
- 所有相对文件引用指向本目录已存在文件；
- 文档不含 API Key、小说正文、本机密钥路径；
- 文档没有声称 API 已运行、模型已排名、Gold 已生成或产品已通过；
- GitHub 当前 SHA、PR 身份和时间边界明确；
- 所有“缺少能力”都写清当前读取、当前输出、小说辅助产品缺少什么、卡住作者哪个操作。

## 设计一致性验收

- M3 输入仍是一个 current C2，不扫描磁盘；
- C3 字段没有被 status、speaker、Diagnostic 或因果 hint 扩写；
- 正式 `f...` 和 `CE-...` 仍由现役 M4／factstore 分配；
- C3 没有被偷加 client item key；lineage→f-ID 映射被明确标成尚缺正式批次回执；
- 机器不能确认 FACT_CAUSAL_EDGE；
- 工具调用从原生字段读取，不从正文或 reasoning 猜；
- 模型可调用工具、控制器固定服务、人工动作已经分开；
- A／B 为 0 API，C／D 才能发真实模型请求；
- provider 缓存不是恢复真源；
- 32 项目录不是 A 票的默认写集。

## 必须回到 CZ 的拍板项

1. B 票早期语义 Patch 是否一律人工批准；
2. D 票允许使用哪些真实小说 C2，怎样脱敏和保存；
3. 每个端点的费用、调用数和停止预算；
4. `status`／`speaker` 的长期保存与读取模块；
5. M3 hint→M4 f-ID→factstore candidate 的触发责任；
6. 过期 causal hint 的长期保留期限。

## 本轮合法结论

> R01.1 把单模型工具 Agent 收缩成可按风险施工的候选合同，并修正了 GitHub 漂移、回包类型混淆、工具 Schema 悬空引用、缓存冲突和因果 writer 接线。它没有证明任何模型已经能稳定自我修复。

来源：Codex
