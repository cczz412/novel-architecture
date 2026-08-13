## 结论

最适合这个产品的 MVP 是：

- React 19 + TypeScript + Vite 8
- `@xyflow/react`（React Flow 12）做主画布
- TanStack Query 管服务端数据，Zustand 只管选择、视口、侧栏等临时状态
- 原生 `textarea` 做第一版纯文本区；需要行内标注时换 CodeMirror 6
- 托管 PostgreSQL/Auth/Object Storage；AI、版本落账和审批走薄服务端 API
- SVG 使用“稳定编号 + revision/hash”，Cache API 存文件，IndexedDB 存索引和 LRU 元数据
- MVP 不上 Service Worker、不上 CRDT、不上图数据库、不自研画布内核

最重要的性能结论是：

> “一本书有几千个对象”没问题；“同屏挂载几千张富 DOM 卡片和上万条关系线”才是问题。

应让画布成为领域数据的可重建投影：事实、人物、章节和版本保存在数据层；画布只渲染当前视口、当前缩放层级和当前筛选所需的卡片。

------

## 1. 画布方案对比

| 方案                         | 对本产品的适配度                                             | 几千节点结论                                                 | 实现成本                                                     | 许可与活跃度                                                 |
| ---------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **React Flow**               | **最高**。节点就是 React/HTML，适合标题、摘要、徽标、按钮、菜单和详情入口 | 几千“总对象”可以；官方只明确展示“数百节点/边”，几千张完整卡同屏不应承诺 | 低—中；自动布局、LOD 和大图优化需自己补                      | MIT；v12.11.3，更新活跃，约 38k stars、12.66M 周安装量。[官网](https://reactflow.dev/)、[发布记录](https://github.com/xyflow/xyflow/releases) |
| **tldraw**                   | 完整白板能力最强；自由绘制、触摸、旋转、媒体、协作明显领先   | 官方面向 thousands of shapes，有空间裁剪、signals、LOD；但默认每页 `maxShapesPerPage=4000`，复杂 React shape 同屏仍受 DOM 限制 | 中—高；领域卡片要写 ShapeUtil、迁移、bindings、工具状态机    | **生产商用必须购买许可证**；v5.3.0，更新密集。[性能](https://tldraw.dev/sdk-features/performance)、[选项](https://tldraw.dev/sdk-features/options) |
| **Konva**                    | 适合图片编辑、标注、版式，不太适合富卡片工作台               | 官方有 10k/20k 圆点示例，但只是简单 Canvas 图元，不能外推到多行文字和菜单卡片 | 高；文本编辑、DOM 表单、a11y、关系图语义基本都要自建         | MIT；v10.3.0，稳定活跃。[20k 示例](https://konvajs.org/docs/sandbox/20000_Nodes.html)、[性能指南](https://konvajs.org/docs/performance/All_Performance_Tips.html) |
| **PixiJS**                   | 适合海量精灵、动画、GPU 数据可视化；离编辑器最远             | 简单图元吞吐量最高，但富卡片、输入框、可访问性和排版不属于其性能模型 | **很高**；还要管理纹理、GPU 内存、命中和 DOM 覆盖层          | MIT；v8.19.0，成熟活跃。[性能指南](https://pixijs.com/8.x/guides/concepts/performance-tips)、[发布记录](https://github.com/pixijs/pixijs/releases) |
| **Excalidraw 底层**          | 适合直接嵌入手绘白板，不适合领域卡片平台                     | 社区报告约 4k–8k 尚可、再往上明显下降；仍有全场景 O(N) 优化议题 | 嵌入低，改造成自定义卡片内核很高；缺少稳定的自定义 element 类型 | MIT；v0.18.1，主仓活跃但 npm 正式版较慢。[自定义元素问题](https://github.com/excalidraw/excalidraw/issues/4957)、[大场景性能讨论](https://github.com/excalidraw/excalidraw/issues/10063) |
| **自研 DOM + CSS transform** | HTML 卡片天然，但只是获得了一个“能移动的 div”                | 显式二维裁剪后可以容纳几千总对象；几千复杂 DOM 同屏仍不现实  | **长期最高**；框选、吸附、触摸、撤销、边路由、空间索引、剪贴板都要养 | 自有代码无 SDK 费，但社区和维护全部由团队承担                |

### 推荐顺序

1. **React Flow：首选。**
2. **tldraw：只有自由白板本身属于核心卖点时选。**
3. 自研 DOM：仅当交互被严格限制成固定泳道/看板，而不是任意关系图。
4. Konva：图片和视觉编辑器。
5. Excalidraw：手绘草图板。
6. PixiJS：海量简化图元或未来独立的全书鸟瞰层。

### tldraw 许可证变化

这是本次调查里最需要注意的风险：

- 自 SDK 4.0（2025-09-18）起，生产部署必须提供有效 license key。
- 开发环境免费；trial 为 100 天。
- Hobby 仅供非商业用途且保留水印。
- Commercial 为年度许可、销售询价、value-based pricing；目前没有公开固定金额。
- v5.3 的 comments/collaboration 相关包还属于单独许可的 premium 模块。
- 旧的 MIT `tldraw-v1` 已在 2024 年归档，不再维护，不能作为新产品的长期地基。

来源：[4.0 许可变更公告](https://tldraw.dev/blog/tldraw-sdk-4-0)、[现行许可证说明](https://tldraw.dev/community/license)、[价格页](https://tldraw.dev/pricing)、[旧版归档](https://github.com/tldraw/tldraw-v1)。

### React Flow 商用成本

React Flow 核心为 MIT，可免费商用。默认有角落 attribution；官方明确承认 MIT 下不能法律强制保留，但其政策是“不隐藏无需订阅，隐藏请订阅”。当前 Pro Starter 为 **$169/月**，Professional 为 **$289/月**，主要提供示例、优先 issue 和支持，不是生产运行许可证。[归因政策](https://reactflow.dev/api-reference/types/pro-options)、[Pro 价格](https://reactflow.dev/pro)。

------

## 2. 几千对象的正确性能设计

### 数据和渲染必须分层

建议区分：

| 层           | 内容                                              |
| ------------ | ------------------------------------------------- |
| 领域真值     | 章节、人物、事实句、关系、版本、批准状态          |
| 画布布局     | `view_id / object_id / x / y / w / h / collapsed` |
| 当前渲染投影 | 当前视口 + overscan + 当前 LOD + 选中/拖拽对象    |
| 详情数据     | 点开卡片后再取正文、证据、历史和操作              |

不要把每条事实句永久做成一张卡。远景显示卷/故事线/章节簇，近景或详情面板才展开事实。

### 建议的三档 LOD

- 远景：只显示章节簇、故事线和数量；隐藏正文、端口和普通关系。
- 中景：章节标题、状态、人物头像、关键关系。
- 近景：摘要、标签、按钮、连接点和细节。

拖拽或缩放过程中使用稳定档位，结束后再切换，避免全部卡片反复重排。

### 具体实践

- 元数据可一次加载几千条；卡片正文、历史和素材按需加载。
- 用 R-tree/quadtree 做视口查询，四周保留半屏到一屏 overscan。
- 选中、编辑和正在拖拽的卡片暂不裁掉。
- React Flow 的 `onlyRenderVisibleElements` 必须压测后再开，官方说明它本身也有计算成本。
- 卡片使用 `React.memo`，保持 `nodeTypes`、回调和配置对象稳定。
- 卡片只订阅自己的数据；不要让所有卡订阅完整 `nodes/edges/selection`。
- 拖拽坐标由画布内部高频更新，`dragEnd` 再提交服务器。
- 自动布局、聚类、避障和全文分析放 Web Worker；DOM/SVG 画布本身不能搬进 Worker。
- 远景聚合关系线；只显示视口内或选中节点相关的边。关系线通常比节点更早成为瓶颈。

这些方向与 [React Flow 性能指南](https://reactflow.dev/learn/advanced-use/performance)、[tldraw 裁剪机制](https://tldraw.dev/sdk-features/performance)一致。

### MVP 压测门槛

不要拿圆点 demo 验收。用真实卡片测试：

- 总对象：1,000 / 3,000 / 5,000
- 同屏卡片：100 / 300 / 800
- 每节点关系：2 / 5 / 10
- 操作：冷启动、平移、缩放、框选、拖动、展开详情、单卡更新
- 卡片必须包含真实中文、状态、图标和菜单

建议把“100–300 张完整卡片同屏流畅、800 张简化占位可用”作为第一版工程目标，而不是宣称“支持 5,000 张完整卡片同屏”。具体 FPS 门槛应在目标中端设备上确定。

------

## 3. SVG 本地缓存

### 推荐组合

| 技术            | 应放什么                                                     |
| --------------- | ------------------------------------------------------------ |
| 普通 HTTP 缓存  | 公共 SVG 素材包、字体、带 hash 的静态资源                    |
| Cache API       | 项目生成的 SVG、历史 revision、需要显式删除和 LRU 管理的 Response |
| IndexedDB/Dexie | `assetId → revision/hash/url` 映射、大小、最后访问时间、草稿和同步 outbox |
| Service Worker  | 仅负责拦截请求和离线策略；它本身不是存储系统                 |

[Cache API](https://developer.mozilla.org/en-US/docs/Web/API/Cache)面向 Request/Response；[IndexedDB](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API)适合可索引的结构化记录；[Service Worker](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers)只是网络策略层。

建议 URL 使用：

```text
/assets/{projectId}/{assetId}/{revision}-{sha256}.svg
```

不要原地覆盖：

```text
/assets/character-023.svg
```

否则 CDN、HTTP 缓存和 Service Worker 都可能长期拿到旧内容。

### MVP 是否需要 Service Worker

**不建议第一版上 Service Worker。**

应用代码本身就可以读写 Cache API：

1. 用 IndexedDB 找到逻辑编号对应的 revision URL。
2. `cache.match(url)`。
3. 缺失时联网下载、校验状态和 `Content-Type`。
4. 先写 Cache API，再更新 IndexedDB manifest。
5. 后台清理孤儿版本和超出预算的 LRU 项。

等产品正式承诺“整本书离线可用”时，再用 Workbox 增加：

- hash SVG：`CacheFirst`
- manifest/API：`NetworkFirst` 或 `StaleWhileRevalidate`
- `maxEntries`、`maxAgeSeconds` 和离线包管理

参考：[Workbox 缓存策略](https://developer.chrome.com/docs/workbox/modules/workbox-strategies)、[自动过期管理](https://developer.chrome.com/docs/workbox/modules/workbox-expiration)。

### 两条必须写进施工合同的规则

- 浏览器存储是 best-effort，可能被清理；作者批准的 SVG、正文和历史版本不能只存在本地缓存。可参考 [浏览器存储配额与清理规则](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria)。
- 缓存按 `tenant/user/project` 隔离；退出登录、删除项目或账户时，同时删除相应 Cache API 条目、IndexedDB manifest、草稿和 outbox。普通 HTTP 缓存不能被 JS 精确枚举，因此私有项目素材更适合显式 Cache API。

------

## 4. 整体技术栈建议

| 层               | MVP 推荐                                                     |
| ---------------- | ------------------------------------------------------------ |
| 前端             | React 19 + TypeScript + [Vite 8](https://vite.dev/blog/announcing-vite8) |
| 路由/UI          | React Router；选择团队熟悉的组件库，不自研 Design System     |
| 画布             | `@xyflow/react` 12.x                                         |
| 服务端数据       | TanStack Query                                               |
| 临时 UI/画布状态 | Zustand，仅保存视口、选择、侧栏和交互状态                    |
| 本地持久         | IndexedDB + Dexie                                            |
| 写作区           | 原生 textarea；预留 Editor Adapter                           |
| 后端基础设施     | 托管 PostgreSQL/Auth/Object Storage，例如 Supabase           |
| 业务服务         | 薄 FastAPI 服务负责 AI 密钥、真值写入、批准、回滚和版本事务  |
| 后台任务         | 独立 Python worker；先用 PostgreSQL jobs/outbox，吞吐上来再引 Redis/Celery |
| 聊天和任务进度   | SSE；只有实时多人协作才上 WebSocket                          |
| 同步             | `revision/base_revision + idempotency_key + outbox`          |
| 可观测性         | Sentry/OpenTelemetry、结构化日志、画布可见节点数和帧耗时指标 |

状态边界尤其重要：

- TanStack Query：章节、事实、人物、关系、历史等服务器数据。
- Zustand：选中卡片、缩放、侧栏、当前工具。
- React Flow：拖拽过程中的高频画布状态。
- IndexedDB：未同步草稿、缓存 manifest、离线 outbox。
- PostgreSQL：最终真值和版本。

不要让同一份完整节点数组同时由 React state、Zustand、React Flow 和 TanStack Query 各保存一份。

数据库用普通关系表即可：

```text
books
story_objects
relations
revisions
canvas_layouts
assets
jobs
```

稳定查询字段做普通列和 B-tree 索引；各类卡片少量差异字段放 `jsonb`。PostgreSQL 原生支持 JSONB 和 GIN 索引，几千个对象远不需要 Neo4j。[PostgreSQL JSONB](https://www.postgresql.org/docs/current/datatype-json.html)。

MVP 也不建议上 Yjs/CRDT。当前真正需要的是对象级版本、审批和可解释历史；多人同时编辑出现后，再把 CRDT 限定在正文草稿或实时画布，不要让它替代正式事实账。

------

## 5. 纯文本写作区

| 方案              | 适合程度                                             | 建议                                |
| ----------------- | ---------------------------------------------------- | ----------------------------------- |
| **原生 textarea** | 纯文本、字数统计、自动保存、外置对照面板             | **MVP 首选**                        |
| **CodeMirror 6**  | 行内标记、问题波浪线、点击证据跳转、长文本、差异合并 | 出现这些需求时升级                  |
| ProseMirror       | 标题、列表、批注、嵌入块等真正富文本                 | 当前明显过度设计                    |
| Slate             | 高度自定义 React 富文本树                            | beta/API 变化与维护成本不适合小团队 |

`textarea` 已经处理中文输入法、选择、撤销、拼写和无障碍。[MDN textarea](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/textarea)。

建议：

- 输入状态隔离在编辑区内，不让每次按键触发画布更新。
- 0.8–1.5 秒空闲后保存本地草稿和服务器。
- 监听 `compositionstart/compositionend`，不要在中文拼音组合阶段运行自动改写。
- 数据库始终只保存纯字符串和独立 anchor；不要保存某个编辑器的内部文档树。

如果 MVP 首日就要求“原文范围内直接画问题标记、点击事实跳到字符区间”，直接用 CodeMirror 6。它只渲染视口附近内容，适合长文和 decorations。[CodeMirror 架构指南](https://codemirror.net/docs/guide/)、[API 参考](https://codemirror.net/docs/ref/)。

------

## 6. 值得参考的开源架构

| 项目                                                     | 借什么                                            | 许可提醒                                       |
| -------------------------------------------------------- | ------------------------------------------------- | ---------------------------------------------- |
| [AFFiNE](https://github.com/toeverything/AFFiNE)         | 文档/画布共享领域对象、package 边界、本地状态分层 | 社区版以 MIT 为主，具体包仍需核对              |
| [BlockSuite](https://github.com/toeverything/blocksuite) | PageEditor 与 EdgelessEditor 共用内容模型         | MPL-2.0；仍在快速演进，不建议直接作为 MVP 内核 |
| [Excalidraw](https://github.com/excalidraw/excalidraw)   | 场景序列化、导入导出、应用与可嵌入 package 分离   | MIT                                            |
| [SiYuan](https://github.com/siyuan-note/siyuan)          | 稳定块 ID、前端/内核分离、块级引用                | AGPL-3.0，闭源 SaaS 不应直接复制代码           |
| [AppFlowy](https://github.com/AppFlowy-IO/AppFlowy)      | 本地数据库、同步层、云端边界                      | AGPL-3.0；Flutter/Rust 架构不适合直接照搬      |

最值得借的是“一份领域数据，多种投影视图”。最不该照搬的是 AFFiNE/AppFlowy 的全套 CRDT、Rust 本地数据库、桌面端和多人协作复杂度。

------

## 最终 MVP 决策

选 **React Flow**，同时给自己保留两个逃生口：

1. 领域对象不依赖 React Flow 类型，`canvas_layouts` 只保存投影位置。
2. 如果以后关系线成为瓶颈，可把边层换成 Canvas/WebGL，而 HTML 卡片继续留在 React Flow/DOM。
3. 如果产品后来把自由绘制、触摸白板和实时协作提升为核心，再重新评估 tldraw 商业许可。
4. 如果只是需要十万级全书概览，新增 PixiJS 低细节鸟瞰视图，不要因此推倒主工作台。

许可证与页面价格查证日期：**2026-08-13**。价格可能变化；tldraw 商用条款和 AGPL/MPL 代码复用应在上线前做一次正式法律审查。

来源：ChatGPT