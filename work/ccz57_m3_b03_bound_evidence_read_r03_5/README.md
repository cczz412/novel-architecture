# CCZ-57 M3 B-03 r03.5：沿已绑定 evidence 的受控读取

这块只解决一件事：作者点开一条候选事实时，系统只返回这条事实已经绑定的逐字 evidence。它不是正文浏览器；调用方不能提交字符范围、开始或结束位置、字符上限，也不会拿相邻正文凑上下文。

## 入口和结果

入口是 `subject + evidence_binding + purpose`。候选事实 subject 同时绑住 CandidateVersion、LineageLocator、EvidenceLocator、item hash、章节修订、来源代次和 B-02 上下文。任何一项漂移，写入和读取都在发布前失败。

正式账本条目没有 adapter 时固定失败关闭，错误为 `B03_FORMAL_LEDGER_ADAPTER_REQUIRED`；不会猜字段或读取来源。

SourceSlice 的内容只等于 `CandidateVersion.items[].evidence`。同一句在责任段里出现多次时，binding 保留全部内部 UTF-8 byte 匹配位置，但产品入口不暴露或接受位置参数。

## 记录、权限和清除

持久原件共 7 类：请求、同意、同意生命周期、授权、授权生命周期、SourceSlice、留存回执。每类各有一个 writer；再加一个不落盘的 current-state projector，一共 8 个固定角色。

同意和授权是两条独立 lifecycle。同意逐字绑定 Request、政策版本和用途，不能拿旧同意换用途或套到另一版政策。撤回、替代、到期会在同一事务里禁止读取、清除明文、移除 SourceSlice core，并写入 tombstone 和留存回执。

B03Service 在准入时把上游 context 和 policy 封进私有快照；公开属性只是可修改的副本。可信时间链保存在事务存储里，所有实例每次都读取同一份唯一 current head，旧实例不能继续重放旧 head。服务不公开 store、明文路径或可替换的授权回调；存储内部固定调用已注册的类型校验和当前状态校验。tombstone 后固定返回 `TOMBSTONED_CONTENT_UNAVAILABLE`。

明文不写入不可变状态库，只进入单独的短期内容库。两个库使用同盘 SQLite rollback journal 和 `synchronous=FULL`：SourceSlice 发布、生命周期撤回、权威时间推进、明文清除、tombstone 和留存回执都按一个跨库事务提交。进程中断时由事务日志恢复，不靠事后删除半成品；短期内容库启用 `secure_delete`。清除后 SourceSlice core 和明文都不存在，只保留 5-key tombstone：SourceSlice RecordRef、evidence binding hash、evidence hash、`content_bytes_retained=false` 和不可恢复状态。

运行根只允许系统临时目录或 B-03 唯一写集。根目录和两个数据库文件遇到符号链接会在建库前拒绝，不能把明文带到写集外。

## 离线复验

```bash
uv run --locked python -m py_compile work/ccz57_m3_b03_bound_evidence_read_r03_5/*.py
PYTHONDONTWRITEBYTECODE=1 uv run --locked pytest -q -p no:cacheprovider work/ccz57_m3_b03_bound_evidence_read_r03_5/test_b03_bound_evidence_read.py
uv run --locked ruff check work/ccz57_m3_b03_bound_evidence_read_r03_5
uv run --locked python work/ccz57_m3_b03_bound_evidence_read_r03_5/self_check.py
```

夹具只读 B-01/B-02 的合成接口；没有模型 API、网络、真实小说读取、B-04 Patch 或正式账本写入。

来源：Codex
