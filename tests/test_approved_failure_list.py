from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/check_approved_failure_list.py"
SPEC = importlib.util.spec_from_file_location("check_approved_failure_list", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

BRAND_NEW = (
    "tests/test_brand_new_regression.py::test_author_export_is_not_corrupted"
)
MAIN_SHA = "cec82789322613f04af20e8233cef97c419ab571"


def _dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(MODULE._json_bytes(value))


def _sample_failures() -> list[dict[str, str]]:
    return [
        {
            "id": "tests/test_alpha.py::test_one",
            "domain": "demo",
            "attribution": "夹具债，不是新回归。",
        },
        {
            "id": "tests/test_beta.py::test_two",
            "domain": "demo",
            "attribution": "夹具债，不是新回归。",
        },
    ]


def _sample_document() -> dict:
    return {
        "contract_version": "approved-stable-failure-list-v1",
        "approval": {
            "status": "EFFECTIVE_ON_MERGE",
            "issue": "63",
            "note": "合并含本文件的 PR 即批准这份清单。",
        },
        "predicate": MODULE.PASS_PREDICATE,
        "main_sha": MAIN_SHA,
        "failure_count": 2,
        "command": "uv run --locked pytest -q",
        "environment": "fixture",
        "failures": _sample_failures(),
    }


def _install_list(repo: Path, document: dict | None = None) -> dict:
    schema_src = ROOT / MODULE.SCHEMA_RELATIVE
    schema_dest = repo / MODULE.SCHEMA_RELATIVE
    schema_dest.parent.mkdir(parents=True, exist_ok=True)
    schema_dest.write_bytes(schema_src.read_bytes())
    sealed = MODULE.seal_list(document or _sample_document())
    _dump(repo / MODULE.LIST_RELATIVE, sealed)
    return sealed


def _observed(repo: Path, name: str, ids: list[str]) -> Path:
    path = repo / name
    _dump(path, {"failed_nodeids": ids})
    return path


def test_live_list_has_four_piece_seal_and_sorted_unique_ids() -> None:
    document = MODULE.load_approved_list(ROOT)
    ids = [row["id"] for row in document["failures"]]
    assert document["contract_version"] == "approved-stable-failure-list-v1"
    assert document["approval"]["status"] == "EFFECTIVE_ON_MERGE"
    assert document["predicate"] == MODULE.PASS_PREDICATE
    assert document["main_sha"] == MAIN_SHA
    assert document["failure_count"] == 19 == len(ids)
    assert ids == sorted(set(ids))
    assert document["payload_sha256"] == MODULE.payload_sha256(document)
    assert BRAND_NEW not in ids


def test_live_verify_list_exits_zero() -> None:
    assert MODULE.main(["verify-list"]) == 0


def test_three_copies_of_live_ids_satisfy_the_pass_predicate() -> None:
    approved = MODULE.load_approved_list(ROOT)
    ids = [row["id"] for row in approved["failures"]]
    report = MODULE.classify(approved, [ids, ids, ids])
    assert report["status"] == MODULE.PASS_PREDICATE
    assert report["unapproved_ids"] == []
    assert report["missing_approved_ids"] == []


def test_live_ids_plus_brand_new_regression_is_unapproved() -> None:
    approved = MODULE.load_approved_list(ROOT)
    ids = [row["id"] for row in approved["failures"]]
    report = MODULE.classify(approved, [ids + [BRAND_NEW]] * 3)
    assert report["status"] == MODULE.UNAPPROVED
    assert report["unapproved_ids"] == [BRAND_NEW]


def test_three_equal_rounds_match_approved_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    sealed = _install_list(tmp_path)
    monkeypatch.setattr(MODULE, "ROOT", tmp_path)
    ids = [row["id"] for row in sealed["failures"]]
    paths = [
        str(_observed(tmp_path, f"round{index}.json", ids)) for index in (1, 2, 3)
    ]
    report = MODULE.classify(sealed, [ids, list(reversed(ids)), ids])
    assert report["status"] == MODULE.PASS_PREDICATE
    assert MODULE.main(["check", "--observed", paths[0], "--observed", paths[1], "--observed", paths[2]]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == MODULE.PASS_PREDICATE
    assert payload["approved_count"] == 2
    assert payload["round_count"] == 3


def test_unapproved_finding_even_if_three_rounds_agree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    sealed = _install_list(tmp_path)
    monkeypatch.setattr(MODULE, "ROOT", tmp_path)
    ids = [row["id"] for row in sealed["failures"]] + [BRAND_NEW]
    path = str(_observed(tmp_path, "round.json", ids))
    report = MODULE.classify(sealed, [ids, ids, ids])
    assert report["status"] == MODULE.UNAPPROVED
    assert report["unapproved_ids"] == [BRAND_NEW]
    assert (
        MODULE.main(["check", "--observed", path, "--observed", path, "--observed", path])
        == 2
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == MODULE.UNAPPROVED
    assert payload["unapproved_ids"] == [BRAND_NEW]


def test_missing_approved_id_is_not_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sealed = _install_list(tmp_path)
    monkeypatch.setattr(MODULE, "ROOT", tmp_path)
    ids = [sealed["failures"][0]["id"]]
    path = str(_observed(tmp_path, "round.json", ids))
    report = MODULE.classify(sealed, [ids, ids, ids])
    assert report["status"] == MODULE.MISSING_APPROVED
    assert report["missing_approved_ids"] == [sealed["failures"][1]["id"]]
    assert (
        MODULE.main(["check", "--observed", path, "--observed", path, "--observed", path])
        == 2
    )


def test_single_round_match_is_not_the_pass_predicate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sealed = _install_list(tmp_path)
    monkeypatch.setattr(MODULE, "ROOT", tmp_path)
    ids = [row["id"] for row in sealed["failures"]]
    path = str(_observed(tmp_path, "round.json", ids))
    report = MODULE.classify(sealed, [ids])
    assert report["status"] == MODULE.SINGLE_ROUND
    assert MODULE.main(["check", "--observed", path]) == 2


def test_two_equal_rounds_are_still_not_the_pass_predicate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sealed = _install_list(tmp_path)
    ids = [row["id"] for row in sealed["failures"]]
    report = MODULE.classify(sealed, [ids, ids])
    assert report["status"] == MODULE.SINGLE_ROUND


def test_unequal_rounds_cannot_pass(tmp_path: Path) -> None:
    sealed = _install_list(tmp_path)
    first = [row["id"] for row in sealed["failures"]]
    second = first + [BRAND_NEW]
    report = MODULE.classify(sealed, [first, second, first])
    assert report["status"] == MODULE.ROUNDS_UNEQUAL


def test_tampered_payload_sha256_is_list_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sealed = _install_list(tmp_path)
    sealed["payload_sha256"] = "0" * 64
    _dump(tmp_path / MODULE.LIST_RELATIVE, sealed)
    monkeypatch.setattr(MODULE, "ROOT", tmp_path)
    with pytest.raises(MODULE.ApprovedListError) as exc:
        MODULE.load_approved_list(tmp_path)
    assert exc.value.code == MODULE.LIST_INVALID
    assert MODULE.main(["verify-list"]) == 3


def test_unsorted_ids_are_list_invalid(tmp_path: Path) -> None:
    document = _sample_document()
    document["failures"] = list(reversed(document["failures"]))
    sealed = MODULE.seal_list(document)
    schema_dest = tmp_path / MODULE.SCHEMA_RELATIVE
    schema_dest.parent.mkdir(parents=True, exist_ok=True)
    schema_dest.write_bytes((ROOT / MODULE.SCHEMA_RELATIVE).read_bytes())
    _dump(tmp_path / MODULE.LIST_RELATIVE, sealed)
    with pytest.raises(MODULE.ApprovedListError) as exc:
        MODULE.load_approved_list(tmp_path)
    assert exc.value.code == MODULE.LIST_INVALID
