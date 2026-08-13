✅ 结论：你们现在的“`F1 至少 +0.02 且 Recall 不退`”可以保留，但应改名为“DEV24 晋级门”，不能单独当成“方案已经被证明更好”的替换门。

最合适的组合是：

* 用整道 case 做成对置换检验，判断差异是否可能只是题目波动；
* 用整道 case 做成对 bootstrap，报告差值区间和稳定性；
* 再看逐题变化、单题影响和错误家族；
* 已反复用于挑 Prompt 的这 24 题只能继续当 DEV，最终冠军需要一次未见确认。

## 1. 该用哪种统计方法

| 方法                 | 在你们这里的用法                                       | 判词                           |
| ------------------ | ---------------------------------------------- | ---------------------------- |
| 成对置换／randomization | 每次按整道题交换两个方案的完整 `(TP, FP, FN)`，重算全局 micro-F1 差 | ✅ 主显著性检验                     |
| 成对 case bootstrap  | 有放回抽取 24 道题，两个方案使用同一批索引，重算 micro-F1 差          | ✅ 报置信区间和重采样胜率                |
| 逐题 F1 再取平均         | 检验的是 macro case-F1，不是你们的 micro-F1              | ❌ 不能替代主检验                    |
| McNemar            | 只适合每题“通过／失败”这样的二元结果                            | ⚠️ 可分析格式通过、触顶等，不能检验 micro-F1 |
| sign test／Wilcoxon | 看逐题胜负是否一致                                      | ⚠️ 只作辅助稳定性检查                 |
| paired t-test      | 需要较强分布假设，F1 又是非线性统计量                           | ❌ 24 题不推荐                    |

micro-F1 不是逐题 F1 的平均数，所以每次重采样或交换后都必须重新汇总 TP、FP、FN，再重算整个指标。NAACL 2022 已给出专门处理 F1 这类结构化统计量的精确成对置换方法和公开代码。[[Zmigrod 等，2022](https://aclanthology.org/2022.naacl-main.360/)](https://aclanthology.org/2022.naacl-main.360/)

“paired bootstrap”和“per-case bootstrap”并不是两种竞争方案：只要按 case 抽样，并保持两个 Prompt 的配对关系，它们就是同一种做法。

⚠️ 如果多道题来自同一章节、同一责任段或同一本小说，独立单位还要上移到来源组：同组题必须一起交换、一起重采样。不能把约 280 条 Gold 当成 280 个独立样本。NLP 数据里的同文档依赖会破坏普通独立性假设，[[Dror 等](https://aclanthology.org/P18-1128/)](https://aclanthology.org/P18-1128/)也专门提醒过这个问题。

## 2. `+0.02 F1` 到底有多大

在一对一事实匹配下：

[
F1=\frac{2TP}{Gold数+预测数}
]

如果两个方案预测条数相同，`Gold=280` 时：

| 预测数 | `+0.02 F1` 约等于 |
| --: | -------------: |
| 200 |     净增约 5 个 TP |
| 250 |   净增约 5～6 个 TP |
| 300 |     净增约 6 个 TP |

说白了就是：`+0.02` 可能只由五六条事实决定，并不天然算“大提升”。

更关键的是它们落在哪：

* 6 条改善分布在 6 道独立题上，证据可以很强；
* 6 条全来自一道高密度题，成对置换的单侧 p 值最低也只能到 `0.5`；
* 一批题改善、另一批题退步，只是总计净增 6 条，也可能完全不稳定。

如果只有 (k) 道题真正改变了充分统计量，即使它们全朝同一方向，单侧精确置换检验的最小 p 值也只能达到 (2^{-k})：

* 4 道有效差异：最低 `0.0625`，不可能过 `0.05`；
* 5 道：最低 `0.03125`；
* 双侧检验通常至少需要 6 道有效差异。

所以回答第 2 题很明确：**`+0.02` 足以当产品效果门，但通常不足以单独说明提升。**分布、方案相关性和独立 case 数都比 280 条 Gold 的总数更关键。研究也表明，不存在跨任务通用的“F1 涨多少就自然显著”的阈值。[[Berg-Kirkpatrick 等，2012](https://aclanthology.org/D12-1091.pdf)](https://aclanthology.org/D12-1091.pdf)

## 3. 每次比较应该交付什么

建议固定成一张成绩票：

* 基线和候选各自的 `TP / FP / FN / Precision / Recall / F1`；
* `ΔPrecision / ΔRecall / ΔF1`；
* `ΔF1`、`ΔRecall` 的 95% 成对 case-bootstrap 区间；
* 成对置换检验 p 值；
* bootstrap 中：

  * `ΔF1 > 0` 的比例；
  * `ΔF1 ≥ 0.02` 的比例；
  * `ΔRecall ≥ 0` 的比例；
* 逐题 `ΔTP / ΔFP / ΔFN`；
* 逐题 F1 的胜／平／负，只作诊断；
* leave-one-case-out：每次去掉一道题后的 `ΔF1` 范围；
* 最大单题影响；
* 错误家族的 `修复 / 新增 / 未变`；
* 格式、非法证据、重复、触顶等硬门。

这里的 bootstrap“胜率”只能理解为“换一批 case 权重后仍然领先的比例”，不是“候选真的更好的概率”。

置信区间要算“两个系统差值的区间”，不要分别算两个系统的区间，再靠是否重叠判断。CI 能同时显示效果大小和不确定性，[[Bestgen 2022](https://aclanthology.org/2022.lrec-1.640/)](https://aclanthology.org/2022.lrec-1.640/)专门建议这样报告。

24 个独立单位很少，bootstrap 区间也可能不稳。建议同时算 BCa 和 percentile；如果两者对“是否跨 0”给出不同结论，直接记为不确定。小样本 bootstrap 可能低估波动，[[Søgaard 等](https://aclanthology.org/W14-1601.pdf)](https://aclanthology.org/W14-1601.pdf)给过明确警告。因此主 p 值更适合用精确置换，bootstrap 主要负责区间和稳定性。

错误家族建议按 case 报：

| 错误家族      | 基线出错题 | 候选出错题 | 修复 | 新增 |
| --------- | ----: | ----: | -: | -: |
| 状态边界      |       |       |    |    |
| 误信／客观事实混淆 |       |       |    |    |
| 指代链       |       |       |    |    |
| 过抽        |       |       |    |    |
| 漏抽        |       |       |    |    |
| 证据非法      |       |       |    |    |

如果对这些家族也分别做显著性声明，同样会产生多重比较；普通 Demo 中把它们当错误分析即可。

## 4. 连续挑赢家一定会产生偏差

会产生三层问题：

* 多重比较：看得越多，撞到一个虚高结果的机会越大；
* winner’s curse：被选中的最高分通常把真实提升估高了；
* 自适应过拟合：看过这 24 题的错误后再改 Prompt，评测集已经参与设计。

举个量级：三个家族各看三个候选，虽然没有跑完整的 `3×3×3`，仍然看了九次结果。假设九次完全独立且都没有真实提升，至少撞到一次 `p≤0.05` 的概率约为 37%。实际 Prompt 结果有相关性，所以 37% 不是精确值，但“只公布每家族赢家”不会消除问题。

[[Cawley 与 Talbot](https://jmlr.org/papers/v11/cawley10a.html)](https://jmlr.org/papers/v11/cawley10a.html)表明，选模指标上的过拟合可能和算法之间的真实差距一样大；反复使用 holdout 设计新方案也会逐渐过拟合这份 holdout。[[Dwork 等，2015](https://papers.nips.cc/paper_files/paper/2015/hash/bad5f33780c42f2588878a9d07405083-Abstract.html)](https://papers.nips.cc/paper_files/paper/2015/hash/bad5f33780c42f2588878a9d07405083-Abstract.html)

最小修正分两种：

* 如果所有候选在看结果前已全部冻结：对全部成对置换 p 值做 Holm 校正。公开代码见 [[statsmodels](https://www.statsmodels.org/devel/generated/statsmodels.stats.multitest.multipletests.html)](https://www.statsmodels.org/devel/generated/statsmodels.stats.multitest.multipletests.html)。
* 如果候选是看过错误后继续设计的：Holm 也救不回来。DEV24 只能筛选，最终锁定一个方案后，在未见确认题上只比较一次。

按你附的项目材料，现有 24 题已经参与过多轮方案、checkpoint 或格式选择，所以它们现在只能叫 `DEV24`，不能重新包装成 blind。

## 5. 24 题何时够用

| 用途                        | 24 题是否够            |
| ------------------------- | ------------------ |
| 淘汰格式崩溃、复读、触顶方案            | ✅ 够                |
| 淘汰 F1／Recall 大幅下降且多题同向的方案 | ✅ 够                |
| 发现某条规则造成系统性过抽或漏抽          | ✅ 通常够              |
| `0.894 → 0.622` 这类大跌      | ✅ 不必因样本小而装作看不见     |
| 区分 `+0.01～0.02` 的近邻方案     | ⚠️ 通常不够            |
| 提升主要来自 1～2 道高密度题          | ❌ 不够               |
| 从多个反复调过的 Prompt 中签“冠军”    | ❌ 不够               |
| 宣称真实提升至少有 0.02            | ❌ 除非 CI 下界也高于 0.02 |

小样本实验不只是难以检出真实差异；一旦碰巧检出，提升幅度也更容易被夸大。[[Card 等，2020](https://aclanthology.org/2020.emnlp-main.745/)](https://aclanthology.org/2020.emnlp-main.745/)

## 6. 建议直接采用的低成本规则

### DEV24：只负责晋级

保留你们当前门槛，再补两项：

```text
全部硬门通过
观察到 Δmicro-F1 ≥ 0.02
观察到 ΔRecall ≥ 0
去掉任意一道题后，ΔF1 仍大于 0
提升不是由单一道高密度题决定
```

建议限制：

* 固定原始基线 `B0`，每轮都同时报告；
* 最多 3 个家族，每家族最多 2 个候选；
* 一个家族没有方案过门就关闭，不继续在同一 DEV24 上追小改版；
* 达到总候选预算后停止；
* 结果接近时保留更短、更便宜、更容易维护的 Prompt，不强选分数冠军。

### CONFIRM：只跑最终一对

冻结 Prompt、基线、解码、Gold、裁决规则、评分代码后，在未见题上只跑：

* 原始基线；
* 最终候选。

如果确认集也是 24 题，增量是 48 份输出。可以先跑预先平衡好的 12 题：

* 只允许因硬门失败或明显无效而提前淘汰；
* 不允许在前 12 题宣布成功；
* 未淘汰再补后 12 题。

终局门建议写成：

```text
全部硬门通过
观察 Δmicro-F1 ≥ 0.02
单侧成对置换 p ≤ 0.05
95% paired CI 下界 > 0
Recall 非劣下界 > -εR
关键错误家族没有禁止性退化
```

如果“Recall 不退”是字面要求，`εR=0`；如果产品允许最多退 0.01，就必须事前写成 `εR=0.01`，不能看结果后再放宽。

确认没过门就记“不确定，保留基线”，不要打开逐题错误后修改 Prompt，再继续用同一确认集。只要看了逐题详情，这批确认题就退役成 DEV。

没有未见确认集时，可以上线内部 Demo，但名称应是：

> `DEV24 provisional winner`

不能写“统计确认冠军”。

## 7. 可直接运行的 Python 骨架

输入每道题的 `(TP, FP, FN)`。如果存在同章或同书相关题，应先聚合成来源组，每行代表一个真正独立的 block。

```python
import numpy as np
from statsmodels.stats.multitest import multipletests

# shape = (独立block数, 3)，列为 TP, FP, FN
base = np.asarray(base_counts, dtype=int)
cand = np.asarray(candidate_counts, dtype=int)

def prf(rows):
    tp, fp, fn = rows.sum(axis=0)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
    return np.array([p, r, f])

obs = prf(cand) - prf(base)
n = len(base)
rng = np.random.default_rng(20260811)

# 成对 case bootstrap：差值区间和重采样胜率
B = 100_000
boot = np.empty((B, 3))

for b in range(B):
    idx = rng.integers(0, n, size=n)
    boot[b] = prf(cand[idx]) - prf(base[idx])

ci95 = np.quantile(boot, [0.025, 0.975], axis=0)

print("Observed ΔP, ΔR, ΔF1:", obs)
print("95% percentile CI:", ci95)
print("bootstrap ΔF1 > 0:", np.mean(boot[:, 2] > 0))
print("bootstrap ΔF1 >= .02:", np.mean(boot[:, 2] >= 0.02))
print("bootstrap ΔRecall >= 0:", np.mean(boot[:, 1] >= 0))

# 成对近似随机化：候选是否优于基线
extreme = 0

for _ in range(B):
    swap = rng.random(n) < 0.5
    perm_base = np.where(swap[:, None], cand, base)
    perm_cand = np.where(swap[:, None], base, cand)
    delta = prf(perm_cand)[2] - prf(perm_base)[2]
    extreme += delta >= obs[2] - 1e-15

p_one_sided = (extreme + 1) / (B + 1)
print("one-sided paired-randomization p:", p_one_sided)

# leave-one-case-out 稳定性
loo = np.array([
    (prf(np.delete(cand, i, axis=0))
     - prf(np.delete(base, i, axis=0)))[2]
    for i in range(n)
])

print("LOO ΔF1 range:", loo.min(), loo.max())

# 多个事前冻结候选的 p 值校正
reject, p_holm, _, _ = multipletests(
    raw_candidate_pvalues,
    alpha=0.05,
    method="holm",
)
```

公开工具：

* [[F1 精确成对置换代码](https://github.com/rycolab/paired-perm-test)](https://github.com/rycolab/paired-perm-test)
* [[SciPy paired permutation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html)](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html)
* [[SciPy paired bootstrap／BCa](https://scipy.github.io/devdocs/reference/generated/scipy.stats.bootstrap.html)](https://scipy.github.io/devdocs/reference/generated/scipy.stats.bootstrap.html)

一句话落账：

> **现有 `+0.02 且 Recall 不退` 保留为 DEV 晋级门；统计主检验改为整道 case／来源组的成对置换，bootstrap 负责差值区间；DEV24 可以淘汰明显差方案，但不能给连续挑出来的冠军签终局票。**

来源：ChatGPT
