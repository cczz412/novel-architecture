"""Synthetic, offline R01 stage-one kernel tests. No real permission provider."""
# Imports follow the repository's source-directory bootstrap.
# ruff: noqa: E402

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from hashlib import sha256
import json
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "novel-mvp"))
from mvp.chapter_structure_access import StructureAccessContext, StructureAccessProvider
from mvp.chapter_structure_contract import (
    CONTRACT_TYPES,
    StructureError,
    business_items,
    canonical_bytes,
    decode_request,
    digest,
    load_capacity,
    raw_digest,
    validate_native,
    validate_content,
)
from mvp.chapter_structure_workspace import (
    _StructureKernel,
    _validate_operation_history,
    apply_structure_write,
    read_structure_versions,
)
from mvp.workspace import WorkspaceRouter, _author_workspace_binding

CONFIG = ROOT / "novel-mvp/config/chapter_structure/capacity.json"


@pytest.fixture
def env(tmp_path):
    router = WorkspaceRouter(tmp_path)
    workspace = router.create_project("fixture:author", "合成作品")
    kernel = _StructureKernel(workspace, load_capacity(CONFIG))
    return router, workspace, kernel


def write(kernel, request, **overrides):
    args = dict(
        actor_ref="fixture:author",
        actor_kind="AUTHOR",
        action_grant_ref="fixture:permit",
    )
    args.update(overrides)
    return kernel._write(request, **args)


def request(kernel, action, operation_id, action_input):
    state = kernel.workspace.read("chapter_structures")
    expected = (
        {"version": 0, "sha256": None}
        if state is None
        else {k: state[k] for k in ("version", "sha256")}
    )
    return dict(
        contract="CHAPTER_STRUCTURE_WRITE_REQUEST",
        version="chapter-structure-write-v1",
        action=action,
        operation_id=operation_id,
        expected_container=expected,
        action_input=action_input,
    )


def content():
    raw = "甲收起钥匙。NEW:literal:unchanged\n乙还不知道。"
    return dict(
        contract="CHAPTER_STRUCTURE_CONTENT",
        version="chapter-structure-content-v1",
        fact_items=[
            dict(
                item_id="NEW:s:f1",
                text="甲收起钥匙。",
                source_refs=[],
                material_refs=["NEW:s:m1"],
                source_binding_refs=[],
            ),
            dict(
                item_id="NEW:s:f2",
                text="乙还不知道。",
                source_refs=[],
                material_refs=["NEW:s:m1"],
                source_binding_refs=[],
            ),
        ],
        selected_facts=[
            dict(item_ref="NEW:s:f1", seq=1, seq_basis="author_selected_order"),
            dict(item_ref="NEW:s:f2", seq=2, seq_basis="author_selected_order"),
        ],
        presentation_items=[
            dict(
                item_id="NEW:s:p1",
                text="先展示甲的动作。",
                member_refs=["NEW:s:f1"],
                material_refs=["NEW:s:m1"],
                source_binding_refs=[],
            )
        ],
        materials=[
            dict(
                material_id="NEW:s:m1",
                format="PLAIN_TEXT",
                raw_content=raw,
                raw_content_sha256=raw_digest(raw),
                submitted_by_ref={"actor_kind": "AUTHOR", "actor_id": "a_" + "0" * 32},
                received_at="2026-09-17T00:00:00Z",
                declared_origin="离线合成材料",
            )
        ],
        source_bindings=[],
        basis_refs=[],
    )


def register_create(kernel):
    register = write(
        kernel, request(kernel, "REGISTER_BRANCH", "reg", {"branch_label": "主编辑线"})
    )
    assert register["status"] == "OK", register
    create = request(
        kernel,
        "CREATE_OBJECT",
        "create",
        dict(
            branch_ref=register["result"]["branch_ref"],
            candidate_scope="s",
            new_object_ref="NEW:s:object",
            structure_content=content(),
        ),
    )
    response = write(kernel, create)
    assert response["status"] == "OK", response
    return create, response


def mutation(kernel, action, operation_id, **extra):
    obj = kernel.workspace.read("chapter_structures")["payload"]["objects"][0]
    arg = dict(
        expected_latest_ref=obj["versions"][-1]["ref"],
        expected_object_state_version=obj["object_state_version"],
        expected_selected_ref=obj["selected_ref"],
        **extra,
    )
    return request(kernel, action, operation_id, arg)


def read_request(*refs):
    return dict(
        contract="CHAPTER_STRUCTURE_READ_REQUEST",
        version="chapter-structure-read-v1",
        request_id="REQ-test",
        action="READ_PINNED",
        structure_refs=list(refs),
    )


def read(kernel, *refs):
    return kernel._read(read_request(*refs), access_basis_sha256="1" * 64)


def saved_content(kernel):
    return deepcopy(
        kernel.workspace.read("chapter_structures")["payload"]["objects"][0][
            "versions"
        ][-1]["structure_content"]
    )


def test_stage1_register_create_save_read_replay(env, tmp_path):
    _, workspace, kernel = env
    original_request, create = register_create(kernel)
    r1 = create["result"]["saved_ref"]
    assert create["container_observation"]["version"] == 2
    assert create["result"]["object_state_version"] == 1
    next_content = saved_content(kernel)
    next_content["fact_items"][0]["text"] = "甲拿出钥匙。"
    next_content["selected_facts"].reverse()
    for n, item in enumerate(next_content["selected_facts"], 1):
        item["seq"] = n
    save = write(
        kernel,
        mutation(
            kernel,
            "SAVE_VERSION",
            "save",
            candidate_scope="s2",
            structure_content=next_content,
        ),
    )
    assert save["status"] == "OK", save
    r2 = save["result"]["saved_ref"]
    assert (
        r1["rev"] == 1
        and r2["rev"] == 2
        and r1["content_sha256"] != r2["content_sha256"]
    )
    assert save["result"]["object_state_version"] == 2
    assert save["container_observation"]["version"] == 3
    before = canonical_bytes(workspace.read("chapter_structures"))
    result = read(kernel, r1)
    assert result["status"] == "OK", result
    assert result["data"]["versions"][0]["structure_ref"] == r1
    assert (
        result["data"]["versions"][0]["structure_content"]["fact_items"][0]["text"]
        == "甲收起钥匙。"
    )
    assert canonical_bytes(workspace.read("chapter_structures")) == before
    replay = write(kernel, original_request, action_grant_ref="fresh:permit")
    assert replay["replayed"] is True and replay["result"] == create["result"]
    assert replay["container_observation"]["version"] == 3
    assert (
        workspace.read("chapter_structures")["payload"]["objects"][0]["selected_ref"]
        == r2
    )
    # New router/kernel: history and idempotency are persisted, not a process cache.
    restarted = WorkspaceRouter(tmp_path).open_project(
        "fixture:author", workspace.project_id
    )
    other = _StructureKernel(restarted, load_capacity(CONFIG))
    assert read(other, r1)["data"] == result["data"]
    assert write(other, original_request)["result"] == create["result"]


def test_stage1_seq_gap_rejected(env, monkeypatch):
    _, ws, kernel = env
    register_create(kernel)
    body = saved_content(kernel)
    body["selected_facts"][1]["seq"] = 3
    assert CONTRACT_TYPES["StructureContent"].is_valid(body)
    before = deepcopy(ws.read("chapter_structures"))
    monkeypatch.setattr(
        ws,
        "commit_guarded",
        lambda *a, **k: pytest.fail("invalid sequence called commit"),
    )
    response = write(
        kernel,
        mutation(
            kernel,
            "SAVE_VERSION",
            "bad-seq",
            candidate_scope="s2",
            structure_content=body,
        ),
    )
    assert response["error"]["code"] == "SEQ_NOT_TOTAL_ORDER"
    assert response["commit_state"] == "NOT_COMMITTED"
    assert ws.read("chapter_structures") == before


def test_stage1_selected_old_then_save_next_max_and_retirement(env):
    _, ws, kernel = env
    original, first = register_create(kernel)
    r1 = first["result"]["saved_ref"]
    c = saved_content(kernel)
    c["fact_items"][0]["text"] = "第二版安排"
    second = write(
        kernel,
        mutation(
            kernel, "SAVE_VERSION", "save2", candidate_scope="s", structure_content=c
        ),
    )
    assert second["status"] == "OK"
    selected = write(
        kernel, mutation(kernel, "SELECT_VERSION", "select1", selected_ref=r1)
    )
    assert selected["result"]["latest_rev"] == 2
    c["fact_items"][0]["text"] = "第三版安排"
    third = write(
        kernel,
        mutation(
            kernel, "SAVE_VERSION", "save3", candidate_scope="s", structure_content=c
        ),
    )
    assert third["result"]["saved_ref"]["rev"] == 3
    retired = write(kernel, mutation(kernel, "RETIRE_OBJECT", "retire"))
    assert retired["result"]["lifecycle_status"] == "RETIRED"
    assert read(kernel, r1)["data"]["versions"][0]["retired_notice"] is True
    assert write(kernel, original)["result"] == first["result"]
    assert (
        write(kernel, mutation(kernel, "RETIRE_OBJECT", "retire-again"))["error"][
            "code"
        ]
        == "OBJECT_RETIRED"
    )
    assert len(ws.read("chapter_structures")["payload"]["objects"][0]["versions"]) == 3


def test_stage1_same_operation_conflicts_and_concurrency(env):
    _, ws, kernel = env
    original, first = register_create(kernel)
    with ThreadPoolExecutor(max_workers=6) as pool:
        replies = list(
            pool.map(
                lambda _: write(_StructureKernel(ws, load_capacity(CONFIG)), original),
                range(12),
            )
        )
    assert all(r["replayed"] and r["result"] == first["result"] for r in replies)
    changed = deepcopy(original)
    changed["action_input"]["structure_content"]["fact_items"][0]["text"] = "另一个请求"
    assert write(kernel, changed)["error"]["code"] == "OPERATION_ID_CONFLICT"
    assert (
        write(kernel, original, actor_ref="other:actor")["error"]["code"]
        == "OPERATION_ID_CONFLICT"
    )
    c = saved_content(kernel)
    c["fact_items"][0]["text"] = "并发版本"
    same = mutation(
        kernel, "SAVE_VERSION", "concurrent", candidate_scope="s", structure_content=c
    )
    with ThreadPoolExecutor(max_workers=6) as pool:
        replies = list(
            pool.map(
                lambda _: write(_StructureKernel(ws, load_capacity(CONFIG)), same),
                range(12),
            )
        )
    assert all(r["status"] == "OK" for r in replies), replies
    assert all(r["result"] == replies[0]["result"] for r in replies)
    assert ws.read("chapter_structures")["version"] == 3
    c["fact_items"][0]["text"] = "相互竞争"
    left = mutation(
        kernel, "SAVE_VERSION", "left", candidate_scope="s", structure_content=c
    )
    right = deepcopy(left)
    right["operation_id"] = "right"
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(
            pool.map(
                lambda req: write(_StructureKernel(ws, load_capacity(CONFIG)), req),
                [left, right],
            )
        )
    assert sorted(r["status"] for r in replies) == ["OK", "REJECTED"]
    assert ws.read("chapter_structures")["version"] == 4


def assert_io_evidence(kernel, request, response):
    """R01.2 acceptance oracle: definite state without matching real evidence fails."""
    if (
        response["error"]["code"] != "STORAGE_IO_ERROR"
        or response["commit_state"] == "UNKNOWN"
    ):
        return
    matching = [
        e
        for e in kernel._io_evidence
        if e["operation_id"] == request["operation_id"]
        and e["request_sha256"]
        == kernel._request_hash(request, "fixture:author", "AUTHOR")
        and e["commit_state"] == response["commit_state"]
    ]
    assert matching, "determinate response without this operation's evidence"
    e = matching[-1]
    if response["commit_state"] == "COMMITTED":
        assert e["observed_operation"]["operation_id"] == request["operation_id"]
        assert e["observed_operation"]["request_sha256"] == e["request_sha256"]
    else:
        assert not e["before"]["prepared_journal_exists"]
        assert e["before"] == e["after"]


@pytest.mark.parametrize(
    "fault,expected",
    [
        ("before-write", "NOT_COMMITTED"),
        ("after_prepare", "UNKNOWN"),
        ("after_pointer_swap", "COMMITTED"),
    ],
)
def test_stage1_io_commit_state_evidence(env, monkeypatch, fault, expected):
    router, ws, kernel = env
    register_create(kernel)
    c = saved_content(kernel)
    c["fact_items"][0]["text"] = "故障版本"
    req = mutation(
        kernel, "SAVE_VERSION", "fault", candidate_scope="s", structure_content=c
    )
    backend = _author_workspace_binding(ws).backend
    if fault == "before-write":

        def fail(*args, **kwargs):
            raise OSError("injected before any physical write")

        monkeypatch.setattr(backend, "_write_immutable", fail)
    else:

        def hook(point):
            if point == fault:
                raise OSError("injected fault")

        router._set_failure_hook_for_testing(hook)
    response = write(kernel, req)
    assert response["commit_state"] == expected, response
    assert response["error"]["code"] == "STORAGE_IO_ERROR"
    assert response["result"] is None and response["container_observation"] is None
    assert_io_evidence(kernel, req, response)
    if expected != "UNKNOWN":
        saved = deepcopy(kernel._io_evidence)
        kernel._io_evidence.clear()
        with pytest.raises(AssertionError):
            assert_io_evidence(kernel, req, response)
        kernel._io_evidence = saved
        kernel._io_evidence[-1]["operation_id"] = "wrong-operation"
        with pytest.raises(AssertionError):
            assert_io_evidence(kernel, req, response)


def test_stage1_io_leftover_not_reported_not_committed(env, monkeypatch):
    _, ws, kernel = env
    register_create(kernel)
    c = saved_content(kernel)
    c["fact_items"][0]["text"] = "部分写入"
    req = mutation(
        kernel, "SAVE_VERSION", "partial", candidate_scope="s", structure_content=c
    )
    backend = _author_workspace_binding(ws).backend
    original = backend._write_immutable

    def staged(*args, **kwargs):
        original(*args, **kwargs)
        raise OSError("blob exists; current has not advanced")

    monkeypatch.setattr(backend, "_write_immutable", staged)
    response = write(kernel, req)
    assert response["commit_state"] == "UNKNOWN"


def test_stage1_commit_readback_failed_remains_distinct(env, monkeypatch):
    _, ws, kernel = env
    register_create(kernel)
    c = saved_content(kernel)
    c["fact_items"][0]["text"] = "回读失败"
    req = mutation(
        kernel, "SAVE_VERSION", "readback", candidate_scope="s", structure_content=c
    )
    commit = ws.commit_guarded

    def committed(*args, **kwargs):
        receipt = commit(*args, **kwargs)

        def broken(*args, **kwargs):
            raise OSError("readback")

        monkeypatch.setattr(ws, "read_current_snapshot", broken)
        return receipt

    monkeypatch.setattr(ws, "commit_guarded", committed)
    response = write(kernel, req)
    assert response["error"]["code"] == "COMMIT_READBACK_FAILED"
    assert response["commit_state"] == "COMMITTED" and response["result"] is None


def test_stage1_provider_unbound_closed(env, monkeypatch):
    _, ws, kernel = env
    _, first = register_create(kernel)

    def forbidden(*args, **kwargs):
        pytest.fail("unbound caller probed a stored object")

    monkeypatch.setattr(ws, "read_current_snapshot", forbidden)
    r = apply_structure_write(ws, {}, {"actor_kind": "AUTHOR"}, {})
    assert r["error"]["code"] == "CAPABILITY_UNAVAILABLE"
    r = read_structure_versions(ws, {}, {}, read_request(first["result"]["saved_ref"]))
    assert r["reason_code"] == "CAPABILITY_UNAVAILABLE" and r["data"] is None
    assert all(
        r["receipt"][k] is None
        for k in (
            "author_id",
            "project_id",
            "request_sha256",
            "access_basis_sha256",
            "storage_generation",
        )
    )
    assert r["receipt"]["source_manifest"] == []
    assert r["limits"]["response_bytes"] == len(canonical_bytes(r))
    with pytest.raises(StructureError):
        StructureAccessContext()
    with pytest.raises(TypeError):
        StructureAccessProvider()


def test_stage1_read_exactness_counters_order_and_no_fallback(env):
    _, ws, kernel = env
    _, first = register_create(kernel)
    r1 = first["result"]["saved_ref"]
    c = saved_content(kernel)
    c["fact_items"][0]["text"] = "第二版"
    second = write(
        kernel,
        mutation(
            kernel, "SAVE_VERSION", "save", candidate_scope="s", structure_content=c
        ),
    )
    r2 = second["result"]["saved_ref"]
    response = read(kernel, r2, r1)
    assert [x["structure_ref"] for x in response["data"]["versions"]] == [r2, r1]
    assert [x["structure_ref"] for x in response["receipt"]["source_manifest"]] == [
        r1,
        r2,
    ]
    assert response["limits"]["business_items"] == 2 * business_items(c)
    assert response["limits"]["response_bytes"] == len(canonical_bytes(response))
    assert read(kernel, r1, r1)["reason_code"] == "INVALID_SELECTOR"
    bad = {**r1, "content_sha256": "f" * 64}
    assert read(kernel, r1, bad)["reason_code"] == "INVALID_PIN_SET"
    assert read(kernel, bad)["reason_code"] == "SHA_MISMATCH"
    assert read(kernel, {**r1, "rev": 99})["reason_code"] == "REVISION_NOT_FOUND"
    assert read(kernel)["reason_code"] == "INVALID_SELECTOR"
    assert read(kernel, *([r1] * 51))["reason_code"] == "RESULT_TOO_LARGE"
    store = ws.read("chapter_structures")
    store["payload"]["objects"][0]["versions"][0]["structure_content"]["fact_items"][0][
        "text"
    ] = "篡改"
    ws.commit(
        "corrupt",
        {"chapter_structures": store["payload"]},
        {
            "chapter_structures": {
                "version": store["version"],
                "sha256": store["sha256"],
            }
        },
    )
    assert read(kernel, r1)["reason_code"] == "SOURCE_CORRUPTED"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c["fact_items"][0].update(material_refs=["NEW:s:absent"]),
        lambda c: c["fact_items"][0].update(item_id="NEW:foreign:f1"),
        lambda c: c["materials"][0].update(material_id="NEW:s:f1"),
        lambda c: c["materials"][0].update(raw_content_sha256="0" * 64),
        lambda c: c["selected_facts"][0].update(seq=True),
    ],
)
def test_stage1_invalid_new_maps_or_materials_rejected(env, mutate):
    _, ws, kernel = env
    register_create(kernel)
    c = content()
    mutate(c)
    branch = ws.read("chapter_structures")["payload"]["branch"]["branch_id"]
    before = deepcopy(ws.read("chapter_structures"))
    req = request(
        kernel,
        "CREATE_OBJECT",
        "bad-new",
        dict(
            branch_ref=branch,
            candidate_scope="s",
            new_object_ref="NEW:s:object",
            structure_content=c,
        ),
    )
    assert write(kernel, req)["status"] == "REJECTED"
    assert ws.read("chapter_structures") == before


def test_stage1_capacity_policy_and_replay(env):
    _, ws, kernel = env
    req, first = register_create(kernel)
    kernel.capacity["owner"]["objects_max"] = 1
    duplicate = deepcopy(req)
    duplicate["operation_id"] = "new-object"
    duplicate["expected_container"] = {
        k: ws.read("chapter_structures")[k] for k in ("version", "sha256")
    }
    assert write(kernel, duplicate)["error"]["code"] == "CAPACITY_EXCEEDED"
    kernel.capacity["owner"]["write_request_max_utf8_bytes"] = 1
    assert write(kernel, req)["result"] == first["result"]
    reader = _StructureKernel(ws, load_capacity(CONFIG))
    reader.capacity["read"]["max_returned_business_items"] = 1
    response = read(reader, first["result"]["saved_ref"])
    assert response["reason_code"] == "RESULT_TOO_LARGE"
    assert response["limits"]["business_items"] == 0 and response["data"] is None


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a":1,"a":2}',
        b"\xef\xbb\xbf{}",
        b'{"a":NaN}',
        b'{"a":Infinity}',
        b'{"a":1.0}',
        b'{"a":"\\ud800"}',
        b'{"a":9007199254740992}',
        b"\xff",
    ],
)
def test_stage1_strict_json(raw):
    with pytest.raises(StructureError):
        decode_request(raw)


def test_stage1_canonical_and_raw_digests():
    assert canonical_bytes({"乙": 2, "甲": 1}) == '{"乙":2,"甲":1}\n'.encode()
    assert raw_digest("x") != digest("x")
    assert canonical_bytes({"z": "e\u0301", "a": "é"}).endswith(b"\n")
    assert decode_request('{"a":9007199254740991}')["a"] == 9007199254740991


def test_stage1_native_reference_specific_rules():
    def wrap(**changes):
        native = dict(
            source_kind="ledger_entry",
            source_contract="fixture",
            source_contract_version="v1",
            logical_ledger_name="人物账",
            object_type="fixture",
            stable_id="fixture",
            revision="workspace-facts-v1",
            logical_content_sha256="0" * 64,
            role="basis",
            binding_mode="recorded_pin",
            retired_notice=False,
            compiler_version=None,
            input_basis_sha256=None,
        )
        return dict(ref_kind="LEDGER_SOURCE_ITEM", native_ref={**native, **changes})

    validate_native(wrap())
    validate_native(
        wrap(source_kind="directory_capability_snapshot", logical_ledger_name=None)
    )
    validate_native(wrap(source_kind="chapter_revision", logical_ledger_name="章节账"))
    validate_native(
        wrap(
            source_kind="projection", compiler_version="v1", input_basis_sha256="1" * 64
        )
    )
    for bad in [
        wrap(logical_ledger_name=None),
        wrap(source_kind="chapter_revision"),
        wrap(source_kind="directory_capability_snapshot"),
        wrap(source_kind="projection"),
        wrap(compiler_version="v1"),
    ]:
        assert CONTRACT_TYPES["NativeSourceRef"].is_valid(bad)
        with pytest.raises(StructureError):
            validate_native(bad)


def test_stage1_all_declared_contract_types_valid():
    for validator in CONTRACT_TYPES.values():
        validator.check_schema(validator.schema)


def test_stage1_field_catalog_mapping():
    mapping = json.loads(
        (ROOT / "novel-mvp/contracts/CHAPTER_STRUCTURE_FIELD_MAP.json").read_text()
    )
    schema_path = ROOT / "novel-mvp/contracts/CHAPTER_STRUCTURE_CONTRACT.schema.json"
    schema = json.loads(schema_path.read_bytes())
    assert mapping["count"] == len(mapping["fields"]) == 284
    assert [x["row_id"] for x in mapping["fields"]] == [
        f"NC{n:03d}" for n in range(1, 285)
    ]
    assert (
        mapping["effective_schema_sha256"]
        == sha256(schema_path.read_bytes()).hexdigest()
    )
    for row in mapping["fields"]:
        node = schema
        for part in row["schema_pointer"].removeprefix("#/").split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            node = node[int(part)] if isinstance(node, list) else node[part]
        assert isinstance(node, dict)
        assert row["definition"] in CONTRACT_TYPES
    grant_rows = [r for r in mapping["fields"] if r["definition"] == "ActionGrant"]
    assert grant_rows and all(
        r["scope"] == "SHAPE_ONLY_REAL_PROVIDER_UNBOUND" for r in grant_rows
    )


def test_stage1_raw_new_literals_unchanged_and_map_typed(env):
    _, _, kernel = env
    req, result = register_create(kernel)
    data = saved_content(kernel)
    assert (
        data["materials"][0]["raw_content"] == content()["materials"][0]["raw_content"]
    )
    rows = result["result"]["local_id_map"]
    assert [r["placeholder"] for r in rows] == sorted(r["placeholder"] for r in rows)
    assert len({r["resolved_id"] for r in rows}) == len(rows) == 5
    old = deepcopy(data)
    data["fact_items"].append(
        dict(
            item_id="NEW:add:f3",
            text="新候选",
            source_refs=[],
            material_refs=[old["materials"][0]["material_id"]],
            source_binding_refs=[],
        )
    )
    response = write(
        kernel,
        mutation(
            kernel,
            "SAVE_VERSION",
            "more",
            candidate_scope="add",
            structure_content=data,
        ),
    )
    assert response["status"] == "OK"
    assert len(response["result"]["local_id_map"]) == 1
    new = saved_content(kernel)
    assert new["fact_items"][:2] == old["fact_items"]
    assert write(kernel, req)["result"] == result["result"]


@pytest.mark.parametrize(
    "limit",
    [
        "versions_per_object_max",
        "committed_operations_max",
        "container_max_utf8_bytes",
        "version_record_max_utf8_bytes",
        "write_request_max_utf8_bytes",
        "write_response_max_utf8_bytes",
        "business_items_per_version_max",
    ],
)
def test_stage1_each_save_capacity_refuses_without_mutation(env, limit, monkeypatch):
    _, ws, kernel = env
    register_create(kernel)
    c = saved_content(kernel)
    c["fact_items"][0]["text"] = "不同安排"
    req = mutation(
        kernel, "SAVE_VERSION", "limited", candidate_scope="s", structure_content=c
    )
    before = deepcopy(ws.read("chapter_structures"))
    kernel.capacity["owner"][limit] = 1
    monkeypatch.setattr(
        ws, "commit_guarded", lambda *a, **k: pytest.fail("over-limit commit")
    )
    r = write(kernel, req)
    assert r["error"]["code"] == "CAPACITY_EXCEEDED", r
    assert ws.read("chapter_structures") == before


def test_stage1_mapping_and_read_byte_limits(env):
    _, ws, kernel = env
    r = write(
        kernel, request(kernel, "REGISTER_BRANCH", "reg", {"branch_label": "main"})
    )
    req = request(
        kernel,
        "CREATE_OBJECT",
        "create",
        dict(
            branch_ref=r["result"]["branch_ref"],
            candidate_scope="s",
            new_object_ref="NEW:s:object",
            structure_content=content(),
        ),
    )
    kernel.capacity["max_new_id_mappings_per_operation"] = 4
    assert write(kernel, req)["error"]["code"] == "CAPACITY_EXCEEDED"
    assert ws.read("chapter_structures")["version"] == 1
    kernel.capacity["max_new_id_mappings_per_operation"] = 5
    saved = write(kernel, req)
    assert saved["status"] == "OK"
    kernel.capacity["read"]["max_response_bytes"] = 1500
    result = read(kernel, saved["result"]["saved_ref"])
    assert result["reason_code"] == "RESULT_TOO_LARGE" and result["data"] is None
    assert 0 < result["limits"]["response_bytes"] <= 1500


def test_stage1_unchanged_save_and_selection_do_not_create_records(env):
    _, ws, kernel = env
    _, r = register_create(kernel)
    before = deepcopy(ws.read("chapter_structures"))
    save = mutation(
        kernel,
        "SAVE_VERSION",
        "unchanged",
        candidate_scope="s",
        structure_content=saved_content(kernel),
    )
    assert write(kernel, save)["error"]["code"] == "CONTENT_UNCHANGED"
    select = mutation(
        kernel,
        "SELECT_VERSION",
        "same-selection",
        selected_ref=r["result"]["saved_ref"],
    )
    assert write(kernel, select)["error"]["code"] == "SELECTION_UNCHANGED"
    assert ws.read("chapter_structures") == before


def test_stage1_capacity_config_missing_is_not_defaulted(tmp_path):
    with pytest.raises(StructureError, match="CAPACITY_POLICY_UNAVAILABLE"):
        load_capacity(tmp_path / "absent.json")
    policy = load_capacity(CONFIG)
    policy["owner"]["objects_max"] = True
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(policy))
    with pytest.raises(StructureError, match="CAPACITY_POLICY_UNAVAILABLE"):
        load_capacity(path)
    with pytest.raises(StructureError, match="CAPACITY_POLICY_UNAVAILABLE"):
        _StructureKernel(None, {})
    broken = load_capacity(CONFIG)
    broken["owner"] = []
    with pytest.raises(StructureError, match="CAPACITY_POLICY_UNAVAILABLE"):
        _StructureKernel(None, broken)


def test_stage1_post_fault_recovery_preserves_old_version(env):
    router, ws, kernel = env
    original, first = register_create(kernel)
    c = saved_content(kernel)
    c["fact_items"][0]["text"] = "待恢复"
    req = mutation(
        kernel, "SAVE_VERSION", "recover-op", candidate_scope="s", structure_content=c
    )

    def fail(point):
        if point == "after_pointer_swap":
            raise OSError("synthetic lost response")

    router._set_failure_hook_for_testing(fail)
    response = write(kernel, req)
    assert response["commit_state"] == "COMMITTED"
    assert_io_evidence(kernel, req, response)
    router._set_failure_hook_for_testing(None)
    ws.recover()
    replay = write(kernel, req)
    assert replay["status"] == "OK" and replay["replayed"]
    assert replay["result"]["saved_ref"]["rev"] == 2
    assert read(kernel, first["result"]["saved_ref"])["status"] == "OK"
    assert write(kernel, original)["result"] == first["result"]


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda store: store["operations"][-1]["result"].update(latest_rev=2),
        lambda store: store["branch"].update(created_operation_id="create"),
        lambda store: store["operations"][-1]["result"]["local_id_map"].pop(),
        lambda store: store["operations"][-1]["result"].update(
            lifecycle_status="RETIRED"
        ),
    ],
)
def test_stage1_object_operation_inconsistency_rejected(env, corrupt):
    _, ws, kernel = env
    _, first = register_create(kernel)
    state = ws.read("chapter_structures")
    corrupt(state["payload"])
    with pytest.raises(StructureError):
        _validate_operation_history(state["payload"])
    # Even a backend-valid envelope cannot make inconsistent business data valid.
    ws.commit(
        "corrupt-operation",
        {"chapter_structures": state["payload"]},
        {"chapter_structures": {k: state[k] for k in ("version", "sha256")}},
    )
    result = read(kernel, first["result"]["saved_ref"])
    assert result["reason_code"] == "SOURCE_CORRUPTED"
    assert result["data"] is None


def test_stage1_system_action_is_not_author_attestation(env):
    _, _, kernel = env
    register_create(kernel)
    body = saved_content(kernel)
    material_id = body["materials"][0]["material_id"]
    body["source_bindings"] = [
        dict(
            binding_id="sb_" + "f" * 32,
            source_kind="AUTHOR_DECLARATION",
            source_ref=None,
            material_refs=[material_id],
            resolution_status="UNRESOLVED",
            unresolved_reasons=["OWNER_BINDING_UNAVAILABLE"],
            details=dict(
                statement_material_ref=material_id,
                author_ref={"actor_kind": "AUTHOR", "actor_id": "a_" + "0" * 32},
                accepted_span_refs=[],
                scope_text=None,
                author_attestation_ref=dict(
                    kind="OWNER_ACTION",
                    action_contract="fixture",
                    action_contract_version="v1",
                    action_id="fixture:action",
                    actor="SYSTEM",
                    action_sha256="0" * 64,
                ),
            ),
        )
    ]
    assert CONTRACT_TYPES["StructureContent"].is_valid(body)
    with pytest.raises(StructureError):
        validate_content(body)
