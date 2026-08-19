from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"
CHECK_TOOL_SCRIPT = PRODUCT_ROOT / "mvp" / "check_tool.py"
C11_SCHEMA = PRODUCT_ROOT / "contracts" / "C11_CHAPTER_REVISION_LEDGER.schema.json"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from mvp import check_tool
finally:
    sys.path.pop(0)


CURRENT_TEXT = "林乔说钥匙在自己手里。片刻后，苏晚说钥匙一直在她手里。"
OLD_TEXT = "林乔把钥匙放在桌上。"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _revision_ref(
    *,
    revision_no: int = 2,
    text: str = CURRENT_TEXT,
) -> dict:
    return {
        "chapter_id": "c01",
        "revision_no": revision_no,
        "revision_text_sha256": _sha(text),
    }


def _fact(
    fact_id: str,
    *,
    text: str,
    quote: str,
    status: str = "confirmed",
    revision_no: int = 2,
    revision_text: str = CURRENT_TEXT,
    anchor_state: str = "VERIFIED",
) -> dict:
    start = revision_text.index(quote) if quote in revision_text else 0
    revision_ref = _revision_ref(revision_no=revision_no, text=revision_text)
    return {
        "contract": "C4_FACT_QUERY",
        "version": "v1",
        "id": fact_id,
        "chapter_id": "c01",
        "text": text,
        "quote": quote,
        "status": status,
        "source": "fixture-c4-snapshot",
        "note": "",
        "added_at": "2026-08-19 11:00:00",
        "seg": 1,
        "decided_at": "2026-08-19 11:01:00",
        "chapter_revision_ref": revision_ref,
        "anchor_ref": (
            {
                **revision_ref,
                "coordinate_basis": check_tool.COORDINATE_BASIS,
                "start": start,
                "end": start + len(quote),
                "slice_sha256": _sha(quote),
            }
            if anchor_state == "VERIFIED"
            else None
        ),
        "anchor_state": anchor_state,
        "recheck": (
            {
                "previous_status": "confirmed",
                "reason": "evidence_gone",
                "from_revision_no": 1,
                "target_revision_no": 2,
                "flagged_at": "2026-08-19 11:02:00",
            }
            if status == "needs_recheck"
            else None
        ),
    }


def _facts() -> tuple[dict, dict]:
    return (
        _fact(
            "f001",
            text="林乔说钥匙在自己手里。",
            quote="林乔说钥匙在自己手里",
        ),
        _fact(
            "f002",
            text="苏晚说钥匙一直在她手里。",
            quote="苏晚说钥匙一直在她手里",
        ),
    )


def _request(*facts: dict) -> dict:
    return {
        "project": "合成钥匙案",
        "generated_at": "2026-08-19 11:30:00",
        "facts": list(facts),
        "current_revision_refs": [_revision_ref()],
        "check_config": {
            "scope_name": "全量当前真值",
            "scope_kind": "leftover",
            "kinds": ["naming", "timeline", "setting", "event"],
        },
    }


def _finding(**overrides: object) -> dict:
    value = {
        "fact_ids": ["f001", "f002"],
        "kind": "setting",
        "verdict": "conflict",
        "severity": "red",
        "hard": True,
        "confidence": "high",
        "note": "同一把钥匙在同一时点被两人分别声称持有。",
    }
    value.update(overrides)
    return value


def _frozen(*findings: dict) -> dict:
    return {
        "provider_id": "frozen-offline-health-map-v1",
        "model_calls": 0,
        "response": {"findings": list(findings)},
    }


class _RecordingProvider:
    provider_id = "recording-frozen-provider"
    model_calls = 0

    def __init__(self, response: dict):
        self.response = response
        self.batch: dict | None = None

    def find(self, batch: dict) -> dict:
        self.batch = copy.deepcopy(batch)
        return copy.deepcopy(self.response)


def test_execute_builds_current_c6_v1_with_bound_evidence_and_zero_calls() -> None:
    fact_a, fact_b = _facts()
    request = _request(fact_a, fact_b)
    before = copy.deepcopy(request)

    report = check_tool.execute(
        request,
        check_tool.FrozenFindingProvider(_frozen(_finding())),
    )

    assert report["contract"] == "C6_HEALTH_REPORT"
    assert report["version"] == "v1"
    assert report["source_revision_state"] == "CURRENT"
    assert report["model"] == "frozen-offline-health-map-v1"
    assert report["chapter_revision_refs"] == [_revision_ref()]
    assert report["scan"]["api_calls"] == 0
    assert report["scan"]["total_tokens"] == 0
    assert report["scan"]["groups"] == [
        {
            "name": "全量当前真值",
            "kind": "leftover",
            "facts": 2,
            "status": "ok",
            "findings": 1,
        }
    ]
    conflict = report["conflicts"][0]
    assert conflict["issue_id"] == "h001"
    assert conflict["layer"] == "confirmed"
    assert conflict["severity"] == "red"
    assert [row["fact_id"] for row in conflict["evidence"]] == ["f001", "f002"]
    assert conflict["evidence"][0]["anchor_ref"] == fact_a["anchor_ref"]
    assert report["summary"]["red"] == 1
    assert request == before
    Draft202012Validator(json.loads(C11_SCHEMA.read_text(encoding="utf-8"))).validate(
        report
    )


def test_current_extracted_candidate_participates_and_produces_mixed_layer() -> None:
    fact_a, fact_b = _facts()
    fact_b["status"] = "extracted"
    fact_b.pop("decided_at")

    report = check_tool.execute(
        _request(fact_a, fact_b),
        check_tool.FrozenFindingProvider(_frozen(_finding())),
    )

    assert report["scan"]["confirmed"] == 1
    assert report["scan"]["extracted"] == 1
    assert report["conflicts"][0]["layer"] == "mixed"
    assert report["summary"]["by_layer"] == {
        "confirmed": 0,
        "mixed": 1,
        "candidate": 0,
    }


def test_old_revision_rejected_needs_recheck_and_bad_anchor_are_excluded() -> None:
    fact_a, fact_b = _facts()
    stale = _fact(
        "f003",
        text="林乔把钥匙放在桌上。",
        quote="林乔把钥匙放在桌上",
        revision_no=1,
        revision_text=OLD_TEXT,
    )
    rejected = _fact(
        "f004",
        text="被作者驳回的钥匙说法。",
        quote="林乔说钥匙在自己手里",
        status="rejected",
    )
    needs_recheck = _fact(
        "f005",
        text="需要重查的钥匙说法。",
        quote="苏晚说钥匙一直在她手里",
        status="needs_recheck",
    )
    bad_anchor = _fact(
        "f006",
        text="锚损坏的钥匙说法。",
        quote="林乔说钥匙在自己手里",
    )
    bad_anchor["anchor_ref"]["slice_sha256"] = "0" * 64

    provider = _RecordingProvider({"findings": [_finding()]})
    report = check_tool.execute(
        _request(fact_a, fact_b, stale, rejected, needs_recheck, bad_anchor),
        provider,
    )

    counts = report["scan"]["excluded_counts"]
    assert counts["stale_revision"] == 1
    assert counts["rejected"] == 1
    assert counts["needs_recheck"] == 1
    assert counts["invalid_evidence"] == 1
    assert report["scan"]["facts_total"] == 2
    assert {
        row["fact_id"]
        for finding in report["conflicts"]
        for row in finding["evidence"]
    } == {"f001", "f002"}
    assert provider.batch is not None
    assert [fact["id"] for fact in provider.batch["facts"]] == ["f001", "f002"]


@pytest.mark.parametrize(
    "bad_response",
    [
        {"findings": [_finding(fact_ids=["f001", "f999"])]},
        {"findings": [{key: value for key, value in _finding().items() if key != "note"}]},
        {"findings": [{**_finding(), "extra": "forbidden"}]},
        {"findings": [_finding(severity="critical")]},
    ],
    ids=["unknown-fact", "missing-field", "extra-field", "bad-severity"],
)
def test_bad_provider_output_rejects_whole_batch(bad_response: dict) -> None:
    fact_a, fact_b = _facts()
    provider = check_tool.FrozenFindingProvider(
        {
            "provider_id": "bad-frozen-provider",
            "model_calls": 0,
            "response": bad_response,
        }
    )

    with pytest.raises(check_tool.CheckToolError):
        check_tool.execute(_request(fact_a, fact_b), provider)


def test_cli_normal_file_chain_is_restart_parseable(tmp_path: Path) -> None:
    fact_a, fact_b = _facts()
    input_path = tmp_path / "request.json"
    responses_path = tmp_path / "responses.json"
    output_path = tmp_path / "health_report.json"
    input_path.write_text(
        json.dumps(_request(fact_a, fact_b), ensure_ascii=False),
        encoding="utf-8",
    )
    responses_path.write_text(
        json.dumps(_frozen(_finding()), ensure_ascii=False),
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    completed = subprocess.run(
        [
            sys.executable,
            str(CHECK_TOOL_SCRIPT),
            "--input",
            str(input_path),
            "--responses",
            str(responses_path),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr
    reread = json.loads(output_path.read_text(encoding="utf-8"))
    assert reread["contract"] == "C6_HEALTH_REPORT"
    assert reread["conflicts"][0]["evidence"][1]["fact_id"] == "f002"
    assert reread["scan"]["api_calls"] == 0


def test_batch_failure_does_not_overwrite_existing_output(tmp_path: Path) -> None:
    fact_a, fact_b = _facts()
    input_path = tmp_path / "request.json"
    responses_path = tmp_path / "responses.json"
    output_path = tmp_path / "health_report.json"
    input_path.write_text(
        json.dumps(_request(fact_a, fact_b), ensure_ascii=False),
        encoding="utf-8",
    )
    responses_path.write_text(
        json.dumps(
            _frozen(_finding(fact_ids=["f001", "f999"])),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output_path.write_text('{"sentinel":"old"}\n', encoding="utf-8")
    before = output_path.read_bytes()
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    completed = subprocess.run(
        [
            sys.executable,
            str(CHECK_TOOL_SCRIPT),
            "--input",
            str(input_path),
            "--responses",
            str(responses_path),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 2
    assert "未知 fact" in completed.stderr
    assert output_path.read_bytes() == before


def test_atomic_replace_failure_preserves_old_output_and_removes_tmp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "health_report.json"
    output_path.write_text('{"sentinel":"old"}\n', encoding="utf-8")
    before = output_path.read_bytes()

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("synthetic replace failure")

    monkeypatch.setattr(check_tool.os, "replace", fail_replace)
    with pytest.raises(OSError, match="synthetic replace failure"):
        check_tool._atomic_write_json(output_path, {"contract": "synthetic"})

    assert output_path.read_bytes() == before
    assert list(tmp_path.glob(".health_report.json.*.tmp")) == []


def test_execute_rejects_path_instead_of_reading_project_files() -> None:
    with pytest.raises(check_tool.CheckToolError, match="request 必须是对象"):
        check_tool.execute(  # type: ignore[arg-type]
            Path("facts.json"),
            check_tool.FrozenFindingProvider(_frozen()),
        )


def _multi_severity_report() -> dict:
    fact_a, fact_b = _facts()
    fact_c = _fact(
        "f003",
        text="林乔再次确认钥匙在自己手里。",
        quote="林乔说钥匙在自己手里",
    )
    fact_d = _fact(
        "f004",
        text="苏晚再次确认钥匙在她手里。",
        quote="苏晚说钥匙一直在她手里",
    )
    yellow = _finding(
        fact_ids=["f003", "f004"],
        kind="event",
        severity="yellow",
        hard=False,
        confidence="low",
        note="两条事项可能互斥，但现有材料不足以判为硬矛盾。",
    )
    return check_tool.execute(
        _request(fact_a, fact_b, fact_c, fact_d),
        check_tool.FrozenFindingProvider(_frozen(_finding(), yellow)),
    )


def test_render_multi_severity_report_is_complete_and_human_readable() -> None:
    report = _multi_severity_report()

    rendered = check_tool.render_report(report)

    assert "报告身份：C6_HEALTH_REPORT v1" in rendered
    assert "生成时间：2026-08-19 11:30:00" in rendered
    assert "Provider：frozen-offline-health-map-v1" in rendered
    assert "原报告记录 API 调用 0 次" in rendered
    assert "事实水位：纳入 4 条；已确认 4 条；候选 0 条" in rendered
    assert f"SHA {_revision_ref()['revision_text_sha256']}" in rendered
    assert "### h001 · 矛盾" in rendered
    assert "### h002 · 矛盾" in rendered
    assert "严重度：red" in rendered
    assert "严重度：yellow" in rendered
    assert "类别：setting" in rendered
    assert "类别：event" in rendered
    assert "事实号：f001, f002" in rendered
    assert "引文：林乔说钥匙在自己手里" in rendered
    assert "锚点：c01 / revision 2" in rendered
    assert "## 排除、弃权与未知项" in rendered
    assert "current_revision_missing：0" in rendered
    assert "通过" not in rendered
    assert "全绿" not in rendered


@pytest.mark.parametrize(
    "category",
    ["mismatch", "missing", "unplanned", "unknown"],
)
def test_render_preserves_open_category_without_positive_claim(category: str) -> None:
    fact_a, fact_b = _facts()
    report = check_tool.execute(
        _request(fact_a, fact_b),
        check_tool.FrozenFindingProvider(_frozen(_finding())),
    )
    report["conflicts"][0]["kind"] = category
    report["summary"]["by_kind"]["setting"] = 0
    report["summary"]["by_kind"][category] = 1

    rendered = check_tool.render_report(report)

    assert f"类别：{category}" in rendered
    assert "以上类别按原报告展示，没有给出整体结论" in rendered
    assert "通过" not in rendered
    assert "全绿" not in rendered


def test_render_empty_findings_is_explicitly_inconclusive() -> None:
    report = check_tool.execute(
        _request(),
        check_tool.FrozenFindingProvider(_frozen()),
    )

    rendered = check_tool.render_report(report)

    assert "本次未返回 finding；这不能证明没有问题" in rendered
    assert "通过" not in rendered
    assert "全绿" not in rendered
    assert "invalid_c4_v1：0" in rendered


@pytest.mark.parametrize(
    "damage",
    [
        "duplicate-finding",
        "bad-evidence-ref",
        "bad-severity",
        "bad-source-ref",
        "schema-drift",
    ],
)
def test_validate_and_render_reject_corrupt_report(damage: str) -> None:
    report = _multi_severity_report()
    if damage == "duplicate-finding":
        duplicate = copy.deepcopy(report["conflicts"][0])
        duplicate["issue_id"] = "h999"
        report["conflicts"].append(duplicate)
        report["scan"]["groups"][0]["findings"] += 1
        report["summary"]["red"] += 1
        report["summary"]["by_layer"]["confirmed"] += 1
        report["summary"]["by_kind"]["setting"] += 1
    elif damage == "bad-evidence-ref":
        report["conflicts"][0]["evidence"][0]["fact_id"] = "f999"
    elif damage == "bad-severity":
        report["conflicts"][0]["severity"] = "critical"
    elif damage == "bad-source-ref":
        report["chapter_revision_refs"][0]["revision_text_sha256"] = "0" * 64
    else:
        report["unexpected"] = True

    with pytest.raises(check_tool.CheckToolError):
        check_tool.validate_report(report)
    with pytest.raises(check_tool.CheckToolError):
        check_tool.render_report(report)


def test_render_cli_is_cross_process_byte_stable_and_uses_no_responses(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "health_report.json"
    report_path.write_text(
        json.dumps(_multi_severity_report(), ensure_ascii=False),
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [
        sys.executable,
        str(CHECK_TOOL_SCRIPT),
        "--render",
        "--input",
        str(report_path),
        "--output",
        "-",
    ]

    first = subprocess.run(
        command,
        check=False,
        capture_output=True,
        env=environment,
    )
    second = subprocess.run(
        command,
        check=False,
        capture_output=True,
        env=environment,
    )

    assert first.returncode == second.returncode == 0, first.stderr + second.stderr
    assert first.stdout == second.stdout
    assert "Provider：frozen-offline-health-map-v1" in first.stdout.decode("utf-8")
    assert b"responses" not in first.stdout


def test_render_cli_failure_preserves_existing_output(tmp_path: Path) -> None:
    report = _multi_severity_report()
    report["conflicts"][0]["evidence"][0]["fact_id"] = "f999"
    report_path = tmp_path / "bad_report.json"
    output_path = tmp_path / "health_report.txt"
    report_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    output_path.write_text("旧的人读报告\n", encoding="utf-8")
    before = output_path.read_bytes()
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    completed = subprocess.run(
        [
            sys.executable,
            str(CHECK_TOOL_SCRIPT),
            "--render",
            "--input",
            str(report_path),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 2
    assert "check_tool error" in completed.stderr
    assert output_path.read_bytes() == before
    assert list(tmp_path.glob(".health_report.txt.*.tmp")) == []
