# T-03 统一精确 JSON 围栏离线重放

本目录只离线重放已经存在的两份合成握手 raw。候选规则对豆包和 DeepSeek Flash 完全一致：裸 JSON 两路都允许；整个 `content` 恰好是一层小写 `json` Markdown 围栏、围栏外 0 字符时，两路也都允许机械剥离。

机械剥离只能拿掉围栏包装，不能改 JSON 内部任何字节、字段、值、顺序、身份或证据内容。本轮不调用模型，不产生能力评分，也不会改写旧 `HANDSHAKE_FAIL` 或旧 8 次 `NO_VERDICT`。

来源：Codex
