# 工具说明

`validate_event_output.py` 只做确定性机械检查，不调用模型，也不宣称能判断剧情语义。

运行示例：

```bash
python tools/validate_event_output.py --output 04_第3章完整抽取结果.json --anchors appendix/第3章冻结证据目录.json --chapter 3
```

`event_output.schema.json` 可给本地 JSON Schema 校验器使用。供应商支持严格结构化输出时，也可参考 `02B_接口支持时可替换的严格response_format.json`。

来源：ChatGPT
