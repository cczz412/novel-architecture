---
name: composer-team
description: >
  用户说「cursor 团队」「composer 团队」「grok 团队」类口令时启用（同一 skill，不另建）。
  1主+N子并发，默认三轮（W1→W2→W3），只要触发口令且同条消息未写「单轮」「两轮」即为三轮，禁止再问用户波次。
  W1/W2 每波最多 4 子（硬顶，禁止派 6）；W3 仍 2～3。
  可覆盖为单轮或双轮。子 agent 的 model 必须与主会话 slug 逐字相同（含速度档：composer-2.5 ≠ composer-2.5-fast；
  Cursor Grok 4.6 extra high／口语「4.6 xhigh」→ cursor-grok-4.6-xhigh，禁止加 -fast；旧界面 Cursor Grok 4.5 → cursor-grok-4.5-high；禁止猜成别的 grok 名，禁止偷跑 fable/claude）。
  按任务类型自动匹配角色组（方案审批/效果评估/通用），见 reference/task-presets.md。
  审查类任务加载 reference/audit-mode.md 走 A 段先行。写盘默认仅 temp/。
  reference/ 路径相对本 SKILL.md 所在目录（即 skill 安装目录），非当前工作区根目录。
---

# Cursor 团队（原 Composer Team）：1 主 + 子阵（默认三轮）

## 🔥 子 agent 模型（最高优先级，先于一切派发）

> **CZ 2026-07-14 钉死**：cursor 团队／composer 团队／grok 团队——只要派 `Task`，`model` 必须与主会话 slug **逐字相同**；**禁止偷跑别的模型**。

| 主会话（界面名） | Task 必须写的 `model` | ❌ 禁止写成 |
| --- | --- | --- |
| Cursor Grok 4.6／口语「4.6 extra high」「4.6 xhigh」 | **`cursor-grok-4.6-xhigh`** | `cursor-grok-4.6-xhigh-fast`（带 fast）、`cursor-grok-4.5-high`、任何 fable／claude、`composer-*`、漏写 `model` |
| Cursor Grok 4.5／口语「Grok 4.5 high」 | **`cursor-grok-4.5-high`** | `claude-fable-5-thinking-medium`、任何 fable／claude、`composer-*`、`grok-4.5-xhigh`、`grok-4.5-high`、漏写 `model` |
| Composer 2.5 | `composer-2.5` | `composer-2.5-fast` 或其它族 |
| Composer 2.5 Fast | `composer-2.5-fast` | `composer-2.5` 或其它族 |

- 每次 `Task` **必须显式传 `model`**；W1/W2/W3 全员同一 slug。
- 写错模型＝本 skill **执行失败**；先改参再派，不得用错模型输出充当团队结论。

本 skill 是**一套团队编排**，不绑死某一个模型族。主会话是 **Composer** 或 **Cursor Grok 4.6／4.5** 时，都用**同模型子 agent 并发 + 主 agent 穿插综合**。不另建 `grok-team` skill；Grok 走同一套「先自检 slug → 全员继承（含速度档）」。

适合审批大方案、评估执行效果、多角度决策论证等场景。

**架构约束（星形拓扑）**：子 agent 之间**不能互相通信**，所有信息只能通过主 agent 中转。因此主 agent 在穿插阶段的核心工作是**搬运原文摘录给下一波**，而非自己做深度综合——深度综合交给 W2 的 S（综合者）角色。

**核心规则**：
- **模型继承（含速度档，最高优先级）**：见上文 **🔥** 与下文 **§模型 slug 继承**；先自检主会话完整 slug，再让每个 Task 的 `model` 逐字相同。`composer-2.5` ≠ `composer-2.5-fast`；Grok 界面「Cursor Grok 4.6 extra high／4.6 xhigh」派发用 **`cursor-grok-4.6-xhigh`**（禁止加 `-fast`）；旧界面「Cursor Grok 4.5」才用 `cursor-grok-4.5-high`
- **角色分层**：角色定义见 [reference/roles.md](reference/roles.md)，任务预设见 [reference/task-presets.md](reference/task-presets.md)
- **审查模式**：审查类任务加载 [reference/audit-mode.md](reference/audit-mode.md) 做 A 段事实核验先行

**支持的主会话族（同一 skill）**：`composer-2.5` / `composer-2.5-fast` / `cursor-grok-4.6-xhigh` / `cursor-grok-4.5-high`（及平台后续登记的同族 slug）。若主模型是其它族（opus / claude / gpt / gemini 等），可**一行**提醒「非本 skill 主推族，团队收益与额度需自行判断」；**仍可按用户口令跑团队**，子阵同样逐字继承主会话 slug。**不得**与「单轮/双轮」合并提问。**用户已按 Step 1 触发口令时，波次默认三轮**（见 §2b），除非用户同条消息写了「单轮」或「两轮」。

---

## 可调参数（测试后可改数字，不改逻辑）

| 参数 | 默认值 | 实测结果 | 说明 |
| --- | --- | --- | --- |
| 单波 Task 硬顶 | **4** | CZ 2026-08-24：6 子并发易出错 | 任意一波实际派出不得超过 4；禁止拆两批凑 6 |
| W1 子 agent 数 | **4（硬顶）** | 满编取 C1～C4 | 按角色表顺序取前 4 个；C5/C6 留给 W2 补位 |
| W2 子 agent 数 | **4（硬顶）** | S+D+1 补位 | S + D1 + D2 + C补位×1 |
| W3 子 agent 数 | **2～3** | 不超过硬顶 | R1+R2 必派，R3 可选（高风险深潜） |
| 单 batch 最大并发 Task | **8**（平台余量） | 满编 4 应一次派出 | 不得为凑旧编制拆批 |
| 子 agent prompt 长度 | ≥3000 字符 | ✅ 3000 字符完整送达 | 搬运原文摘录的容量充裕 |
| 子 agent 工具能力 | **可用 Read/grep** | ✅ 子 agent 能读文件 | C5/C6/R 可自行读文件核验，不必全靠主 agent 粘贴 |

> W1/W2 人数是硬顶，不可为「更全面」自行加回 6。其余数字可随平台更新，逻辑不改。

---

## Step 1：触发识别

仅在用户消息中出现下列**显式口令**时启用：

**推荐总口令（模型无关）**：
- `cursor 团队` / `cursor team` / `跑个 cursor 团队` / `开 cursor 团队` / `开启 cursor 团队`

**旧口令仍有效（同一 skill，不另建）**：
- `composer 团队` / `composer-2.5 团队` / `composer2.5 团队` / `composer team`
- `跑个 composer 团队` / `用 composer 跑团队` / `开 composer 团队` / `开启 composer 团队`
- `grok 团队` / `grok team` / `cursor grok 团队` / `用 grok 跑团队`
- `三个臭皮匠` / `4 个 composer` / `6 个 composer` / `4 子 1 主` / `6 子 1 主`

> 口令只负责**启用本 skill**；子阵用哪个模型，一律看主会话 slug 继承，不看口令里写了 composer 还是 grok。口令里写「6 个」仍按每波 4 封顶，不得真派 6。

**同条消息可自然语言覆盖波次**（不要求固定词表）：
- 要**单轮**：「单波」「一轮就够」「只要一轮子 agent」等
- 要**收口轮**：「收口轮」「再开一轮只核验」「第三轮子 agent」等
- 要**指定预设**：「审批模式」「效果评估模式」等

**兜底**：仅当语义明确才进入；模糊场景（「跑一下」「分析一下」）**不进入**。

---

## 路径解析（强制，优先于一切 Step）

本 skill 的 `reference/*.md` 文件**一律相对于本 SKILL.md 所在的 skill 安装目录**，即与 `composer-team/SKILL.md` 同级的 `reference/` 子目录。

**硬性规则**：
1. 主 agent 必须用 **Read / 文件读取工具** 从 skill 目录读取 reference 文件（路径示例：与本 SKILL.md 同级的 `reference/audit-mode.md`（仓内即 `.cursor/skills/composer-team/reference/audit-mode.md`）），**不得**用当前工作区根目录推断路径
2. **禁止**：因工作区里没有 `reference/audit-mode.md` 就判定「文件缺失」并跳过
3. 若 Read 工具确实报错（文件不存在），才可报告「reference 文件缺失」并回退到 SKILL.md 内联规则

## 执行门禁（强制，优先于一切 Step）

以下为**硬性禁令**，违反等于 skill 执行失败：

1. **禁止伪团队**：触发团队口令且档位=B（见 §2c）时，**禁止**在未并发派出 W1 子 agent 并等待其全部返回之前，输出最终结论。声明行 + 工具调用 + 简短进度除外
2. **禁止跳过 W2**：双轮/三轮模式下，**禁止**在 W2 全返回之前输出最终综合
3. **禁止单人套皮**：主 agent 不得自己写完内容后仅追加「来源：Cursor 团队」或「来源：Composer 团队」。**必须**实际调用子 agent 工具
4. **子 agent 最低数量**：档位 B 每波至少 2 个；档位 A 可 1～2 个
5. **禁止追问波次**：细则见 Step 2b
6. **部分失败降级**（新增）：同一波内若 **≥2 个子 agent 空输出/跑偏**且重试 1 次仍失败，主 agent 可**降级为自己精读源文件后补位**，但须在声明中标注 `C? 降级为主读` + 理由。不必为合规无限重试
7. **禁止错模型派发**：任一 Task 的 `model` 与主会话 slug 不一致（含漏写/多写 `-fast`、Grok 4.6 xhigh 写成 `cursor-grok-4.6-xhigh-fast`、写成旧名 `grok-4.5-xhigh`／`grok-4.5-high`、偷跑 `claude-fable-*`／其它族、Grok 与 Composer 互串）= skill 执行失败；须在重派前改正，不得用错误模型的子输出充当团队结论
8. **禁止超编**：任意一波实际派出的 Task 数不得超过 **4**。禁止分两批凑 6。用户说「6 个」时仍按 4 封顶，声明行写 `封顶：4`

---

## 模型 slug 继承（强制，优先于 Step 6 派发）

子 agent 的推理档位、延迟、额度与主会话绑定。**速度档 / 思考档是 slug 的一部分，不是可选项。**

流程只有三步，口令不决定模型：

1. **自检**：写出当前主会话完整 slug
2. **继承**：每个 Task 的 `model` 与该 slug **逐字相同**
3. **速度也继承**：`-fast` 等后缀有就全员有，没有就全员没有。Grok 4.6 extra high 的整词是 **`cursor-grok-4.6-xhigh`**，**不要**加 `-fast`。旧 4.5 整词是 `cursor-grok-4.5-high`。

### 界面名 vs 派发 slug（Grok 必读）

| 你在 Cursor 里看到的 | 派发 Task 时必须写的 `model` | 不要写成 |
| --- | --- | --- |
| Cursor Grok 4.6 extra high（口语「4.6 xhigh」） | **`cursor-grok-4.6-xhigh`** | `cursor-grok-4.6-xhigh-fast`、`cursor-grok-4.5-high`、`claude-fable-*`、随便猜的 fast／high 变体 |
| Cursor Grok 4.5（或口语「Grok 4.5 high」） | **`cursor-grok-4.5-high`** | `grok-4.5-xhigh`、`grok-4.5-high`、`grok-4.5`、`claude-fable-*`、随便猜的 high 变体 |
| Composer 2.5 | `composer-2.5` | `composer-2.5-fast` |
| Composer 2.5 Fast | `composer-2.5-fast` | `composer-2.5` |

> 平台若以后改登记名，以**当前会话实际模型标识 / Task 工具允许的 model 列表**为准；本表只防常见误写。CZ 2026-08-13 钉：4.6 extra high＝`cursor-grok-4.6-xhigh`，**不用 fast**。`cursor-grok-4.6-xhigh-fast` 禁止。旧 4.5 仍是 `cursor-grok-4.5-high`。

### 合法 slug 对照（示例，以平台实际登记为准）

| 主会话 slug | 子 agent `model` 必须写成 | 常见误用（一律禁止） |
| --- | --- | --- |
| `composer-2.5` | `composer-2.5` | 写成 `composer-2.5-fast` |
| `composer-2.5-fast` | `composer-2.5-fast` | 写成 `composer-2.5` |
| `composer-2`（若仍在用） | `composer-2` | 与 2.5 族互串 |
| `cursor-grok-4.6-xhigh` | `cursor-grok-4.6-xhigh` | 写成 `cursor-grok-4.6-xhigh-fast`／`cursor-grok-4.5-high`／fable／或与 composer 互串 |
| `cursor-grok-4.5-high` | `cursor-grok-4.5-high` | 写成 `grok-4.5-xhigh`／`grok-4.5-high`／fable／或与 composer 互串 |

### 主会话 slug 从哪来（按优先级）

1. **当前对话实际使用的模型标识**（系统/会话元数据、模型选择器可见名 → 映射到上表派发 slug）
2. **用户同条消息显式指定**（如「用 composer-2.5 跑团队」「用 cursor-grok-4.6-xhigh」）
3. **仍无法确定时**：用**一句话**问用户要完整 slug（Composer 要问清是否带 `-fast`；Grok 要确认是 `cursor-grok-4.6-xhigh` 还是旧的 `cursor-grok-4.5-high`）；**禁止**自行加 `-fast` / 写成 `cursor-grok-4.6-xhigh-fast` / 旧名 `grok-4.5-xhigh`

### 硬性禁令

- **禁止默认 fast**：不得因 skill 示例、历史习惯、省 token、觉得「团队该用快模型」而把全体子 agent 写成 `-fast`。🔥 尤其不得把 4.6 xhigh 写成 `cursor-grok-4.6-xhigh-fast`
- **禁止族内互替**：不得把 `composer-2.5` 与 `composer-2.5-fast` 当作「差不多」；不得把 Grok 界面名与派发 slug 混用
- **禁止跨族替换**：主会话是 Grok 时，子 agent 不得改成 composer／fable／claude；反之亦然——除非用户同条消息**显式**指定另一完整 slug
- **禁止升级/降级**：主会话是标准档，子 agent 不得升 fast；主会话是 fast，子 agent 不得降标准档
- **禁止省略 `model` 参数后指望平台自动对齐**——Team 模式下主 agent **必须**在每次 Task 调用里显式传入与主会话相同的 `model`
- **禁止为 Grok 另建 skill**：Grok 与 Composer 共用本 skill；口令用 `cursor 团队` 即可
- **禁止偷跑 fable**：主会话是 Grok 时，任何 Task 不得写 `claude-fable-5-thinking-medium` 或其它 claude 族

### 派发前自检（每一波 Task batch 前必做）

```
主会话 slug = <逐字抄写，如 composer-2.5 或 cursor-grok-4.6-xhigh>
本波 N 个 Task 的 model 参数 = 全部与上一行相同？ 是 / 否
声明行「全员 <slug>」= 与上一行相同？ 是 / 否
```

任一为「否」→ **不得派发**；先改参数再并发。

### 写进声明与末尾标注

- Step 3 声明行：`全员 <主模型 slug>` 必须是**实际派发 slug**，不要写「composer 系」「grok 系」「Cursor Grok 4.6（或 xhigh）」这类模糊名
- 团队回复末尾可在 `来源：Cursor 团队…` 后追加：`｜子阵模型：<slug>`（与派发一致，便于 CZ 核对）

---

## Step 2：任务档位 + 预设匹配 + 波次判定

触发后主 agent **先**完成四件事，再输出声明：

0. **解析主会话 slug**（见 **§模型 slug 继承**）：写下将用于本任务全部 Task 的完整 slug；未完成不得进入 2a

### 2a. 任务预设匹配

根据用户任务描述中的关键词，匹配 [reference/task-presets.md](reference/task-presets.md) 中的预设。匹配后 C1～C6 职责被预设覆盖。无匹配则用 [reference/roles.md](reference/roles.md) 通用定义。

如果任务是审查类（审/核/复审/check/audit），加载 [reference/audit-mode.md](reference/audit-mode.md)，先完成 A 段再继续。

### 2c. 任务档位（A/B）— 在波次判定之前

| 档位 | 适用场景 | 编队 | 说明 |
| --- | --- | --- | --- |
| **A（证据穷尽型）** | diff 已全量 / 单文件精读 / grep 可机械核对 / 用户明确说「证据已穷尽」「diff 已看完」 | 主 agent 精读 + **1～2 个子 agent 交叉核对**，不要求满编 | 避免对窄证据任务形式主义满编 |
| **B（裁决综合型）** | 多文档、多张力、设计权衡、方案审批、效果评估 | **满编 W1/W2/W3**（默认三轮） | 当前 skill 的主力场景 |

**判定规则**：
- 用户同条消息含「diff 已全量」「证据已穷尽」「只需交叉核对」「单文件」→ **档位 A**
- 其余一切 → **档位 B**
- 声明行须标注 `档位：A` 或 `档位：B`

**档位 A 的简化流程**：
1. 主 agent 先自己精读源文件 / diff / grep 结果
2. 派 1～2 个子 agent（按 C1→C2 顺序取）做交叉核对，prompt 贴主 agent 的精读结论让子 agent 挑刺
3. 综合后直接输出，不要求走 W1→W2→W3 全阵

### 2b. 波次判定

| 优先级 | 条件 | 波次 |
| --- | --- | --- |
| **用户覆盖** | 同条消息语义为「单轮」 | **单轮** |
| **用户覆盖** | 同条消息语义为「两轮就够」「不要 W3」 | **双轮**（跳过 W3） |
| **默认** | **一切其它情况**（含仅出现 Step 1 触发口令） | **三轮** |

> **设计理由**：composer-2.5 额度大 token 便宜，默认三轮（W1 广度扫描 → W2 综合+对质 → W3 高风险深潜）。W3 的 R 角色对 S 结论中的 Top 风险做深度分析，这是弱模型最需要的深度补强。

#### 波次：禁止追问（强制，与上表同等效力）

用户消息里**已经出现 Step 1 触发口令**时：

1. **波次已判定**：只要同条消息**没有**「单轮」「两轮就够」「不要 W3」等覆盖词，就是 **三轮（W1→W2→W3）**，**禁止**再问用户波次——追问视为 skill 执行错误。
2. **禁止把波次写进待确认事项**：Step 3 声明里直接写 `波次：三轮` 即可。
3. **唯一例外**：用户**同时写了矛盾**，才用**一句话**让用户选其一。

- **单轮**：一轮 **C1～C4（4 子）** → 主综合
- **双轮**：**W1 满编 4 子** → **主穿插** → **W2：S+D1+D2+C补位×1（4 子）** → **主 agent 基于 S 裁决**
- **三轮（默认）**：W1(4子) → 主穿插 → W2(4子) → 主穿插 → **W3：R1+R2[+R3]（2～3 子，高风险深潜）** → **主 agent 最终裁决**

---

## Step 3：进入声明

自判完成后输出声明。**声明行必须含 `档位` + `预设` + `波次` + 理由**：

```
> 模式：Cursor 团队 ｜ 全员 <主模型 slug> ｜ 档位：<A|B> ｜ 预设：<plan-review｜outcome-eval｜general> ｜ 波次：<单轮｜双轮｜三轮> ｜ 理由：<半句> ｜ 任务：<一句话>
```

**三轮（默认）追加**：
```
> 执行：W1(4子) + 穿插 + W2(S+D+C补位1) + 穿插 + W3(R1+R2[+R3] 高风险深潜)
> 落盘：默认仅 temp/
```

**双轮追加**：
```
> 执行：W1(4子) + 穿插 + W2(S+D+C补位1)，跳过 W3
```

`<主模型 slug>` 必须打印**本对话实际使用的完整派发 slug**（如 `composer-2.5` / `composer-2.5-fast` / `cursor-grok-4.6-xhigh`，逐字抄写），不写模糊族名、不写「或 fast / 或 high」。

**何时才能问用户一句**：仅当**任务目标 / 审什么 / 边界**不清楚，无法派发子 agent 时，才问**任务本身**；**不得**把「波次单双轮」放进这句提问里（波次已由 §2b 锁定）。

**禁止**：用「任务不清楚」当借口，顺带追问「要不要双轮 / 三轮」——默认已是三轮。

---

## Step 4：主穿插（轻量搬运，不做深度综合）

**架构核心**：主 agent 在穿插阶段不再做深度综合——那是 W2 中 S（综合者）的工作。主 agent 只做**三件轻量事**：

### 4a. 事实确认（可选，有工具则做）
用 grep / Read 快速验证 W1 子 agent 引用的 2-3 个关键事实是否正确。能做就做，不强求。

### 4b. 覆盖盘点
用一个**简短清单**列出 W1 的 4 子分别覆盖了什么维度、**哪 1 个维度最薄**（决定 W2 的唯一 C 补位选谁）。优先补 W1 没出场的 C5 或 C6。格式：
```
W1 覆盖盘点：
- C1(...): 覆盖 xxx，深度 够/薄
- C2(...): 覆盖 xxx，深度 够/薄
- C3(...): 覆盖 xxx，深度 够/薄
- C4(...): 覆盖 xxx，深度 够/薄
- 最薄 1 维度：C? → W2 补位（优先未出场的 C5/C6）
```

### 4c. 委派包（两种形态，按输出长度选）

把 W1 各子 agent 的发现打包给 W2。**两种形态**，主 agent 按子 agent 输出长度自选：

**形态 1：结构化短表**（推荐，子 agent 输出简短时优先用）
```
C1(正面论证): 结论=xxx | 关键证据=文件+行号 | 置信度=高/中/低
C2(反面攻击): 风险1=xxx | 风险2=xxx | 证据=...
...
```
每子 1-3 行，总量可控，不易截断。

**形态 2：原文摘录**（子 agent 输出较长且含重要推理链时用）
- 粘贴子 agent 的原话（不二次加工）
- 每子摘录 2-5 个最关键段落

**通用规则**：
- S 的 prompt 要包含**全部 4 子的委派信息**
- D1 的 prompt 只需包含 **C1+C2**
- D2 的 prompt 只需包含 **C3+C4**
- C 补位的 prompt 包含**对应维度** + `wave=2, 补位=true, 禁止同题重写`

**禁止**：主 agent 在穿插阶段写出完整的综合结论——那是 S 的工作。

### 4d. W2→W3 穿插（三轮模式专用）

W2 全部返回后，主 agent 做**两件事**：

1. **从 S 结论中提取 Top 2-3 高风险点**（风险描述 + S 的判定 + D1/D2 对该风险的质疑原文）
2. **写 R 的 prompt**：每个 R 只深挖一个风险点，prompt 包含该风险的全部上下文

**轻量原则同 4a-4c**：搬运 S 和 D 的原文，不做深度综合。

---

## Step 5：写盘与仓库边界

1. **子 agent**：不调用写入类工具改用户仓库；只返回文本/analysis
2. **主 agent**：
   - **默认允许**：仅在工作区 `temp/` 内写入（含子目录）
   - **默认禁止**：`temp/` 以外任意路径，除非用户在同一任务里明示
3. 若无 `temp/` 目录，主 agent 可在用户确认后创建

---

## Step 6：派发规则

**模型硬约束（与 §模型 slug 继承 同义，派发时再强调一次）**：

- 每个子 agent 的 Task 参数 `model` = 主会话 slug，**字符级一致**（含 `-fast` 等后缀有无）
- 主会话 `composer-2.5` → 全部 Task `model: "composer-2.5"`
- 主会话 `composer-2.5-fast` → 全部 Task `model: "composer-2.5-fast"`
- 主会话 `cursor-grok-4.6-xhigh` → 全部 Task `model: "cursor-grok-4.6-xhigh"`
- 主会话 `cursor-grok-4.5-high` → 全部 Task `model: "cursor-grok-4.5-high"`
- **错误示例**：主会话是 `composer-2.5` 却写 `model: "composer-2.5-fast"`；主会话是 Cursor Grok 4.6 extra high 却写 `cursor-grok-4.6-xhigh-fast`、`cursor-grok-4.5-high`、`composer-2.5`、`claude-fable-5-thinking-medium`（违反门禁 §7）

每个子 agent 的 prompt 必须包含：

1. **任务原文**（用户消息原文，不要复述加工）
2. **角色与禁止项**（来自预设表或通用角色表）
3. **窄化指令**：`你只负责 X，不要发散到其它维度`
4. **必须产出字段**（角色表「窄化职责」列）
5. **返回格式**：markdown 小节，方便主 agent 引用
6. **直接出干货**：「你的输出会被主 agent 综合，不必客套，不必复述任务」
7. **证据纪律**：凡涉及具体文件/规则的判断，须带「路径 + 行号」或「grep 模式」；无证据的论断综合时**降级为 see-also**
8. **W2/W3 子 agent 额外**：prompt 嵌入上一波的委派包（见 Step 4c）

### 子 agent 硬约束三句（每个 prompt 末尾必加）

以下三句**逐字写进每个子 agent 的 prompt 末尾**，防止弱模型走捷径：

```
【硬约束 1】你必须用 Read 工具读取以下绝对路径的文件：<主 agent 填入路径>。禁止用全库关键词搜索替代读指定文件。
【硬约束 2】若该文件不存在或无法读取，你必须明确报错「文件 <路径> 不存在/无法读取」，不得用「未找到相关内容」搪塞。
【硬约束 3】你的每条结论必须包含「摘录原文 + 行号范围」或明确写「本段未读源文件，仅基于 prompt 内信息」。
```

**主 agent 的责任**：在写 prompt 时必须填入子 agent 应该读的**绝对路径**（可多个）。若任务不涉及特定文件（纯观点碰撞），硬约束 1 改为 `无需读取特定文件，基于 prompt 内信息回答`。

**并发规则**：
- 同一波内全部子 agent **同一条消息并发派出**（同一 tool-call batch）
- 满编 4 必须一次派出；禁止为凑旧的 6 人编制拆成两批
- 仅当平台单 batch 并发上限 **低于 4** 时，才允许把本波拆成两批，两批合计仍 ≤4，且视为同一波
- 禁止不同轮（W1/W2/W3）混进同一 batch
- 每波人数：W1 = 4（硬顶）；W2 = 4（硬顶）；W3 = 2～3

**Cursor 实现映射与限制**：
- W1/W2/W3 子 agent 并发 = **单次回复里并行发起多次 Task 工具调用**；**每一次** Task 都必须带 `model` 字段，值 = §模型 slug 继承 中已解析的主会话 slug
- 派发前执行 **§模型 slug 继承 · 派发前自检**；禁止先派再改 model
- 每个 Task 调用对应一个角色，prompt 按上方 8 条 + 硬约束三句填充
- **禁止**用「我来模拟多个角色的思考」替代实际 Task 调用
- 子 agent **可以使用 Read / grep 等工具**（实测确认）
- **子 agent 不宜承担需要看完整巨大 git diff 的任务**——大 diff 由主 agent 切成 hunk 摘要再派子审，比让子 agent 读全量 diff 更稳
- 子 agent 的 `subagent_type` 参数须与平台文档一致，若不确定可省略让平台用默认值

**失败与降级规则**（实测强化版）：
- 单子 agent 空输出/跑偏 → **重试 1 次**（同角色、同 prompt、**同 model slug**，同波内不算新波次）
- 重试仍失败 → 标注「C? 未产出，该维度缺失」
- **同波 ≥2 个子 agent 失败** → 主 agent 可**降级为自己精读源文件补位**，声明中标注 `C?+C? 降级为主读`，不必为合规无限重试
- 子 agent 跑偏（输出与指定任务无关） → 视同空输出，走重试/降级流程

---

## Step 7：主 agent 最终裁决（基于 S 的初步综合）

**v3.0 核心变化**：主 agent 不再从零综合多份子 agent 输出。流程：

1. **读 S 的初步综合**：S 已按预设输出格式写好了结构化结论
2. **读 D1+D2 的对质发现**：看是否有矛盾/遗漏需要修正 S 的结论
3. **读 C 补位的补充**：看 W1 的薄弱维度是否被补上
4. **裁决**：在 S 的初步综合基础上做**最终裁决**——修改、补充或推翻 S 的部分结论

**输出格式**取决于任务预设——见 [reference/task-presets.md](reference/task-presets.md) 中对应预设的「综合输出格式」节。

**通用规则**：
- **单轮**：子 agent 全部返回后，主 agent 自己写综合（无 S 角色）
- **双轮**：W2 全部返回后，基于 S 裁决写最终答复
- **三轮（默认）**：W3 返回后再写最终答复。流程：读 S 初步综合 → 读 D 对质 → 读 R 深潜 → **看 R 的深潜结果是否改变 S 的结论** → 最终裁决
- 主结论处须**显式**写：采纳哪些子结论、不采纳哪些、一句理由
- **S 与主 agent 裁决的差异**（若有）须显式标注
- **R 的深潜发现**须在最终输出中单列「深潜分析」节，标注「R? 深潜后是否改变结论」
- **未采纳条目同样列出**，让用户能反查
- 三轮：增加「W1 小结」「W2 小结」「W3 深潜小结」，再写合并结论

---

## Step 8：模式生命周期

- 进入后**仅对当前一轮任务生效**。下条消息默认回到普通对话；再次触发口令才再次启用
- 用户在同轮说「再发散一次」→ 可加一轮子 agent + 综合
- 已跑完三轮（W1+W2+W3） → 要再跑子 agent 请用户新开一条任务

---

## 输出末尾标注

每条团队模式回复**末尾追加一行**：

- 单轮：`来源：Cursor 团队（C1~C4 综合）｜子阵模型：<slug>`
- 双轮：`来源：Cursor 团队·双轮（W1:4子 + W2:S+D+C补位1）｜子阵模型：<slug>`
- 三轮：`来源：Cursor 团队·三轮（W1:4子 + W2:S+D+C补位1 + W3:R深潜）｜子阵模型：<slug>`

（旧写法「Composer 团队」仍可识别为同一 skill；新回复优先用 Cursor 团队。）

---

## 与其他 skill 的边界

- 固定身份持续对话（旧 `role-switch`）已停用，不再提供
- 本 skill 专门解决：**当前主会话（Composer / Cursor Grok 等）如何用同模型子阵 + 穿插综合提升质量**；不另建 grok skill
- 跑腿取证走 `aux-crew`；动手护栏走 `scout-check`；外发走 `external-handoff`

## 不做的事

- 档位 A 不走全阵；档位 B 走波次判定（Step 2b/2c）
- 同一任务内子阵链路**不超过 W1→W2→W3**
- 不为省 tokens 跳过「主穿插 + 委派包」直接叠下一波
- 不做嵌套子 agent（子 agent 不再 spawn）
- 不在未见用户授权时写入 `temp/` 以外路径
- 不为「更全面」把 W1/W2 加回 6 子

## 维护历史

- 2026-05-06 v2.0 · 模块化重构：角色定义→roles.md、审查约束→audit-mode.md、任务预设→task-presets.md · 波次判定简化为默认双轮 · H 角色按任务类型决定 · 新增方案审批/效果评估专用角色组和输出格式 · description 瘦身 · Step 编号连续化
- 2026-05-06 v2.1 · 堵偷懒四洞：新增「路径解析（强制）」块防止 reference 文件在工作区找不到 · 新增「执行门禁（强制）」块禁止伪团队/跳W2/单人套皮 · Step 6 补 Cursor Task 工具实现映射 · audit-mode.md 消除与审批任务的语义冲突
- 2026-05-06 v2.2 · 波次默认双轮写死：§2b 增「波次：禁止追问」· Step 3 区分「任务不清」与「不问波次」· description/执行门禁同步 · 弱化强模型确认与波次混谈
- 2026-05-13 v3.0 · 弱模型扩量架构：W1 从 4 子扩到 6 子 + 窄化 prompt（每个角色只做一件事）· W2 引入 S（综合者）做初步综合 + D1/D2（对质者）互挑矛盾 · 主穿插从深度综合改为轻量搬运（复制粘贴子 agent 原文摘录）· Step 7 从从零综合改为基于 S 裁决 · 新增可调参数表 · 明确星形拓扑约束
- 2026-05-13 v3.1 · 实测校准：并发上限实测 ≥8（参数表更新）· 子 agent 可用 Read/grep 工具（C5/C6 可自行读文件）· 新增子 agent 空输出重试规则（C4/C6 实测出现过首次空返回）
- 2026-05-13 v3.2 · 默认三轮：W3 从可选收口改为默认启用，使用 R（高风险深潜者）角色对 S 结论中 Top 2-3 风险做深度分析 · 波次判定表更新· Step 4 增加 W2→W3 穿插规则 · Step 7 增加 R 深潜结果整合逻辑
- 2026-05-14 v3.3 · 实战强化六补丁：(1) 新增任务档位 A/B（证据穷尽型不走全阵）(2) 子 agent prompt 硬约束三句（强制读指定路径、报错而非搪塞、输出带行号）(3) 同波≥2子失败时主 agent可降级为精读补位 (4) 委派包增加结构化短表形态 (5) Cursor Task 约束说明（大 diff 切 hunk、subagent_type 默认值）(6) 执行门禁增加部分失败降级条款
- 2026-05-19 v3.4 · 模型族升级 composer-2 → composer-2.5；子 agent 仍逐字继承主会话 slug（含速度档 fast）
- 2026-05-25 v3.5 · 模型 slug 继承专节：禁止默认 `-fast`、`composer-2.5` 与 `composer-2.5-fast` 对照表、Step 2 先解析 slug、门禁 §7 错模型=执行失败、派发前自检与声明/末尾标注要求
- 2026-07-09 v3.6 · 模型族扩展：同一 skill 支持 Cursor Grok 4.5；推荐总口令改为「cursor 团队」；保留 composer / grok 旧口令；流程固定为自检 slug → 全员继承（含速度档）；不为 Grok 另建 skill
- 2026-07-14 v3.7 · CZ 钉：顶部「🔥 子 agent 模型」；当时 Grok 派发 slug 更正为 `cursor-grok-4.5-high`（旧文 `grok-4.5-xhigh` 作废）；禁止偷跑 fable／claude／其它族；门禁 §7 同步
- 2026-08-13 v3.8 · CZ 钉：Grok 4.6 extra high／口语「4.6 xhigh」派发 slug＝`cursor-grok-4.6-xhigh`，**不用 fast**；禁止写成 `cursor-grok-4.6-xhigh-fast`；旧 4.5 仍映射 `cursor-grok-4.5-high`
- 2026-08-24 v3.9 · CZ 钉：任意一波最多 4 子（硬顶）。W1/W2 满编从 6 降到 4；W3 仍 2～3。禁止拆两批凑 6。审查要派 H 时占用唯一补位槽，W2 不得变成 5/7
