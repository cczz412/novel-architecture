# novel-mvp · 产品试跑示例（不是现行产品）

🔥 这是测试阶段的示例代码和设计稿，**不是**已经上线的产品，也**不是**共同背景板。

- 产品怎么想：回本仓 [共同背景板 R13](../references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/00_READ_ME_FIRST.md)
- 这里真正有用的： [design/INDEX.md](design/INDEX.md) 和 [contracts/](contracts/)
- 大部分代码偏旧，不能当成现行产品；其中 T03-A 已把 M1 常用入口收到 C10-first，并完成 M1/M2 本地机械收口，仍不等于 Production Ready。`mvp/planstore.py` 已补出 handover／跨文件恢复护栏，`mvp/reconcile.py` 已接通六态观察与作者 facts 准入，`mvp/factstore.py` 已把旧 M5 确认／改判写入口收进同一事务链；这些仍不等于通用 planstore 或完整主循环。

本夹没有 `AGENTS.md`。Agent 仍读本仓根目录的 [AGENTS.md](../AGENTS.md)。

## 试跑时怎么用

纯 Python 标准库。调模型需要本机 arkcli 已登录。作者书稿在 `data/`，不进 Git。

```bash
uv run --locked python novel-mvp/cli.py init 我的第一本书
uv run --locked python novel-mvp/cli.py ingest 我的第一本书 第一章.txt --material-role chapter
uv run --locked python novel-mvp/cli.py extract 我的第一本书
uv run --locked python novel-mvp/cli.py confirm 我的第一本书
uv run --locked python novel-mvp/cli.py ask 我的第一本书 陈平
uv run --locked python novel-mvp/cli.py status 我的第一本书
```

`ingest` 不填 `--material-role` 时不会猜正文，整份按 Unknown 保存且不生成 C1。整份明确材料可选 `chapter / intro / setting / title / tags / unknown`；同一 source 内混合多种材料时用 `--declarations <JSON>` 提供精确 spans。TXT、MD、DOCX、ZIP 共用这一入口；DOCX 有未覆盖区域，或 ZIP 任一成员失败、没有有效材料时，都会整批强停，不留下半套 C1。`extract`、`refine` 和外部 `candidates` 都要先通过同一套 Pre-M3 准入门。

发现问题记 [ISSUES.md](ISSUES.md)。默认只记问题、不改核心代码，除非 CZ 点名。

## 别和这几张「背景」搞混

| 你找的 | 在哪 | 不是什么 |
|---|---|---|
| 共同背景板 | 本仓 `references/shared-context/…R13` | 不是本夹，也不是 `foundation/` |
| P3 背景卡 | `references/novel_fact_extraction_contract_v2.md` | 只是抽事实的五条小抄 |
| `foundation/` | 2026-07-16 快照 | 不是现行共享背景板 |

来源：CZ 2026-08-15 把试跑示例迁进小说架构仓；代码骨架 2026-08-13
