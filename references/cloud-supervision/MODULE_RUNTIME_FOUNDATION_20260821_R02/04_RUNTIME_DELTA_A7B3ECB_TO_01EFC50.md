# `a7b3ecb` 到 `01efc50` 的运行能力差量索引

本页只帮助外审快速定位这段时间改了什么。每项是否真的可用，仍要回代码、合同和直接测试判断。

## 提交顺序

- `92273d3` docs: align product pipeline and ledger directory
- `3f69b3b` feat: add chapter fact and ledger runtime slices
- `7c289c3` docs: release R14 context and atomic expectations R03
- `98579d9` tools: package three current background boards
- `3f526f5` feat: add CSV intake and Excel conversion gate
- `a376acc` feat: persist pending chapter fact handovers
- `66f545d` feat: add current planning longline view
- `aeac47a` feat: preflight pending chapter fact handovers
- `3f7314a` feat: bundle current facts and planning supply
- `5bcc1e7` fix: reserve M7 red lights for confirmed conflicts
- `c6d90a7` feat: render author-readable fact material bundles
- `5707ec8` feat: preflight external chapter fact migrations
- `9d8c667` feat: show current pending fact handovers
- `11acbee` feat: show current planning longline view
- `6186fe0` feat: record author adjudications for unknown checks
- `01efc50` docs: register future creative material imports

## 主要变化组

### 产品方向和长期参照

- 产品共同背景升到 R14：双车道、章事实稿、十本账、M5／M7／M8／M9 定位纠偏。
- 原子需求升到 R03，共 142 条；旧 127×6 测试设计不能冒充覆盖新增 15 条。
- 账本目录和主架构图已经落本地，但“目录存在”不等于十本账都有内容读写入口。

### 入料和双车道边缘

- CSV 进入显式导入入口；Excel 有安全转换门，不会被误当普通 ZIP。
- 外来章修订可做事实证据迁移预演，并要求 C10→C11→C1 外来道身份。
- 剧本、灵感、产品原生大纲只登记为未来缺口，没有当前实现。

### 章事实稿与交棒

- 可以生成章事实稿原型和作者可读版。
- 可以生成明确交棒请求，保存 pending 请求，重启读回，并做 current 预演。
- 当前仍不能把这些局部能力合写成“正式自产章已经交棒并进入事实账”。

### 供料、规划和检查

- M11 可以把当前已确认事实与未来规划分开装入材料包，并生成作者安全页面。
- M8 可以只读展示当前规划里的故事线和伏笔；它不是完整长线账。
- M7 只有 confirmed 证据可以升红灯；候选和混合层不能伪装硬冲突。
- T14 可以保存检测结果、引用 full_check、展示变化，并给 unknown 保存作者自报裁决；原模型 unknown 不会被改写。

## 仍应保持的边界

- 原型文件不等于正式合同对象。
- 预演不等于写账成功。
- 作者可读页面不等于新的真源。
- `completed` 不等于全绿。
- 规划中的 `paid／revealed` 不等于故事里已经兑现或读者已经知道。
- 测试通过不等于真实模型语义质量通过。

来源：Codex
