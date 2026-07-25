# 试验专区

新专项试验统一写到 `experiments/<experiment_id>/`。历史 `runs/`、`reports/` 和候选原件不搬、不回写。

## 两种目录不要混认

- **合同登记试验**：根上有 `experiment.json`，符合 `experiment.schema.json`，进入生成版 `experiments/INDEX.md` 的“已按合同登记”区。
- **本地候选程序／证据包**：可能只有本目录 README、合同、程序和票据。没有 `experiment.json` 时，不进入生成版索引，也不冒充已登记路线；合同、schema、清单和小型审计样例可进 Git，能还原正文的 `catalogs/`、`requests/` 和超大候选池照 `.gitignore` 只留本机。

所以，`experiments/INDEX.md` 只列**按合同登记**的试验。要看本机还有哪些未登记目录，可运行：

```bash
find experiments -mindepth 1 -maxdepth 1 -type d ! -name '_*' -print
```

这条命令只说明目录存在，不代表垃圾、可删除、可续跑或质量失败。

## 新登记试验的标准结构

新试验推荐使用：

```text
experiments/<experiment_id>/
  experiment.json   # 身份、替换模块、基线、状态与红线
  inputs/            # 只放正式工件的内容地址引用
  candidate/         # 候选模块输出
  scorecard/         # 对照成绩
  receipt.md         # 停点回执
```

历史目录不为追新格式而批量回写。要继续历史实验时，另开新运行编号并按当轮施工令补齐身份。

## 四条机械规则

- 上游正式工件只读，候选不得覆盖原件。
- 一次只声明替换哪个模块版本。
- 候选输出先过合同闸，后段才可启动。
- 试验结果只进候选索引；转正只改获批指针，不移动历史原件。

`experiment.schema.json` 是目录身份合同；`_template/experiment.json` 是空白样板，不代表正式试验。

需要横向换供应商或模型时，统一从 [模型横向试验通道](model_benchmarks/README.md) 进入；历史与当前成绩看 [模型试验索引](model_benchmarks/INDEX.md)。

当前能不能继续某条路线，只认 [治理索引](../governance/INDEX.md)、路线登记册和当轮施工令；不要按目录名或修改时间猜。

来源：Codex
