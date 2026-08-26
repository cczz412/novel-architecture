# 12 SenseNova 6.8 Flash Lite 与 Ling-3.0-flash 非思考观察

这一轮按你点的两家来打：商汤日日新的 6.8 Flash，蚂蚁百灵的 Ling 3.0 Flash。同一冻结 Prompt、同一四题、温度 0、思考关、JSON Object、每题一次、重试 0。没有重跑 Doubao、官方 Flash、Agent Plan 第二批。

不写准确率、总分、排名、整体可用、Gold、CCZ-57／CCZ-84 已完成。

回执：[11_sensenova68_ling30_run.json](11_sensenova68_ling30_run.json)

## 身份怎么对上的

你说的是「6.8flash」。实时目录里没有 `sensenova-6.8-flash`，有 `sensenova-6.8-flash-lite`。官方 Token Plan 现在能打的 6.8 Flash 产品就是 Flash Lite；更强的 6.8 Flash 官方还写着即将推出。这次请求名和返回名都是 `sensenova-6.8-flash-lite`，没有换成 6.7。GitHub 现役名单里还只有 6.7 Flash Lite 和 DeepSeek V4 Flash，本轮按你点名发网，没改那份名单。

Ling 实时目录里有精确 ID `Ling-3.0-flash`，请求名和返回名一致。

思考开关按各家自己的字段关：SenseNova 用 `reasoning_effort=none`，回包里 `reasoning_tokens=0`；Ling 用 `thinking.type=disabled`，回包里没有思考正文。两边都不是换号、也不是改 Prompt。

## 两个模型各自最扎眼的点

**SenseNova 6.8 Flash Lite** 四题都是直接 JSON，Schema 合法，没有空 `speaker`，多数选择省略字段。Q3 把乔米那句「从今天起不再做助理」标了说话人，其余动作省略，这路是对的。Q2 把「没有立刻站起来」标成已发生，不是否定，这是语义问题，不是 Schema FAIL。Q4 把「温控器午前跳闸」和「荔枝很快渗水」拆成两条并列事实，没有收成一条因果。

**Ling-3.0-flash** 四题也是直接 JSON，Schema 合法，没有空 `speaker`，也没有代码围栏。Q1 抽得更粗，把走到走廊尽头、拧手电、扫鞋架收进同一条。Q2 全部填了 `speaker`：对讲机那句写成说话人「对讲机」，其余动作一律写成「旁白」。合同不判 FAIL——字段不是空串——但跟「没说话就省略」不是同一路。Q4 同样是并列事件，没有把跳闸写成渗水的原因。

## 和已经测过的对照

| 模型 | 通道 | Q1 Schema | Q2 Schema | Q3 Schema | Q4 Schema | Q4 因果有没有写成一条 |
|---|---|---|---|---|---|---|
| Doubao 2.1 Turbo | Agent Plan | 不合法（空 speaker） | 不合法（空 speaker） | 合法 | 合法 | 无 |
| 官方 Flash | 官方 API | 合法 | 不合法（空 speaker） | 合法 | 合法 | 无 |
| Doubao Mini | Agent Plan | 合法 | 合法 | 合法 | 合法 | 有 |
| Doubao Lite | Agent Plan | 合法 | JSON 坏掉 | 合法 | 合法 | 有 |
| MiniMax M3 | Agent Plan | 合法 | 合法 | 合法 | 合法 | 无 |
| GLM-5.2 | Agent Plan | 直接 JSON 失败（围栏） | 直接 JSON 失败（围栏） | 合法 | 合法 | 无 |
| SenseNova 6.8 Flash Lite | 日日新 Token Plan | 合法 | 合法 | 合法 | 合法 | 无 |
| Ling-3.0-flash | 蚂蚁百灵 | 合法 | 合法 | 合法 | 合法 | 无 |

这不能证明这两家已经能进严格管线，样本只有四道合成题。

## 这轮没打的

千问 `qwen3.8-max`、OpenRouter 上的 GLM 5.3 Flash，这一轮按你最新点的两家先打完了。要接着打再说一声。
