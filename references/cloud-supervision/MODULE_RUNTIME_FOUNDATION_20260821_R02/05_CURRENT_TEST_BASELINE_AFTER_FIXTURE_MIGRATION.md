# 当前模块测试基线｜测试材料已随仓库走

日期：2026-08-21

## 现在能确认什么

在分支 `codex/module-runtime-foundation-20260819-r01` 上，两份过去依赖本机 `TEMP` 的正式测试已经改读仓内安全合成材料。全套小说辅助产品模块测试可以在这份工作树里完整收集并运行：

```text
1574 passed in 48.62s
```

同一工作树里，Ruff 对 `novel-mvp/mvp` 和全部 `tests/test_novel_mvp_*.py` 检查通过。

## 修掉的是哪类问题

- `tests/test_novel_mvp_m3_admission.py` 不再读取本机临时锁和绝对路径。
- `tests/test_novel_mvp_chapterization.py` 不再读取本机真实材料或临时目录。
- 17 份测试文本与两份相对路径清单现在放在 `tests/fixtures/novel_mvp/intake_regressions/`，云端克隆仓库后也能读取。
- 原来安全的 14 份短合成文本保持字节一致；3 份可能含真实正文的材料换成原创合成替身，没有进入 Git。

## 这份结果不能证明什么

- 1574 项都是当前代码的机械和合成回归，不等于真实小说内容质量已经通过。
- 它不能证明外部模型的抽取、规划、体检或梗概语义正确。
- 它不表示 142 条原子需求的 852 个六例测试已经齐全；新增 15 条对应的 90 个设计仍待 Pro 回包和本地吸收。
- 它不产生 API、Gold、训练、真实小说读取、上传或生产权限。

## 复跑命令

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --locked pytest -q -p no:cacheprovider tests/test_novel_mvp_*.py
uv run --locked ruff check novel-mvp/mvp tests/test_novel_mvp_*.py
```

来源：Codex
