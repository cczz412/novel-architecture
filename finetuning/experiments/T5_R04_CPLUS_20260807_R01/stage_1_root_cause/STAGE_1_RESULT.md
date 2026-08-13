# T5 R04 C+｜阶段 1 三个根因证伪结果

✅ 三个实验都只改了一个变量，原始一次生成全部保留；没有训练、API、500 本抽数或历史成绩覆盖。

## 1A｜只换 checkpoint

- A：STAGE2_FORMAT_POLLUTION_SUPPORTED
  - JSON 有效：stage1 4/41；final 14/41
  - 恢复后归一 F1：stage1 0.0000；final 0.0000
  - 格式病理：stage1 0 案；final 16 案
- C：MIXED_STAGE_EFFECT
  - JSON 有效：stage1 37/41；final 35/41
  - 恢复后归一 F1：stage1 0.0000；final 0.0000
  - 格式病理：stage1 0 案；final 0 案

## 1B｜A 的 22 个触顶案只把上限改成 4096

- 判定：`OUTPUT_LIMIT_IS_TERMINATOR_SUPPORTED`
- 4096 内闭合：0/22
- 仍复读或再次触顶：22/22
- 首次复读发生在 2048 前：22/22
- 2048 后完整对象：669，其中重复 669（100.00%）
- 恢复后归一召回：2048=0.0000；4096=0.0000

## 1C｜只把 C 题面标题范围改成自然语言

- 判定：`NO_MATERIAL_HEADER_EFFECT`
- 标题范围复制率：64.58% → 60.00%
- 严格指针合法率：2.07% → 1.13%

这轮只负责把旧 A/C 的失败原因分清，不拿当前 41 题决定新 A/C-2 胜负。

来源：Codex
