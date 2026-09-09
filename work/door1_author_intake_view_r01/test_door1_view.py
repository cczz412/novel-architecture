"""正常画面、两条票面失败路径，以及越界／坏标记等回归测试。"""

from __future__ import annotations

import ast
import hashlib
import json
import shutil
import subprocess
import sys
from copy import deepcopy
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
for path in (REPO, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import build_view as builder  # noqa: E402
import marks_sidecar as marks  # noqa: E402
from view_render import SCRIPT, render_page, safe_json  # noqa: E402


@pytest.fixture
def fixture():
    return builder.load_fixture("北塔夹具", 1)


@pytest.fixture
def proof(fixture):
    """这是投影单测替身，不是 CandidateAuthorityStore 联调回执。"""
    # 直接取包内冻结五条候选，避免单测偷偷换成另一章。
    source = (
        REPO / "work/ccz142_human_card_vertical_wire_r01/vertical_wire.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    raw_items = next(
        ast.literal_eval(n.value)
        for n in tree.body
        if isinstance(n, ast.AnnAssign)
        and isinstance(n.target, ast.Name)
        and n.target.id == "FROZEN_HANDOFF_ITEMS"
    )
    known_locations = {
        "甲走进北塔。": [
            {"seg": 1, "start_byte": 0, "end_byte": 18},
            {"seg": 1, "start_byte": 39, "end_byte": 57},
        ],
        "甲拿起铜钥匙。": [{"seg": 1, "start_byte": 18, "end_byte": 39}],
    }
    kinds = {"已发生": "已发生", "推测": "传闻／怀疑", "误信": "误信", "计划": "未证实"}
    items = []
    for index, raw in enumerate(raw_items):
        locations = deepcopy(known_locations[raw["evidence"]])
        items.append(
            {
                **raw,
                "stable_item_id": f"lin_unit_test_{index + 1:03}",
                "match_locations": locations,
                "source_location": "；".join(
                    f"责任段 {p['seg']}，字节 {p['start_byte']}–{p['end_byte']}"
                    for p in locations
                ),
                "kind": kinds[raw["status"]],
            }
        )
    return {
        "status": "READ_OK",
        "gaps": [],
        "pointer_key": "fixture-unit-test-pointer",
        "identity": {
            "pointer_namespace": "FIXTURE_ONLY",
            "candidate_access": "POLICY_FIXTURE_READ_ONLY",
            "product_adopted": False,
        },
        "result_scope": {
            "book_title": "未提供",
            "project_scope_id": builder.PROJECT_SCOPE_ID,
            "chapter_id": "synthetic-chapter-001",
            "revision_no": 7,
            "revision_text_sha256": fixture["text_sha256"],
            "responsibility_segment": 1,
        },
        "human_card": {"items": items},
    }


@pytest.fixture
def model(fixture, proof):
    return builder.project_view(proof, fixture)


@pytest.fixture
def ids(model):
    return (
        {s["id"] for s in model["sentences"]},
        {c["id"] for c in model["candidates"]},
    )


def snapshot(root):
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }


def page_model(page):
    text = page.split('<script id="door1-data" type="application/json">', 1)[1].split(
        "</script>", 1
    )[0]
    return json.loads(text)


def assert_gap(call, code):
    with pytest.raises(builder.ViewGap) as error:
        call()
    assert error.value.code == code


def test_fixture_is_frozen_chapter_and_two_segments(fixture):
    assert fixture["text"] == "甲走进北塔。甲拿起铜钥匙。甲走进北塔。乙停在门外。"
    assert [s["start_byte"] for s in fixture["segments"]] == [0, 57]
    assert fixture["revision"]["revision_no"] == 7


@pytest.mark.parametrize(
    "book,chapter",
    [("别的书", 1), ("北塔夹具", 2), ("北塔夹具", True), ("北塔夹具 ", 1)],
)
def test_unreleased_never_reads_text(monkeypatch, book, chapter):
    def forbidden(*args, **kwargs):
        pytest.fail("没放行的书不该读文件")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    assert_gap(lambda: builder.load_fixture(book, chapter), "GAP_NOT_RELEASED")


def test_fixture_file_changed_is_closed(monkeypatch):
    original = Path.read_bytes
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda p: (
            b"different fixture" if p.name == "synthetic_chapter.txt" else original(p)
        ),
    )
    assert_gap(lambda: builder.load_fixture("北塔夹具", 1), "GAP_FIXTURE_MISMATCH")


@pytest.mark.parametrize(
    "text",
    [
        "甲。甲。乙！",
        "甲说：“好！”乙走了。",
        "无句末标点",
        "甲\n乙",
        "甲😀。乙？",
        "甲。\n\n乙。",
    ],
)
def test_sentence_split_preserves_text_and_utf8_offsets(text):
    result = builder.split_sentences(text)
    assert "".join(s["text"] for s in result) == text
    raw = text.encode()
    assert all(
        raw[s["start_byte"] : s["end_byte"]].decode() == s["text"] for s in result
    )
    assert len({s["id"] for s in result}) == len(result)


def test_repeated_quote_uses_both_real_locations_and_leaves_fourth_missing(model):
    one, two, three, four = model["sentences"]
    assert model["candidates"][0]["source_ids"] == [one["id"], three["id"]]
    assert model["candidates"][1]["source_ids"] == [two["id"]]
    assert four["possibly_missing"] and not four["candidate_ids"]
    assert model["missing_count"] == 1
    assert len(one["candidate_ids"]) == 3


def test_missing_source_location_never_guesses_even_with_exact_quote(fixture, proof):
    proof["human_card"]["items"][0].pop("source_location")
    result = builder.project_view(proof, fixture)
    item = result["candidates"][0]
    assert item["source_ids"] == [] and item["source_message"] == "来源没对上"
    assert all(item["id"] not in s["candidate_ids"] for s in result["sentences"])


@pytest.mark.parametrize(
    "change",
    [
        {"source_location": "未提供"},
        {"source_location": "第 1 句"},
        {"evidence": "甲没有进塔。"},
        {
            "source_location": "责任段 1，字节 1–18",
            "match_locations": [{"seg": 1, "start_byte": 1, "end_byte": 18}],
        },
        {
            "source_location": "责任段 3，字节 0–18",
            "match_locations": [{"seg": 3, "start_byte": 0, "end_byte": 18}],
        },
        {
            "source_location": "责任段 1，字节 0–999",
            "match_locations": [{"seg": 1, "start_byte": 0, "end_byte": 999}],
        },
        {"match_locations": []},
        {"match_locations": [{"seg": True, "start_byte": 0, "end_byte": 18}]},
        {
            "source_location": "责任段 1，字节 0–18；责任段 1，字节 40–57",
            "match_locations": [
                {"seg": 1, "start_byte": 0, "end_byte": 18},
                {"seg": 1, "start_byte": 40, "end_byte": 57},
            ],
        },
    ],
)
def test_bad_source_is_local_row_failure_not_page_crash(fixture, proof, change):
    proof["human_card"]["items"][0].update(change)
    result = builder.project_view(proof, fixture)
    assert len(result["candidates"]) == 5
    assert result["candidates"][0]["source_ids"] == []


def test_strict_source_string_can_supply_locations_without_search(fixture, proof):
    item = proof["human_card"]["items"][0]
    item.pop("match_locations")
    result = builder.project_view(proof, fixture)
    assert len(result["candidates"][0]["source_ids"]) == 2


def test_segment_relative_byte_offsets_are_added_to_segment_base(fixture, proof):
    raw = proof["human_card"]["items"][0]
    raw.update(
        evidence="乙停在门外。",
        source_location="责任段 2，字节 0–18",
        match_locations=[{"seg": 2, "start_byte": 0, "end_byte": 18}],
    )
    result = builder.project_view(proof, fixture)
    assert result["candidates"][0]["source_ids"] == [result["sentences"][3]["id"]]


def test_one_evidence_can_cover_two_sentences(fixture, proof):
    proof["human_card"]["items"][0].update(
        evidence="甲走进北塔。甲拿起铜钥匙。",
        source_location="责任段 1，字节 0–39",
        match_locations=[{"seg": 1, "start_byte": 0, "end_byte": 39}],
    )
    result = builder.project_view(proof, fixture)
    assert result["candidates"][0]["source_ids"] == [
        s["id"] for s in result["sentences"][:2]
    ]


def test_ten_ledgers_one_home_per_candidate_and_empty_ledgers_remain(model):
    assert [b["name"] for b in model["ledgers"]] == list(builder.LEDGER_NAMES)
    entries = [r for ledger in model["ledgers"] for r in ledger["entries"]]
    ids = [r["candidate_id"] for r in entries if r["candidate_id"]]
    assert sorted(ids) == sorted(c["id"] for c in model["candidates"])
    assert all(
        set(r) == {"id", "candidate_id", "primary_key", "tags", "tag_groups"}
        for r in entries
    )
    assert all(r["tag_groups"] == ["只读"] for r in entries)
    assert len([b for b in model["ledgers"] if not b["entries"]]) == 7
    assert model["candidates"][-1]["ledger"] == "长线账"
    assert model["ledgers"][9]["entries"] == []


@pytest.mark.parametrize(
    "status,expected",
    [
        ("已发生", "事实账"),
        ("计划", "长线账"),
        ("承诺", "长线账"),
        ("条件", "事实账"),
        ("误信", "事实账"),
        ("推测", "事实账"),
    ],
)
def test_routing_never_turns_speaker_into_character_or_condition_into_world_rule(
    status, expected
):
    assert (
        builder.route_ledger(
            {"status": status, "speaker": "旁白", "fact": "北塔、铜钥匙、甲"}
        )
        == expected
    )


@pytest.mark.parametrize(
    "area,key,value",
    [
        ("identity", "pointer_namespace", "PRODUCT_CANDIDATE_AUTHORITY"),
        ("identity", "candidate_access", "PRODUCT_READ_ONLY"),
        ("identity", "product_adopted", True),
        ("result_scope", "project_scope_id", "another-project"),
        ("result_scope", "revision_text_sha256", "0" * 64),
        ("result_scope", "revision_no", 8),
        ("result_scope", "chapter_id", "chapter-2"),
        ("result_scope", "book_title", "另一夹具"),
        ("result_scope", "responsibility_segment", 2),
    ],
)
def test_wrong_identity_is_closed(fixture, proof, area, key, value):
    proof[area][key] = value
    assert_gap(lambda: builder.project_view(proof, fixture), "GAP_SCOPE_MISMATCH")


def test_missing_fact_field_is_not_silently_omitted(fixture, proof):
    proof["human_card"]["items"][0].pop("fact")
    assert_gap(lambda: builder.project_view(proof, fixture), "GAP_CANDIDATE_SHAPE")


def test_duplicate_stable_id_is_closed(fixture, proof):
    proof["human_card"]["items"][1]["stable_item_id"] = proof["human_card"]["items"][0][
        "stable_item_id"
    ]
    assert_gap(lambda: builder.project_view(proof, fixture), "GAP_CANDIDATE_SHAPE")


def test_no_stable_id_uses_honest_view_local_id(fixture, proof):
    proof["human_card"]["items"][0]["stable_item_id"] = "未提供"
    result = builder.project_view(proof, fixture)
    assert result["candidates"][0]["id"].startswith("c_")
    assert "仅本页定位" in result["candidates"][0]["stable_item_id"]


def test_view_id_is_deterministic_and_changes_when_source_or_candidate_changes(
    fixture, proof, model
):
    assert builder.project_view(deepcopy(proof), fixture)["view_id"] == model["view_id"]
    proof["human_card"]["items"][0]["fact"] += "（不同版本）"
    assert builder.project_view(proof, fixture)["view_id"] != model["view_id"]


class PageScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.buttons = []
        self.text = []
        self.button = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if tag == "button":
            self.button = {"attrs": attrs, "text": ""}
            self.buttons.append(self.button)

    def handle_endtag(self, tag):
        if tag == "button":
            self.button = None

    def handle_data(self, data):
        self.text.append(data)
        if self.button is not None:
            self.button["text"] += data


def render(model, side=None):
    side = side or {
        "status": "MISSING",
        "gap": None,
        "document": marks.empty_document(model["view_id"]),
    }
    return render_page(model, side, output_name="door1.html", document_token="a" * 32)


def test_single_file_four_columns_and_exact_toolbar_actions(model):
    page = render(model)
    parser = PageScan()
    parser.feed(page)
    assert sum("panel" in a.get("class", "").split() for _, a in parser.tags) == 4
    assert (
        sum("ledger-group" in a.get("class", "").split() for _, a in parser.tags) == 10
    )
    actions = [b for b in parser.buttons if "data-action" in b["attrs"]]
    assert len(actions) == 9
    assert {b["text"] for b in actions} == {"＋ 补一条", "重新抽"}
    assert all(
        not any(c in b["text"] for c in ["删除", "拒绝", "×", "✕", "−", "叉", "减号"])
        for b in parser.buttons
    )
    assert not any("src" in a or "href" in a for _, a in parser.tags)
    assert "connect-src 'none'" in page and "分镜（占位，本刀不接）" in page
    assert "作者已认可" not in page
    assert model["identity"] in page
    assert page_model(page)["view_id"] == model["view_id"]


def test_untrusted_strings_do_not_break_html_or_inline_json(fixture, proof):
    attack = '</script><script>alert("test")</script><img src=x onerror=alert(1)>'
    proof["human_card"]["items"][0]["fact"] = attack
    result = builder.project_view(proof, fixture)
    page = render(result)
    assert attack not in page and "&lt;/script&gt;" in page
    assert page.count("<script") == 2
    assert page_model(page)["candidates"][0]["fact"] == attack
    assert "<" not in safe_json({"x": attack})


def test_javascript_syntax_with_available_node(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("本地没有 Node；不是运行页面的依赖。")
    script = tmp_path / "door1-inline.js"
    script.write_text(SCRIPT, encoding="utf-8")
    result = subprocess.run(
        [node, "--check", str(script)], capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0, result.stderr


def test_append_readback_and_reextract_never_change_model(tmp_path, model, ids):
    before = deepcopy(model)
    path = tmp_path / marks.SIDECAR_NAME
    missing = marks.new_mark("漏抽", model["sentences"][3]["id"])
    rerun = marks.new_mark("重新抽", model["candidates"][0]["id"])
    marks.append_mark(path, missing, model["view_id"], *ids)
    marks.append_mark(path, rerun, model["view_id"], *ids)
    value = marks.read_marks(path, model["view_id"], *ids)
    assert value["status"] == "OK" and len(value["document"]["marks"]) == 2
    assert model == before
    restored = page_model(render(model, value))
    assert restored["marks"]["document"]["marks"] == [missing, rerun]
    assert set(missing) == marks.MARK_KEYS


def test_missing_marks_is_different_from_corrupt(tmp_path, model, ids):
    path = tmp_path / marks.SIDECAR_NAME
    assert marks.read_marks(path, model["view_id"], *ids)["status"] == "MISSING"
    assert not path.exists()
    path.write_bytes(b"{broken")
    result = marks.read_marks(path, model["view_id"], *ids)
    assert result["status"] == "ERROR" and result["message"] == "标记没读到"
    assert "标记没读到" in render(model, result)
    with pytest.raises(marks.MarksError):
        marks.append_mark(
            path,
            marks.new_mark("漏抽", model["sentences"][0]["id"]),
            model["view_id"],
            *ids,
        )
    assert path.read_bytes() == b"{broken"


@pytest.mark.parametrize(
    "case",
    [
        "wrong_view",
        "bool_version",
        "extra_key",
        "wrong_target",
        "bad_date",
        "duplicate_id",
        "wrong_type",
        "extra_mark_key",
        "forward_reference",
    ],
)
def test_bad_marks_fail_as_whole_document(tmp_path, model, ids, case):
    value = marks.empty_document(model["view_id"])
    mark = marks.new_mark("漏抽", model["sentences"][0]["id"])
    value["marks"] = [mark]
    if case == "wrong_view":
        value["view_id"] = "0" * 64
    elif case == "bool_version":
        value["schema_version"] = True
    elif case == "extra_key":
        value["author_approval"] = True
    elif case == "wrong_target":
        mark["target_id"] = "unknown"
    elif case == "bad_date":
        mark["created_at"] = "2026-02-31T10:00:00Z"
    elif case == "duplicate_id":
        value["marks"].append(dict(mark))
    elif case == "wrong_type":
        mark["mark_type"] = "确认"
    elif case == "extra_mark_key":
        mark["fact"] = "不该写入"
    elif case == "forward_reference":
        value["marks"].insert(
            0, marks.new_mark("重新抽", marks.placeholder_id(mark["mark_id"]))
        )
    path = tmp_path / marks.SIDECAR_NAME
    path.write_text(json.dumps(value), encoding="utf-8")
    assert marks.read_marks(path, model["view_id"], *ids)["status"] == "ERROR"


def test_new_placeholder_can_be_target_of_later_rerun(tmp_path, model, ids):
    path = tmp_path / marks.SIDECAR_NAME
    addition = marks.new_mark("漏抽", model["sentences"][3]["id"])
    marks.append_mark(path, addition, model["view_id"], *ids)
    rerun = marks.new_mark("重新抽", marks.placeholder_id(addition["mark_id"]))
    value = marks.append_mark(path, rerun, model["view_id"], *ids)
    assert len(value["marks"]) == 2


def test_idempotent_retry_and_conflicting_same_id(tmp_path, model, ids):
    path = tmp_path / marks.SIDECAR_NAME
    item = marks.new_mark("重新抽", model["candidates"][0]["id"])
    marks.append_mark(path, item, model["view_id"], *ids)
    assert (
        len(marks.append_mark(path, dict(item), model["view_id"], *ids)["marks"]) == 1
    )
    wrong = {**item, "target_id": model["candidates"][1]["id"]}
    with pytest.raises(marks.MarksError, match="GAP_MARKS_CONFLICT"):
        marks.append_mark(path, wrong, model["view_id"], *ids)


def test_failed_replace_preserves_original_and_cleans_temp(
    monkeypatch, tmp_path, model, ids
):
    path = tmp_path / marks.SIDECAR_NAME
    marks.create_if_missing(path, marks.empty_document(model["view_id"]))
    before = path.read_bytes()

    def fail(*args):
        raise OSError("synthetic write failure")

    monkeypatch.setattr(marks.os, "replace", fail)
    with pytest.raises(OSError):
        marks.append_mark(
            path,
            marks.new_mark("漏抽", model["sentences"][0]["id"]),
            model["view_id"],
            *ids,
        )
    assert path.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == [marks.SIDECAR_NAME]


def test_sidecar_busy_refuses_instead_of_overwriting(tmp_path, model, ids):
    path = tmp_path / marks.SIDECAR_NAME
    lock = tmp_path / ".door1.marks.lock"
    lock.write_text("test lock")
    with pytest.raises(marks.MarksError, match="GAP_MARKS_BUSY"):
        marks.append_mark(
            path,
            marks.new_mark("漏抽", model["sentences"][0]["id"]),
            model["view_id"],
            *ids,
        )
    assert not path.exists() and lock.read_text() == "test lock"


def test_large_file_and_symlink_are_not_overwritten(tmp_path, model, ids):
    target = tmp_path / "target.json"
    target.write_bytes(b"x" * (marks.MAX_BYTES + 1))
    path = tmp_path / marks.SIDECAR_NAME
    path.symlink_to(target)
    assert marks.read_marks(path, model["view_id"], *ids)["status"] == "ERROR"
    with pytest.raises(marks.MarksError):
        marks.create_if_missing(path, marks.empty_document(model["view_id"]))
    path.unlink()
    path.write_bytes(target.read_bytes())
    assert (
        marks.read_marks(path, model["view_id"], *ids)["gap"] == "GAP_MARKS_TOO_LARGE"
    )


def test_existing_sidecar_is_never_reinitialized(tmp_path, model):
    path = tmp_path / marks.SIDECAR_NAME
    path.write_bytes(b"{broken")
    assert (
        marks.create_if_missing(path, marks.empty_document(model["view_id"])) is False
    )
    assert path.read_bytes() == b"{broken"


def test_missing_store_cli_returns_stable_gap_and_writes_nothing(tmp_path, capsys):
    code = builder.main(
        [
            "--book",
            "北塔夹具",
            "--chapter",
            "1",
            "--store",
            str(tmp_path / "missing"),
            "--out",
            str(tmp_path / "door1.html"),
        ]
    )
    result = json.loads(capsys.readouterr().out)
    assert code == 2 and result["gaps"] == ["GAP_STORE_MISSING"]
    assert not result["authority_wrote"] and list(tmp_path.iterdir()) == []
    assert str(tmp_path) not in json.dumps(result)


def test_bad_book_cli_stops_before_creating_files(tmp_path, capsys):
    code = builder.main(
        [
            "--book",
            "别的书",
            "--chapter",
            "1",
            "--store",
            str(tmp_path / "missing"),
            "--out",
            str(tmp_path / "door1.html"),
        ]
    )
    assert code == 2 and "GAP_NOT_RELEASED" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


def test_unit_builder_writes_inline_page_and_preserves_marks(
    monkeypatch, tmp_path, proof, model, ids
):
    monkeypatch.setattr(builder, "read_current_fixture", lambda store: deepcopy(proof))
    out = tmp_path / "door1.html"
    store = tmp_path / "store-that-unit-test-never-creates"
    result = builder.build_view(book="北塔夹具", chapter=1, store_root=store, out=out)
    assert (
        result["status"] == "BUILT"
        and not result["authority_wrote"]
        and not store.exists()
    )
    assert result["candidate_count"] == 5
    side = tmp_path / marks.SIDECAR_NAME
    marks.append_mark(
        side,
        marks.new_mark("重新抽", model["candidates"][0]["id"]),
        model["view_id"],
        *ids,
    )
    before = side.read_bytes()
    builder.build_view(book="北塔夹具", chapter=1, store_root=store, out=out)
    assert side.read_bytes() == before
    assert len(page_model(out.read_text())["marks"]["document"]["marks"]) == 1


def test_unit_corrupt_sidecar_does_not_stop_page_or_replace_file(
    monkeypatch, tmp_path, proof
):
    monkeypatch.setattr(builder, "read_current_fixture", lambda store: deepcopy(proof))
    side = tmp_path / marks.SIDECAR_NAME
    side.write_bytes(b"corrupt json")
    out = tmp_path / "door1.html"
    result = builder.build_view(
        book="北塔夹具", chapter=1, store_root=tmp_path / "store", out=out
    )
    assert result["status"] == "BUILT" and result["marks_status"] == "ERROR"
    assert side.read_bytes() == b"corrupt json" and "标记没读到" in out.read_text()


def test_unit_current_drift_is_zero_output(monkeypatch, tmp_path, proof):
    changed = deepcopy(proof)
    changed["human_card"]["items"][0]["fact"] = "合成变化"
    values = iter([proof, changed])
    monkeypatch.setattr(builder, "read_current_fixture", lambda store: next(values))
    assert_gap(
        lambda: builder.build_view(
            book="北塔夹具",
            chapter=1,
            store_root=tmp_path / "store",
            out=tmp_path / "door1.html",
        ),
        "GAP_CURRENT_CHANGED",
    )
    assert list(tmp_path.iterdir()) == []


def test_cannot_overwrite_arbitrary_file_or_write_under_store(
    tmp_path, proof, monkeypatch
):
    monkeypatch.setattr(builder, "read_current_fixture", lambda store: deepcopy(proof))
    out = tmp_path / "keep.html"
    out.write_text("existing unrelated page")
    assert_gap(
        lambda: builder.build_view(
            book="北塔夹具", chapter=1, store_root=tmp_path / "store", out=out
        ),
        "GAP_OUTPUT_PATH",
    )
    assert out.read_text() == "existing unrelated page"
    assert_gap(
        lambda: builder.build_view(
            book="北塔夹具", chapter=1, store_root=tmp_path, out=tmp_path / "new.html"
        ),
        "GAP_OUTPUT_PATH",
    )
    assert_gap(
        lambda: builder.build_view(
            book="北塔夹具",
            chapter=1,
            store_root=tmp_path / "store",
            out=ROOT / "new.html",
        ),
        "GAP_OUTPUT_PATH",
    )


def require_real_store_dependencies():
    required = [
        "work/ccz57_m3_b05_patch_route_r03_5/b05_store.py",
        "work/ccz57_m3_b06_commit_core_r01/b06_store.py",
        "work/ccz57_m3_b06_commit_core_r01/b06_contracts.py",
        "work/ccz57_m3_b07_local_recovery_stop_r01/b07_store.py",
        "work/ccz57_m3_b08_segment_terminal_r01/b08_store.py",
    ]
    missing = [path for path in required if not (REPO / path).is_file()]
    if missing:
        pytest.skip("真实库联调未运行；切片缺依赖：" + ", ".join(missing))
    named_root = REPO / "work/ccz142_named_chapter_txt_card_r01"
    if str(named_root) not in sys.path:
        sys.path.insert(0, str(named_root))
    from named_chapter import drop_named_chapter

    return drop_named_chapter


def test_integration_real_store_read_and_marks_never_write_authority(tmp_path):
    drop = require_real_store_dependencies()
    store = tmp_path / "authority"
    seeded = drop(book="北塔夹具", chapter_no=1, store_root=store)
    assert seeded["wrote"] is True
    before = snapshot(store)
    out = tmp_path / "door1.html"
    result = builder.build_view(book="北塔夹具", chapter=1, store_root=store, out=out)
    assert result["status"] == "BUILT" and result["candidate_count"] == 5
    projected = page_model(out.read_text())
    ids = (
        {s["id"] for s in projected["sentences"]},
        {c["id"] for c in projected["candidates"]},
    )
    side = tmp_path / marks.SIDECAR_NAME
    for typ, target in [
        ("漏抽", projected["sentences"][3]["id"]),
        ("重新抽", projected["candidates"][0]["id"]),
    ]:
        marks.append_mark(side, marks.new_mark(typ, target), projected["view_id"], *ids)
    builder.build_view(book="北塔夹具", chapter=1, store_root=store, out=out)
    assert len(page_model(out.read_text())["marks"]["document"]["marks"]) == 2
    assert snapshot(store) == before


def test_integration_real_store_missing_source_projection_is_local_gap(
    tmp_path, monkeypatch
):
    drop = require_real_store_dependencies()
    store = tmp_path / "authority"
    drop(book="北塔夹具", chapter_no=1, store_root=store)
    before = snapshot(store)
    import current_read_proof

    original = current_read_proof.project_human_card

    def omit(**kwargs):
        card = original(**kwargs)
        card["items"][0].pop("source_location", None)
        return card

    monkeypatch.setattr(current_read_proof, "project_human_card", omit)
    out = tmp_path / "door1.html"
    builder.build_view(book="北塔夹具", chapter=1, store_root=store, out=out)
    assert page_model(out.read_text())["candidates"][0]["source_ids"] == []
    assert "来源没对上" in out.read_text() and snapshot(store) == before


def test_integration_real_store_corrupt_sidecar_still_opens(tmp_path):
    drop = require_real_store_dependencies()
    store = tmp_path / "authority"
    drop(book="北塔夹具", chapter_no=1, store_root=store)
    before = snapshot(store)
    side = tmp_path / marks.SIDECAR_NAME
    side.write_bytes(b"{bad sidecar")
    out = tmp_path / "door1.html"
    result = builder.build_view(book="北塔夹具", chapter=1, store_root=store, out=out)
    assert result["status"] == "BUILT" and "标记没读到" in out.read_text()
    assert side.read_bytes() == b"{bad sidecar" and snapshot(store) == before


def test_package_self_check():
    from work.door1_author_intake_view_r01.self_check import run_self_check

    assert run_self_check()["result"] == "PASS"


@pytest.mark.parametrize("preexisting", [False, True])
def test_unit_html_publish_failure_preserves_old_files(
    monkeypatch, tmp_path, proof, model, preexisting
):
    monkeypatch.setattr(builder, "read_current_fixture", lambda store: deepcopy(proof))
    out = tmp_path / "door1.html"
    side = tmp_path / marks.SIDECAR_NAME
    if preexisting:
        out.write_text('<meta name="door1-document" content="old">old page')
        side.write_bytes(b"old corrupt sidecar")
    before = snapshot(tmp_path)

    def fail_publish(*args):
        raise OSError("unit test: simulated publish failure")

    monkeypatch.setattr(builder.os, "replace", fail_publish)
    assert_gap(
        lambda: builder.build_view(
            book="北塔夹具", chapter=1, store_root=tmp_path / "store", out=out
        ),
        "GAP_OUTPUT_WRITE",
    )
    assert snapshot(tmp_path) == before
    assert not list(tmp_path.glob("*.tmp"))


def test_unit_output_read_error_is_stable_gap(monkeypatch, tmp_path, capsys):
    def bad_guard(*args):
        raise OSError("unit test: no file access")

    monkeypatch.setattr(builder, "_output_guard", bad_guard)
    code = builder.main(
        [
            "--book",
            "北塔夹具",
            "--chapter",
            "1",
            "--store",
            str(tmp_path / "store"),
            "--out",
            str(tmp_path / "door1.html"),
        ]
    )
    assert code == 2 and json.loads(capsys.readouterr().out)["gaps"] == [
        "GAP_OUTPUT_PATH"
    ]
    assert list(tmp_path.iterdir()) == []


def test_documented_object_keys_match_runtime_projection(model, ids, tmp_path):
    shapes = json.loads((ROOT / "OBJECT_SHAPES.json").read_text(encoding="utf-8"))
    assert sorted(model) == shapes["view_keys"]
    assert sorted(model["sentences"][0]) == shapes["sentence_keys"]
    assert sorted(model["candidates"][0]) == shapes["candidate_keys"]
    observed = marks.read_marks(tmp_path / marks.SIDECAR_NAME, model["view_id"], *ids)
    assert sorted(observed) == shapes["marks_read_result_keys"]


@pytest.fixture
def self_check_copy(tmp_path, monkeypatch):
    import shutil
    from work.door1_author_intake_view_r01 import self_check as checker

    package = tmp_path / "work" / ROOT.name
    package.mkdir(parents=True)
    for name in checker.EXPECTED_FILES:
        shutil.copyfile(ROOT / name, package / name)
    shapes = json.loads((package / "OBJECT_SHAPES.json").read_text())
    for rel in shapes["protected_input_sha256"]:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(checker.REPO / rel, target)
    monkeypatch.setattr(checker, "ROOT", package)
    monkeypatch.setattr(checker, "REPO", tmp_path)

    def refresh():
        (package / "MANIFEST.sha256").write_text(
            "".join(
                f"{checker.sha(package / name)}  {name}\n"
                for name in sorted(checker.EXPECTED_FILES - {"MANIFEST.sha256"})
            )
        )

    return checker, shapes, refresh


def test_self_check_reports_nine_historical_differences_and_62_strict():
    from work.door1_author_intake_view_r01 import self_check as checker

    report = checker.run_self_check()
    assert report["result"] == "PASS"
    assert report["manifest_verified_files"] == 9
    assert report["protected_input_verified_files"] == 62
    assert report["historical_input_compared_files"] == 9
    records = report["historical_input_evidence"]
    assert {r["path"] for r in records} == checker.HISTORICAL_INPUT_PATHS
    for record in records:
        assert record["current_sha256"] == checker.sha(checker.REPO / record["path"])
        expected_status = (
            "same"
            if record["current_sha256"] == record["historical_sha256"]
            else "changed"
        )
        assert record["status"] == expected_status


@pytest.mark.parametrize("state", ["same", "changed", "missing", "unreadable"])
def test_historical_comparison_preserves_all_rows(self_check_copy, monkeypatch, state):
    checker, shapes, _ = self_check_copy
    rel = sorted(checker.HISTORICAL_INPUT_PATHS)[0]
    real_sha = checker.sha

    def read(path):
        if path == checker.REPO / rel:
            if state == "same":
                return shapes["protected_input_sha256"][rel]
            if state == "changed":
                return "0" * 64
            if state == "missing":
                raise FileNotFoundError(path)
            raise PermissionError(path)
        return real_sha(path)

    monkeypatch.setattr(checker, "sha", read)
    report = checker.run_self_check()
    records = report["historical_input_evidence"]
    record = next(r for r in records if r["path"] == rel)
    assert len(records) == 9 and record["status"] == state
    assert record["historical_sha256"] == shapes["protected_input_sha256"][rel]
    available = state in {"same", "changed"}
    assert report["result"] == ("PASS" if available else "FAIL")
    assert report["historical_input_compared_files"] == (9 if available else 8)
    assert (record["current_sha256"] is not None) == available
    assert report["protected_input_verified_files"] == 62


@pytest.mark.parametrize(
    "mutation", ["missing", "extra", "replace", "metadata", "baseline"]
)
def test_historical_classification_rejects_expansion_and_incomplete_data(
    self_check_copy, mutation
):
    checker, shapes, refresh = self_check_copy
    classification = shapes["historical_input_evidence"]
    key = next(iter(classification))
    if mutation == "missing":
        del classification[key]
    elif mutation == "extra":
        classification["governance/*"] = classification[key]
    elif mutation == "replace":
        strict = next(
            p for p in shapes["protected_input_sha256"] if p not in classification
        )
        classification[strict] = classification.pop(key)
    elif mutation == "metadata":
        classification[key]["reason"] = ""
    else:
        shapes["base_main_sha"] = "0" * 40
    (checker.ROOT / "OBJECT_SHAPES.json").write_text(json.dumps(shapes))
    refresh()
    with pytest.raises(RuntimeError, match="DOOR1_HISTORICAL_CLASSIFICATION"):
        checker.run_self_check()


def test_each_remaining_protected_input_still_rejects_tampering(self_check_copy):
    checker, shapes, _ = self_check_copy
    strict = set(shapes["protected_input_sha256"]) - checker.HISTORICAL_INPUT_PATHS
    assert len(strict) == 62
    for rel in strict:
        path = checker.REPO / rel
        original = path.read_bytes()
        path.write_bytes(original + b"\nchanged")
        with pytest.raises(RuntimeError, match="DOOR1_PROTECTED_INPUT_DRIFT"):
            checker.run_self_check()
        path.write_bytes(original)


@pytest.mark.parametrize("guard", ["manifest", "schema", "import", "call", "js"])
def test_existing_package_and_boundary_guards_survive(
    self_check_copy, monkeypatch, guard
):
    checker, shapes, refresh = self_check_copy
    errors = {
        "manifest": "DOOR1_MANIFEST_HASH",
        "schema": "DOOR1_OBJECT_SHAPES_DRIFT",
        "import": "DOOR1_FORBIDDEN_IMPORT",
        "call": "DOOR1_FORBIDDEN_CALL",
        "js": "DOOR1_FORBIDDEN_JS_CALL",
    }
    if guard == "schema":
        shapes["authority_wrote"] = True
        (checker.ROOT / "OBJECT_SHAPES.json").write_text(json.dumps(shapes))
    elif guard == "js":
        monkeypatch.setattr(checker, "SCRIPT", checker.SCRIPT + "fetch(")
    else:
        with (checker.ROOT / "build_view.py").open("a") as stream:
            stream.write("\nimport socket\n" if guard == "import" else "\nexecute()\n")
    if guard != "manifest":
        refresh()
    with pytest.raises(RuntimeError, match=errors[guard]):
        checker.run_self_check()
