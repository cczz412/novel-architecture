# READ1 TRAIN72 V2 单格资格跑｜准备说明

这个包只把未来一次本地 Demo 的数据、参数、顺序和停点写死。当前没有 CZ 精确执行票，所以不能训练，也不能加载 Base 或 LoRA 做推理。

## 这次将来只跑什么

- 教材固定为 READ1 TRAIN72：72题、830条事实、7个自然空答案。
- 训练只跑36 iterations，也就是72行完整看一遍、9次参数更新。
- 只保留最终 LoRA；不留24/48/72/96多检查点，不调学习率，不重试。
- L6和REAL24只把 system 换成TRAIN72的V2合同；user、题序、负责区和Gold不动。
- Base和LoRA先各答L6六题。L6有一项不过，REAL24就不能运行。
- L6通过后，Base和LoRA才各答REAL24二十四题；新增同义事实必须盲审到待审数为0。

这不是单变量实验。教材组成、行序、格式合同和训练剂量一起更新，所以即便通过，也只能叫“整包候选配方取得资格”，不能解释成某一个改动单独带来了提升。通过之后，才有资格另开READ1/2/4只改正文范围的对照。

## 授权怎么认

CZ已经允许：本地4B事实抽取对照在数据、参数、硬停门和runner/scorer SHA冻结后，可由控制窗直接放行，不必逐次再问CZ。但这不等于当前已经开跑。

本次训练和两个推理命令仍必须收到控制窗验收后下发的精确JSON票。票要逐字绑定本包规格、TRAIN72、两套V2请求、runner、scorer、唯一run目录和CZ决策身份。票不存在、`approved`不是布尔值`true`，或任一SHA不符，runner都会在模型加载前停下。施工者不得在这个准备包里创建批准票。

这份长期口径不包含商用API费用、Mini/Lite云训练、Notion、Git、CURRENT或生产晋级。

## 将来获票后的固定命令顺序

下面只是操作说明，本轮没有执行：

```bash
/opt/homebrew/opt/python@3.12/bin/python3.12 run_read1_train72_v2.py train --ticket /控制窗下发的精确票.json
/opt/homebrew/opt/python@3.12/bin/python3.12 run_read1_train72_v2.py infer-l6 --ticket /同一张精确票.json
uv run --locked python score_read1_train72_v2.py l6-pre
uv run --locked python score_read1_train72_v2.py l6-final --adjudications /L6盲审裁决.jsonl
```

只有 `L6_GATE.json` 明确为通过，才能继续：

```bash
/opt/homebrew/opt/python@3.12/bin/python3.12 run_read1_train72_v2.py infer-real24 --ticket /同一张精确票.json
uv run --locked python score_read1_train72_v2.py real24-pre
uv run --locked python score_read1_train72_v2.py real24-final --adjudications /REAL24增量盲审裁决.jsonl
```

评分里事实语义是主分；JSON、完整Schema、status、speaker、evidence、复读、触顶和重复事实分别报告。REAL24只有在LoRA事实F1严格高于同合同Base、Recall不退、status命中正确率过半且格式与稳定性全过时，才取得资格。旧0.428只作历史参照。

## 当前停点

本包只完成静态身份、参数和代码准备。没有创建 `runs/T5_R04_READ1_TRAIN72_V2_QUALIFICATION_R01/`，没有config、adapter或raw，也没有模型/API/训练动作。

来源：Codex
