"""Generate a compact local replay receipt; no network or source corpus access."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from b03_contracts import LEGACY_CALLER_FIELDS, OUTPUT_TYPES, PROJECTOR_NAME, WRITER_MAP

ROOT = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if set(WRITER_MAP) != OUTPUT_TYPES or not PROJECTOR_NAME:
        raise SystemExit("writer registry drift")
    shapes = json.loads((ROOT / "OBJECT_SHAPES.json").read_text(encoding="utf-8"))
    if set(shapes["forbidden_caller_keys"]) != LEGACY_CALLER_FIELDS:
        raise SystemExit("legacy caller-field catalog drift")
    checked = []
    for path in sorted(ROOT.glob("*.py")):
        if path.name == "self_check.py":
            continue
        content = path.read_text(encoding="utf-8")
        # Range vocabulary is allowed only in the explicit legacy-rejection test.
        if (
            path.name not in {"b03_contracts.py", "test_b03_bound_evidence_read.py"}
            and "max_chars" in content
        ):
            raise SystemExit(f"legacy limit leaked into {path.name}")
        checked.append({"path": path.name, "sha256": sha(path)})
    service_text = (ROOT / "service.py").read_text(encoding="utf-8")
    store_text = (ROOT / "b03_store.py").read_text(encoding="utf-8")
    if "self.store" in service_text or "authorization_validator" in store_text:
        raise SystemExit("replaceable plaintext authorization path detected")
    if (
        "expiring-content.sqlite3" not in store_text
        or "secure_delete=ON" not in store_text
    ):
        raise SystemExit("transactional plaintext store missing")
    report = {
        "contract_version": "r03.5-candidate",
        "candidate_schema_id": "novel-fact-extraction-v2.1",
        "offline_only": True,
        "runtime_count_evidence": {
            "model_api_calls": "NOT_PRODUCED_BY_SELF_CHECK",
            "network_calls": "NOT_PRODUCED_BY_SELF_CHECK",
            "real_novel_read_events": "NOT_PRODUCED_BY_SELF_CHECK",
            "required_source": "EXACT_HEAD_PARENT_RUN_RECEIPT",
        },
        "writer_count": len(WRITER_MAP) + 1,
        "immutable_record_types": len(OUTPUT_TYPES),
        "projector": PROJECTOR_NAME,
        "b03_tests_expected": 40,
        "transaction_store": "sqlite-attached-rollback-journal",
        "plaintext_secure_delete": True,
        "public_store_exposed": False,
        "public_upstream_context_exposed": False,
        "files_checked": checked,
    }
    (ROOT / "OFFLINE_REPLAY_REPORT.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
