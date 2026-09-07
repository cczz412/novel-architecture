# 外部正文首次接纳

把 M1 已保存、当前用途已确认的外部章节，原样接成 C11 首版和 C1 当前章节。成功只表示章节来源和版本已经落盘，不表示已抽取或确认事实。

入口是 `mvp.external_chapter_admission_workspace`，只接受已绑定作者与项目的 `AuthorWorkspace`。不接受调用方塞入正文、路径、作者号或自报车道。真实身份仍由工作区句柄提供；动作中的 `actor` 表示动作种类。

## 读入与写出

前置是 `ingest_workspace.persist_m1_result` 已保存的当前 M1 结果，以及同项目当前上传清单引用的不可变原件。预览与提交都从 `load_persisted_m1_snapshot` 取得一致输入，再通过 M1 原有格式／解码器逐字复验父来源。

本版接收直接上传的文本材料。ZIP／DOCX 派生文本不冒充其原上传 bytes，缺少直接父来源时拒绝。只接一个已划定的 C10 `CONFIRMED / CHAPTER` 材料片段，按当前 identity revision 引用；不改它的声明、修订历史、材料号或源文件号。同源 M1 材料分区必须精确覆盖原文，不允许重叠或缺口。

正文是该材料的完整精确区间，标题行、换行、首尾空白都保留。不是旧 M1 已剥离标题的 C1 v0 文本，也不借旧章节号冒充本次稳定编号。一个材料含多章时返回 `EXTERNAL_MATERIAL_REQUIRES_CHAPTER_SPLIT`；调用方应在 M1 明确划定各章片段。一个原上传可以包含多个已分别划定的章节材料，它们共用父来源。

六个既有逻辑键一次提交：

| 逻辑键 | 内容 |
|---|---|
| `chapter_sources` | 已核验原 bytes、精确解码文本、原上传回执及 `EXTERNAL_UPLOAD` 来源 |
| `chapter_materials` | 原 C10 身份记录，包括其完整 identity revision 历史 |
| `chapter_revisions` | 新 stable chapter_id 的 C11 INITIAL r1；复用原编号分配器 |
| `chapters` | 与该版本逐字、摘要和标题一致的 C1 v1 |
| `chapter_index` | 同批当前章节版本引用 |
| `chapter_admission_operations` | 本次动作、请求摘要、材料身份与输入水位 |

不改 C10／C11／C1 Schema，不写事实、规划、工作稿、六本设定账或章末结算。C11 的 `actor=AUTHOR` 表示作者执行接纳动作，不表示正文由作者在本产品内写成；来源始终是外部上传。

## 调用

```python
from mvp.external_chapter_admission_workspace import (
    preview_external_chapters,
    commit_external_chapter,
    resolve_external_admission,
)

# workspace 来自已认证作者打开的项目。
preview = preview_external_chapters(workspace)
selected = preview["candidates"][0]  # 调用方已明确点名这一材料。
action = {
    "contract": "EXTERNAL_CHAPTER_ADMISSION_ACTION",
    "version": "v1",
    "operation_id": "op-external-01",
    "actor": "AUTHOR",
    "intent": "ADMIT_AS_INITIAL_CHAPTER",
    "material_unit_id": selected["material_unit_id"],
    "identity_revision_no": selected["identity_revision_no"],
    "chapter_title": selected["title"],
    "expected_m1_state": preview["m1_state"],
    "expected_next_chapter_number": preview["next_chapter_number"],
}
receipt = commit_external_chapter(workspace, action, "2026-09-07T12:00:00+08:00")
resolved = resolve_external_admission(workspace, "op-external-01")
# resolved["chapter"] 可交给现有 M2；本入口不自动抽取或确认事实。
```

动作字段必须恰好为示例中的十个字段。`operation_id` 按工作区既有规则校验；两个修订／编号字段必须为正整数，拒绝 bool；标题必须为非空、无首尾空白的字符串。`expected_m1_state` 恰含 `input_manifest` 和 `module_state`，各有正整数 `version` 及64位十六进制 `sha256`；两者版本必须一致。提交时间是带时区的 ISO 时间，与完整动作一起进入请求摘要。

预览返回材料可否接纳、原因、候选标题、字符数、来源摘要及动作所需水位，不返回正文，不写章节。不可接纳项不会因调用方补入标题变成合法输入。材料内容有多章、空白或边界冲突时，仍返回对应拒绝。

成功回执身份为 `EXTERNAL_CHAPTER_INITIAL_ADMISSION_R01`，状态为 `EXTERNAL_INITIAL_COMMITTED`，包含章节号、版本引用、材料号、材料 identity revision、来源区间、M1 输入水位及六个 owner 的工作区水位。提交前已通过现有 `external_chapter_route_tool.execute`，回执附它的只读 M2 路由结果。重开接口额外返回正式 owner 中的 C10、C11、C1 对象。`workspace_state` 是本次读回的当前水位，后续接纳后可变化；章节、材料、来源和接纳动作身份不变。

## 原子性与重放

提交复用 `AuthorWorkspace.commit_guarded`。六个章节 owner 的版本和摘要都属于预期写入水位，M1 两个键属于只读前置；提交锁内若任一变化，整次拒绝。失败不会靠清除文件伪装成零写入。

同一操作号、完整动作和提交时间重放，读回已提交结果，不再分配章节号；同操作号换请求拒绝。已接纳材料改用另一个操作号也拒绝；重新划分同源片段时，若与已接纳正文重叠，同样拒绝，不能借换材料号重复建章。并发取得同一个预期章节号时只允许一个成功，另一个必须重新读取再决定，不自动重试。

原 M1 上传清单只暴露当前上传，不能承担历史章节读取。接纳时已验证的父来源随六键事务冻结进 `chapter_sources`，以后更换 M1 批次不改旧 C10／C11／C1；重开从该冻结来源逐字回放并验证摘要。原上传回执保留出处，不要求旧回执仍出现在当前 M1 清单。外部材料重新分类、同章替换／恢复与旧 C1 迁移不属于本次 INITIAL 动作。

## 与作者工作稿共存

仍只使用一个编号分配器和一套章节 owner。首次写入外部来源时，来源容器由 `chapter-sources-v1` 显式升为 `chapter-sources-v2`，动作容器由 `chapter-admission-operations-v1` 升为 `chapter-admission-operations-v2`；既有作者来源与动作逐字段保留。材料、版本、C1 和索引形状不变。

v2 容器允许两种有区分的记录：原 `AUTHOR_WORK_DRAFT_FREEZE` 及外部 `EXTERNAL_UPLOAD`。外部来源只附不可变上传回执，不含 work_ref；外部动作不含槽位、工作稿版本或规划交棒。旧作者入口仍只回读作者动作，原 planstore 入口拒绝外部动作；后续作者工作稿继续正常分配下一章并交棒。

旧代码会拒绝 v2 容器。因此回退代码前应保留已有数据并使用理解该版本的读取代码，不能把 v2 容器改标 v1 或删除外部记录。尚无外部接纳的项目继续使用原 v1 容器。

## 主要拒绝

| 情况 | 错误 |
|---|---|
| 未保存 M1 | `M1_PERSISTED_STATE_REQUIRED` |
| M1 水位已变 | `EXTERNAL_M1_STATE_STALE` 或提交锁内 `VERSION_CONFLICT` |
| 材料不存在／重复 | `EXTERNAL_MATERIAL_NOT_FOUND`／`EXTERNAL_M1_MATERIAL_DUPLICATE` |
| 当前用途不是已确认章节 | `C10_NOT_CONFIRMED_CHAPTER` |
| 引用的材料身份版本失效 | `EXTERNAL_C10_REVISION_STALE` |
| 父来源不能从原上传精确回放 | `EXTERNAL_M1_SOURCE_REPLAY_MISMATCH` |
| 片段边界／摘要不闭合 | `EXTERNAL_MATERIAL_SPAN_INVALID`／`EXTERNAL_MATERIAL_SOURCE_MISMATCH` |
| 同一材料已经接纳 | `EXTERNAL_MATERIAL_ALREADY_ADMITTED` |
| 预期章节号失效 | `EXTERNAL_CHAPTER_ALLOCATOR_CHANGED` |
| 已有旧 C1 或缺少部分正式 owner | `CHAPTER_ADMISSION_STATE_PARTIAL` |

工作区既有鉴权、原件完整性和恢复错误原样保留；未知失败不转成成功。最小合成回归位于 `tests/test_novel_mvp_external_chapter_admission_workspace.py`，作者旧路兼容回归继续使用原首次接纳／交棒测试。真书正文及候选不进入这些测试或仓库。

来源：Codex
