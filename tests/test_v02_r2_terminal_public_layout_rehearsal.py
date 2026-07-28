from __future__ import annotations

from pathlib import Path

import pytest

from experiments.V02_R2_terminal_once_20260727 import (
    public_layout_rehearsal as rehearsal,
)
from experiments.V02_R2_terminal_once_20260727 import (
    terminal_controller as terminal,
)


ROOT = Path(__file__).resolve().parents[1]
HANDOFF = (
    ROOT
    / "reports/单管线多工位_统一收件箱_20260727"
    / "主线三_M3-06_R2终验重开新卷_20260727_2145"
)
HANDOFF_RELATIVE = HANDOFF.relative_to(ROOT)


def test_m3_06_public_layout_runs_full_zero_api_pipeline(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fail_if_model_invoked(**_: object) -> None:
        raise AssertionError("公开彩排不得调用模型")

    monkeypatch.setattr(terminal, "invoke_model", fail_if_model_invoked)
    result = rehearsal.run_rehearsal(
        ticket_path=HANDOFF_RELATIVE / "SEAL_TICKET.json",
        contract_path=HANDOFF_RELATIVE / "QUESTION_SET_LAYOUT_CONTRACT.json",
        sample_path=HANDOFF_RELATIVE / "FAKE_QUESTION_SET_SAMPLE.json",
        output_dir=tmp_path,
        expected_ticket_id="M3-06-R2-TERMINAL-30-REOPEN-20260727-2145",
    )

    assert result["status"] == "PASS"
    assert result["contract"]["parser_sha256"] == terminal.sha256_file(
        Path(terminal.__file__)
    )
    assert result["pipeline"]["expanded_question_cell_total"] == 30
    assert result["pipeline"]["per_case_cell_count"] == {
        "SYN-LAYOUT-A": 10,
        "SYN-LAYOUT-B": 10,
        "SYN-LAYOUT-C": 10,
    }
    assert result["pipeline"]["request_adapter_total"] == 60
    assert result["pipeline"]["answer_adapter_total"] == 60
    assert result["pipeline"]["gold_adapter_cell_count"] == 30
    assert result["pipeline"]["score_row_total"] == 60
    assert result["pipeline"]["public_rehearsal_semantic_stub_adapter"] == {
        "enabled": True,
        "scope": "PUBLIC_ZERO_API_REHEARSAL_ONLY",
        "reason": (
            "公开假题不对应开发集语义槽；仅替换离线规划文本，"
            "保留题号、格数和顺序，不进入正式运行。"
        ),
        "stub_count": 10,
        "question_ids_preserved": True,
        "formal_runtime_allowed": False,
        "semantic_quality_evidence": False,
    }
    assert result["pipeline"]["semantic_quality_gate_evaluated"] is False
    assert result["negative_layout_case_total"] >= 20
    assert result["wrong_layout_rejection_passed"] is True
    assert result["model_api_calls"] == 0
    assert result["network_requests"] == 0
    assert result["private_terminal_files_read"] == 0
    assert result["sealed_directory_reads"] == 0
    assert result["formal_cycle_created"] is False
    assert result["formal_run_created"] is False
    assert result["formal_terminal_ticket_consumed"] is False
    assert (tmp_path / "PUBLIC_LAYOUT_REHEARSAL_RECEIPT.json").is_file()


def test_public_layout_rehearsal_rejects_wrong_ticket_binding(
    tmp_path: Path,
) -> None:
    with pytest.raises(rehearsal.PublicRehearsalError, match="TICKET_ID_INVALID"):
        rehearsal.run_rehearsal(
            ticket_path=HANDOFF_RELATIVE / "SEAL_TICKET.json",
            contract_path=HANDOFF_RELATIVE / "QUESTION_SET_LAYOUT_CONTRACT.json",
            sample_path=HANDOFF_RELATIVE / "FAKE_QUESTION_SET_SAMPLE.json",
            output_dir=tmp_path,
            expected_ticket_id="M3-07-WRONG-TICKET",
        )


@pytest.mark.parametrize(
    "ticket_path",
    [
        HANDOFF / "SEAL_TICKET.json",
        Path("../escape/SEAL_TICKET.json"),
        Path("sealed/SEAL_TICKET.json"),
        Path("public/private-ticket.json"),
        Path("public\\ticket.json"),
    ],
)
def test_public_layout_rehearsal_rejects_non_public_input_paths(
    tmp_path: Path,
    ticket_path: Path,
) -> None:
    with pytest.raises(
        rehearsal.PublicRehearsalError,
        match="TICKET_INPUT_PUBLIC_PATH_INVALID",
    ):
        rehearsal.run_rehearsal(
            ticket_path=ticket_path,
            contract_path=HANDOFF_RELATIVE / "QUESTION_SET_LAYOUT_CONTRACT.json",
            sample_path=HANDOFF_RELATIVE / "FAKE_QUESTION_SET_SAMPLE.json",
            output_dir=tmp_path,
            expected_ticket_id="M3-07-WRONG-TICKET",
        )


def test_public_layout_rehearsal_rejects_symlink_input(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    public_dir = project_root / "public"
    public_dir.mkdir(parents=True)
    target = project_root / "ticket-target.json"
    target.write_text("{}\n", encoding="utf-8")
    (public_dir / "SEAL_TICKET.json").symlink_to(target)

    with pytest.raises(
        rehearsal.PublicRehearsalError,
        match="TICKET_INPUT_PUBLIC_PATH_INVALID",
    ):
        rehearsal.run_rehearsal(
            ticket_path=Path("public/SEAL_TICKET.json"),
            contract_path=Path("public/contract.json"),
            sample_path=Path("public/sample.json"),
            output_dir=tmp_path / "output",
            expected_ticket_id="M3-07-WRONG-TICKET",
            project_root=project_root,
        )
