# novel-mvp · 产品试跑示例（不是现行产品）

🔥 这是测试阶段的示例代码和设计稿，**不是**已经上线的产品，也**不是**共同背景板。

- 产品怎么想：回本仓 [共同背景板 R13](../references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/00_READ_ME_FIRST.md)
- 这里真正有用的： [design/INDEX.md](design/INDEX.md) 和 [contracts/](contracts/)
- 代码偏旧，很长一段时间没跟着背景板改。能跑通「导入 → 抽事实 → 确认 → 提问」这一圈，但不能当成现行实现。

本夹没有 `AGENTS.md`。Agent 仍读本仓根目录的 [AGENTS.md](../AGENTS.md)。

## 试跑时怎么用

纯 Python 标准库。调模型需要本机 arkcli 已登录。作者书稿在 `data/`，不进 Git。

```bash
python3 cli.py init 我的第一本书
python3 cli.py ingest 我的第一本书 第一章.txt --title "第一章 雪夜"
python3 cli.py extract 我的第一本书
python3 cli.py confirm 我的第一本书
python3 cli.py ask 我的第一本书 陈平
python3 cli.py status 我的第一本书
```

发现问题记 [ISSUES.md](ISSUES.md)。默认只记问题、不改核心代码，除非 CZ 点名。

## 别和这几张「背景」搞混

| 你找的 | 在哪 | 不是什么 |
|---|---|---|
| 共同背景板 | 本仓 `references/shared-context/…R13` | 不是本夹，也不是 `foundation/` |
| P3 背景卡 | `references/novel_fact_extraction_contract_v2.md` | 只是抽事实的五条小抄 |
| `foundation/` | 2026-07-16 快照 | 不是现行共享背景板 |

来源：CZ 2026-08-15 把试跑示例迁进小说架构仓；代码骨架 2026-08-13
