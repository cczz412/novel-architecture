# 10 Agent Plan 第二批非思考观察

这一批补了 4 个 Agent Plan 模型。同一冻结 Prompt、同一四题、温度 0、思考关、JSON Object、每题一次、重试 0。没有重跑 Doubao 2.1 Turbo，也没有重跑官方 Flash。

实时目录 SHA 与昨晚相同。`auto` 没用。身份都对上了：Mini／Lite 请求名等于返回名；MiniMax 请求 `minimax-m3-modelhub`、返回 `minimax-m3`；GLM 请求 `glm-5-2-260601`、返回 `glm-5-2-260617`。这是发网前按目录冻结合格绑定，不是临时换号。

不写准确率、总分、排名、整体可用、Gold、CCZ-57／CCZ-84 已完成。

回执：[09_AgentPlan第二批运行回执.json](09_AgentPlan第二批运行回执.json)

## 四个模型各自最扎眼的点

**Doubao Mini** 四题都是「JSON 能解析且 Schema 合法」。Q2 没有交空 `speaker`，选择了省略字段。Q4 有一条写成「整箱荔枝因冷库温控器午前跳闸开始渗水」。把「没有立刻站起来」标成已发生，而不是否定，这是语义问题，不是 Schema FAIL。

**Doubao Lite** Q1／Q3／Q4 Schema 合法；Q4 有明确「因为温控器跳闸」。Q2 回包完成，但 JSON 写坏了：`facts` 只合法收了第一条，后面的字段掉到数组外面，直接解析失败。内容看起来像抽对了，却进不了合同管线。

**MiniMax M3** 四题 Schema 都合法，空 `speaker` 没有出现。Q4 仍是并列事件，没有把因果收成一条事实。

**GLM-5.2** 请求了 `json_object`，Q1／Q2 仍然用 markdown 代码围栏包住 JSON。产品如果只对 `content` 做 `json.loads`，这两题会当失败；去掉围栏后 Schema 合法。Q3／Q4 是直接 JSON。Q4 没有明确因果命题。

## 和已经测过的两个对照

| 模型 | 通道 | Q1 Schema | Q2 Schema | Q3 Schema | Q4 Schema | Q4 因果有没有写成一条 |
|---|---|---|---|---|---|---|
| Doubao 2.1 Turbo | Agent Plan | 不合法（空 speaker） | 不合法（空 speaker） | 合法 | 合法 | 无 |
| 官方 Flash | 官方 API | 合法 | 不合法（空 speaker） | 合法 | 合法 | 无 |
| Doubao Mini | Agent Plan | 合法 | 合法 | 合法 | 合法 | 有（「因……」） |
| Doubao Lite | Agent Plan | 合法 | JSON 坏掉 | 合法 | 合法 | 有（「因为……」） |
| MiniMax M3 | Agent Plan | 合法 | 合法 | 合法 | 合法 | 无 |
| GLM-5.2 | Agent Plan | 直接 JSON 失败（围栏） | 直接 JSON 失败（围栏） | 合法 | 合法 | 无 |

更准确的产品结论是：

> 同一 Prompt、同一四题、都非思考时，合同违例不只出现在「较弱模型」这一家。有的模型会交空 `speaker`，有的会把 JSON 写坏，有的会在 `json_object` 外再包代码围栏。接收端必须做正式 Schema 校验，不能只看接口成功、也不能只看返回了像 JSON 的字。

这不能证明 Mini 或 MiniMax 已经能进严格管线，样本只有四道合成题。

## 目录里还没打的

还在实时目录、这批故意没动的：Evolving、GLM-5.3、Agent Plan 上的 DeepSeek Flash／Pro、Kimi K3、Kimi K2.7 Code。GitHub 旧名单里的 2.0 Pro、2.0 Code、MiniMax M2.7、Kimi K2.6 今晚目录里没有，不能打。
