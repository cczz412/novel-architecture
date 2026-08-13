# 微调域入口

这个目录只做微调工作的控制面，不保存小说正文、私有金标、模型权重、训练日志或原始答卷。

日常找路只走两步：

1. `CURRENT.json`：当前要看的实验是谁；
2. `experiments/<experiment_id>/MANIFEST.json`：这轮实验实际用了什么、产出了什么、原件在哪。

`CURRENT.json` 只是一根指针，不保存训练进度、实验结论或全仓任务状态。全仓正在做什么仍看 `governance/CURRENT_STATE.json`；两者不是竞争真源。

## 权威关系

```text
真实文件字节
    ↓ 机械读取
单次实验 MANIFEST.json
    ↓ 派生
实验摘要 / 训练说明 / 评测说明

MANIFEST + 某次外审选材规则
    ↓
PACKAGE_MANIFEST / Prompt / Scope / Receipt

CZ / 正式流程
    ↓
DECISION.md
```

`MANIFEST.json` 只是单次实验机器事实的总账，不替代全仓治理、Notion 拍板、资产目录或真实文件本身。

## 三个仓位

- `MAIN_REPO`：索引、规则、可复用工具和少量关键证据；
- `LAB`：正在训练、考试或诊断的重资产；
- `ARCHIVE`：已经冷下来的历史重资产。

正式文件只登记逻辑仓位。本机 `/Users/...` 路径写在 `.local/finetuning/stores.local.json`，不进 Git。

## 硬规则

- 封版 MANIFEST 不原地覆盖；真实文件变化必须新建实验 revision。
- 缺文件、SHA 不符、JSONL 解析失败或关键分母对不上，一律硬停。
- 同一份实物连续构建两次，稳定 MANIFEST 必须逐字节一致；时间戳只进运行回执。
- `SUMMARY.md` 是机器事实的人话视图；`DECISION.md` 才允许写人工判断，并绑定所依据的 MANIFEST SHA。
- 外审包的 source 数量属于某次打包，不进入实验 MANIFEST。
- 当前训练集、考卷、正文和私有金标只登记身份、SHA 与统计，不抄进本目录。
- 复制到外置仓不等于允许删除；删除仍须另行取得授权。

R01 只给现有事实加机械索引，不移动、不删除、不改旧路由、不写 Notion，也不重解释历史。

## 后续实验怎么接入

新实验走三个分开的动作：

```bash
python3 tools/finetuning_control.py register --spec /path/to/SPEC.json
python3 tools/finetuning_control.py build --experiment-id EXPERIMENT_ID
python3 tools/finetuning_control.py switch-current --experiment-id EXPERIMENT_ID
```

- `register`：只登记实验，不生成 MANIFEST，也不切换当前；
- `build`：从真实文件构建并封版 MANIFEST，仍不切换当前；
- `switch-current`：重新核验 Schema、全部工件 SHA 和 SPEC 规定的验收票，全部通过后才切换。

新实验使用 `finetuning-experiment-spec-v2`。所有行数、事实数和运行参数通过 `measurements` 从实物读取，通过 `assertions` 对账；源码不写死某一轮 R04 的目录和分母。

可复制的起步模板：`finetuning/templates/experiment-spec-v2.example.json`。模板只演示合同，不代表已经注册的实验。

## 旧 T5 R04 路牌怎么认

- `references/t5-r04/route_catalog.json`：只保存历史材料的导航身份，不定义当前实验；
- `references/t5-r04/route_registry.json`：由历史目录、CURRENT 和当前 MANIFEST 生成的兼容视图；
- `references/t5-r04/README.md`：同样是可删除重建的派生说明。

重建命令：

```bash
python3 tools/finetuning_control.py routes build
```

不要再人工修“C 未生成”“哪个 A 最新”一类旧摘要。当前实验变化后，重新生成派生视图即可。

来源：Codex
