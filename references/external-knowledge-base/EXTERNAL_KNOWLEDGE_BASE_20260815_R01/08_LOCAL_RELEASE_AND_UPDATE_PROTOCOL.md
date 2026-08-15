# 外部报告知识库｜本地登记与更新协议

## 这份协议主要解决什么

它把“新报告怎么融进去”落到本仓库的具体位置和动作。新报告不能整篇塞进日常背景页，也不能直接覆盖旧版本。

## 三个长期位置

| 对象 | 放哪里 | 它负责什么 |
|---|---|---|
| 原始报告与 Prompt | `references/survey-inbox/packages/<batch_id>/` | 保存原字节、题意、日期、SHA 和收件边界 |
| 编译后的完整版本 | `references/external-knowledge-base/EXTERNAL_KNOWLEDGE_BASE_<date>_RNN/` | 保存准入账、结论账、来源、冲突、缺口和主题背景页 |
| 当前入口 | `references/external-knowledge-base/CURRENT.json` | 只指向一个已经验收并获准启用的版本 |

产品共同背景板继续放在 `references/shared-context/`。两块背景并列读取，不互相覆盖。

## 一批新报告进来时怎么做

1. **原件入档**：复制原文件，不改正文；登记报告编号、原文件名、日期、字节数和 SHA。逐字 Prompt 缺失时写 `PROMPT_RECONSTRUCTED`，不能用报告标题冒充原文。
2. **报告准入**：判断整份报告是可拆结论、部分可用、只作线索、无法追源、已被接替，还是只属于项目历史。
3. **拆结论**：每条只说一件可判断的事，登记范围、等级、来源、反例、时效、复现情况和旧知识关系。
4. **处理新旧关系**：同向独立证据并列；重复来源不加分；冲突按平台、时间、题材或方法拆开；拆不开就保持 U。
5. **重编受影响页面**：只改涉及的主题，但发布时复制成一个完整新版本，让日常窗口始终只读一个入口。
6. **验来源与引用**：新进入正向背景的 A／B 结论至少有一个本轮可打开来源；编号、JSONL、CSV、SHA 和背景引用全部对上。
7. **切当前入口**：写清相对上一版增加、收窄、反驳、替代和未解决项；经 CZ 明确允许后再更新 `CURRENT.json`。

## 什么时候必须升版本

只要报告准入账、结论账、来源状态、冲突图、研究队列或背景页中的任一正式内容改变，就生成下一个 R 版本。旧版发布后不静默修改。

纯粹收到文件但尚未完成审查时，只登记 SI 收件包，不切知识库当前入口。多个小批次可以攒成一次新版本，但每份收件都要有稳定编号和 SHA。

## ChatGPT Pro 与本地验收怎么分工

- ChatGPT Pro 可以阅读报告、提出原子结论、证据等级、冲突和背景页草稿。
- 本地验收负责原件 SHA、真实路径、URL 打开状态、编号引用、版本差异和当前入口。
- ChatGPT Pro 的判断仍是候选。来源打不开、范围越界或与本地结果冲突时，本地账如实降级或保留未知。
- 产品采用哪条建议仍由 CZ 拍板；报告知识库不能给自己增加执行权。

## 每版最低交件

- `00_READ_ME_FIRST.md`
- `01_REPORT_ADMISSION_LEDGER.md`
- `02_CLAIM_LEDGER.jsonl`
- `03_SOURCE_REGISTRY.csv`
- `04_CONFLICT_AND_SUPERSESSION_MAP.md`
- `05_RESEARCH_GAPS_AND_REFRESH_QUEUE.md`
- `06_FUTURE_REPORT_INGESTION_STANDARD.md`
- 来源核验摘要与逐条回执
- `background/` 完整主题页
- `MANIFEST.json` 与相对上一版的变化说明

来源：Codex
