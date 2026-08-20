# Project Sources 与大量报告的放置标准

## 1. 最佳结构：MD 给脑子，ZIP 给手

```text
Project Sources/
├─ 00_PROJECT_ROUTER.md          # 语义入口
├─ 01_CURRENT.json               # 精确 current
├─ 02_AUTHORITY_AND_SCOPE.md     # 权力与范围
├─ 10_PRODUCT_CONTEXT.md         # 主题背景
├─ 11_ATOMIC_EXPECTATIONS.json   # 机器需求
├─ 20_REPORT_DIGEST_MEMORY.md    # 主题摘要
├─ 21_REPORT_DIGEST_UX.md
├─ 22_CLAIM_LEDGER.jsonl
├─ 23_SOURCE_REGISTRY.csv
├─ CODEBASE_R41.zip              # 完整代码资产
└─ REPORT_ARCHIVE_R01.zip        # 全量原报告归档
```

## 2. 能不能把很多报告压成一个 ZIP？

### 可以：作为归档和一次性深读资产

优点：

- 保留目录结构；
- 减少 Project Source 槽位；
- 便于版本化、下载和本地替换；
- 新 Project Chat 代码环境可按实测取得 raw ZIP，再解压分析。

### 不可以：作为唯一长期语义源

本次 ZIP 内 10 项 canary 两个 Chat 均 `0/10`。所以只上传一个 `152_REPORTS.zip`，然后在新聊天直接问某份报告内容，不是合格设计。

## 3. 大量报告推荐四层

### 层 A：总 Router

一页说明：

- 这批报告解决什么；
- 每个主题入口；
- 哪个版本 current；
- 权力边界；
- 冲突时看什么。

### 层 B：主题 Digest

按任务主题分 5～15 个 MD，而不是一份无限长总稿：

- 作者工作流
- 记忆/真值/时间
- 抽取与证据
- UX 与 Agent 工具
- 合规与平台规则
- 商业和市场
- 知识治理

每页只保留：高影响结论、限制、claim ID 和原报告指针。

### 层 C：机器账

- claim ledger JSONL
- source registry CSV
- conflict / supersession map
- manifest / SHA

### 层 D：原件归档 ZIP

只在需要全文复核、重新编译或审查来源时解压。

## 4. 一份超长 MD 是否可以？

本次 631,764-byte MD 中部、近尾和尾部均能召回，说明长文本 Source 可工作。但工程上仍 SHOULD 按主题拆分，因为：

- 版本更新半径更小；
- 检索歧义更少；
- 不容易触及 2M-token 单文件限制；
- 任务只读相关主题，减少上下文污染。

## 5. 文件命名

所有平铺文件 MUST 带身份与版本前缀，避免重名：

```text
PRODUCT_R13__00_READ_ME_FIRST.md
REPORT_R01__BG__04_MEMORY_TRUTH_TIME_AND_RULES.md
ATOMIC_R02__02_ATOMIC_EXPECTATIONS.json
```

这与现有 `00_CHATGPT_MASTER_ROUTER` 的运输方式一致。

## 6. Source 内容不要混身份

同一个 Source 不应同时冒充：

- 产品拍板；
- 当前代码能力；
- 外部研究；
- 施工任务；
- 运行结果。

Router 必须声明身份。背景文件不能证明产品已经实现；结果票不能替代产品拍板。

## 7. ZIP Source 解压协议

ChatGPT 接到 ZIP Source 后必须：

1. 在当前沙箱按文件名和预期 SHA 找到 raw ZIP；
2. 不假设固定路径；
3. 运行安全检查；
4. 解压到新的 staging 目录；
5. 输出 member / bytes / SHA / rejected paths 回执；
6. 验证后再进入工作目录；
7. 不把 ZIP 内 `.env` 自动加载为环境变量。

工具：`15_TOOLS/safe_extract_zip.py`。
