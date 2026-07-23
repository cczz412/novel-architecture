# 试验专区

从第76道第一期起，新专项试验统一写到 `experiments/<experiment_id>/`。历史 `runs/`、`reports/` 和候选原件不搬、不回写。

每个试验目录固定包含：

```text
experiments/<experiment_id>/
  experiment.json   # 身份、替换模块、基线、状态与红线
  inputs/            # 只放正式工件的内容地址引用
  candidate/         # 候选模块输出
  scorecard/         # 对照成绩
  receipt.md         # 停点回执
```

四条机械规则：

- 上游正式工件只读，候选不得覆盖原件。
- 一次只声明替换哪个模块版本。
- 候选输出先过合同闸，后段才可启动。
- 试验结果只进候选索引；转正只改获批指针，不移动历史原件。

`experiment.schema.json` 是目录身份合同；`_template/experiment.json` 是空白样板，不代表正式试验。

需要横向换供应商或模型时，统一从 [模型横向试验通道](model_benchmarks/README.md) 进入；历史与当前成绩看 [模型试验索引](model_benchmarks/INDEX.md)。

来源：Codex
