# 事实抽取实验总路牌 R04｜现役决策账

✅ 这份 R04 主要解决一个问题：**以后不能因为一轮失败，就忘掉前面的依据，临时狂加空题、狂加高密题，或者把整条路线推倒重来。**

它继承两份旧路牌，不回改旧文件：

- R02：19 个实验家族、先比 READ 再比 OUT、禁止无意义的 3×3 全组合。
- R03：登记 CONSUME 和 EDGE 两个后续家族；它们不插队当前事实抽取实验。

本版只新增当前事实抽取 Demo 的“决策记忆”。内容分三层：

- **稳定规则**：没有新的成组证据，不得推翻。
- **当前假设**：只允许跑一次受控实验验证；失败不能被包装成长期规则。
- **已淘汰做法**：保留失败证据，后面不得换个名字再跑。

人看入口是 [EXPERIMENT_DECISION_LEDGER.md](EXPERIMENT_DECISION_LEDGER.md)，机器读取用 [DECISION_REGISTRY.json](DECISION_REGISTRY.json)。

## 当前一句话状态

TRAIN72 reducer、TRAIN96 token-weighted、TRAIN96 sample-mean 三条诊断都已执行。sample-mean 的 L6 六题全部预测为空，四道非空题因此机械 FAIL。当前 **TRAIN96＋loss／data／order／hparam 4B recipe 已停止**，停止票见 [STOP_RESULT_TICKET.json](STOP_RESULT_TICKET.json)。

## 当前只允许的顺序

1. 不再为当前配方新增第三种 loss、教材或行序，也不调整学习率、训练步数、LoRA，不扫 checkpoint、不 retry。
2. 不从这些失败格进入 READ2、READ4、OUT 或 REAL24。
3. 模型中立 Gold、TRAIN96、L6 和既有运行结果继续保留；停止当前配方不等于永久淘汰 4B，也不决定 Mini。
4. 已经跑过的低剂量／格式配方能否作为新的 READ Demo 底座，只能由控制窗另行核定，当前不自动开跑。

这份路牌本身不是单次运行票，不允许 API、Notion、Git 或生产晋级。后续本地 4B 训练仍由控制窗按每一格的材料、参数、门槛和唯一运行目录签精确执行票。

来源：Codex
