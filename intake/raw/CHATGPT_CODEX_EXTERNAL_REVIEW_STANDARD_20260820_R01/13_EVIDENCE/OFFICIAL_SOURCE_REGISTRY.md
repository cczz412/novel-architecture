# 官方来源登记｜检索日 2026-08-20

## OpenAI

### OAI-PROJECTS

- 标题：Projects in ChatGPT
- URL：https://help.openai.com/en/articles/10169521-projects-in-chatgpt
- 支持：Projects 组合 chats/files/instructions；Project memory；Project-only 边界；Save to project；Connected Apps；删除与保留。

### OAI-RELEASE-NOTES

- 标题：ChatGPT Release Notes
- URL：https://help.openai.com/en/articles/6825453-chatgpt-release-notes
- 支持：现有 Project 可切 Default / Project-only；变更可能需几小时；shared projects 固定 Project-only。

### OAI-DATA-ANALYSIS

- 标题：Data analysis with ChatGPT
- URL：https://help.openai.com/en/articles/8437071-data-analysis-with-chatgpt
- 支持：Python 环境不能发 external web requests / API calls；大而复杂文件可能不能完整分析。

### OAI-FILE-UPLOADS

- 标题：File Uploads FAQ
- URL：https://help.openai.com/articles/8555545-file-uploads-faq
- 支持：512 MB/file；文本/文档 2M tokens/file；Pro Project 40 files。

### OAI-LIBRARY

- 标题：File storage and Library in ChatGPT
- URL：https://help.openai.com/en/articles/20001052-file-storage-and-library-in-chatgpt
- 支持：Library 浏览/搜索/下载/Add from Library；Pro 页面列 100 GB；Temporary Chat 不保存。

### OAI-MEMORY

- 标题：Memory FAQ
- URL：https://help.openai.com/articles/8590148-memory-faq
- 支持：Saved memories 独立于 chat history，系统可更新/合并/删除；不是精确机器状态合同。

### OAI-RETENTION

- 标题：Chat and File Retention Policies in ChatGPT
- URL：https://help.openai.com/en/articles/8983778-chat-and-file-retention-policies-in-chatgpt
- 支持：Project 文件通常保留到 Project 被删除；删除后按政策处理。

## Python / pip / npm

### PIP-DOWNLOAD

- URL：https://pip.pypa.io/en/stable/cli/pip_download/
- 支持：`pip download` 收集分发包，目录可用于 offline / locked-down `pip install --find-links`。

### PIP-WHEEL

- URL：https://pip.pypa.io/en/stable/cli/pip_wheel/
- 支持：预构建 wheel，避免每次安装重复编译；本地 `--no-index --find-links`。

### PYTHON-ZIPFILE

- URL：https://docs.python.org/3/library/zipfile.html
- 支持：处理不可信 ZIP 时要验证路径，防止 path traversal。

### NPM-INSTALL

- URL：https://docs.npmjs.com/cli/install/
- 支持：npm 可从本地 tarball 安装。

### NPM-PACK

- URL：https://docs.npmjs.com/cli/v7/commands/npm-pack/
- 支持：把 package 打成 `.tgz` 供本地运输/安装。

## 当前官方数字冲突提醒

OpenAI Library 页面列 Pro Library 100 GB；File Uploads FAQ 同时描述跨 chats/Projects/GPT knowledge 的其他共享存储 cap。规格不把“账号总可用容量”硬编码，运行时以 `Settings > Storage` 和当前 UI 为准。
