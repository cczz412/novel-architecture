# 能力矩阵

## 读法

- “官方”只写平台公开承诺。
- “实测”只写这批探针观察。
- “工程处理”才是本地 Codex 应执行的规则。

| 能力 | 官方边界 | 本账号实测 | 证据级别 | 工程处理 |
|---|---|---|---|---|
| Project 持续上下文 | Project 记住项目 chats/files；Project-only 隔离项目外记忆 | 普通聊天 canary 曾进入非隔离 Project；Project-only 精确 12 项未取回 | OFFICIAL + EMPIRICAL | 长期工程默认 Project-only；仍把精确状态写文件 |
| 同 Chat 文件连续性 | Data Analysis 是 stateful 环境 | A35 第二次独立工具调用 SHA 一致 | EMPIRICAL_REPEATED | 同阶段复用同 Chat |
| 跨 Chat 文件连续性 | 官方未承诺共享沙箱 | A→B seed 不见；B→C 扫描不见 | EMPIRICAL_REPEATED | 一律当不存在；新 Chat 从 Source/Bootstrap 重建 |
| 平铺 MD Project Source | Project 文件可作上下文 | B′ `10/10`；C′ `10/10`，含 631,764-byte 文件尾部 | EMPIRICAL_REPEATED | Router/Current/主题摘要用 MD/JSON 平铺 |
| ZIP Project Source 语义 | 官方未承诺展开 ZIP | B′ `0/10`；C′ `0/10` | EMPIRICAL_REPEATED | ZIP 只当资产，禁止当唯一知识源 |
| Project Source 原始文件挂载 | 官方只承诺项目文件可用，未承诺路径 | MD/ZIP 在 B′、C′、D1、D2 新沙箱均按 SHA 出现 | EMPIRICAL_REPEATED | 代码可找原文件，但按 name+SHA 发现，不硬编码 `/mnt/data` |
| 同 Chat 模型切换 | 官方允许模型演进/切换，但未承诺沙箱身份 | Pro→Extra High：marker/blob/SQLite/Git/hostname/Source SHA 全保留 | EMPIRICAL_SINGLE_STRONG | 允许同 Chat 切模型；切前 checkpoint |
| 不同模型新 Chat 规格 | 官方无固定硬件 SLA | Pro 与 Fresh Extra High 均 5 visible / 4 CPU quota / 4 GiB | EMPIRICAL_REPEATED | 不按模型档位假设更大机器 |
| 公网/API | 官方明确 Python 环境不能发外部 Web/API 请求 | A/B/C/D2 固定域名 DNS 失败 | OFFICIAL + EMPIRICAL_REPEATED | 默认离线；禁止真实 API key |
| pip/npm 在线安装 | 官方不保证外网 | pip DNS 失败；npm 超时 | EMPIRICAL | 携带 wheelhouse / local tarballs |
| ZIP/JSON/SQLite/Git | 官方允许数据分析和文件处理 | ZIP 往返、SQLite、local Git、localhost、1500 files 通过 | EMPIRICAL | 适合作为离线工程沙箱 |
| Library | 官方支持人工浏览、搜索、Add from Library；Pro 页面列 100 GB | B/C 自动寻找前轮 result ZIP 均失败 | OFFICIAL + EMPIRICAL | Library 只作人工便利层；结果当场下载 |
| Project 文件保留 | 项目文件保留到项目删除；删除后按政策移除 | 未做长期时间探针 | OFFICIAL | 不等于本地备份；本地仍保留正式包 |

## 实测环境快照

```text
Debian 13 / Linux x86_64
Python 3.13.5
Node 22.16.0
Git 2.47.3
CPU visible: 5
CPU affinity count: 5
cgroup cpu.max: 400000 100000  ≈ 4 CPU
cgroup memory.max: 4294967296 bytes = 4.00 GiB
root filesystem observed: 63 GiB, about 38 GiB free
/dev/shm observed: about 989 MiB
```

禁止把这张快照写成 OpenAI 固定规格。运行前必须重新探测关键字段。

## 项目内聊天记忆的正确定位

这批测试同时出现：

- 普通聊天随机 canary 被后续非隔离 Project 精确召回；
- 同 Project 上一聊天的 12 项精确随机块在后续聊天为 `0/12`；
- 后一测试存在缺少 BPRIME_RUN_ID 的协议瑕疵。

因此最稳结论不是“Project memory 完全无效”，而是：

> Project memory 可以帮助延续项目大意，但不得承担机器状态、current、RUN_ID、SHA、owner、状态枚举或完整 JSON 的职责。

来源：`13_EVIDENCE/PROBE_EVIDENCE.md`。
