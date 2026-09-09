from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = ROOT / "novel-mvp"

sys.path.insert(0, str(PRODUCT_ROOT))
try:
    from contracts import validate_c10_intake_material_identity as c10_contract
finally:
    sys.path.pop(0)


EXPECTED_LEGACY_SHA256 = {
    "novel-mvp/contracts/C1_CHAPTER_DOC.md": (
        "78441c00f76bcb2d955f157e5369f3176dc40f7b626c07dcc32937fe0fcec4d4"
    ),
    "novel-mvp/contracts/C2_SEGMENT.md": (
        "ee6d36aa3c9edd8877d8d100c626ec94fdaa94ed855868c255bb9104f8557d4f"
    ),
}


def test_c10_formal_validator_reports_current_legacy_contract_locks(capsys) -> None:
    assert c10_contract.main() == 0

    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "PASS"
    assert report["legacy_sha256"] == EXPECTED_LEGACY_SHA256


@pytest.mark.parametrize("relative_path", sorted(EXPECTED_LEGACY_SHA256))
def test_c10_legacy_contract_lock_rejects_one_byte_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative_path: str,
) -> None:
    for source_relative_path in EXPECTED_LEGACY_SHA256:
        source = ROOT / source_relative_path
        copied = tmp_path / source_relative_path
        copied.parent.mkdir(parents=True, exist_ok=True)
        copied.write_bytes(source.read_bytes())

    changed = tmp_path / relative_path
    changed.write_bytes(changed.read_bytes() + b"\n")
    monkeypatch.setattr(c10_contract, "REPO_ROOT", tmp_path)

    with pytest.raises(
        c10_contract.ContractValidationError,
        match=rf"^{re.escape(relative_path)}: legacy SHA drift",
    ):
        c10_contract.validate_legacy_shas()
