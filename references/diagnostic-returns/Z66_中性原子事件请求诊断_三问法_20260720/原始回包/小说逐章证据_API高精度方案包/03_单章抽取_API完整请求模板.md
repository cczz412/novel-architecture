# 单章抽取：API 完整请求模板

## 1. 推荐调用方式

高精度模式对每章先发两个互补请求。两次请求使用同一份：

- 当前章完整行号文本；
- 当前章元数据；
- 只来自前文章节的状态账本；
- 严格 JSON 输出合同。

区别只在覆盖职责。

---

## 2. Extractor-A：动作、动机、关系与状态

### 2.1 System Prompt

```text
你是“中文小说逐章证据抽取器 A”。你只依据 CURRENT_CHAPTER 抽取可核验的原子事实。

PRIOR_STATE 只用于解析人物别名、代词、既有关系和是否首次出现；它不是本章证据。任何证据的原文短引必须逐字来自 CURRENT_CHAPTER。禁止使用本章之后的信息，禁止使用常识、作品知识或猜测补足原文。

目标是高召回：宁多勿漏，但每条必须忠于原文。重点覆盖：
1. 人物对人物或物体做出的动作及结果；
2. 决定、计划、命令、请求、承诺、拒绝；
3. 动机、目标、态度与明确情绪变化；
4. 人物关系的建立、确认、变化或冲突；
5. 身体、身份、职位、能力、财物等状态变化；
6. 对话中明确说出的信息；
7. 正文明确提出但本章尚未回答的问题；
8. 会影响后续理解的时间、数量、价格和条件。

原子性规则：一条只表达一个“主体—动作／状态／关系—对象—结果”。不同主体、不同动作或可独立成立的结果必须拆开。

模态规则：
- 叙述明确事实，直接陈述；
- 人物说法写成“X称／告诉／回答……”；
- 人物猜测写成“X猜测／怀疑／认为可能……”；
- 人物计划写成“X计划／决定……”；
- 传闻、报纸、信件必须标明信息来源；
- “可能、似乎、也许、暂时”等不确定词不得删除；
- 不得把问题、愿望、假设或比喻改写成客观事实。

引用规则：
- 每条至少有一个 source_ref；
- quote 必须是 CURRENT_CHAPTER 中连续、逐字一致的短引，建议 12～80 个汉字；
- line_ids 必须覆盖 quote 所在行；
- 短引要包含足以支持主体、动作和结果的上下文，不能只截半句；
- 不得引用 PRIOR_STATE。

只输出一个符合约定 Schema 的 JSON 对象，不要 Markdown，不要解释，不要输出最终 E 编号。
```

### 2.2 User Message 模板

```text
<JOB>
job_type: chapter_evidence_extraction_A
schema_version: novel-evidence-candidate-v2
chapter_no: {{CHAPTER_NO}}
chapter_title: {{CHAPTER_TITLE}}
source_sha256: {{CHAPTER_SHA256}}
prompt_version: extractor-A-v2.0
</JOB>

<PRIOR_STATE context_only="true" citable="false">
{{PRIOR_STATE_JSON}}
</PRIOR_STATE>

<CURRENT_CHAPTER sole_evidence_source="true">
{{LINE_NUMBERED_FULL_CHAPTER_TEXT}}
</CURRENT_CHAPTER>

<OUTPUT_CONTRACT>
输出字段：
- schema_version：固定为 novel-evidence-candidate-v2
- chapter：必须等于 {{CHAPTER_NO}}
- extractor：固定为 A
- candidates：按原文出现顺序排列
- coverage_check：逐项说明是否已检查，不得只写“完成”

candidate 字段：
- temp_id：C-A-001 起连续编号
- fact：一句中文原子事实
- category：从 event_action、intent_plan、motivation_attitude、relationship、state_change、dialogue_claim、unresolved_question、time_numeric 中选择
- assertion_mode：从 narrator_fact、dialogue_claim、character_belief、intention_plan、reported_information、unresolved_question 中选择
- entities：原文出现的主要实体名称数组
- source_refs：至少1项，每项含 line_ids 与 exact quote
- notes：只在存在边界风险时填写，否则空字符串
</OUTPUT_CONTRACT>
```

### 2.3 输出示例

```json
{
  "schema_version": "novel-evidence-candidate-v2",
  "chapter": 3,
  "extractor": "A",
  "candidates": [
    {
      "temp_id": "C-A-001",
      "fact": "周明瑞决定在当前世界重做转运仪式，以尝试寻找返回原世界的办法。",
      "category": "intent_plan",
      "assertion_mode": "intention_plan",
      "entities": ["周明瑞", "转运仪式"],
      "source_refs": [
        {
          "line_ids": ["L0002"],
          "quote": "确定了计划，周明瑞顿时有了主心骨"
        }
      ],
      "notes": "若具体计划未在本章当前短引中重述，应引用能够明确计划内容的本章行；否则不得补写计划内容。"
    }
  ],
  "coverage_check": {
    "event_action": "已逐段检查",
    "intent_plan": "已逐段检查",
    "motivation_attitude": "已逐段检查",
    "relationship": "已逐段检查",
    "state_change": "已逐段检查",
    "dialogue_claim": "已逐段检查",
    "unresolved_question": "已逐段检查",
    "time_numeric": "已逐段检查"
  }
}
```

示例中的 `notes` 展示的是边界意识；正式运行中若本章没有明确重述“计划内容”，应只写“周明瑞确定了一个计划”，或者引用本章能明确计划内容的完整段落。不能从前章状态账本把计划内容写成本章新证据。

---

## 3. Extractor-B：人物、地点、组织、规则与体系

### 3.1 System Prompt

```text
你是“中文小说逐章证据抽取器 B”。你只依据 CURRENT_CHAPTER 抽取可核验的实体与世界信息。

PRIOR_STATE 仅用于解析别名、判断某实体是否已在前章出现，以及识别关系是否为延续；它不是本章证据。所有 quote 必须逐字来自 CURRENT_CHAPTER。禁止使用本章之后的信息、作品常识或外部知识。

目标是高召回：逐段检查并抽取以下信息：
1. 人物首次出场候选、姓名、别名、身份、职业、年龄、外貌、性格表现、教育、能力、财务与资源；
2. 地点名称、性质、位置、内部结构、交通和关联事件；
3. 组织、教会、家族、公司、学校、政府机构、隐秘势力；
4. 特殊物品、武器、文件、货币、食物、交通工具及明确属性；
5. 世界规则、社会制度、法律、历法、价格、单位、宗教、能力体系、特殊概念；
6. 亲属、师生、雇佣、同事、敌对、交易等明确关系；
7. 数字、日期、距离、费用、比例、等级和条件。

每条仍必须是一个原子事实。描述必须保留原文模态；人物判断、传闻和推测不得写成客观结论。

“首次出场”只输出 first_appearance_candidate。最终是否首次由程序依据 PRIOR_STATE 决定。不得因为 PRIOR_STATE 出现某个未来别名，就在本章使用正文尚未出现的称呼。

引用必须来自 CURRENT_CHAPTER 的完整连续短引，并包含足以支持事实的上下文。只输出合法 JSON，不要解释，不要最终 E 编号。
```

### 3.2 User Message 模板

```text
<JOB>
job_type: chapter_evidence_extraction_B
schema_version: novel-evidence-candidate-v2
chapter_no: {{CHAPTER_NO}}
chapter_title: {{CHAPTER_TITLE}}
source_sha256: {{CHAPTER_SHA256}}
prompt_version: extractor-B-v2.0
</JOB>

<PRIOR_STATE context_only="true" citable="false">
{{PRIOR_STATE_JSON}}
</PRIOR_STATE>

<CURRENT_CHAPTER sole_evidence_source="true">
{{LINE_NUMBERED_FULL_CHAPTER_TEXT}}
</CURRENT_CHAPTER>

<OUTPUT_CONTRACT>
category 从以下枚举选择：
person_identity、person_trait、person_resource、place、organization、relationship、object、rule_concept、ability_system、time_numeric。

每个 candidate 必含：
temp_id、fact、category、assertion_mode、entities、first_appearance_candidate、source_refs、notes。

coverage_check 必须逐项返回检查结果。
</OUTPUT_CONTRACT>
```

### 3.3 输出示例

```json
{
  "schema_version": "novel-evidence-candidate-v2",
  "chapter": 3,
  "extractor": "B",
  "candidates": [
    {
      "temp_id": "C-B-001",
      "fact": "梅丽莎十五岁，通过入学考试后进入廷根技术学校蒸汽与机械系学习。",
      "category": "person_identity",
      "assertion_mode": "narrator_fact",
      "entities": ["梅丽莎", "廷根技术学校"],
      "first_appearance_candidate": true,
      "source_refs": [
        {
          "line_ids": ["L0015"],
          "quote": "去年七月份，十五岁的梅丽莎通过入学考试，如愿以偿成为廷根技术学校蒸汽与机械系的一员"
        }
      ],
      "notes": ""
    }
  ],
  "coverage_check": {
    "person_identity": "已逐段检查",
    "person_trait": "已逐段检查",
    "person_resource": "已逐段检查",
    "place": "已逐段检查",
    "organization": "已逐段检查",
    "relationship": "已逐段检查",
    "object": "已逐段检查",
    "rule_concept": "已逐段检查",
    "ability_system": "已逐段检查",
    "time_numeric": "已逐段检查"
  }
}
```

---

## 4. 建议 JSON Schema

提供商支持严格 JSON Schema 时使用严格模式；不支持时使用 `json_object`，再由本地 `jsonschema` 二次验证。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "chapter", "extractor", "candidates", "coverage_check"],
  "properties": {
    "schema_version": {"const": "novel-evidence-candidate-v2"},
    "chapter": {"type": "integer", "minimum": 1},
    "extractor": {"enum": ["A", "B", "COMBINED"]},
    "candidates": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "temp_id", "fact", "category", "assertion_mode", "entities",
          "first_appearance_candidate", "source_refs", "notes"
        ],
        "properties": {
          "temp_id": {"type": "string", "pattern": "^C-(A|B|X)-[0-9]{3}$"},
          "fact": {"type": "string", "minLength": 4, "maxLength": 180},
          "category": {
            "enum": [
              "event_action", "intent_plan", "motivation_attitude", "relationship",
              "state_change", "dialogue_claim", "unresolved_question", "time_numeric",
              "person_identity", "person_trait", "person_resource", "place",
              "organization", "object", "rule_concept", "ability_system"
            ]
          },
          "assertion_mode": {
            "enum": [
              "narrator_fact", "dialogue_claim", "character_belief",
              "intention_plan", "reported_information", "unresolved_question"
            ]
          },
          "entities": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "uniqueItems": true
          },
          "first_appearance_candidate": {"type": "boolean"},
          "source_refs": {
            "type": "array",
            "minItems": 1,
            "items": {
              "type": "object",
              "additionalProperties": false,
              "required": ["line_ids", "quote"],
              "properties": {
                "line_ids": {
                  "type": "array",
                  "minItems": 1,
                  "items": {"type": "string", "pattern": "^L[0-9]{4,6}$"}
                },
                "quote": {"type": "string", "minLength": 4, "maxLength": 220}
              }
            }
          },
          "notes": {"type": "string", "maxLength": 240}
        }
      }
    },
    "coverage_check": {"type": "object"}
  }
}
```

## 5. OpenAI-compatible `/chat/completions` 请求体模板

下面只是接口形态模板；模型名、基础地址和是否支持严格 Schema 由你的提供商决定。

```json
{
  "model": "YOUR_MODEL",
  "temperature": 0,
  "n": 1,
  "max_tokens": 12000,
  "messages": [
    {
      "role": "system",
      "content": "{{EXTRACTOR_SYSTEM_PROMPT}}"
    },
    {
      "role": "user",
      "content": "{{USER_MESSAGE_WITH_PRIOR_STATE_AND_FULL_CHAPTER}}"
    }
  ],
  "response_format": {
    "type": "json_object"
  }
}
```

提供商支持严格 Schema 时，可替换为类似：

```json
{
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "novel_evidence_candidate_v2",
      "strict": true,
      "schema": {{JSON_SCHEMA_OBJECT}}
    }
  }
}
```

### 参数建议

- `temperature`：0或0.1。低温用于稳定格式，但不能代替审校。
- `n`：1。与其同 Prompt 采样两份，不如使用两个职责不同的抽取器。
- `max_tokens`：根据章长和预期证据数动态设置；必须检查 `finish_reason`，不能把截断响应当成功。
- 输入上下文：提示词＋prior state＋当前章建议不超过上下文容量的60%～70%，为输出和审校留空间。
- 流式输出：结构化 JSON 初期建议关闭，便于整体解析；使用流式时必须完整拼接后再验 JSON。
- 日志：不得记录 Authorization；请求和响应分别保存 SHA 与 Prompt 版本。

## 6. 只有一次调用预算时的综合 Prompt

单调用无法拥有真正独立的补漏审校，但可以使用以下保底合同。它仍应发送完整章节，而不是短引目录。

### System Prompt

```text
你是中文小说逐章证据抽取器。CURRENT_CHAPTER 是唯一证据源，PRIOR_STATE 只用于指代和首次出场判断，绝不可引用。

先逐段建立候选，再按以下16类检查遗漏：事件动作、计划、动机、关系、状态变化、对话信息、未决问题、时间数字、人物身份、人物特征、人物资源、地点、组织、物品、规则概念、能力体系。

每条只写一个原子事实，保留“谁说／谁猜／谁计划”等模态；quote 必须逐字来自当前章且完整支持事实。禁止先验知识、后文知识、推测和文学解读。

在同一 JSON 中输出 candidates 和 self_audit。self_audit 必须列出：发现并修正的过度推断、拆分的复合事实、补入的遗漏类别、仍需人工复核的边界项。不要输出 Markdown，不要最终 E 编号。
```

### 输出结构

```json
{
  "schema_version": "novel-evidence-candidate-v2",
  "chapter": 3,
  "extractor": "COMBINED",
  "candidates": [],
  "coverage_check": {},
  "self_audit": {
    "overclaim_fixed": [],
    "compound_split": [],
    "missing_added": [],
    "manual_review": []
  }
}
```

## 7. 不应继续发送的内容

- 任意字符长度的滑动短引目录；
- 未来章节出现范围和次数；
- 当前章尚未建立的别名；
- `来源：Codex`、导出回执、测试说明等日志元数据；
- 全书正文；
- 已由程序能确定的最终编号、文件排版和 Markdown 装饰要求；
- “只抽以后有用的内容”这类无法验收的预测标准。
