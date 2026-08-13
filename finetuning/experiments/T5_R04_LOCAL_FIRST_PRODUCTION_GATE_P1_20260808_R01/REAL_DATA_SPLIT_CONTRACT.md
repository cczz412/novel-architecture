# 真实数据 Split 合同

## 先分组，再选窗口

split 的最小单位是作者组，不是单行或单章。同一作者的全部作品默认只能去同一侧。

硬规则：

- TRAIN／DEV／最终 blind 的作者集合交集必须为 0；
- 作品集合交集必须为 0；
- 同作品相邻章节不得跨 split；
- 同一来源族的改写、重切、A/C2 视图不得跨 split；
- 相同正文 SHA 和近重复文本不得跨 split；
- DEV 一旦用于选格式、seed、checkpoint 或数据量，就登记为 DEV，不再称 holdout。

## 当前五本冻结清单

- 《领袖》；
- 《重生78，从知青返城开始》；
- 《末日来袭，我能无限升级庇护所》；
- 《有道行》；
- 《颠婆勇者太多了》。

五本都不进入新 TRAIN。Codex 不替 CZ 选其中哪两本做未来 DEV，也不提前切片、建 gold 或消费 blind。

历史特殊 84 中已经存在上述书的 4 行。新 P1 split 必须机械排除它们；历史卷和历史训练结果保持原样。

## 推荐分法

在作者身份补齐后，先锁：

```text
train_authors
dev_authors
blind_candidate_authors
```

比例只作容量参考，作者隔离优先于精确命中 80/10/10。任何作者合并、笔名关系不确定时写 `unknown`，不能凭书名猜。

## 机器验收

- 作者／作品／正文 SHA／近重复四种泄漏为 0；
- 每个 case 都能追到 source、chapter、book、author、rights；
- 每个 split 的行数、事实数、八态、题材、普通／困难层单独统计；
- A/C2 的 split 和 pair_id 顺序完全相同；
- split lock 一旦用于训练，不原地覆盖。

来源：Codex
