import importlib.util
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "tools" / "audit_r02_contracts.py"
spec = importlib.util.spec_from_file_location("audit_r02_contracts", MODULE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_duplicate_occurrences_are_all_returned():
    assert audit.occurrences("甲乙。甲乙。", "甲乙") == [(0, 2), (3, 5)]


def test_candidate_mapping_does_not_choose_first():
    units = [
        {"char_start": 0, "char_end": 3, "local_id": "T01"},
        {"char_start": 3, "char_end": 6, "local_id": "T02"},
    ]
    first = audit.mapped_candidate(units, 0, 2, 2)
    second = audit.mapped_candidate(units, 3, 5, 2)
    assert first["evidence_ids"] == ["T01"]
    assert second["evidence_ids"] == ["T02"]
    assert first["evidence_ids"] != second["evidence_ids"]
