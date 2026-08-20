from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
PACKER_TOOL_SCRIPT = PRODUCT_ROOT / "mvp/packer_tool.py"
sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import packer_tool
finally:
    sys.path.pop(0)


def _material(
    material_id: str,
    *,
    tokens: int,
    actuality: str,
    obligation: str,
    rank: int | None,
    recall: str = "RETRIEVABLE",
    handle: str | None = None,
    unresolved_reason: str | None = None,
) -> dict:
    if recall == "RETRIEVABLE" and handle is None:
        handle = f"material://{material_id}"
    return {
        "id": material_id,
        "estimated_tokens": tokens,
        "actuality_class": actuality,
        "obligation_tier": obligation,
        "selection_rank": rank,
        "task_relation": f"{material_id} 与当前写作任务直接相关",
        "recall_disposition": recall,
        "recall_handle": handle,
        "unresolved_reason": unresolved_reason,
    }


def _request(
    *materials: dict,
    budget: int = 100,
    scope: str = "CURRENT_TRUTH_REQUIRED",
    task_id: str = "M11-TOOL-SYNTHETIC",
) -> dict:
    return {
        "task_id": task_id,
        "task_actuality_scope": scope,
        "budget_tokens": budget,
        "token_estimator": {
            "identity": packer_tool.ESTIMATOR_IDENTITY,
            "estimates": {item["id"]: item["estimated_tokens"] for item in materials},
        },
        "candidate_materials": list(materials),
    }


def _hard(material_id: str, tokens: int) -> dict:
    return _material(
        material_id,
        tokens=tokens,
        actuality="ACTIVE_CONSTRAINT",
        obligation="HARD",
        rank=None,
        recall="NOT_RETRIEVABLE",
        handle=None,
    )


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_normal_budget_keeps_hard_first_and_exposes_recallable_omission() -> None:
    should = _material(
        "SHOULD-01",
        tokens=30,
        actuality="CURRENT_FACT_OR_STATE",
        obligation="SHOULD",
        rank=1,
    )
    may = _material(
        "MAY-01",
        tokens=20,
        actuality="CURRENT_FACT_OR_STATE",
        obligation="MAY",
        rank=1,
    )
    request = _request(may, should, _hard("HARD-01", 60), budget=90)
    before = copy.deepcopy(request)

    result = packer_tool.execute(request)

    assert result["decision_state"] == "READY"
    assert [item["id"] for item in result["loaded"]] == ["HARD-01", "SHOULD-01"]
    assert result["loaded"][0]["recall_disposition"] == "NOT_RETRIEVABLE"
    assert result["omitted"] == [
        {
            "id": "MAY-01",
            "reason": "BUDGET_OPTIONAL_DEFERRED",
            "recall_disposition": "RETRIEVABLE",
            "recall_handle": "material://MAY-01",
        }
    ]
    assert set(result["why_loaded"]) == {"HARD-01", "SHOULD-01"}
    assert result["budget"] == {
        "limit_tokens": 90,
        "used_tokens": 90,
        "estimator_identity": packer_tool.ESTIMATOR_IDENTITY,
    }
    assert request == before
    assert set(result) == {
        "prototype",
        "task_receipt",
        "decision_state",
        "loaded",
        "omitted",
        "why_loaded",
        "unresolved",
        "budget",
        "errors",
    }
    assert json.dumps(result, ensure_ascii=False, sort_keys=True) == json.dumps(
        packer_tool.execute(copy.deepcopy(request)),
        ensure_ascii=False,
        sort_keys=True,
    )


def test_unresolved_stops_without_context_package() -> None:
    unresolved = _material(
        "OPEN-01",
        tokens=20,
        actuality="UNRESOLVED",
        obligation="HARD",
        rank=None,
        unresolved_reason="作者尚未确认邀请是否接受",
    )

    result = packer_tool.execute(_request(unresolved, budget=100))

    assert result["decision_state"] == "STOP_UNRESOLVED"
    assert result["loaded"] == []
    assert result["budget"]["used_tokens"] == 0
    assert result["unresolved"][0]["id"] == "OPEN-01"


def test_hard_over_budget_stops_without_partial_package() -> None:
    result = packer_tool.execute(_request(_hard("HARD-A", 60), _hard("HARD-B", 50), budget=100))

    assert result["decision_state"] == "STOP_HARD_BUDGET"
    assert result["loaded"] == []
    assert result["budget"]["used_tokens"] == 0
    assert result["errors"][0]["code"] == "M11_HARD_OBLIGATIONS_EXCEED_BUDGET"


def test_ready_unresolved_and_hard_budget_stop_all_carry_task_identity() -> None:
    ready = packer_tool.execute(_request(_hard("HARD-READY", 20), budget=100))
    unresolved = packer_tool.execute(
        _request(
            _material(
                "OPEN-01",
                tokens=20,
                actuality="UNRESOLVED",
                obligation="HARD",
                rank=None,
                unresolved_reason="作者尚未决定",
            ),
            budget=100,
        )
    )
    over_budget = packer_tool.execute(
        _request(_hard("HARD-A", 60), _hard("HARD-B", 50), budget=100)
    )

    assert [
        ready["decision_state"],
        unresolved["decision_state"],
        over_budget["decision_state"],
    ] == ["READY", "STOP_UNRESOLVED", "STOP_HARD_BUDGET"]
    for result in (ready, unresolved, over_budget):
        assert result["prototype"] == {
            "identity": packer_tool.PROTOTYPE_IDENTITY,
            "version": packer_tool.PROTOTYPE_VERSION,
        }
        assert set(result["task_receipt"]) == {
            "task_id",
            "task_actuality_scope",
            "normalized_request_sha256",
        }
        assert result["task_receipt"]["task_id"] == "M11-TOOL-SYNTHETIC"
        assert result["task_receipt"]["task_actuality_scope"] == (
            "CURRENT_TRUTH_REQUIRED"
        )
        assert len(result["task_receipt"]["normalized_request_sha256"]) == 64


def test_equivalent_material_permutation_keeps_request_sha_and_decision() -> None:
    hard = _hard("HARD-01", 60)
    should = _material(
        "SHOULD-01",
        tokens=30,
        actuality="CURRENT_FACT_OR_STATE",
        obligation="SHOULD",
        rank=1,
    )
    may = _material(
        "MAY-01",
        tokens=20,
        actuality="CURRENT_FACT_OR_STATE",
        obligation="MAY",
        rank=1,
    )

    left = packer_tool.execute(_request(may, should, hard, budget=90))
    right = packer_tool.execute(_request(hard, may, should, budget=90))

    assert left == right
    assert left["task_receipt"]["normalized_request_sha256"] == (
        right["task_receipt"]["normalized_request_sha256"]
    )


def test_each_business_identity_input_changes_normalized_request_sha() -> None:
    material = _hard("HARD-01", 20)
    baseline = _request(material, budget=100)
    variants: list[dict] = []

    variants.append(_request(material, budget=100, task_id="M11-TOOL-OTHER"))
    variants.append(
        _request(
            material,
            budget=100,
            scope="FUTURE_MATERIAL_EXPLICITLY_IN_SCOPE",
        )
    )
    changed_material = copy.deepcopy(material)
    changed_material["task_relation"] = "同一材料改为服务另一个明确任务关系"
    variants.append(_request(changed_material, budget=100))
    variants.append(_request(material, budget=101))
    changed_estimator = copy.deepcopy(baseline)
    changed_estimator["token_estimator"]["identity"] = "ANOTHER_ESTIMATOR"
    variants.append(changed_estimator)

    baseline_sha = packer_tool._request_sha256(baseline)
    assert all(
        packer_tool._request_sha256(variant) != baseline_sha
        for variant in variants
    )
    with pytest.raises(
        packer_tool.PackerToolError,
        match="TOKEN_ESTIMATOR_IDENTITY_INVALID",
    ):
        packer_tool.execute(changed_estimator)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda request: request.update(task_id=" bad-task "),
        lambda request: request.update(task_actuality_scope="UNKNOWN_SCOPE"),
        lambda request: request.update(budget_tokens=0),
        lambda request: request["token_estimator"].update(identity="UNKNOWN"),
        lambda request: request["candidate_materials"][0].update(task_relation=""),
    ],
)
def test_bad_task_scope_budget_estimator_and_material_are_rejected(mutate) -> None:
    request = _request(_hard("HARD-01", 20), budget=100)
    mutate(request)

    with pytest.raises(packer_tool.PackerToolError):
        packer_tool.execute(request)


def test_future_hard_current_scope_is_an_explicit_obligation_conflict() -> None:
    future_hard = _material(
        "FUTURE-HARD",
        tokens=10,
        actuality="FUTURE_PLAN_OR_PROJECTION",
        obligation="HARD",
        rank=None,
    )

    result = packer_tool.execute(_request(future_hard, budget=100))

    assert result["decision_state"] == "STOP_CONFLICT"
    assert result["loaded"] == []
    assert result["errors"][0]["code"] == "M11_ACTUALITY_HARD_CONFLICT"


@pytest.mark.parametrize("fault", ["unknown_field", "duplicate_id", "missing_actuality"])
def test_invalid_batch_shape_is_rejected_without_silent_default(fault: str) -> None:
    first = _hard("HARD-01", 20)
    materials = [first]
    if fault == "unknown_field":
        first["invented"] = True
    elif fault == "duplicate_id":
        materials.append(copy.deepcopy(first))
    else:
        del first["actuality_class"]
    request = _request(*materials, budget=100)

    with pytest.raises(packer_tool.PackerToolError):
        packer_tool.execute(request)


def test_estimate_drift_is_rejected_instead_of_recomputed() -> None:
    request = _request(_hard("HARD-01", 20), budget=100)
    request["token_estimator"]["estimates"]["HARD-01"] = 21

    with pytest.raises(packer_tool.PackerToolError, match="TOKEN_ESTIMATE_DRIFT:HARD-01"):
        packer_tool.execute(request)


def test_cli_round_trip_is_parseable_and_failure_preserves_previous_output(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "request.json"
    output_path = tmp_path / "result.json"
    request = _request(_hard("HARD-01", 20), budget=100)
    _write_json(input_path, request)

    completed = subprocess.run(
        [
            sys.executable,
            str(PACKER_TOOL_SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert completed.returncode == 0, completed.stderr
    first = json.loads(output_path.read_text(encoding="utf-8"))
    assert first["loaded"][0]["id"] == "HARD-01"
    before = output_path.read_bytes()

    repeated = subprocess.run(
        [
            sys.executable,
            str(PACKER_TOOL_SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert repeated.returncode == 0, repeated.stderr
    assert output_path.read_bytes() == before

    request["token_estimator"]["estimates"]["HARD-01"] = 19
    _write_json(input_path, request)
    stderr = io.StringIO()
    code = packer_tool.main(
        ["--input", str(input_path), "--output", str(output_path)],
        stderr=stderr,
    )

    assert code == 2
    assert "TOKEN_ESTIMATE_DRIFT:HARD-01" in stderr.getvalue()
    assert output_path.read_bytes() == before
    assert not list(tmp_path.glob(".result.json.*.tmp"))


def test_atomic_replace_failure_preserves_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "request.json"
    output_path = tmp_path / "result.json"
    _write_json(input_path, _request(_hard("HARD-01", 20), budget=100))
    output_path.write_text('{"sentinel":"old"}\n', encoding="utf-8")
    before = output_path.read_bytes()

    def fail_replace(_source: str, _target: Path) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(packer_tool.os, "replace", fail_replace)
    stderr = io.StringIO()
    code = packer_tool.main(
        ["--input", str(input_path), "--output", str(output_path)],
        stderr=stderr,
    )

    assert code == 2
    assert "synthetic replace failure" in stderr.getvalue()
    assert output_path.read_bytes() == before
    assert not list(tmp_path.glob(".result.json.*.tmp"))


def test_render_ready_lists_loaded_order_omission_reason_and_recall() -> None:
    should = _material(
        "SHOULD-01",
        tokens=30,
        actuality="CURRENT_FACT_OR_STATE",
        obligation="SHOULD",
        rank=1,
    )
    may = _material(
        "MAY-01",
        tokens=20,
        actuality="CURRENT_FACT_OR_STATE",
        obligation="MAY",
        rank=1,
    )
    result = packer_tool.execute(
        _request(may, should, _hard("HARD-01", 60), budget=90)
    )

    rendered = packer_tool.render(result)

    assert f"原型：{packer_tool.PROTOTYPE_IDENTITY} / v1" in rendered
    assert "任务：M11-TOOL-SYNTHETIC" in rendered
    assert "事实范围：CURRENT_TRUTH_REQUIRED" in rendered
    assert result["task_receipt"]["normalized_request_sha256"] in rendered
    assert rendered.index("1. HARD-01｜义务 HARD") < rendered.index(
        "2. SHOULD-01｜义务 SHOULD"
    )
    assert "MAY-01｜原因 BUDGET_OPTIONAL_DEFERRED" in rendered
    assert "回取：可回取，入口 material://MAY-01" in rendered
    assert "本次未装入”不代表永久删除" in rendered
    assert "不代表正式 C9 或生产可用" in rendered


def test_render_unresolved_and_hard_budget_explain_why_no_package_exists() -> None:
    unresolved = packer_tool.execute(
        _request(
            _material(
                "OPEN-01",
                tokens=20,
                actuality="UNRESOLVED",
                obligation="HARD",
                rank=None,
                unresolved_reason="作者尚未确认邀请是否接受",
            ),
            budget=100,
        )
    )
    hard_budget = packer_tool.execute(
        _request(_hard("HARD-A", 60), _hard("HARD-B", 50), budget=100)
    )

    unresolved_text = packer_tool.render(unresolved)
    hard_budget_text = packer_tool.render(hard_budget)

    assert "未决事项（1）" in unresolved_text
    assert "OPEN-01｜义务 HARD｜原因 作者尚未确认" in unresolved_text
    assert "本次没有自动解决" in unresolved_text
    assert "STOP_HARD_BUDGET" in hard_budget_text
    assert "M11_HARD_OBLIGATIONS_EXCEED_BUDGET" in hard_budget_text
    assert "硬性材料超过本次预算" in hard_budget_text


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda result: result["prototype"].update(identity="WRONG"),
        lambda result: result["task_receipt"].update(
            normalized_request_sha256="broken"
        ),
        lambda result: result["loaded"].append(copy.deepcopy(result["loaded"][0])),
        lambda result: result["budget"].update(used_tokens=89),
        lambda result: result["why_loaded"].pop("SHOULD-01"),
        lambda result: result["errors"].append({"code": "BAD", "detail": "矛盾"}),
    ],
)
def test_render_rejects_bad_identity_duplicates_budget_and_state_contradictions(
    corrupt,
) -> None:
    should = _material(
        "SHOULD-01",
        tokens=30,
        actuality="CURRENT_FACT_OR_STATE",
        obligation="SHOULD",
        rank=1,
    )
    result = packer_tool.execute(
        _request(should, _hard("HARD-01", 60), budget=90)
    )
    corrupt(result)

    with pytest.raises(packer_tool.PackerToolError):
        packer_tool.render(result)


def test_render_cli_file_and_stdin_are_stable_and_match_object_render(
    tmp_path: Path,
) -> None:
    result = packer_tool.execute(_request(_hard("HARD-01", 20), budget=100))
    input_path = tmp_path / "result.json"
    output_path = tmp_path / "receipt.txt"
    _write_json(input_path, result)
    command = [
        sys.executable,
        str(PACKER_TOOL_SCRIPT),
        "--render",
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    ]

    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert completed.returncode == 0, completed.stderr
    first = output_path.read_bytes()
    assert first == packer_tool.render(result).encode("utf-8")

    repeated = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert repeated.returncode == 0, repeated.stderr
    assert output_path.read_bytes() == first

    stdout = io.StringIO()
    assert (
        packer_tool.main(
            ["--render"],
            stdin=io.StringIO(json.dumps(result, ensure_ascii=False)),
            stdout=stdout,
        )
        == 0
    )
    assert stdout.getvalue().encode("utf-8") == first


def test_render_atomic_failure_preserves_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "result.json"
    output_path = tmp_path / "receipt.txt"
    _write_json(
        input_path,
        packer_tool.execute(_request(_hard("HARD-01", 20), budget=100)),
    )
    output_path.write_text("旧清单\n", encoding="utf-8")
    before = output_path.read_bytes()

    def fail_replace(_source: str, _target: Path) -> None:
        raise OSError("synthetic render replace failure")

    monkeypatch.setattr(packer_tool.os, "replace", fail_replace)
    stderr = io.StringIO()
    code = packer_tool.main(
        ["--render", "--input", str(input_path), "--output", str(output_path)],
        stderr=stderr,
    )

    assert code == 2
    assert "synthetic render replace failure" in stderr.getvalue()
    assert output_path.read_bytes() == before
    assert not list(tmp_path.glob(".receipt.txt.*.tmp"))


def _spoiler_omission_request() -> dict:
    return _request(
        _hard("HARD-SAFE", 20),
        _material(
            "凶手其实是店主",
            tokens=10,
            actuality="FUTURE_PLAN_OR_PROJECTION",
            obligation="MAY",
            rank=1,
            handle="plan://reveal/killer-shopkeeper",
        ),
        _material(
            "MAY-BUDGET",
            tokens=90,
            actuality="CURRENT_FACT_OR_STATE",
            obligation="MAY",
            rank=2,
        ),
        budget=30,
    )


def _assert_hides_omission_identity(text: str) -> None:
    secrets = (
        "凶手其实是店主",
        "凶手",
        "店主",
        "MAY-BUDGET",
        "plan://reveal/killer-shopkeeper",
        "killer",
        "shopkeeper",
        "plan://",
        "material://MAY-BUDGET",
        "OUTSIDE_TASK_ACTUALITY_SCOPE",
        "BUDGET_OPTIONAL_DEFERRED",
    )
    for secret in secrets:
        assert secret not in text
    for raw in ("凶手其实是店主", "plan://reveal/killer-shopkeeper", "MAY-BUDGET"):
        encoded = raw.encode("utf-8")
        assert hashlib.sha256(encoded).hexdigest() not in text
        assert base64.b64encode(encoded).decode("ascii") not in text
        assert raw[:4] not in text


def test_author_safe_render_hides_omission_identity_and_keeps_machine_refs() -> None:
    result = packer_tool.execute(_spoiler_omission_request())
    technical = packer_tool.render(result)
    author_text = packer_tool.render_author_safe(result)

    assert result["decision_state"] == "READY"
    assert [item["id"] for item in result["loaded"]] == ["HARD-SAFE"]
    omitted_by_id = {row["id"]: row for row in result["omitted"]}
    assert omitted_by_id["凶手其实是店主"] == {
        "id": "凶手其实是店主",
        "reason": "OUTSIDE_TASK_ACTUALITY_SCOPE",
        "recall_disposition": "RETRIEVABLE",
        "recall_handle": "plan://reveal/killer-shopkeeper",
    }
    assert omitted_by_id["MAY-BUDGET"]["reason"] == "BUDGET_OPTIONAL_DEFERRED"
    assert omitted_by_id["MAY-BUDGET"]["recall_handle"] == "material://MAY-BUDGET"

    assert "1. HARD-SAFE｜义务 HARD" in author_text
    assert "已阻断 2 条" in author_text
    assert "超出当前故事时点或本次任务允许范围：1 条" in author_text
    assert "本次预算未装入：1 条" in author_text
    assert "可由系统重新检查：2 条" in author_text
    _assert_hides_omission_identity(author_text)

    assert "凶手其实是店主｜原因 OUTSIDE_TASK_ACTUALITY_SCOPE" in technical
    assert "回取：可回取，入口 plan://reveal/killer-shopkeeper" in technical
    assert "MAY-BUDGET｜原因 BUDGET_OPTIONAL_DEFERRED" in technical


def test_author_safe_not_retrievable_omission_is_not_recheckable() -> None:
    result = packer_tool.execute(
        _request(
            _hard("HARD-SAFE", 20),
            _material(
                "凶手其实是店主",
                tokens=10,
                actuality="FUTURE_PLAN_OR_PROJECTION",
                obligation="MAY",
                rank=1,
                recall="NOT_RETRIEVABLE",
                handle=None,
            ),
            budget=30,
        )
    )

    author_text = packer_tool.render_author_safe(result)

    assert result["omitted"][0]["recall_disposition"] == "NOT_RETRIEVABLE"
    assert "已阻断 1 条" in author_text
    assert "可由系统重新检查：0 条" in author_text
    assert "凶手" not in author_text
    assert "店主" not in author_text


def test_author_safe_unknown_omission_reason_fails_closed_without_raw_reason() -> None:
    result = packer_tool.execute(_spoiler_omission_request())
    result["omitted"][0]["reason"] = "凶手其实是店主"

    with pytest.raises(
        packer_tool.PackerToolError,
        match="AUTHOR_SAFE_OMISSION_REASON_UNKNOWN",
    ) as caught:
        packer_tool.render_author_safe(result)

    assert str(caught.value) == "AUTHOR_SAFE_OMISSION_REASON_UNKNOWN"
    assert "凶手" not in str(caught.value)

    stderr = io.StringIO()
    stdout = io.StringIO()
    code = packer_tool.main(
        ["--render-author-safe"],
        stdin=io.StringIO(json.dumps(result, ensure_ascii=False)),
        stdout=stdout,
        stderr=stderr,
    )
    assert code == 2
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == (
        "M11_PACKER_TOOL_REJECTED:AUTHOR_SAFE_OMISSION_REASON_UNKNOWN\n"
    )


def test_author_safe_cli_file_and_stdin_are_stable_and_match_object_render(
    tmp_path: Path,
) -> None:
    result = packer_tool.execute(_spoiler_omission_request())
    input_path = tmp_path / "result.json"
    output_path = tmp_path / "author.txt"
    _write_json(input_path, result)
    command = [
        sys.executable,
        str(PACKER_TOOL_SCRIPT),
        "--render-author-safe",
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    ]

    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert completed.returncode == 0, completed.stderr
    first = output_path.read_bytes()
    assert first == packer_tool.render_author_safe(result).encode("utf-8")
    _assert_hides_omission_identity(first.decode("utf-8"))

    repeated = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert repeated.returncode == 0, repeated.stderr
    assert output_path.read_bytes() == first

    stdout = io.StringIO()
    assert (
        packer_tool.main(
            ["--render-author-safe"],
            stdin=io.StringIO(json.dumps(result, ensure_ascii=False)),
            stdout=stdout,
        )
        == 0
    )
    assert stdout.getvalue().encode("utf-8") == first


def test_author_safe_atomic_failure_preserves_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "result.json"
    output_path = tmp_path / "author.txt"
    _write_json(input_path, packer_tool.execute(_spoiler_omission_request()))
    output_path.write_text("旧作者页\n", encoding="utf-8")
    before = output_path.read_bytes()

    def fail_replace(_source: str, _target: Path) -> None:
        raise OSError("synthetic author-safe replace failure")

    monkeypatch.setattr(packer_tool.os, "replace", fail_replace)
    stderr = io.StringIO()
    code = packer_tool.main(
        [
            "--render-author-safe",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        stderr=stderr,
    )

    assert code == 2
    assert "synthetic author-safe replace failure" in stderr.getvalue()
    assert output_path.read_bytes() == before
    assert not list(tmp_path.glob(".author.txt.*.tmp"))


def test_render_and_render_author_safe_flags_are_mutually_exclusive(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "result.json"
    _write_json(input_path, packer_tool.execute(_request(_hard("HARD-01", 20))))

    completed = subprocess.run(
        [
            sys.executable,
            str(PACKER_TOOL_SCRIPT),
            "--render",
            "--render-author-safe",
            "--input",
            str(input_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )

    assert completed.returncode != 0
    assert completed.stdout == ""
    assert "not allowed with argument" in completed.stderr
