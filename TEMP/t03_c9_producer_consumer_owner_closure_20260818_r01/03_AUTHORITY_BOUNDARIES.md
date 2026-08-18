# 四条权限边界

## Actuality

C4 的 current truth 资格由 M4／M5 作者确认路径和 current revision 可回验证据决定；M11 只能只读。planstore 自己区分计划、暗稿与有 support set 的 actual 派生，M11 不能改写这些源语义。

统一 `actuality_class` 映射尚无正式 owner。M11 可以消费将来正式给出的分类，不能自行把 C4／planstore 的混合对象拍成当前或未来。

## Budget

M11 可以执行硬上限：保全部 HARD，SHOULD/MAY 只用余量，复算失败就停。

M11 无权决定预算值、估算器版本、HARD/SHOULD/MAY 或排序。预算也无权裁决材料真值。

## Unresolved-state

状态：`OPEN_NO_DEFAULT`。

Actuality 不能因为“尚未完成”把它默认成 false、resolved、unknown 或 completed；budget 也不能因为省 token 直接省掉。命中未决语义时，M11 输入门停止，等未来正式语义 owner 决定。

## Evidence recall

状态：`OPEN_NO_DEFAULT`。

Actuality 不能决定证据是否只进 recall；budget 只能说“本包没装”，不能宣称材料可回取。handle 和可回取性仍由外部 preflight／未来 recall owner 管理。

## 三条新停线门

- 双 owner：未出现。没有字段被同时交给两个唯一 owner。
- consumer 反写 producer：未出现。C9 是只读执行材料，M8/C7 不得回写 C4、planstore 或输入语义。
- 被迫发明正式默认值：未出现。所有未冻语义保持 OPEN 并失败关闭。

来源：Codex
