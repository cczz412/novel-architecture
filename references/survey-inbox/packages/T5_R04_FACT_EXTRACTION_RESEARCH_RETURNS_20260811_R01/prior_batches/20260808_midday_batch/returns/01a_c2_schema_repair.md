# C2 语义最好、Schema 却更差：怎样“只修格式，不伤内容”

## 结论：C2 现在最该做的是 runtime constraint，不是继续改训练

✅ **对你们现在这个 C2，我最推荐的下一步不是格式 SFT，而是做一次完全零训练、同 checkpoint 的约束解码 A/B。**

原因很直接：C2 已经不是“模型不会抽事实”，而更像是“模型会抽，但偶尔没把答案装进规定的盒子里”。

按你们给出的 DEV24：

| 项目 | C2 当前结果 |
|---|---:|
| Semantic Fact F1 | **89.36%** |
| Schema Valid | **75.00% = 18/24** |
| Status | 83.33% |
| semantic-hit facts 的 evidence_ids | **42/42 正确** |
| nonexistent ID | **0** |
| 正常停止 | **24/24** |
| 系统复读 | 无 |
| 触顶 | 无 |

也就是说，眼下最清楚的问题只有 **6/24 条没有通过完整 Schema**。而且 evidence binding 已经非常干净。

更关键的是，你们自己的 MICRO24 已经证明了一件事：**“只改训练输出格式”并不等于“只改格式”。** A_FULL → C2_FULL 的唯一控制变量是 evidence 表达方式，但 Semantic F1 相差 **12.44 个百分点**；D_RANGE 比 C2 低 **8.93 个百分点**，E_UNIT_QUOTE 也低 **2.76 个百分点**。所以，对你们这套只有 24 条训练文本的小样本 LoRA 来说，再做“格式 SFT”绝不能当成一个语义中性的动作。

而 runtime constrained decoding 的优势不是“绝不会伤语义”，而是：

**它不改权重、随时能关、能和 C2 原版一一配对比较，而且可以把约束缩到只有括号、key、类型、容器这些结构层。**

这正适合你们现在的问题。

但有一个很重要的反面结论：

> ⚠️ **不要把“Schema Valid 100%”当成成功。**

标准 constrained decoding 会在每一步把“不合法 token”的概率变成 0，再对剩余 token 重新归一化；因此模型实际采样的概率分布确实变了。NeurIPS 2024 的 *Grammar-Aligned Decoding* 明确指出，常见的逐 token grammar masking 并不等同于从原模型“在合法输出条件下”的真实条件分布采样，可能得到语法正确却质量变差的结果。2026 年的 DCCD 也把这个问题概括为：当模型给“当前合法 continuation”的原始概率质量很小时，硬约束可能把生成推入**局部合法、语义错误**的路径。citeturn17search2turn18search2

因此我对 C2 的推荐顺序是：

> **C2 自由生成 → C2 + 通用 JSON grammar → C2 + structural-only JSON Schema。**

其中 JSON Schema 初测时**只约束结构，不约束语义选择**：

- required keys：约束；
- object / array / string / integer 类型：约束；
- 括号、逗号、引号、容器：约束；
- `additionalProperties: false`：可以约束；
- `status` 的具体值：**第一轮不要 enum**；
- `evidence_ids`：只约束它必须是正确类型的数组，**第一轮不要把所有合法 ID 做成 enum**；
- 事实数组数量：**不要人为固定**；
- 不要用 `minItems` 强迫模型“必须抽出事实”。

这样才是真正接近你们要验证的命题：

> **“模型的内容决策已经够好；runtime 只负责把它装进合法结构。”**

JSON Schema 本身支持 `required`、类型、数组数量、唯一性等结构验证能力，但各 constrained-decoding 引擎实际支持的 JSON Schema 子集并不完全一样；JSONSchemaBench 对多种引擎的测试就发现了明显的 schema feature coverage 差异，所以实验结束后仍应再用独立 validator 验证，而不能只相信解码器自己说“合法”。citeturn22search0turn19view1


## 方法地图：Grammar、CFG、FSM、Schema、parser-guided 到底有什么区别

这些词看起来很多，其实可以把它们理解成两层：

**上层在描述“什么答案算合法”，下层在决定“生成时怎么禁止非法 token”。**

### Grammar-constrained decoding

这是最大的总称，中文可以直接理解成“**按语法规则限制生成**”。

模型每生成一个 token，系统根据当前已生成前缀判断：

> 哪些 token 继续下去还可能形成合法答案？

不可能形成合法答案的 token 被屏蔽，只让模型在剩下的 token 中选。

EMNLP 2023 的 Geng 等人把这种方法用于信息抽取、实体消歧和句法分析；他们使用 incremental parser，也就是“边生成边解析”，动态算出下一步允许哪些 token，而且整个方法不需要任务微调。论文还特别讨论了 **input-dependent grammar**：不同输入可以产生不同的合法值集合，这和你们未来若想把某篇小说里的合法 `evidence_ids` 动态编进约束非常接近。citeturn17search0

### Finite-state decoding

Finite-state，中文一般叫**有限状态机**，你可以把它理解成一个只有有限个状态的流程图。

例如规定输出只能是：

```text
"yes" | "no" | "unknown"
```

或者：

```text
E[0-9]+
```

这类规则可以用 DFA/FSM 很方便地表示。

它特别适合：

- regex；
- 固定选项；
- 简单模板；
- 非递归的结构。

Outlines 的早期 structured generation 工作，就是把许多约束转成有限状态结构，再在 token 生成阶段高效查合法 continuation。LMQL 也会把高层的 choice、regex、长度等约束转成 token mask。citeturn12search0turn21search5

但真正一般化的 JSON 可以无限嵌套 object / array：

```json
{
  "a": {
    "b": {
      "c": [...]
    }
  }
}
```

这种递归结构更自然地由 CFG 处理。

### CFG decoding

CFG 是 **Context-Free Grammar， 上下文无关文法**。

它比有限状态机多了类似“栈”的能力，所以比较自然地表示：

- 成对括号；
- 递归 object；
- 递归 array；
- 嵌套表达式；
- JSON；
- SQL / 编程语言语法。

OpenAI 公开解释 Structured Outputs 时，明确说他们会把提供的 JSON Schema 转换成 CFG，然后在采样过程中只允许符合 grammar 的 token。XGrammar 则把 CFG 编译成适合高性能 token masking 的结构，并已提供 JSON、regex、CFG 等 structured-generation 支持。citeturn16search8turn16search20turn21search4

所以：

> **CFG 是一种“表示合法语言”的方式；grammar-constrained decoding 是“利用这些规则控制生成”的方法。**

两者不是互斥方案。

### Parser-guided decoding

这个名字描述的是**执行约束的方法**。

假设已经输出：

```json
{"status":
```

incremental parser 会说：

> 这里接下来只能出现符合 `status` 值规则的 token；不能突然输出 `]`。

再往后一步一步更新 parser 状态。

EMNLP 2023 的 GCD 就属于这种方式：incremental parser 充当 completion engine，依据 grammar 返回合法的下一步 continuation。citeturn17search0

XGrammar、llguidance 这类现代实现内部会再做大量自动机、缓存、bitmask、预计算等优化，但逻辑还是同一家族。XGrammar 当前也提供可以直接接 Hugging Face Transformers generation loop 的 token bitmask / matcher 工作流。citeturn21search0turn21search2

### JSON grammar 与 JSON Schema constrained decoding

这是你们实验里**最应该分开的两个概念**。

**JSON grammar** 可以只规定：

> “输出必须是一段语法正确、完整的 JSON。”

例如下面这个答案：

```json
{"banana": 123}
```

完全是合法 JSON。

但它显然可能完全不符合你们的任务 Schema。

**JSON Schema constrained decoding** 可以进一步规定：

```text
根节点必须是 object
必须有 status
必须有 facts
facts 必须是 array
每个 fact 必须是 object
每个 fact 必须有 evidence_ids
evidence_ids 必须是 array
不能出现其他 key
```

JSON Schema 标准中的 `required`、`properties`、`additionalProperties`、`items`、`minItems`、`maxItems`、`uniqueItems` 等，就是用来表达这些约束的。citeturn22search0turn22search4

但 JSON Schema constrained decoding **不是一种固定算法**。实际系统可能把 Schema：

- 编译成 CFG；
- 编译成 FSM；
- 转成 regex；
- 转成自定义 parser / automaton；
- 再转成 token mask。

JSONSchemaBench 比较 Guidance、llama.cpp、Outlines、XGrammar、OpenAI、Gemini 时就发现，不同引擎对同一 JSON Schema 标准的理论 coverage 和实际 compliance 差异明显。citeturn19view1

所以实验报告不能只写：

> “我们用了 JSON Schema。”

应该写到：

> `backend + version + schema + decoding order`

否则别人很难复现。


## 约束会不会改变 precision / recall、token probability 和模型原本的决定

会。

但要把“改变模型”与“改变模型的采样分布”分开。

### 权重和 raw logits 没变，但真正采样的概率变了

假设模型原来的下一 token 分布是：

\[
p(t\mid x)
\]

grammar 根据当前前缀得到合法 token 集合 \(V(x)\)。

最常见的硬 masking 相当于：

\[
q(t\mid x)
=
\frac{
p(t\mid x)\mathbf 1[t\in V(x)]
}{
\sum_{u\in V(x)}p(u\mid x)
}
\]

也就是说：

- 非法 token → 概率 0；
- 合法 token → 重新归一化。

所以 checkpoint、参数、模型 forward 得到的 raw logits 没改，但**实际用于生成的概率分布 \(q\) 已经不是原来的 \(p\)**。Grammar-Aligned Decoding 和后续关于 constrained decoding distortion 的工作都把这个问题当作核心研究对象。citeturn17search2turn18search3

最麻烦的地方在于，这个归一化因子取决于**当前 prefix**。

所以整个序列的概率并不是简单地：

> “原模型输出概率，只不过把所有非法 JSON 删掉。”

标准逐 token GCD 会改变不同合法序列之间的相对概率，这就是所谓的**搜索偏差 / distribution distortion**。NeurIPS 2024 的 Grammar-Aligned Decoding 就是专门想解决这个问题，让生成分布更接近“原模型在 grammar 条件下”的目标分布。citeturn17search2

### 对 precision / recall 没有单方向保证

不存在一个可靠定律说：

> constrained decoding 一定提高 precision，而 recall 不变。

也不存在相反定律。

可能出现四种情况。

**情况一：纯格式错误被修掉，语义完全不变。**

这就是你们最希望看到的：

```text
自由：
{"status":"ok","facts":[...]
                         ↑ 少了 }

受约束：
{"status":"ok","facts":[...]}
```

这时候 Schema Valid 上升，Semantic F1 可以完全不变。

**情况二：原来非法的高概率 token 被挡住，模型选到另一个同义合法路径。**

Semantic F1 也可能不变甚至更高。

JSONSchemaBench 在 Llama-3.1-8B-Instruct 的 Last Letters、Shuffle Objects、GSM8K 三组 quality 测试里，并没有观察到 constrained decoding 必然伤语义；四种框架全部达到或超过 unconstrained baseline。例如 GSM8K 的 LM-only 为 80.1%，XGrammar 83.7%，llama.cpp 82.4%，Outlines 81.6%，Guidance 83.8%。作者认为 tokenization / token healing 等实现细节会影响结果。citeturn19view2

**情况三：正确内容的自然表达恰好与 grammar 冲突，模型被推到错误答案。**

JSONSchemaBench 举的直观例子是：模型本来可能想生成正确数字的某种格式，但该格式被 constraint 拒绝，于是模型沿着剩下的 token 继续，最后数字本身也可能变错。论文明确把 tokenization ambiguity 和 constraint 引入的 distribution shift 当作质量风险。citeturn19view1

**情况四：constraint 强迫模型回答它原本想“不回答”的字段。**

例如模型原来想停在：

```json
{
  "status": "uncertain"
}
```

但 Schema 强制：

```text
facts 必须存在
facts 至少 1 条
```

EOS 被禁止后，它不得不继续生成一个 fact。

于是：

> Schema 从 invalid → valid，  
> recall 看似上来了，  
> 实际可能是 hallucination。

这正是为什么我不建议你们第一轮加 `minItems: 1` 或固定数组长度。JSON Schema 的确能够通过 `minItems` / `maxItems` 强制数组长度，但它不知道小说原文里“正确的事实数量”是多少。citeturn22search3

### “小模型 + constrained decoding 比格式 SFT 更安全吗？”

没有论文支持一个普遍定律说：

> “模型越小，constrained decoding 一定比 SFT 更安全。”

更准确的说法是：

> **对你们这种“checkpoint 已经有高语义质量、故障明显集中在结构层”的状态，runtime constraint 是更低风险、更容易证伪的下一步实验。**

它的优势是**不修改权重**，不是“不会改变输出”。

而且小模型反而更应该警惕 hard constraint。2026 年 DCCD 的结果说明，当模型在合法 continuation 上的概率质量很低时，普通 constrained decoding 会受到明显的“projection tax”；其两阶段、training-free 的办法是先自由生成 draft，再在 draft 条件下做约束。在他们的 structured reasoning 测试中，1B 模型的 GSM8K strict structured accuracy 从普通 CD 的 15.2% 提升到 DCCD 的 39.0%。这不是你们任务的直接结果，但它非常清楚地说明：**“小模型 + hard constraint”绝不能默认语义无损。** citeturn18search2

另一方面，EMNLP 2023 已经证明 grammar-constrained decoding 可以直接作用于没有针对该 grammar 微调的模型，并在 structured NLP / information extraction 上取得很强结果，所以目前没有证据支持“推理时用了 grammar，就必须先按同一个 grammar 训练”这种说法。citeturn17search0

因此关于你问的 training/inference mismatch，我会这样下结论：

> **有明确实证支持“推理时 constraint 会造成 decoding-distribution mismatch”；但没有明确实证支持“因为训练时自由生成，所以推理时 constrained decoding 必然明显退化”。**

前者由 Grammar-Aligned Decoding、DOMINO、DCCD 等工作直接研究；后者反而被很多 zero-finetuning constrained decoding 成功案例削弱。更准确的名字应该叫**解码时的分布投影 / search distortion**，而不是简单把它归因于传统 train-test distribution mismatch。citeturn17search0turn17search1turn17search2turn18search2


## 与你们情况最接近的研究和实现

下面我按“对 C2 是否真的有用”排序，而不是按论文名气排序。

| 研究 / 实现 | 和 C2 的关系 | 最重要的结论 |
|---|---|---|
| **Geng et al., EMNLP 2023 — Grammar-Constrained Decoding for Structured NLP Tasks without Finetuning** | **非常近**：直接包含 information extraction，而且不需要微调 | incremental parser 可在 inference 时保证 grammar；input-dependent grammar 可把当前输入允许的实体/值写入约束。citeturn17search0 |
| **Beurer-Kellner et al., ICML 2024 — DOMINO** | **非常重要的安全性论文** | 约束如果没有正确处理 tokenizer/subword 边界，会“侵入”原生成；DOMINO 目标是 subword-aligned、minimally invasive constrained generation。citeturn17search1 |
| **Park et al., NeurIPS 2024 — Grammar-Aligned Decoding** | **直接回答“会不会改变概率”** | 普通 greedy GCD 会扭曲原 LM 的 sequence distribution；“合法”不代表仍然是原模型最自然的合法答案。citeturn17search2 |
| **Tam et al., EMNLP Industry 2024 — Let Me Speak Freely?** | 重要反例 | 格式限制在一些 reasoning 设置中会降低任务性能，所以 structured output 不能只看 validity。citeturn17search3 |
| **Geng et al., JSONSchemaBench 2025** | **目前最直接的 JSON Schema benchmark 之一** | 约 10K real-world schemas；比较 Guidance、llama.cpp、Outlines、XGrammar、OpenAI、Gemini，并单独评估 efficiency、schema coverage、quality。也显示良好实现下语义质量并不必然下降。citeturn18search1turn19view2 |
| **Sakota et al., EMNLP 2025 — BoostCD / BoostIE** | **和你们的 IE 最接近的新证据之一** | constrained 与 unconstrained IE 会犯**互补错误**，说明 constraint 并不是严格支配自由生成；论文进一步训练 boosted model 融合两边。你们现在不需要采用训练部分，但这个结果是很重要的警告。citeturn18search0 |
| **Reddy et al., 2026 — DCCD** | 小模型风险的强提醒 | hard CD 在合法概率质量低时可能走向“合法但语义错”；training-free draft → constraint 可减轻问题。citeturn18search2 |
| **Li et al., ICSE 2026 — AdapTrack** | 强调 search distortion | 用 backtracking 减少 standard constrained decoding 把模型推离原始 intent 的问题；主要实验在代码/API completion，不应直接外推到小说 IE。citeturn18search3turn18search25 |
| **XGrammar / XGrammar-2** | **本地 Qwen 最值得先试** | 支持 JSON、JSON Schema/CFG 类 structured generation，与 Hugging Face 工作流集成；官方项目列出 Qwen，并已集成进 vLLM、SGLang 等推理栈。citeturn21search0turn21search4 |
| **Outlines** | 非常成熟的高层 API | 可以用 JSON Schema、regex、grammar 定义输出；当前还有官方 `mlx-lm` integration，很适合 Apple Silicon / MLX 测试。citeturn15search0turn15search4 |
| **Guidance / llguidance** | 高性能 constrained generation | JSON/CFG 类约束成熟；JSONSchemaBench 中 Guidance 的 quality 结果很好，作者特别讨论了 token healing。citeturn19view2 |
| **llama.cpp grammar** | 本地部署成熟路线 | 支持 grammar / JSON Schema 转 grammar；一个很有价值的设计是约束本身可以作为 decoding constraint，而不是必须靠自然语言 prompt 让模型自己遵守。JSON Schema 支持仍应按引擎子集验证。citeturn3search2turn3search6 |
| **vLLM Structured Outputs** | **GPU production 很合适** | 当前 structured outputs 支持 XGrammar / Guidance backend；旧的 `guided_json` 等接口已迁移到统一 `structured_outputs`。citeturn15search2 |
| **SGLang Structured Outputs** | **GPU production 另一强选项** | 直接支持 JSON Schema、regex、EBNF，并提供多种 grammar backend；还支持 reasoning 段自由、最终答案受约束的模式。citeturn21search1turn21search3 |
| **LMQL** | 更适合复杂控制流，而非你们首选 | 可以做 choice、长度、stop、integer、regex 等 token-level constraints；当前文档仍把 regex 标成 preview，因此单纯为了 C2 JSON Schema，我不会排在 XGrammar / Outlines 前面。citeturn21search5 |

这里有一组证据尤其值得放在一起看：

Tam 2024 得到“格式限制可能伤 reasoning”；DOMINO 和 Grammar-Aligned Decoding 从算法层解释“为什么会伤”；但 JSONSchemaBench 后来的受控实验又发现，良好的 constrained frameworks 在三项 quality test 上**没有下降，反而小幅提高**。因此目前文献真正支持的不是“constraint 好”或“constraint 坏”，而是：

> **constraint 的侵入程度、tokenizer 对齐、schema 强度、prompt 与 schema 是否冲突、模型在合法 continuation 上原本有多少概率质量，都很重要。** citeturn17search1turn17search2turn17search3turn19view1turn19view2

这也解释了为什么你们最好做**同 checkpoint、同 DEV24、同后端**的小实验，而不是根据通用 benchmark 直接决定。


## JSON grammar 能保证什么，不能保证什么

这部分是整个问题里最容易被“Schema 100%”骗到的地方。

| 问题 | 通用 JSON grammar | 任务 CFG / grammar | JSON Schema constraint | 能保证语义正确吗 |
|---|---|---|---|---|
| JSON 括号、逗号、引号正确 | ✅ | ✅ | ✅ | 不涉及 |
| 根节点是 object | 可编码 | ✅ | ✅ | 不涉及 |
| 必须存在某个 key | ❌ 通常不保证 | ✅ 可编码 | ✅ `required` | ❌ |
| 字段类型正确 | ❌ | ✅ 可编码 | ✅ | ❌ |
| `status` 只能来自固定集合 | ❌ | ✅ enum grammar | ✅ `enum` | **❌ 只保证合法标签，不保证选对** |
| `evidence_ids` 必须是数组 | ❌ | ✅ | ✅ | ❌ |
| evidence ID 必须存在 | ❌ | ✅ 若把合法 ID 编进去 | ✅ 若用 enum/模式且引擎支持 | **❌ 不保证这个 ID 真能支持事实** |
| 数组最多 / 至少 N 个 | ❌ | ✅ 可编码 | ✅ `minItems/maxItems` | **❌ 不知道正确 N** |
| 完成 object 后禁止尾巴文字 | ✅ 可做 | ✅ | ✅ | 不涉及 |
| 不重复事实 | ❌ | 很难 | `uniqueItems` 只能处理 JSON item 的唯一性 | **❌ 不懂语义重复** |
| 应该抽几条事实 | ❌ | ❌ 除非外部已知 | ❌ 除非你硬编码数量 | **❌** |
| status 判断正确 | ❌ | ❌ | ❌ | **❌** |
| 什么时候应该输出空数组 | ❌ | ❌ | ❌ | **❌** |

JSON Schema 标准确实可以通过 `minItems`、`maxItems`、`uniqueItems`、`required` 等限制数组和 object；但这些约束检查的是 JSON 实例是否符合声明的规则，不理解“小说中到底发生了什么”。citeturn22search0turn22search4turn22search5

### 重复事实

假设输出：

```json
[
  {"fact": "张三离开京城", "evidence_ids": [12]},
  {"fact": "张三离京",     "evidence_ids": [12]}
]
```

这两条在语义上可能是同一事实。

即便后端完整支持 `uniqueItems: true`，这两个 JSON object 也不是完全相同的 item，所以 Schema 不会替你做语义去重。`uniqueItems` 保证的是数组元素的唯一性规则，而不是自然语言语义等价。citeturn22search3

### 错 status

这是最典型的“合法 JSON 把内容错藏起来”。

假设真正状态应该是：

```text
"contradicted"
```

模型原始 top choice 却是：

```text
"unknown"
```

如果两个都在 enum 里：

```json
"enum": ["supported", "contradicted", "unknown"]
```

grammar 什么也帮不了。

它只能保证：

> “status 是这三个中的一个。”

不能保证：

> “status 是正确那个。”

反过来，如果模型原本很想输出：

```text
"partially_supported"
```

但你 Schema 里没有这个值，那么 hard enum 会直接禁止它，迫使模型挑另一个合法 label。

于是 Schema Valid 变成 100%，Status accuracy 反而可能下降。

OpenAI 当前的 Structured Outputs 文档也明确把“required key / invalid enum”这类 schema compliance 与字段值本身是否正确区分开来：Structured Outputs 保证 supplied schema，而不是替模型保证业务事实正确。citeturn16search4

所以你们**第一轮实验不要把 status enum 打开**。

Status 已经是你们独立评估指标，应该让模型自由暴露自己的 status 决策，然后看 structural constraint 是否影响它。

### evidence_ids 合法但选错

假设当前文本允许：

```text
E1 E2 E3 E4
```

Schema 可以规定：

```text
evidence_id ∈ {E1,E2,E3,E4}
```

于是 `E99` 永远不会出现。

但它完全可以生成：

```text
E2
```

而正确证据其实是 E4。

所以：

> **合法 ID ≠ 正确 evidence binding。**

EMNLP 2023 的 input-dependent grammar 很适合实现“ID 必须来自当前输入”；但这是**候选域约束**，不是 evidence entailment 判断。citeturn17search0

而你们 C2 已经：

> nonexistent-ID = 0，  
> semantic-hit evidence = 42/42。

所以这一层约束现在几乎没有收益，却多了一种改变生成路径的机会。

✅ **我建议第一轮完全不要约束 evidence ID 的候选集合。**

只规定：

```text
evidence_ids 必须是 array
array element 必须是你们协议里的 ID 类型
```

这样干净得多。

### 数组数量

JSON Schema 可以非常轻松地规定：

```json
"minItems": 2,
"maxItems": 2
```

于是永远输出两条。

但 grammar 并不知道小说里正确答案到底是：

- 0 条；
- 1 条；
- 2 条；
- 5 条。

因此固定数量最容易制造两类假提升：

**事实少的时候，被迫 hallucinate；事实多的时候，被迫漏 recall。**

JSON Schema 标准只保证数组长度满足声明的范围。citeturn22search3

所以你们 primary test 的 `facts`：

```text
允许 0...自然结束
```

不要给任务语义没有明确规定的 `minItems/maxItems`。

### 是否应该结束

Grammar 可以很好地解决：

> 已经完成一个合法根 JSON 后，不允许继续吐解释文字。

也可以阻止：

```json
{"status": ...
```

这种还没完成必需结构时过早 EOS。

但这同时意味着一件事：

> **“正常停止 24/24”在 constrained arm 里不能和自由解码的 24/24 直接视为同一种成功。**

自由解码时可能是“模型自己选择 EOS”。

constraint 下则可能是：

- EOS 被 mask；
- 模型被迫补字段；
- 到 accepting state 后 runtime 强制结束。

所以建议你们把 termination 再拆成：

```text
model-EOS
grammar-accept termination
max-token termination
error
```

否则 grammar 让 termination 变成 100%，你看不出来模型自己的停止能力是否变差。


## Qwen、Hugging Face、MLX 以及云端方案该怎么选

### Qwen + Hugging Face：首选 XGrammar 做研究实验

如果你们现在是直接用 Hugging Face `transformers` 跑 Qwen3-4B，我会把 **XGrammar** 放在首选。

当前 XGrammar 官方文档直接提供 Hugging Face Transformers 的 valid-JSON generation quickstart，并公开 generation loop 里如何维护 grammar matcher、生成 token bitmask、对 logits 应用 mask。项目当前也明确列出 Qwen 支持，并已进入 vLLM、SGLang 等主流 serving 栈。citeturn21search0turn21search2turn21search4

对你们的实验它有一个特别大的好处：

> **可以尽可能保持现在的模型加载、tokenizer、chat template 和生成代码不变，只在 logits → sampling 中间加 constraint。**

这比同时换成另一套 inference engine 干净。

建议实验时固定 XGrammar 版本，而不要写“latest”。截至 2026 年 8 月检索时，项目仍在持续更新 JSON Schema、FSM 和 termination 等实现细节；近期 release 里也包含 `additionalProperties`、numeric constraints、termination 等修复，说明 constrained engine 自己也属于实验变量。citeturn21search6

### vLLM：如果你们已经用它 serving，就别换 host

当前 vLLM 的统一 Structured Outputs API 支持 XGrammar 或 Guidance backend；旧式 `guided_json` 等字段已经迁移到 `structured_outputs`。其文档还明确提示 `auto` backend 的选择可能随版本变化。citeturn15search2turn15search6

所以实验里不要写：

```text
backend=auto
```

而应该：

> **pin 一个 backend。**

例如全程 XGrammar。

否则：

```text
C2 + grammar
```

和：

```text
C2 + JSON Schema
```

如果被 vLLM 自动分配到了不同后端，你实际上一次改了两个变量。

vLLM 当前甚至已经提供 structured-output benchmark tooling，可以单独 benchmark JSON、grammar、regex 请求，因此做 latency / throughput 的工程评估比较方便。citeturn15search25

### SGLang：同样成熟，尤其适合后续 production

SGLang 当前可以直接指定：

- JSON Schema；
- regex；
- EBNF。

并由 structured-output backend 在生成过程中保证相应 constraint。它还有“reasoning 区域不约束、最终 structured answer 才约束”的机制，体现了一个很实用的工程原则：**让需要自由生成的部分自由，让机器接口部分严格。** citeturn21search1turn21search3

你们不是 CoT reasoning 任务，因此未必需要 reasoning exemption，但这个设计思想跟“只修格式，不伤内容”是一致的。

### MLX / Apple Silicon：Outlines + mlx-lm 是现在最顺手的路线

Outlines 当前有明确的官方 `mlx-lm` integration，可以直接把 MLX-LM model/tokenizer 接进去做 structured generation。citeturn15search0turn15search11

所以如果你们的 Qwen3-4B 实验跑在 Mac：

> **MLX-LM + Outlines**

是现实可用的选项。

不过研究对比时我仍然建议：

> **不要为了测试 constraint，顺便从现有 HF runtime 改到 MLX。**

历史上 Outlines/MLX integration 确实出现过 tokenizer、generation argument、bitmask 等兼容问题，项目后续也持续修复 MLX-LM integration。因此如果 C2 baseline 是 HF 跑出来的，就在 HF 里完成三臂 primary experiment；MLX 只做后面的部署复现。citeturn15search16turn15search24

### llama.cpp

llama.cpp 的 grammar / GBNF 路线已经非常成熟，也支持 JSON Schema 转 grammar。它有一个对你们特别有研究价值的特征：constraint 可以作为生成器单独的 grammar 参数，而不是非得把完整 schema 文本塞进 prompt 让模型阅读。citeturn3search2turn3search6

这非常适合“只研究 runtime intervention”。

因为：

```text
prompt 不变
checkpoint 不变
schema instruction 不变
只添加 token mask
```

才是干净实验。

### Outlines 与 Guidance

Outlines 目前把 structured generation 抽象成高层 output type，可以使用 JSON Schema、regex、grammar，并支持多种模型后端。citeturn15search4

Guidance / llguidance 也是很成熟的 constrained-generation 路线，而且 JSONSchemaBench 的 quality test 中 Guidance 在三项任务上都是表现最高的 constrained framework；论文作者认为 token healing 可能是原因之一。citeturn19view2

所以它们都值得 production benchmark。

但为了 MICRO24 的**科学控制变量**，我不会一上来把：

```text
HF free decoding
```

跟：

```text
Guidance server
```

比较。

因为模型 runtime 本身也变了。

### LMQL

LMQL 更像“带约束的 LLM 编程语言”。

你可以写：

```text
答案必须来自集合
必须在某个 token 数以内
遇到某字符串停止
必须匹配 regex
```

然后 LMQL runtime 在生成过程中转成 token masks。citeturn21search5

它很强，但你们现在的问题只是稳定 JSON object Schema，没必要先引入这么大一层 abstraction。

### OpenAI Structured Outputs：工业上证明了路线成立，但不是你们实验的直接证据

OpenAI Structured Outputs 当前保证输出遵循给定 JSON Schema；公开技术说明里描述了将 Schema 转成 CFG 并在采样时 constrained decoding。同时 OpenAI 也明确说 Structured Outputs 不只是 constraint——其方案还包含让模型更理解复杂 schema 的训练。citeturn16search4turn16search8turn16search20

所以：

> OpenAI 的“Schema 100%”可以证明这种产品架构成熟，  
> **不能证明“裸 Qwen3-4B + runtime CFG 一定语义无损”。**

它不是你们实验的严格 analogue。

### Anthropic：现在也有 guaranteed structured outputs，但 tool use 与纯 runtime constraint 要分开

Claude 当前 Structured Outputs 文档明确提供 guaranteed schema conformance，并建议需要固定 JSON Schema 时直接使用 Structured Outputs。citeturn16search1turn16search15

但传统 tool use 有一个关键区别：Anthropic 官方文档说明 tool definitions，包括 `input_schema`，会进入构造出的 system prompt，让模型本身看到 tool/schema 上下文。citeturn16search5

所以：

> **tool use ≠ 纯粹“模型完全不知道 schema，只在 logits 上加 mask”。**

对你们这种要研究 causal effect 的实验，不建议拿 tool-use benchmark 直接当 runtime-only constraint 证据。

### Google Gemini

Gemini 当前也支持提供 JSON Schema 的 Structured Outputs，用于 data extraction、classification 和 tool/API workflow，并宣称输出遵循提供的 Schema。citeturn16search2

Google 早期把这类能力称为 controlled generation / constrained generation，并支持用 enum 限制字段值。citeturn16search3

这里的成熟经验同样是：

> schema compliance 是产品层必须解决的问题，  
> 但不要因此把 semantic correctness 和 schema correctness 合成一个指标。

这正应该成为你们 C2 下一轮实验的评估原则。


## 零训练最小实验：自由解码 vs JSON grammar vs structural JSON Schema

我建议把 primary experiment 设计成真正的“三档约束强度”。

```text
C2 原始自由解码
        ↓
C2 + generic JSON grammar
        ↓
C2 + structural-only JSON Schema
```

🔥 **三组必须使用同一个 C2 checkpoint。不要再训练一 token。**

### 三个实验臂

#### Free

完全复刻现在的 C2 DEV24：

```text
checkpoint     = 当前 C2
prompt         = 当前 C2 prompt
chat template  = 当前版本
tokenizer      = 当前版本
temperature    = 当前值
top_p          = 当前值
top_k          = 当前值
repetition     = 当前值
max_new_tokens = 当前值
seed           = 当前逐样本 seed
constraint     = none
```

目标是复现：

```text
Semantic F1       ≈ 89.36%
Schema Valid      = 18/24
Evidence correct  = 42/42 among semantic hits
termination       = 24/24
```

只要 Free 不能复现，就先别比较 constraint。

#### Grammar

这一臂只回答：

> “如果我只禁止非法 JSON 语法，会发生什么？”

用**通用 JSON grammar**：

```text
root 必须是一个完整 JSON value/object
括号必须配对
string escape 合法
逗号 / 冒号合法
根 JSON 完成后不允许继续吐自然语言
```

但**不规定**：

```text
必须有哪些 key
status 是什么类型
facts 是什么类型
evidence_ids 是什么类型
```

这点很重要。

否则 Grammar arm 和 JSON Schema arm 没有清晰区别。

这一臂可能出现：

```json
{"foo": "bar"}
```

JSON syntax 100% valid，但任务 Schema invalid。

这不是实验失败，而是一个很有价值的结果：

> 如果 JSON grammar 把 75% 拉到比如 83%，而 JSON Schema 拉到 100%，说明原来的六个失败里，只有一部分是纯括号/JSON syntax，剩下的是 missing-key/type/container 问题。

#### JSON Schema

这组才针对你们真正的 Schema failure。

但用 **structural-only schema**，不要把语义判断也锁死。

概念上类似：

```json
{
  "type": "object",
  "required": ["status", "facts"],
  "additionalProperties": false,
  "properties": {
    "status": {
      "type": "string"
    },
    "facts": {
      "type": "array",
      "items": {
        "type": "object",
        "required": [
          "<你们现有事实字段>",
          "evidence_ids"
        ],
        "additionalProperties": false,
        "properties": {
          "<你们现有事实字段>": {
            "<保持现有协议类型>"
          },
          "evidence_ids": {
            "type": "array",
            "items": {
              "<保持当前 ID 的真实类型>"
            }
          }
        }
      }
    }
  }
}
```

这里故意没有：

```json
"status": {
  "enum": [...]
}
```

也故意没有：

```json
"evidence_ids": {
  "items": {
    "enum": ["E1", "E2", ...]
  }
}
```

更没有：

```json
"minItems": 1
```

这三个都已经开始干涉“内容选择”，不是单纯修结构。JSON Schema 标准支持这些能力，但 primary experiment 应该选择**最弱、刚好足以修你们六类结构错误的约束**。citeturn22search0turn22search3

### 最重要的控制变量

实验时请冻结：

| 项目 | 三臂要求 |
|---|---|
| checkpoint | 完全相同 |
| LoRA adapter | 完全相同 |
| tokenizer | 完全相同 |
| chat template | 完全相同 |
| prompt 字节内容 | 完全相同 |
| DEV24 顺序 | 完全相同 |
| temperature / top-p / top-k | 完全相同 |
| repetition penalty | 完全相同 |
| max_new_tokens | 完全相同 |
| seed | 每个 sample 使用同一对应 seed |
| retries | **全部禁止** |
| post-hoc JSON repair | **全部禁止** |
| backend | Grammar 与 Schema 使用**同一个 constraint backend** |
| validator | 三臂用**同一个外部独立 validator** |

特别是：

> **不要把 JSON Schema 文本额外塞进 Schema arm 的 prompt。**

否则你测到的是：

```text
prompt change + constrained decoding
```

而不是：

```text
constrained decoding
```

vLLM 的 tool-calling 文档甚至建议把预期 schema 同时告诉模型以改善模型意图与 constraint 的一致性，这在 production 是合理建议，但对于你们这一轮 causal experiment 恰恰是额外变量。citeturn15search19

这一轮要故意保持 prompt 一模一样。

### 为什么 Grammar 和 Schema 必须用同一个 backend

JSONSchemaBench 已经表明，不同 structured-generation 引擎会有不同的：

- tokenizer handling；
- schema coverage；
- over/under-constraining；
- token healing；
- performance。

因此：

```text
Free: HF
Grammar: llama.cpp
Schema: Outlines
```

是一个很差的科学实验。

你不知道差异来自：

```text
constraint type
```

还是：

```text
runtime implementation
```

JSONSchemaBench 对不同引擎的 quality 和 schema coverage 都观察到了明显差异。citeturn19view1turn19view2

✅ 如果现在 C2 就是 HF：

> **HF + XGrammar，一套 generation loop 完成 Grammar / Schema 两臂。**

这最干净。

### 预注册指标

你列的八项都保留，但我建议把定义再锁死。

| 指标 | 预注册定义 |
|---|---|
| **Semantic Fact F1** | 使用你们现在的同一 evaluator；micro P/R/F1 算法完全不改 |
| **Schema Valid** | 先 `json.loads`，再使用独立 JSON Schema validator；不是 constraint engine 自报 |
| **Status** | 使用当前同一 Status evaluator；primary schema 不使用 status enum |
| **Evidence ID correctness** | 同时报 `correct / semantic-hit facts` 和 nonexistent-ID rate，不能只报百分比 |
| **repetition** | 保留你们已有判定；另报 exact duplicate fact count |
| **termination** | 分成 model EOS / grammar accepting-state / max-token / error |
| **output tokens** | 对最终完整输出用同一 tokenizer 重新计数 |
| **latency** | 单样本 end-to-end；另分 cold schema compile 与 warm decode |

JSONSchemaBench 本身也把 grammar compilation、per-token efficiency、coverage、quality 分开评估，这种拆法可以避免“引擎预编译快慢”混进模型 decode latency。citeturn18search1turn19view1

我还强烈建议加两个**诊断指标**，不作为主结果，但能直接回答“约束到底有没有碰内容”。

**Mask intervention rate**

```text
有多少 decoding step：
unconstrained top-1 token 是非法的？
```

以及：

**Allowed probability mass**

\[
Z_t=\sum_{v\in V_t}p(v\mid prefix)
\]

直观解释：

```text
Z_t ≈ 1.00
```

表示：

> 模型本来就很想走合法路径，constraint 几乎没碰它。

如果你们看到：

```text
大部分 content span: Z_t > 0.99
只有 key / 括号附近发生 intervention
```

这是“只修格式”的非常强证据。

反过来，如果某条事实内容生成过程中频繁出现：

```text
Z_t = 0.2
0.1
0.05
```

说明 grammar 一直在强行把模型从它本来的高概率路径拉走。

DCCD 对“feasible probability mass 太低时 hard constraint 会造成 projection tax”的分析正是这个方向。citeturn18search2

### DEV24 的判定标准

我建议在看结果之前把下面标准写死。

**支持“runtime constraint 足够，不必为了 Schema 重训”的强结果：**

```text
JSON Schema arm:

Schema Valid        = 24/24
Semantic Fact F1    >= 88.36%   （89.36 - 1.00pp）
Evidence correctness= 不低于当前
nonexistent ID      = 0
Status              = 不下降或仅在预注册误差内
system repetition   = 0
max-token hit       = 0
termination failure = 0
```

但只看 aggregate F1 仍然不够。

🔥 更强、更重要的 paired 条件是：

> **当前那 6 条 Schema-invalid 样本全部被修成 valid，而且 constraint 没有把任何原本语义正确的 fact 改错。**

也就是说做一个 24×3 的 paired diff 表：

```text
sample
free semantic facts
grammar semantic facts
schema semantic facts

free schema error
grammar schema error
schema schema error

新增事实
消失事实
改变 status
改变 evidence_ids
```

你真正想看到的是：

```text
6 个 schema failure → 全修
0 个 semantic regression
```

如果刚好从 18/24 到 24/24，而且六条都是单向修复、没有反向损坏，paired exact McNemar 的双侧 p 值是 0.03125。它可以作为 DEV24 上“schema improvement 不是偶然配对变化”的一个辅助统计量；但只有 24 条，不能把它包装成泛化证明。

Semantic F1 建议另外做**按 document 重采样的 paired bootstrap**：每次从 24 条 DEV document 有放回抽 24 条，然后重算两臂的 micro-F1 差：

\[
\Delta F1=
F1_{\text{Schema}}-F1_{\text{Free}}
\]

预注册 non-inferiority margin：

\[
\Delta F1 \ge -1.0\text{ pp}
\]

如果 95% bootstrap CI 下界也高于 -1.0 pp，那是相当漂亮的“语义非劣”证据。

但 DEV24 很小，如果 CI 很宽，不要强行下统计结论；此时最有说服力的是**逐样本语义 diff + 六个 schema failure 的定点修复结果**。

### 什么结果不能宣称成功

下面这种：

```text
Free:
Schema 75%
Semantic F1 89.36%

Schema constrained:
Schema 100%
Semantic F1 84%
```

❌ 不能说：

> “structured decoding 成功。”

只能说：

> “JSON 更合法了，但任务变差了。”

这种：

```text
Schema 100%
Status 从 83.33% → 75%
```

也不能。

这种：

```text
Schema 100%
Evidence ID syntactically valid 100%
实际 support correctness 42/42 → 36/42
```

更不能。

这种也很危险：

```text
Schema 100%
Semantic F1 89.5%
但预测 facts 从正常数量变成大量 duplicate
```

因为 micro scorer 可能没有完全惩罚重复。

### 最容易制造“100% Schema 假成功”的七种约束

**强制 required field。**

模型本来想漏掉一个它不确定的字段；constraint 禁止 EOS，于是它编一个值补上。

**status enum。**

非法/不确定表达消失了，但被强行映射到一个合法、错误的 status。

**evidence ID enum。**

不存在的 ID 消失了，但模型可能从几个存在的 ID 中挑错一个。

**`minItems`。**

没事实时也得输出事实，直接提升 hallucination 风险。

**`maxItems` / 固定长度。**

事实很多时被迫提前丢掉，伤 recall。

**`uniqueItems`。**

只能禁止严格重复的 JSON item，不会识别：

```text
“张三离京”
“张三离开京城”
```

是不是同一事实。citeturn22search3

**允许空值的 Schema。**

这是反方向的坑：

```json
{
  "status": "",
  "facts": []
}
```

可以是 100% schema-valid。

Semantic recall 却可以接近 0。

因此 structured-output benchmark 不能把：

```text
valid JSON
```

或：

```text
schema compliance
```

当成：

```text
task success
```

JSONSchemaBench 也明确把 schema coverage/compliance 与 downstream quality 分开测试；其结果说明两者必须独立评价。citeturn19view1turn19view2

### 对 C2 的最终推荐

把你们现在的状况压缩成一句话：

> **C2 已经更像“一个会做题、偶尔答题卡涂错格式的学生”，而不是“不会做题的学生”。**

因此当前最合理的实验不是继续教它做题，而是看看能不能给答题卡加一道机械边界。

我会把方案定成：

```text
Primary backend:
    现有 HF runtime + XGrammar
    （如果现在已经是 vLLM，就固定 vLLM + XGrammar）

Arm A:
    C2 free

Arm B:
    C2 + generic JSON grammar

Arm C:
    C2 + structural-only JSON Schema
```

并且**暂时不约束**：

```text
status enum
合法 evidence ID 集
事实数组数量
语义 duplicate
```

因为这些已经进入内容层。

如果结果是：

```text
Free:
Semantic F1 89.36
Schema 18/24

JSON Grammar:
Semantic ≈ Free
JSON syntax 明显改善
Schema 仍未满

Structural Schema:
Semantic >= 88.36，最好维持约 89.36
Schema 24/24
Evidence correctness 不降
Status 不降
0 repetition
24/24 正常完成
```

而且逐样本能看到：

```text
原来的 6 个 invalid 全修，
没有新 semantic error，
mask intervention 主要发生在结构 token 附近，
```

那么你们就有相当直接的证据支持：

> **“当前 C2 的 Schema 问题可以在 inference/runtime 层解决；至少在这个 checkpoint 和 DEV 分布上，没有必要为了 Schema 再改训练权重。”**

反过来，如果 Schema 变成 24/24，但 Semantic F1、Status 或 evidence binding 有稳定下降，正确反应也不是马上重训，而是**先减弱 constraint**：

```text
full Schema
→ structural-only Schema
→ JSON grammar
```

如果仍有明显 semantic drift，再考虑更“非侵入”的 constrained decoding 实现、token-aligned 方法，或 DCCD 这种“先自由形成语义 draft、再结构化”的 training-free 路线。DOMINO、Grammar-Aligned Decoding、DCCD 都说明：约束的目标不应只是“让非法 token 出不来”，还要尽量避免把原模型已经正确的高概率意图改掉。citeturn17search1turn17search2turn18search2

对你们现有结果而言，**最有价值的不是把 75% Schema 变成一个好看的 100%，而是证明那剩下的 25% 真的是 serialization failure，而不是 semantic uncertainty。**

只要三臂实验把这件事证明出来，C2 的 89.36% 就有很大机会被保住。