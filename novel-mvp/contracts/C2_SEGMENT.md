# C2 · 责任段（SEGMENT）

**版本：v1**（增加输入章节 revision 身份；v0 作为迁移前内存态）

一句话用途：从一份明确的 C1 current revision 切出责任段＋左右只读背景，是一次模型调用的输入单位。内存态合同，不落盘。

| 方向 | 模块 |
|---|---|
| 发 | M2 切窗器（[segment.py](../mvp/segment.py) 的 `segment_chapter`） |
| 收 | M3 抽取器（[extract.py](../mvp/extract.py) 的 `build_user_content`／`extract_segment`） |

## 字段表

| 字段 | 类型 | 含义 | 必填 |
|---|---|---|---|
| contract | str | 固定 `C2_SEGMENT` | 是 |
| version | str | 固定 `v1` | 是 |
| chapter_revision_ref | obj | 必须逐字段复制输入 C1 v1 的 current revision ref | 是 |
| seg | int | 段序号，本章内从 1 起 | 是 |
| text | str | 责任段正文（若干完整自然段，用 `\n` 连接） | 是 |
| start | int | 段起点字符偏移（见下「偏移基准」） | 是 |
| end | int | 段终点字符偏移（`start + len(text)`） | 是 |
| halo_before | str | 前文只读背景，最多 `halo_chars` 字；开篇段为空串 | 是（可空串） |
| halo_after | str | 后文只读背景，最多 `halo_chars` 字；末段为空串 | 是（可空串） |

⚠️ 偏移基准：`start`／`end` 相对「规范化拼接文本」——各自然段去首尾空白后用单个 `\n` 连接——**不是**原始文件里的偏移。

因此 C2 `start/end` 只服务本次切窗，不能保存成 C11 章节证据 anchor。正式 anchor 一律回到 revision 逐字正文并使用 `CHAPTER_REVISION_TEXT_UNICODE_CODEPOINT_0_BASED_HALF_OPEN`。

切窗参数在 [config.json](../config.json)：`seg_min_chars` 620／`seg_max_chars` 923／`halo_chars` 180（研究仓 T5_R04 守擂冠军配方），由调用方（M0）读配置传入。

## 真实示例

《万鬼伏藏》c01 切出 4 段，这是第 2 段（长字段截断展示，实际 `text` 948 字、halo 各 180 字）：

```json
{
  "contract": "C2_SEGMENT",
  "version": "v1",
  "chapter_revision_ref": {
    "chapter_id": "c01",
    "revision_no": 2,
    "revision_text_sha256": "0aeb78621f82e724f19a56e01f2dc9bfcdec630b1748e2fb2c78edb0b0e47cfc"
  },
  "seg": 2,
  "text": "听着李星燃的描述，陈医生开始在问诊单上写下：患者意识清，仪态整齐，接触尚可，被动合作。思维连贯，语速…",
  "start": 941,
  "end": 1889,
  "halo_before": "…然后找她家要了十斤大米，这才把她的魂魄给超度。”\n",
  "halo_after": "\n他被吓得双腿发软，真从医院高楼跌落惨死。\n…"
}
```

v0 reader 遇到 v1 不得剥掉 revision ref 后继续抽取；产品完成 revision-aware 升级前必须 fail closed。
