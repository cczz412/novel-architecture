# 项目接入参考

状态：**R07 辅助参考；保存接入方案，不是当前路由或执行合同。**

## 这页保留什么

为了让新窗口和未来自动化找到共同背景板，曾设计三层入口：外层 `README.md`、机器可读 `CURRENT.json`、仓库 `AGENTS.md` 阅读规则。当前只启用 R06 已有的 `AGENTS.md` 最小入口，没有第二个 shared-context CURRENT。

## R07 本次建版结果

- [本地 R07 入口](00_READ_ME_FIRST.md)已经创建并对平账序，Notion 建版、逐页回读与最终 SHA 登记也已完成；
- Notion 总入口已指向 R07，R01～R06 均保持原样；
- 本任务不修改根 [AGENTS.md](../../../AGENTS.md)，不创建 `README.md` 或 `CURRENT.json`，也不改治理 CURRENT；
- 根 `AGENTS.md` 与本地机器指针仍未切换；如需切换，必须另有明确工单，并同时核对所有直接消费者。

## 以后启用稳定指针时

- 在 shared-context 外层建 `README.md` 指向当前版本；
- 建 `CURRENT.json` 登记版本号、入口、核心 SHA 和整包 SHA；
- 每次发新版同步更新两者并在账序留证；
- 发布前跑 06 页机械验收；
- 不得让 `CURRENT.json` 与 `AGENTS.md` 各指一处。

## 本地与 Notion 的关系

- R07 这次依 CZ 明确指令先做本地建版，再创建 Notion 页面；
- 29 个原子已按账序 2026-08-12 21:18 条校准；Notion 上传后已逐页回读并对平本地；
- R07 现为共同产品说明，R06 作为不可变父版保留；
- 技术状态仍以本地正式合同、结果票和运行指针为准，背景板只做解读。

来源：Codex
