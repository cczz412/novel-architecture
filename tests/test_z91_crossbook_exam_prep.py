from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import z91_crossbook_exam_prep as z91
from zbatch_modules.errors import ZBatchError


def test_build_payloads_is_deterministic_and_keeps_all_arm_messages_identical() -> None:
    first, meta = z91.build_payloads()
    second, _ = z91.build_payloads()

    assert first == second
    assert meta["receipt"]["model_api_calls"] == 0
    assert meta["receipt"]["network_attempts"] == 0
    assert meta["receipt"]["step2_locked"] is True
    matrix = json.loads(first["request_matrix.json"])
    by_case: dict[str, set[str]] = {}
    for row in matrix["rows"]:
        by_case.setdefault(row["case_key"], set()).add(row["messages_sha256"])
    assert len(matrix["rows"]) == 12
    assert all(len(values) == 1 for values in by_case.values())


def test_cloud_pro_requests_use_provider_specific_fields_without_official_api() -> None:
    payloads, meta = z91.build_payloads()
    case = "cases/X02-C0031/requests"
    tencent = json.loads(payloads[f"{case}/pro_primary_tencent.json"])
    qianwen = json.loads(payloads[f"{case}/pro_standby_qianwen.json"])
    volcengine = json.loads(payloads[f"{case}/pro_standby_volcengine.json"])

    assert tencent["model"] == "deepseek-v4-pro-202606"
    assert tencent["thinking"] == {
        "type": "enabled",
        "reasoning_effort": "medium",
    }
    assert "response_format" not in tencent
    assert "reasoning_effort" not in tencent

    assert qianwen["model"] == "deepseek-v4-pro"
    assert qianwen["enable_thinking"] is True
    assert qianwen["reasoning_effort"] == "medium"
    assert qianwen["max_completion_tokens"] == 32000
    assert "max_tokens" not in qianwen
    assert "response_format" not in qianwen
    assert "n" not in qianwen

    assert volcengine["model"] == "deepseek-v4-pro-260425"
    assert volcengine["thinking"] == {"type": "enabled"}
    assert volcengine["reasoning_effort"] == "medium"
    assert "response_format" not in volcengine
    assert "n" not in volcengine

    assert meta["provider_plan"]["official_deepseek_api"] == (
        "forbidden_not_a_fallback"
    )
    assert meta["provider_plan"]["recommended_primary"]["provider"] == (
        "tencent_tokenhub"
    )


def test_probe_slots_are_source_anchored_but_do_not_contain_answers() -> None:
    payloads, _ = z91.build_payloads()
    probes = json.loads(payloads["probe_slots.json"])

    assert probes["slot_count"] == 18
    assert probes["gold_status"] == "not_gold_not_silver_answer_set"
    assert all(row["source_fact"] is None for row in probes["slots"])
    assert all(row["source_quote"] for row in probes["slots"])
    request_bytes = b"".join(
        raw
        for name, raw in payloads.items()
        if "/requests/" in name and not name.endswith("_diff.json")
    )
    assert b"slot_frozen_fact_pending_rubric_approval" not in request_bytes


def test_prepare_and_audit_are_zero_call_and_refuse_overwrite(tmp_path: Path) -> None:
    run_dir = tmp_path / "z91"

    receipt = z91.prepare(run_dir)
    audit = z91.audit_run(run_dir)

    assert receipt["model_api_calls"] == 0
    assert receipt["network_attempts"] == 0
    assert receipt["tokens"] == 0
    assert audit["status"] == "pass"
    verification = json.loads(
        (run_dir / "mechanical_verification.json").read_text(encoding="utf-8")
    )
    assert verification["status"] == "pass_twice_identical"
    assert verification["protected_unchanged"] is True

    with pytest.raises(ZBatchError, match="拒绝覆盖或复跑"):
        z91.prepare(run_dir)


def test_source_pins_cover_cloud_configs_and_generator_dependencies() -> None:
    payloads, _ = z91.build_payloads()
    pins = json.loads(payloads["provenance/source_pins.json"])

    assert set(pins["provider_configs"]) == {
        "qianwen_platform",
        "tencent_tokenhub",
        "volcengine_ark",
    }
    assert set(pins["generator_dependencies"]) == {
        "z91_prepare",
        "evidence_catalog",
        "z68_instantiation_helpers",
        "z79_v3_contract",
        "z80_crossbook_instantiation",
    }
    for group in ("provider_configs", "generator_dependencies"):
        for row in pins[group].values():
            path = z91.ROOT / row["path"]
            assert path.is_file()
            assert row["sha256"] == z91.sha256_file(path)


def test_audit_rejects_unregistered_file(tmp_path: Path) -> None:
    run_dir = tmp_path / "z91"
    z91.prepare(run_dir)
    (run_dir / "unregistered_request.json").write_text(
        '{"Authorization":"Bearer fake"}\n', encoding="utf-8"
    )

    with pytest.raises(ZBatchError, match="未登记或缺失文件"):
        z91.audit_run(run_dir)


def test_audit_rejects_manifest_vector_tampering(tmp_path: Path) -> None:
    run_dir = tmp_path / "z91"
    z91.prepare(run_dir)
    manifest_path = run_dir / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["vector_sha256"] = "0" * 64
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ZBatchError, match="向量 SHA"):
        z91.audit_run(run_dir)


def test_audit_rejects_mechanical_ticket_tampering(tmp_path: Path) -> None:
    run_dir = tmp_path / "z91"
    z91.prepare(run_dir)
    ticket_path = run_dir / "mechanical_verification.json"
    ticket = json.loads(ticket_path.read_text(encoding="utf-8"))
    ticket["protected_unchanged"] = False
    ticket_path.write_text(
        json.dumps(ticket, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ZBatchError, match="机械保护票"):
        z91.audit_run(run_dir)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "tampered"),
        ("false_claim", "pass"),
    ],
)
def test_audit_requires_exact_mechanical_ticket_contract(
    tmp_path: Path, field: str, value: str
) -> None:
    run_dir = tmp_path / "z91"
    z91.prepare(run_dir)
    ticket_path = run_dir / "mechanical_verification.json"
    ticket = json.loads(ticket_path.read_text(encoding="utf-8"))
    ticket[field] = value
    ticket_path.write_text(
        json.dumps(ticket, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ZBatchError, match="机械保护票"):
        z91.audit_run(run_dir)


def test_audit_rejects_sha256sums_tampering(tmp_path: Path) -> None:
    run_dir = tmp_path / "z91"
    z91.prepare(run_dir)
    pristine = tmp_path / "pristine"
    shutil.copytree(run_dir, pristine)
    (run_dir / "SHA256SUMS").write_text("tampered\n", encoding="utf-8")

    with pytest.raises(ZBatchError, match="SHA256SUMS"):
        z91.audit_run(run_dir)
    assert z91.audit_run(pristine)["status"] == "pass"
